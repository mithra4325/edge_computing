import cv2
import time
import sys
import numpy as np
from pathlib import Path
from ultralytics import YOLO
from gpio_manager import gpio_controller

# Configuration
MODEL_PATH = "best.pt"
CAMERA_INDEX = 0
IMG_SIZE = 320       # Lower resolution for lighter inference
CONFIDENCE = 0.35
SKIN_RATIO_THRESHOLD = 0.32
TEXTURE_LAPLACIAN_THRESHOLD = 750.0

def classify_hand_crop(crop):
    """
    Differentiates between a bare hand (without gloves) and a gloved hand (with gloves).
    Uses multi-spectrum skin colorimetry (YCrCb + HSV + RGB) combined with
    surface texture analysis (Laplacian edge variance).
    
    Returns:
        is_bare_hand (bool): True if bare hand (no gloves), False if wearing gloves
        skin_ratio (float): Percentage of biological skin pixels (0.0 to 1.0)
        texture_var (float): Laplacian variance (smooth skin vs textured glove)
    """
    if crop is None or crop.size == 0:
        return False, 0.0, 0.0

    h, w = crop.shape[:2]
    # Sample inner 80% to avoid background boundary contamination
    pad_y = max(1, int(h * 0.1))
    pad_x = max(1, int(w * 0.1))
    inner = crop[pad_y:h - pad_y, pad_x:w - pad_x] if (h > 20 and w > 20) else crop

    # 1. Multi-Space Skin Color Analysis
    ycrcb = cv2.cvtColor(inner, cv2.COLOR_BGR2YCrCb)
    hsv = cv2.cvtColor(inner, cv2.COLOR_BGR2HSV)

    # YCrCb: Human blood / melanin chroma cluster
    mask_ycrcb = cv2.inRange(ycrcb, np.array([0, 133, 77], dtype=np.uint8), np.array([255, 175, 127], dtype=np.uint8))

    # HSV: Human skin hue and non-extreme saturation
    mask_hsv1 = cv2.inRange(hsv, np.array([0, 25, 40], dtype=np.uint8), np.array([25, 240, 255], dtype=np.uint8))
    mask_hsv2 = cv2.inRange(hsv, np.array([165, 25, 40], dtype=np.uint8), np.array([180, 240, 255], dtype=np.uint8))
    mask_hsv = cv2.bitwise_or(mask_hsv1, mask_hsv2)

    # RGB constraint: R > G > B with minimum red dominance
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
    # Bare human hand has high biological skin ratio and smooth skin surface.
    # Safety gloves (nitrile, rubber, leather, fabric) have low skin ratio and/or high texture from grip ridges/stitching.
    if skin_ratio >= 0.50:
        is_bare = True
    elif skin_ratio >= SKIN_RATIO_THRESHOLD and texture_var < TEXTURE_LAPLACIAN_THRESHOLD:
        is_bare = True
    else:
        is_bare = False

    return is_bare, skin_ratio, texture_var


def main():
    # Check that the model exists
    if not Path(MODEL_PATH).is_file():
        print(f"ERROR: Cannot find {MODEL_PATH}")
        print("Place best.pt in the same folder as detect.py.")
        return

    print("Loading YOLO model...")
    model = YOLO(MODEL_PATH)

    print("Opening webcam...")
    if sys.platform.startswith("win"):
        camera = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW)
    else:
        camera = cv2.VideoCapture(CAMERA_INDEX)

    if not camera.isOpened():
        print("ERROR: Cannot open camera.")
        print("Check the connection or try CAMERA_INDEX = 1.")
        return

    # Limit camera resolution to reduce resource usage
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    print("Detection started with Hand/Glove differentiation. Press Q to quit.")

    frame_count = 0
    start_time = time.time()

    try:
        while True:
            success, frame = camera.read()

            if not success:
                print("Could not read frame from webcam.")
                break

            # Run YOLO on CPU with a small inference image
            results = model.predict(
                source=frame,
                imgsz=IMG_SIZE,
                conf=CONFIDENCE,
                device="cpu",
                verbose=False
            )

            annotated_frame = frame.copy()
            h, w = frame.shape[:2]

            counts = {
                "helmet": 0,
                "gloves": 0,       # Hand WITH gloves
                "bare_hand": 0,    # Hand WITHOUT gloves (Violation)
                "head": 0          # Head WITHOUT helmet (Violation)
            }

            for box in results[0].boxes:
                cls_id = int(box.cls)
                cls_name = model.names.get(cls_id, f"class_{cls_id}")
                conf = float(box.conf)
                x1, y1, x2, y2 = [int(v) for v in box.xyxy[0].tolist()]

                # Clip bounding box to frame boundaries
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(w, x2), min(h, y2)
                crop = frame[y1:y2, x1:x2]

                # Differentiate between hand with gloves vs hand without gloves
                if cls_name == "gloves":
                    is_bare, skin_ratio, _ = classify_hand_crop(crop)
                    if is_bare:
                        # Reclassified as bare hand without gloves
                        cls_name = "bare_hand"
                        label_text = f"! NO GLOVE (BARE HAND) {int(conf * 100)}% [Skin: {int(skin_ratio * 100)}%]"
                        color = (0, 0, 245)  # Crimson Red (Violation)
                        counts["bare_hand"] += 1
                    else:
                        # Genuine safety glove
                        label_text = f"GLOVES (PROTECTED) {int(conf * 100)}% [Skin: {int(skin_ratio * 100)}%]"
                        color = (255, 180, 0)  # Cyan-Blue (Compliant)
                        counts["gloves"] += 1

                elif cls_name == "head":
                    label_text = f"! NO HELMET {int(conf * 100)}%"
                    color = (0, 0, 245)  # Crimson Red (Violation)
                    counts["head"] += 1

                elif cls_name == "helmet":
                    label_text = f"HELMET {int(conf * 100)}%"
                    color = (50, 220, 50)  # Green (Compliant)
                    counts["helmet"] += 1

                else:
                    label_text = f"{cls_name} {int(conf * 100)}%"
                    color = (200, 200, 200)

                # Draw high-visibility bounding box
                cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), color, 2)

                # Corner bracket accents
                line_len = min(15, (x2 - x1) // 4, (y2 - y1) // 4)
                cv2.line(annotated_frame, (x1, y1), (x1 + line_len, y1), color, 3)
                cv2.line(annotated_frame, (x1, y1), (x1, y1 + line_len), color, 3)
                cv2.line(annotated_frame, (x2, y1), (x2 - line_len, y1), color, 3)
                cv2.line(annotated_frame, (x2, y1), (x2, y1 - line_len), color, 3)
                cv2.line(annotated_frame, (x1, y2), (x1 + line_len, y2), color, 3)
                cv2.line(annotated_frame, (x1, y2), (x1, y2 - line_len), color, 3)
                cv2.line(annotated_frame, (x2, y2), (x2 - line_len, y2), color, 3)
                cv2.line(annotated_frame, (x2, y2), (x2, y2 - line_len), color, 3)

                # Label banner
                (tw, th), _ = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
                cv2.rectangle(annotated_frame, (x1, max(0, y1 - 20)), (x1 + tw + 10, max(20, y1)), color, -1)
                text_color = (0, 0, 0) if color != (0, 0, 245) else (255, 255, 255)
                cv2.putText(
                    annotated_frame,
                    label_text,
                    (x1 + 5, max(14, y1 - 5)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.45,
                    text_color,
                    1,
                    cv2.LINE_AA
                )

            # Calculate FPS
            frame_count += 1
            elapsed = time.time() - start_time
            fps = frame_count / elapsed if elapsed > 0 else 0

            # Update Raspberry Pi 5 3-LED hardware and virtual controller
            has_helmet = (counts["helmet"] > 0)
            has_gloves = (counts["gloves"] > 0)
            led_state = gpio_controller.update(has_helmet, has_gloves)

            # Determine Overall Safety Status
            violations = []
            if counts["head"] > 0:
                violations.append(f"{counts['head']} Missing Helmet")
            if counts["bare_hand"] > 0:
                violations.append(f"{counts['bare_hand']} Bare Hand (No Glove)")

            if violations:
                status_text = f"[ FAIL: {', '.join(violations)} ]"
                status_color = (0, 0, 240)
            elif counts["helmet"] > 0 or counts["gloves"] > 0:
                status_text = "[ PASS: ALL PPE VERIFIED ]"
                status_color = (50, 220, 50)
            else:
                status_text = "[ SCANNING / CLEAR ZONE ]"
                status_color = (180, 180, 180)

            # Top HUD Bar
            cv2.rectangle(annotated_frame, (0, 0), (w, 36), (20, 20, 20), -1)
            cv2.putText(
                annotated_frame,
                f"FPS: {fps:.1f}",
                (12, 24),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (0, 240, 255),
                1,
                cv2.LINE_AA
            )
            cv2.putText(
                annotated_frame,
                status_text,
                (w // 2 - 140, 24),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                status_color,
                2,
                cv2.LINE_AA
            )

            # Render 3 Physical LED Tower Indicators in HUD (Upper Right)
            # Yellow: Pin 11 (Gloves Only)
            y_on = led_state["yellow"]["active"]
            y_col = (0, 214, 255) if y_on else (25, 55, 65)
            cv2.circle(annotated_frame, (w - 180, 18), 6, y_col, -1)
            if y_on: cv2.circle(annotated_frame, (w - 180, 18), 8, (0, 214, 255), 1)
            cv2.putText(annotated_frame, "Y:P11", (w - 170, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.35, y_col, 1)

            # Green: Pin 13 (Helmet Only)
            g_on = led_state["green"]["active"]
            g_col = (60, 225, 60) if g_on else (20, 60, 30)
            cv2.circle(annotated_frame, (w - 125, 18), 6, g_col, -1)
            if g_on: cv2.circle(annotated_frame, (w - 125, 18), 8, (60, 225, 60), 1)
            cv2.putText(annotated_frame, "G:P13", (w - 115, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.35, g_col, 1)

            # Red: Pin 15 (Both Helmet & Gloves)
            r_on = led_state["red"]["active"]
            r_col = (60, 60, 245) if r_on else (30, 30, 75)
            cv2.circle(annotated_frame, (w - 70, 18), 6, r_col, -1)
            if r_on: cv2.circle(annotated_frame, (w - 70, 18), 8, (60, 60, 245), 1)
            cv2.putText(annotated_frame, "R:P15", (w - 60, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.35, r_col, 1)

            # Bottom Stats Bar
            cv2.rectangle(annotated_frame, (0, h - 26), (w, h), (20, 20, 20), -1)
            led_msg = f"LED: {led_state['active_condition']}"
            hud_bot = f"Helmets: {counts['helmet']} | Gloves: {counts['gloves']} | Bare Hands: {counts['bare_hand']} | {led_msg}"
            cv2.putText(
                annotated_frame,
                hud_bot,
                (12, h - 8),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.40,
                (200, 220, 240),
                1,
                cv2.LINE_AA
            )

            cv2.imshow("YOLO PPE Detection - Hand & Glove Discriminator", annotated_frame)

            # Press Q to stop
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    except KeyboardInterrupt:
        print("\nDetection stopped.")

    finally:
        camera.release()
        cv2.destroyAllWindows()
        gpio_controller.cleanup()
        print("Camera released and GPIO pins reset. Program ended.")

if __name__ == "__main__":
    main()