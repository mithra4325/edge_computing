"""
FastAPI Server for Industrial Edge Vision Dashboard
Hardware Profile: Raspberry Pi 5 / Arducam UC-844 / YOLOv8
"""

import os
import sys
import time
import asyncio
import base64
import psutil
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import cv2
import numpy as np

from engine import EdgeVisionEngine

app = FastAPI(title="AegisEdge Industrial AI Vision System", version="2.4.0")

# Mount static directory for CSS, JS, assets
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Create snapshots output directory
snapshots_dir = Path(__file__).parent / "snapshots"
snapshots_dir.mkdir(exist_ok=True)

# Initialize Edge Vision Engine
engine = EdgeVisionEngine(model_path="best.pt")


@app.on_event("startup")
async def startup_event():
    print("[Server] Starting Edge Vision Engine...")
    engine.start()


@app.on_event("shutdown")
async def shutdown_event():
    print("[Server] Stopping Edge Vision Engine...")
    engine.stop()


@app.get("/", response_class=HTMLResponse)
async def get_index():
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return HTMLResponse("<h1>Industrial Dashboard Initializing...</h1>")


def generate_frames():
    """Generator for MJPEG video stream."""
    while True:
        frame_bytes = engine.get_jpeg_frame(raw=False)
        if frame_bytes is not None:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        time.sleep(0.033)  # ~30 FPS stream cap


@app.get("/api/video_feed")
async def video_feed():
    """MJPEG Live Video Stream endpoint."""
    return StreamingResponse(
        generate_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


@app.get("/api/telemetry")
async def get_telemetry():
    """Poll latest telemetry data."""
    return engine.get_latest_telemetry()


@app.websocket("/ws/telemetry")
async def websocket_telemetry(websocket: WebSocket):
    """High-frequency real-time WebSocket telemetry stream."""
    await websocket.accept()
    try:
        while True:
            telemetry = engine.get_latest_telemetry()
            # Append dynamic CPU and Memory
            telemetry["system"]["cpu_percent"] = psutil.cpu_percent(interval=None)
            telemetry["system"]["ram_percent"] = psutil.virtual_memory().percent
            await websocket.send_json(telemetry)
            await asyncio.sleep(0.1)  # 10 updates per second (smooth 100ms tick)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[WebSocket] Disconnected with error: {e}")


@app.get("/api/history")
async def get_history(limit: int = 20):
    """Retrieve last 10-20 inspection events."""
    return engine.get_history(limit=limit)


@app.post("/api/history/clear")
async def clear_history():
    """Clear inspection history and counters."""
    engine.clear_history()
    return {"status": "success", "message": "History and inspection statistics reset."}


class ConfigModel(BaseModel):
    confidence: Optional[float] = None
    iou: Optional[float] = None
    inference_size: Optional[int] = None
    rule_mode: Optional[str] = None
    source_mode: Optional[str] = None
    camera_index: Optional[int] = None
    is_paused: Optional[bool] = None


@app.get("/api/config")
async def get_config():
    """Retrieve current engine configuration."""
    with engine.lock:
        return {
            "confidence": engine.confidence_threshold,
            "iou": engine.iou_threshold,
            "inference_size": engine.inference_size,
            "rule_mode": engine.rule_mode,
            "source_mode": engine.source_mode,
            "camera_index": engine.camera_index,
            "is_paused": engine.is_paused
        }


@app.post("/api/config")
async def update_config(cfg: ConfigModel):
    """Dynamically update threshold, source, rule, or resolution."""
    if cfg.source_mode is not None or cfg.camera_index is not None:
        src = cfg.source_mode or engine.source_mode
        cam = cfg.camera_index if cfg.camera_index is not None else engine.camera_index
        engine.set_source_mode(src, cam)

    if cfg.is_paused is not None:
        with engine.lock:
            engine.is_paused = cfg.is_paused

    engine.update_config(
        conf=cfg.confidence,
        iou=cfg.iou,
        size=cfg.inference_size,
        rule=cfg.rule_mode
    )
    return {"status": "success", "config": await get_config()}


@app.post("/api/snapshot")
async def capture_snapshot():
    """Capture current annotated frame and persist to disk."""
    frame = None
    with engine.lock:
        if engine.latest_annotated_frame is not None:
            frame = engine.latest_annotated_frame.copy()

    if frame is None:
        return JSONResponse({"status": "error", "message": "No frame available to capture"}, status_code=400)

    telemetry = engine.get_latest_telemetry()
    filename = f"snapshot_{int(time.time())}.jpg"
    filepath = snapshots_dir / filename
    cv2.imwrite(str(filepath), frame)

    _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
    img_b64 = f"data:image/jpeg;base64,{base64.b64encode(buffer).decode('utf-8')}"

    return {
        "status": "success",
        "filename": filename,
        "image": img_b64,
        "telemetry": telemetry
    }


@app.post("/api/test_upload")
async def test_upload(file: UploadFile = File(...)):
    """Upload a custom image to inspect with current model and thresholds."""
    contents = await file.read()
    nparr = np.frombuffer(contents, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img is None:
        return JSONResponse({"status": "error", "message": "Invalid image file"}, status_code=400)

    # Perform inference with current settings
    with engine.lock:
        conf_thresh = engine.confidence_threshold
        iou_thresh = engine.iou_threshold
        imgsz = engine.inference_size

    t0 = time.perf_counter()
    results = engine.model.predict(
        source=img,
        imgsz=imgsz,
        conf=conf_thresh,
        iou=iou_thresh,
        device=engine.device,
        verbose=False
    )
    lat_ms = (time.perf_counter() - t0) * 1000.0

    res = results[0]
    detections = []
    counts = {"helmet": 0, "gloves": 0, "head": 0, "total": 0}
    conf_sum = 0.0

    for box in res.boxes:
        cls_id = int(box.cls)
        cls_name = engine.model.names.get(cls_id, f"class_{cls_id}")
        conf = float(box.conf)
        xyxy = [int(v) for v in box.xyxy[0].tolist()]

        detections.append({
            "class": cls_name,
            "confidence": round(conf, 3),
            "bbox": xyxy
        })
        if cls_name in counts:
            counts[cls_name] += 1
        conf_sum += conf

    counts["total"] = len(detections)
    status, reason = engine._evaluate_compliance(counts)
    annotated = engine._render_industrial_hud(img.copy(), detections, status, lat_ms)

    _, buffer = cv2.imencode('.jpg', annotated, [cv2.IMWRITE_JPEG_QUALITY, 85])
    img_b64 = f"data:image/jpeg;base64,{base64.b64encode(buffer).decode('utf-8')}"

    # Also log to history buffer
    with engine.lock:
        avg_conf = (conf_sum / len(detections)) if detections else 0.0
        engine._record_history_event(status, f"MANUAL UPLOAD: {reason}", counts, lat_ms, avg_conf, annotated)

    return {
        "status": "success",
        "verdict": status,
        "reason": reason,
        "counts": counts,
        "latency_ms": round(lat_ms, 1),
        "detections": detections,
        "annotated_image": img_b64
    }


@app.get("/api/system_info")
async def system_info():
    """Hardware profile, sensor spec, and edge computing environment."""
    vm = psutil.virtual_memory()
    return {
        "profile": {
            "name": "Raspberry Pi 5 Industrial Edge Gateway",
            "processor": "Broadcom BCM2712 Quad-Core Arm Cortex-A76 @ 2.4GHz",
            "sensor": "Arducam UC-844 Industrial Camera (V4L2 / USB / DSHOW)",
            "os": f"{sys.platform} (Host Runtime)",
            "python_version": sys.version.split()[0],
            "framework": "YOLOv8 Edge Vision Pipeline (PyTorch ONNX-compatible)"
        },
        "resources": {
            "cpu_percent": psutil.cpu_percent(interval=None),
            "cpu_count": psutil.cpu_count(),
            "ram_total_mb": round(vm.total / (1024 * 1024), 1),
            "ram_used_mb": round(vm.used / (1024 * 1024), 1),
            "ram_percent": vm.percent
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)
