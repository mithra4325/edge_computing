
import cv2
import time
from pathlib import Path
from ultralytics import YOLO

# Configuration
MODEL_PATH = "best.pt"
CAMERA_INDEX = 0
IMG_SIZE = 320       # Lower resolution for lighter inference
CONFIDENCE = 0.35

def main():
    # Check that the model exists
    if not Path(MODEL_PATH).is_file():
        print(f"ERROR: Cannot find {MODEL_PATH}")
        print("Place best.pt in the same folder as detect.py.")
        return

    print("Loading YOLO model...")
    model = YOLO(MODEL_PATH)

    print("Opening webcam...")
    camera = cv2.VideoCapture(CAMERA_INDEX)

    if not camera.isOpened():
        print("ERROR: Cannot open camera.")
        print("Check the connection or try CAMERA_INDEX = 1.")
        return

    # Limit camera resolution to reduce resource usage
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    print("Detection started. Press Q to quit.")

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

            # Draw bounding boxes and labels
            annotated_frame = results[0].plot()

            # Display FPS
            frame_count += 1
            elapsed = time.time() - start_time
            fps = frame_count / elapsed if elapsed > 0 else 0

            cv2.putText(
                annotated_frame,
                f"FPS: {fps:.1f}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2
            )

            cv2.imshow("YOLO Helmet and Gloves Detection", annotated_frame)

            # Press Q to stop
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    except KeyboardInterrupt:
        print("\nDetection stopped.")

    finally:
        camera.release()
        cv2.destroyAllWindows()
        print("Camera released. Program ended.")

if __name__ == "__main__":
    main()