# EDGE_COMPUTING

A small Raspberry Pi camera check that searches for a working camera with
OpenCV, captures one frame, and saves it as a JPEG.

## Hardware

- Host: Raspberry Pi 5
- Camera: Arducam UC-844 (model name as supplied)

See [DEVICE_SPEC.md](DEVICE_SPEC.md) for the device profile and details that
still need confirmation.

## What it does

[`snapshot.py`](snapshot.py) tries camera indices 0 through 9 in order. For the
first camera that opens and returns a frame, it writes
`captured_frame_<index>.jpg` in the current working directory and exits. If no
camera returns a frame, it reports an error.

## Quick start

On Raspberry Pi OS, install the system OpenCV package:

```bash
sudo apt update
sudo apt install -y python3-opencv
```

Connect the camera, then run:

```bash
python3 snapshot.py
```

Run the script from the directory where you want the captured image saved.
More detailed setup, checks, and troubleshooting are in
[SETUP_NOTES.md](SETUP_NOTES.md).

## Notes

- The script does not configure camera settings or stream video.
- The camera must be available to OpenCV through a camera index.
- Captured images are local output and are not required to run the project.
