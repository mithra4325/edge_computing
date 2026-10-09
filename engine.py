"""
Edge AI Vision & Inference Engine for Industrial Safety Monitoring
Hardware Target: Raspberry Pi 5 / Edge Worker with Arducam UC-844
Model: YOLOv8 (best.pt) - PPE Detection (Helmet, Gloves, Bare Head)
"""

import time
import os
import sys
import cv2
import numpy as np
import base64
import threading
from collections import deque
from typing import Dict, Any, List, Optional
from ultralytics import YOLO

# Class ID mapping in best.pt: 0: 'gloves', 1: 'head', 2: 'helmet'
CLASS_COLORS = {
    "helmet": (70, 220, 50),     # Bright Emerald Green (BGR)
    "gloves": (255, 180, 0),     # Electric Cyan (BGR)
    "head": (50, 40, 240),       # Bright Crimson Red / Violation (BGR)
    "bare_hand": (30, 100, 255)  # Amber-Red / Violation (BGR)
}

CLASS_HEX = {
    "helmet": "#32d74b",
    "gloves": "#0a84ff",
    "head": "#ff453a",
    "bare_hand": "#ff9f0a"
}


def classify_hand_crop(crop, skin_threshold=0.32, laplacian_threshold=750.0):
    """
    Differentiates between a bare hand (without gloves) and a gloved hand (with gloves).
    Uses multi-spectrum skin colorimetry (YCrCb + HSV + RGB) combined with
    surface texture analysis (Laplacian edge variance).
    """
    if crop is None or crop.size == 0:
        return False, 0.0, 0.0

    h, w = crop.shape[:2]
    pad_y = max(1, int(h * 0.1))
    pad_x = max(1, int(w * 0.1))
    inner = crop[pad_y:h - pad_y, pad_x:w - pad_x] if (h > 20 and w > 20) else crop

    # 1. Multi-Space Skin Color Analysis
    ycrcb = cv2.cvtColor(inner, cv2.COLOR_BGR2YCrCb)
    hsv = cv2.cvtColor(inner, cv2.COLOR_BGR2HSV)

    mask_ycrcb = cv2.inRange(ycrcb, np.array([0, 133, 77], dtype=np.uint8), np.array([255, 175, 127], dtype=np.uint8))
    mask_hsv1 = cv2.inRange(hsv, np.array([0, 25, 40], dtype=np.uint8), np.array([25, 240, 255], dtype=np.uint8))
    mask_hsv2 = cv2.inRange(hsv, np.array([165, 25, 40], dtype=np.uint8), np.array([180, 240, 255], dtype=np.uint8))
    mask_hsv = cv2.bitwise_or(mask_hsv1, mask_hsv2)

    b, g, r = cv2.split(inner)
    mask_rgb = (r > g) & (g > b) & ((r - g) > 8)

    skin_mask = cv2.bitwise_and(mask_ycrcb, mask_hsv)
    skin_mask = cv2.bitwise_and(skin_mask, skin_mask, mask=mask_rgb.astype(np.uint8) * 255)

    skin_pixels = cv2.countNonZero(skin_mask)
    total_pixels = inner.shape[0] * inner.shape[1]
    skin_ratio = skin_pixels / total_pixels if total_pixels > 0 else 0.0

    # 2. Surface Texture / Edge Variance
    gray = cv2.cvtColor(inner, cv2.COLOR_BGR2GRAY)
    texture_var = cv2.Laplacian(gray, cv2.CV_64F).var()

    # 3. Decision Boundary
    if skin_ratio >= 0.50:
        is_bare = True
    elif skin_ratio >= skin_threshold and texture_var < laplacian_threshold:
        is_bare = True
    else:
        is_bare = False

    return is_bare, skin_ratio, texture_var


class EdgeVisionEngine:
    def __init__(self, model_path: str = "best.pt"):
        self.model_path = model_path
        self.lock = threading.RLock()
        self.is_running = False
        self.worker_thread = None

        # Load YOLO Model
        print(f"[Engine] Loading YOLO model from {model_path}...")
        self.model = YOLO(model_path)
        print("[Engine] Model loaded. Running initial warmup...")
        # Warmup model so subsequent inferences are instantaneous
        dummy = np.zeros((320, 320, 3), dtype=np.uint8)
        self.model.predict(dummy, imgsz=320, device="cpu", verbose=False)
        print("[Engine] Warmup complete.")

        # Configuration options
        self.confidence_threshold = 0.35
        self.iou_threshold = 0.45
        self.inference_size = 320
        self.device = "cpu"
        self.source_mode = "webcam"  # 'webcam', 'simulation'
        self.camera_index = 0
        self.rule_mode = "standard"  # 'standard' (helmet req), 'strict' (helmet+gloves req)
        self.is_paused = False

        # Live Performance Telemetry
        self.fps = 0.0
        self.fps_window = deque(maxlen=20)
        self.target_fps = 30.0
        self.dropped_frames = 0
        self.total_frames = 0
        self.start_time = time.time()

        # Detailed Latency Tracking (ms)
        self.preprocess_ms = 0.0
        self.inference_ms = 0.0
        self.postprocess_ms = 0.0
        self.total_latency_ms = 0.0
        self.latency_history = deque(maxlen=60)
        self.peak_latency_ms = 0.0
        self.min_latency_ms = 9999.0

        # Live Counts & Compliance
        self.current_counts = {"helmet": 0, "gloves": 0, "bare_hand": 0, "head": 0, "total": 0}
        self.cumulative_counts = {"helmet": 0, "gloves": 0, "bare_hand": 0, "head": 0, "total": 0}
        self.compliance_status = "IDLE"  # "PASS", "FAIL", "IDLE"
        self.compliance_reason = "System online. Initializing monitoring feed..."
        self.total_inspections = 0
        self.pass_count = 0
        self.fail_count = 0

        # Frame buffers
        self.latest_raw_frame = None
        self.latest_annotated_frame = None
        self.latest_detections: List[Dict[str, Any]] = []

        # Inspection Event History (keeps the last 20 events)
        self.history_buffer = deque(maxlen=20)
        self.event_counter = 0
        self.last_history_trigger_time = 0.0

        # Simulation Resources
        self.sim_images = []
        self.sim_index = 0
        self.sim_last_switch = time.time()
        self.sim_pan_x = 0
        self.sim_pan_dx = 1
        self._load_simulation_samples()

        # Camera handle
        self.camera = None

    def _load_simulation_samples(self):
        """Pre-load sample factory station images for simulation mode."""
        sample_paths = [
            "samples/compliant.jpg",
            "samples/violation.jpg",
            "samples/station4.jpg"
        ]
        self.sim_images = []
        for p in sample_paths:
            if os.path.exists(p):
                img = cv2.imread(p)
                if img is not None:
                    self.sim_images.append(img)
        print(f"[Engine] Loaded {len(self.sim_images)} simulation scenarios.")

    def start(self):
        """Start the background processing thread."""
        if self.is_running:
            return
        self.is_running = True
        self.start_time = time.time()
        self._init_source()
        self.worker_thread = threading.Thread(target=self._processing_loop, daemon=True)
        self.worker_thread.start()
        print("[Engine] Background pipeline thread started.")

    def stop(self):
        """Stop processing and release hardware resources."""
        self.is_running = False
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=2.0)
        if self.camera is not None:
            self.camera.release()
            self.camera = None
        print("[Engine] Pipeline stopped and camera released.")

    def _init_source(self):
        """Initialize the selected video source."""
        if self.source_mode == "webcam":
            if self.camera is not None:
                self.camera.release()
                self.camera = None
            print(f"[Engine] Opening camera index {self.camera_index}...")
            # Use CAP_DSHOW on Windows for fast non-blocking initialization
            if sys.platform.startswith("win"):
                self.camera = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
            else:
                self.camera = cv2.VideoCapture(self.camera_index)

            if self.camera.isOpened():
                self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                self.camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                print(f"[Engine] Camera {self.camera_index} connected successfully.")
            else:
                print(f"[Engine] Camera {self.camera_index} could not be opened. Falling back to Simulation mode.")
                self.source_mode = "simulation"
                self.camera = None

    def set_source_mode(self, mode: str, cam_idx: int = 0):
        """Switch video source between webcam and simulation."""
        with self.lock:
            self.source_mode = mode
            self.camera_index = cam_idx
            self._init_source()

    def update_config(self, conf: Optional[float] = None, iou: Optional[float] = None,
                      size: Optional[int] = None, rule: Optional[str] = None):
        """Update inference and safety rule thresholds dynamically."""
        with self.lock:
            if conf is not None:
                self.confidence_threshold = max(0.05, min(0.95, float(conf)))
            if iou is not None:
                self.iou_threshold = max(0.1, min(0.9, float(iou)))
            if size is not None and size in [320, 480, 640]:
                self.inference_size = int(size)
            if rule is not None and rule in ["standard", "strict"]:
                self.rule_mode = rule

    def _get_frame(self) -> Optional[np.ndarray]:
        """Fetch next frame from webcam or synthetic simulation stream."""
        if self.source_mode == "webcam" and self.camera is not None and self.camera.isOpened():
            success, frame = self.camera.read()
            if success and frame is not None:
                return frame
            else:
                self.dropped_frames += 1

        # Simulation mode: cycle scenarios with realistic conveyor / movement simulation
        if self.sim_images:
            now = time.time()
            if now - self.sim_last_switch > 6.0:  # Switch scenario every 6 seconds
                self.sim_index = (self.sim_index + 1) % len(self.sim_images)
                self.sim_last_switch = now
                self.sim_pan_x = 0

            base = self.sim_images[self.sim_index]
            # Resize cleanly to 640x480
            frame = cv2.resize(base, (640, 480))
            return frame

        # Fallback dummy frame
        dummy = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.putText(dummy, "NO VIDEO SOURCE AVAILABLE", (120, 240),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        return dummy

    def _processing_loop(self):
        """Main inference worker loop running on edge device."""
        while self.is_running:
            if self.is_paused:
                time.sleep(0.05)
                continue

            frame_start = time.perf_counter()
            frame = self._get_frame()
            if frame is None:
                time.sleep(0.02)
                continue

            self.total_frames += 1

            # Execute YOLO inference
            conf_thresh = self.confidence_threshold
            iou_thresh = self.iou_threshold
            imgsz = self.inference_size

            t0 = time.perf_counter()
            results = self.model.predict(
                source=frame,
                imgsz=imgsz,
                conf=conf_thresh,
                iou=iou_thresh,
                device=self.device,
                verbose=False
            )
            t_infer = time.perf_counter()

            # Latency extraction
            res = results[0]
            if hasattr(res, 'speed') and res.speed:
                pre_ms = float(res.speed.get('preprocess', 2.0))
                inf_ms = float(res.speed.get('inference', (t_infer - t0) * 1000.0))
                post_ms = float(res.speed.get('postprocess', 1.5))
            else:
                pre_ms = 2.0
                inf_ms = (t_infer - t0) * 1000.0
                post_ms = 1.5

            total_lat = pre_ms + inf_ms + post_ms

            # Parse detections
            detections = []
            frame_counts = {"helmet": 0, "gloves": 0, "bare_hand": 0, "head": 0, "total": 0}
            conf_sum = 0.0

            for box in res.boxes:
                cls_id = int(box.cls)
                cls_name = self.model.names.get(cls_id, f"class_{cls_id}")
                conf = float(box.conf)
                xyxy = [int(v) for v in box.xyxy[0].tolist()]

                # Differentiate between bare hand vs glove if classified as gloves
                skin_pct = 0.0
                if cls_name == "gloves":
                    x1, y1 = max(0, xyxy[0]), max(0, xyxy[1])
                    x2, y2 = min(frame.shape[1], xyxy[2]), min(frame.shape[0], xyxy[3])
                    crop = frame[y1:y2, x1:x2]
                    is_bare, skin_ratio, _ = classify_hand_crop(crop)
                    skin_pct = round(skin_ratio * 100, 1)
                    if is_bare:
                        cls_name = "bare_hand"

                detections.append({
                    "class": cls_name,
                    "confidence": round(conf, 3),
                    "skin_ratio": skin_pct,
                    "bbox": xyxy
                })
                if cls_name in frame_counts:
                    frame_counts[cls_name] += 1
                conf_sum += conf

            frame_counts["total"] = len(detections)
            avg_conf = (conf_sum / len(detections)) if detections else 0.0

            # Evaluate Compliance (Pass / Fail Logic)
            status, reason = self._evaluate_compliance(frame_counts)

            # Draw High-Tech Industrial Annotation Overlay
            annotated = self._render_industrial_hud(frame.copy(), detections, status, total_lat)

            # Update State with thread safety
            now = time.time()
            with self.lock:
                self.latest_raw_frame = frame
                self.latest_annotated_frame = annotated
                self.latest_detections = detections
                self.current_counts = frame_counts

                # Update cumulative counts
                for k in ["helmet", "gloves", "bare_hand", "head", "total"]:
                    self.cumulative_counts[k] += frame_counts[k]

                # Latency & Stats
                self.preprocess_ms = round(pre_ms, 2)
                self.inference_ms = round(inf_ms, 2)
                self.postprocess_ms = round(post_ms, 2)
                self.total_latency_ms = round(total_lat, 2)
                self.latency_history.append(self.total_latency_ms)

                if self.total_latency_ms > self.peak_latency_ms:
                    self.peak_latency_ms = self.total_latency_ms
                if self.total_latency_ms < self.min_latency_ms:
                    self.min_latency_ms = self.total_latency_ms

                self.compliance_status = status
                self.compliance_reason = reason

                # Periodic / State-change History logging
                if status in ["PASS", "FAIL"]:
                    self.total_inspections += 1
                    if status == "PASS":
                        self.pass_count += 1
                    else:
                        self.fail_count += 1

                # Record event in history buffer (throttle to ~every 2.5s or state change)
                if (now - self.last_history_trigger_time > 2.5) or (status == "FAIL" and (now - self.last_history_trigger_time > 1.2)):
                    self._record_history_event(status, reason, frame_counts, total_lat, avg_conf, annotated)
                    self.last_history_trigger_time = now

            # FPS smoothing
            frame_duration = time.perf_counter() - frame_start
            self.fps_window.append(frame_duration)
            if self.fps_window:
                avg_duration = sum(self.fps_window) / len(self.fps_window)
                self.fps = round(1.0 / avg_duration, 1) if avg_duration > 0 else 0.0

            # Edge throttle
            target_sleep = max(0.001, (1.0 / self.target_fps) - frame_duration)
            time.sleep(target_sleep)

    def _evaluate_compliance(self, counts: Dict[str, int]) -> (str, str):
        """
        Evaluate industrial safety compliance based on PPE counts and active rules.
        """
        helmets = counts.get("helmet", 0)
        gloves = counts.get("gloves", 0)
        bare_hands = counts.get("bare_hand", 0)
        heads = counts.get("head", 0)

        if helmets == 0 and heads == 0 and gloves == 0 and bare_hands == 0:
            return "IDLE", "Inspection Zone Clear / No Personnel Detected"

        # Rule Mode A: Standard (Mandatory Helmet, Alert on Bare Hands)
        if self.rule_mode == "standard":
            violations = []
            if heads > 0:
                violations.append(f"{heads} Missing Helmet(s)")
            if bare_hands > 0:
                violations.append(f"{bare_hands} Bare Hand(s) Detected (No Gloves)")
            if violations:
                return "FAIL", f"VIOLATION: {', '.join(violations)}"
            elif helmets > 0:
                return "PASS", f"COMPLIANT: {helmets} Safety Hardhat(s) Verified"
            else:
                return "PASS", "COMPLIANT: No Violations Observed"

        # Rule Mode B: Strict (Mandatory Helmet + Safety Gloves)
        elif self.rule_mode == "strict":
            violations = []
            if heads > 0:
                violations.append(f"{heads} Missing Helmet(s)")
            if bare_hands > 0:
                violations.append(f"{bare_hands} Bare Hand(s) (Gloves Required)")
            if helmets > 0 and gloves == 0 and bare_hands == 0:
                violations.append("Missing Safety Gloves")
            if violations:
                return "FAIL", f"VIOLATION: {', '.join(violations)}"
            elif helmets > 0:
                return "PASS", f"COMPLIANT: Hardhat ({helmets}) & Gloves ({gloves}) Verified"
            else:
                return "PASS", "COMPLIANT: Clear Zone"

        return "IDLE", "Monitoring"

    def _render_industrial_hud(self, frame: np.ndarray, detections: List[Dict[str, Any]],
                               status: str, latency: float) -> np.ndarray:
        """
        Render ultra-crisp, professional industrial HUD overlay onto the frame.
        """
        h, w = frame.shape[:2]

        # Draw Bounding Boxes with industrial bracket styling
        for det in detections:
            cls_name = det["class"]
            conf = det["confidence"]
            x1, y1, x2, y2 = det["bbox"]
            color = CLASS_COLORS.get(cls_name, (200, 200, 200))

            # Main bounding box
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

            # High-tech corner bracket accents
            line_len = min(16, (x2 - x1) // 4, (y2 - y1) // 4)
            # Top-Left
            cv2.line(frame, (x1, y1), (x1 + line_len, y1), color, 3)
            cv2.line(frame, (x1, y1), (x1, y1 + line_len), color, 3)
            # Top-Right
            cv2.line(frame, (x2, y1), (x2 - line_len, y1), color, 3)
            cv2.line(frame, (x2, y1), (x2, y1 + line_len), color, 3)
            # Bottom-Left
            cv2.line(frame, (x1, y2), (x1 + line_len, y2), color, 3)
            cv2.line(frame, (x1, y2), (x1, y2 - line_len), color, 3)
            # Bottom-Right
            cv2.line(frame, (x2, y2), (x2 - line_len, y2), color, 3)
            cv2.line(frame, (x2, y2), (x2, y2 - line_len), color, 3)

            # Label badge
            label_text = f"{cls_name.upper()} {int(conf * 100)}%"
            if cls_name == "head":
                label_text = f"! NO HELMET {int(conf * 100)}%"
            elif cls_name == "bare_hand":
                label_text = f"! NO GLOVE (BARE HAND) {int(conf * 100)}%"

            (tw, th), _ = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
            # Badge background
            cv2.rectangle(frame, (x1, max(0, y1 - 20)), (x1 + tw + 10, max(20, y1)), color, -1)
            # Badge text
            text_color = (0, 0, 0) if cls_name not in ["head", "bare_hand"] else (255, 255, 255)
            cv2.putText(frame, label_text, (x1 + 5, max(14, y1 - 5)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, text_color, 1, cv2.LINE_AA)

        # Top Industrial Header Ribbon Overlay
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, 36), (10, 15, 22), -1)
        cv2.addWeighted(overlay, 0.78, frame, 0.22, 0, frame)

        # Status Badge in Top Ribbon
        if status == "PASS":
            status_color = (60, 225, 60)
            status_text = "[ PASS : COMPLIANT ]"
        elif status == "FAIL":
            status_color = (60, 60, 245)
            status_text = "[ FAIL : SAFETY VIOLATION ]"
        else:
            status_color = (180, 180, 180)
            status_text = "[ STANDBY : SCANNING ]"

        cv2.putText(frame, "AEGIS-EDGE // ARDUCAM UC-844", (12, 23),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.46, (200, 220, 240), 1, cv2.LINE_AA)
        cv2.putText(frame, status_text, (w // 2 - 95, 23),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.50, status_color, 2, cv2.LINE_AA)
        cv2.putText(frame, f"LATENCY: {latency:.1f}ms", (w - 145, 23),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 230, 255), 1, cv2.LINE_AA)

        # Bottom HUD stats bar
        overlay_bot = frame.copy()
        cv2.rectangle(overlay_bot, (0, h - 26), (w, h), (10, 15, 22), -1)
        cv2.addWeighted(overlay_bot, 0.78, frame, 0.22, 0, frame)

        src_label = "SRC: LIVE CAMERA" if self.source_mode == "webcam" else "SRC: SIMULATED FACTORY"
        hud_bot = f"{src_label} | FPS: {self.fps:.1f} | CONF: {int(self.confidence_threshold*100)}% | DETECTIONS: {len(detections)}"
        cv2.putText(frame, hud_bot, (12, h - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.40, (180, 200, 215), 1, cv2.LINE_AA)

        # Timestamp in bottom right
        now_str = time.strftime("%H:%M:%S")
        cv2.putText(frame, now_str, (w - 75, h - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.40, (150, 175, 190), 1, cv2.LINE_AA)

        return frame

    def _record_history_event(self, status: str, reason: str, counts: Dict[str, int],
                              latency: float, avg_conf: float, frame: np.ndarray):
        """Create a structured inspection history record with thumbnail."""
        self.event_counter += 1
        event_id = f"INS-{self.event_counter:04d}"

        # Generate lightweight JPEG thumbnail
        thumb = cv2.resize(frame, (180, 135))
        _, buffer = cv2.imencode('.jpg', thumb, [cv2.IMWRITE_JPEG_QUALITY, 72])
        thumb_b64 = f"data:image/jpeg;base64,{base64.b64encode(buffer).decode('utf-8')}"

        record = {
            "id": event_id,
            "timestamp": time.strftime("%H:%M:%S"),
            "full_timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "verdict": status,
            "reason": reason,
            "counts": dict(counts),
            "latency_ms": round(latency, 1),
            "confidence": round(avg_conf * 100, 1),
            "thumbnail": thumb_b64
        }
        self.history_buffer.appendleft(record)

    def get_latest_telemetry(self) -> Dict[str, Any]:
        """Aggregate all real-time metrics for WebSocket / polling."""
        with self.lock:
            uptime_sec = int(time.time() - self.start_time)
            hours, rem = divmod(uptime_sec, 3600)
            mins, secs = divmod(rem, 60)
            uptime_str = f"{hours:02d}:{mins:02d}:{secs:02d}"

            # Pass rate calculation
            inspections = self.pass_count + self.fail_count
            pass_rate = round((self.pass_count / inspections * 100.0), 1) if inspections > 0 else 100.0

            # Average latency
            avg_lat = round(sum(self.latency_history) / len(self.latency_history), 1) if self.latency_history else 0.0

            return {
                "system": {
                    "runtime_str": uptime_str,
                    "runtime_seconds": uptime_sec,
                    "total_frames": self.total_frames,
                    "fps": self.fps,
                    "target_fps": self.target_fps,
                    "dropped_frames": self.dropped_frames,
                    "source_mode": self.source_mode,
                    "camera_index": self.camera_index,
                    "is_paused": self.is_paused,
                    "device": "Raspberry Pi 5 (Edge Host)",
                    "sensor": "Arducam UC-844 (Vision Camera)",
                    "model": "YOLOv8 PPE Inspection (best.pt)"
                },
                "latency": {
                    "total_ms": self.total_latency_ms,
                    "preprocess_ms": self.preprocess_ms,
                    "inference_ms": self.inference_ms,
                    "postprocess_ms": self.postprocess_ms,
                    "avg_ms": avg_lat,
                    "peak_ms": round(self.peak_latency_ms, 1),
                    "min_ms": round(self.min_latency_ms, 1) if self.min_latency_ms < 9000 else 0.0,
                    "history": list(self.latency_history)
                },
                "thresholds": {
                    "confidence": self.confidence_threshold,
                    "iou": self.iou_threshold,
                    "inference_size": self.inference_size,
                    "rule_mode": self.rule_mode
                },
                "counts": {
                    "current": self.current_counts,
                    "cumulative": self.cumulative_counts
                },
                "compliance": {
                    "status": self.compliance_status,
                    "reason": self.compliance_reason,
                    "total_inspections": self.total_inspections,
                    "pass_count": self.pass_count,
                    "fail_count": self.fail_count,
                    "pass_rate_percent": pass_rate
                },
                "detections": self.latest_detections
            }

    def get_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Return the recent inspection events."""
        with self.lock:
            return list(self.history_buffer)[:limit]

    def clear_history(self):
        """Reset history and stats."""
        with self.lock:
            self.history_buffer.clear()
            self.pass_count = 0
            self.fail_count = 0
            self.total_inspections = 0
            self.cumulative_counts = {"helmet": 0, "gloves": 0, "bare_hand": 0, "head": 0, "total": 0}

    def get_jpeg_frame(self, raw: bool = False) -> Optional[bytes]:
        """Encode the latest frame as JPEG bytes for HTTP MJPEG stream."""
        with self.lock:
            frame = self.latest_raw_frame if raw else self.latest_annotated_frame
            if frame is None:
                return None
            success, encoded = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if success:
                return encoded.tobytes()
        return None
