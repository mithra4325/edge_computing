# Setup notes

## Target setup

- Raspberry Pi 5
- Arducam UC-844 camera
- Raspberry Pi OS with Python 3
- OpenCV's `cv2.VideoCapture` support for the camera's Linux capture interface

The installed OS release, Pi memory size, camera connection mode, and camera
firmware/driver requirements have not been provided. Confirm those against the
camera's documentation and the actual deployment before relying on this setup.

## Install OpenCV

The Raspberry Pi OS package is the simplest starting point:

```bash
sudo apt update
sudo apt install -y python3-opencv
```

Verify that the interpreter can import OpenCV:

```bash
python3 -c "import cv2; print(cv2.__version__)"
```

If the project is run from a Python virtual environment, ensure that it can
access the system OpenCV package, or install a compatible OpenCV package in that
environment. Do not mix package managers without checking which interpreter
runs the script.

## Connect and check the camera

1. Connect the Arducam camera to the Pi using the connection/interface required
   by the exact UC-844 variant.
2. Ensure the camera is powered and securely connected.
3. If it is a USB camera, check whether Linux exposes it as a video device:

   ```bash
   ls /dev/video*
   ```

   The command may report that there are no matching devices if the camera is
   not exposed through V4L2. Follow the camera manufacturer's instructions for
   any required driver or configuration.
4. Run the capture check from this project directory:

   ```bash
   python3 snapshot.py
   ```

The script checks indices 0 through 9. A successful capture is written to the
current directory as `captured_frame_<index>.jpg`.

## Troubleshooting

- **No camera opens:** Check the physical connection, power, OS detection, and
  any model-specific driver/setup requirements. Confirm the camera works with
  another capture utility supported by its interface.
- **A camera opens but no frame is read:** Check camera availability and
  permissions, close applications already using it, and verify the camera's
  interface is supported by the installed OpenCV build.
- **`ModuleNotFoundError: No module named 'cv2'`:** Install OpenCV for the same
  Python interpreter used to run `snapshot.py`.
- **No JPEG appears:** The script only writes a file after a frame is read.
  Check its console output and confirm the current directory is writable.

## Current script behavior

The script probes a fixed range of camera indices and saves the first readable
frame. It does not accept command-line options, select a resolution, or retry
after saving a frame.
