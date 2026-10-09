# Device specification

## Project device profile

| Component | Specification |
|---|---|
| Host computer | Raspberry Pi 5 |
| Camera | Arducam UC-844 (model name supplied for this project) |
| Capture software | Python 3 with OpenCV (`cv2.VideoCapture`) |
| Connection / capture interface | Not confirmed; verify the exact camera variant and interface |
| Operating system | Raspberry Pi OS intended; release/version not specified |

## Host platform

The Raspberry Pi 5 platform uses a 64-bit quad-core Arm Cortex-A76 processor.
The exact board memory configuration, storage medium, power supply, cooling,
and OS image for this project have not been specified; record the deployed
values before treating this as a complete bill of materials.

## Camera and compatibility

The camera model was provided as “Arducam UC-844.” Its sensor, resolution,
maximum frame rate, lens, connector, power requirements, and driver requirements
are not established by the project files. Confirm these specifications against
the label and the manufacturer's documentation for the exact product variant.

The current program calls OpenCV's default `VideoCapture` backend for camera
indices 0–9 and needs at least one index to return a readable frame. If this
camera is a USB model, check that Linux exposes it through a compatible video
device interface (commonly V4L2); do not assume USB support from the script
alone.

## Software requirements

- Python 3
- OpenCV Python bindings (`cv2`)
- Linux camera support appropriate to the specific camera and connection mode

## Validation checklist

- [ ] Record the Pi 5 RAM size and storage configuration.
- [ ] Record the exact Raspberry Pi OS release and kernel.
- [ ] Confirm the full camera product/variant name and interface.
- [ ] Confirm any required camera driver, firmware, power, and permissions.
- [ ] Run `python3 snapshot.py` and verify a captured JPEG is readable.
