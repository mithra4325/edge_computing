import cv2
import time

# ============================================================
# CONFIGURATION
# ============================================================

CAMERA_INDEX = 0          # Change if your USB camera is on another index
THRESHOLD = 100           # 0-255; adjust depending on your objects
MIN_OBJECT_AREA = 500     # Minimum contour area to be considered an object

# Optional: blur to reduce camera noise
BLUR_KERNEL = (5, 5)

# ============================================================
# OPEN CAMERA
# ============================================================

cam = cv2.VideoCapture(CAMERA_INDEX)

if not cam.isOpened():
    print(f"Error: Could not open camera at index {CAMERA_INDEX}")
    exit()

print(f"Camera opened successfully at index {CAMERA_INDEX}")
print("Press 'q' to quit.")
print("Press 's' to save the current frame.")
print("Press '+' / '-' to change threshold.")

# ============================================================
# FPS / LATENCY VARIABLES
# ============================================================

prev_time = time.perf_counter()
fps = 0

# ============================================================
# MAIN LOOP
# ============================================================

while True:

    # --------------------------------------------------------
    # Start timing the complete frame-processing cycle
    # --------------------------------------------------------

    start_time = time.perf_counter()

    # --------------------------------------------------------
    # Capture frame
    # --------------------------------------------------------

    ret, frame = cam.read()

    if not ret:
        print("Error: Could not read frame from camera.")
        break

    # --------------------------------------------------------
    # Convert to grayscale
    # --------------------------------------------------------
    
    # If the camera already provides grayscale, this conversion
    # is harmless if OpenCV reports a single-channel image.
    
    if len(frame.shape) == 3:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    else:
        gray = frame

    # --------------------------------------------------------
    # Reduce noise
    # --------------------------------------------------------

    blurred = cv2.GaussianBlur(gray, BLUR_KERNEL, 0)

    # --------------------------------------------------------
    # THRESHOLDING
    # --------------------------------------------------------

    _, binary = cv2.threshold(
        blurred,
        THRESHOLD,
        255,
        cv2.THRESH_BINARY
    )

    # --------------------------------------------------------
    # Find contours
    # --------------------------------------------------------

    contours, _ = cv2.findContours(
        binary,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )

    # --------------------------------------------------------
    # Detect objects
    # --------------------------------------------------------

    objects = []

    for contour in contours:

        area = cv2.contourArea(contour)

        # Ignore small noise
        if area < MIN_OBJECT_AREA:
            continue

        # Bounding box
        x, y, w, h = cv2.boundingRect(contour)

        objects.append({
            "x": x,
            "y": y,
            "w": w,
            "h": h,
            "area": area
        })

    # Sort objects from largest to smallest
    objects.sort(key=lambda obj: obj["area"], reverse=True)

    # --------------------------------------------------------
    # Draw bounding boxes
    # --------------------------------------------------------

    for i, obj in enumerate(objects):

        x = obj["x"]
        y = obj["y"]
        w = obj["w"]
        h = obj["h"]
        area = obj["area"]

        # Bounding box
        cv2.rectangle(
            frame,
            (x, y),
            (x + w, y + h),
            (0, 255, 0),
            2
        )

        # Object number
        label = f"Object {i + 1}"

        cv2.putText(
            frame,
            label,
            (x, max(y - 10, 20)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 0),
            2
        )

        # Optional: show area
        area_text = f"Area: {int(area)}"

        cv2.putText(
            frame,
            area_text,
            (x, y + h + 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 255, 255),
            1
        )

    # --------------------------------------------------------
    # FPS calculation
    # --------------------------------------------------------

    current_time = time.perf_counter()

    elapsed = current_time - prev_time

    if elapsed > 0:
        fps = 1.0 / elapsed

    prev_time = current_time

    # --------------------------------------------------------
    # Processing latency
    # --------------------------------------------------------

    processing_time_ms = (time.perf_counter() - start_time) * 1000

    # --------------------------------------------------------
    # Display information
    # --------------------------------------------------------

    object_count = len(objects)

    # Background rectangle for information
    cv2.rectangle(
        frame,
        (10, 10),
        (330, 145),
        (0, 0, 0),
        -1
    )

    # Object count
    cv2.putText(
        frame,
        f"Objects: {object_count}",
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (0, 255, 0),
        2
    )

    # Threshold
    cv2.putText(
        frame,
        f"Threshold: {THRESHOLD}",
        (20, 70),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (255, 255, 255),
        2
    )

    # FPS
    cv2.putText(
        frame,
        f"FPS: {fps:.1f}",
        (20, 100),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (255, 255, 255),
        2
    )

    # Processing latency
    cv2.putText(
        frame,
        f"Latency: {processing_time_ms:.2f} ms",
        (20, 130),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (0, 255, 255),
        2
    )

    # --------------------------------------------------------
    # Show camera image
    # --------------------------------------------------------

    cv2.imshow("USB Camera - Object Detection", frame)

    # Optional: show binary threshold image
    cv2.imshow("Threshold", binary)

    # --------------------------------------------------------
    # Keyboard controls
    # --------------------------------------------------------

    key = cv2.waitKey(1) & 0xFF

    # Quit
    if key == ord('q'):
        break

    # Save current annotated frame
    elif key == ord('s'):

        filename = "detected_objects.jpg"

        cv2.imwrite(filename, frame)

        print(f"\nSaved: {filename}")
        print(f"Objects detected: {object_count}")
        print(f"Threshold: {THRESHOLD}")
        print(f"Latency: {processing_time_ms:.2f} ms")
        print(f"FPS: {fps:.1f}")

        for i, obj in enumerate(objects):

            print(
                f"Object {i + 1}: "
                f"x={obj['x']}, "
                f"y={obj['y']}, "
                f"width={obj['w']}, "
                f"height={obj['h']}, "
                f"area={obj['area']:.0f}"
            )

    # Increase threshold
    elif key == ord('+') or key == ord('='):
        THRESHOLD = min(255, THRESHOLD + 5)
        print(f"Threshold increased to {THRESHOLD}")

    # Decrease threshold
    elif key == ord('-') or key == ord('_'):
        THRESHOLD = max(0, THRESHOLD - 5)
        print(f"Threshold decreased to {THRESHOLD}")

# ============================================================
# CLEANUP
# ============================================================

cam.release()
cv2.destroyAllWindows()

print("Camera released.")
