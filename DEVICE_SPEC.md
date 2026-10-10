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
- `gpiozero` & `lgpio` (for Raspberry Pi 5 RP1 GPIO pin control)

## Raspberry Pi 5 3-LED Stack Light Wiring Specification

The system controls 3 physical indicator LEDs based on real-time PPE detection results:

| Indicator LED | Detection Trigger Condition | Raspberry Pi 5 Header Pin | BCM GPIO | Current Limiting Resistor | Ground Pin |
|---|---|---|---|---|---|
| **YELLOW LED** | **Gloves ONLY Identified** (no helmet) | **Physical Pin 11** | `GPIO 17` | 220 &Omega; (1/4W) | Physical Pin 14 (GND) |
| **GREEN LED**  | **Helmet ONLY Identified** (no gloves) | **Physical Pin 13** | `GPIO 27` | 220 &Omega; (1/4W) | Physical Pin 14 (GND) |
| **RED LED**    | **Both Helmet &amp; Gloves Identified** | **Physical Pin 15** | `GPIO 22` | 220 &Omega; (1/4W) | Physical Pin 14 (GND) |
| **ALL OFF**    | Neither identified                     | None (All Low)    | -        | -                 | -                     |

### Hardware Wiring Diagram & Circuit Setup:

```text
Raspberry Pi 5 40-Pin Header
========================================================================
Pin 1  (3.3V)           [ . ]  [ . ]  Pin 2  (5V)
Pin 3  (GPIO 2 / SDA)   [ . ]  [ . ]  Pin 4  (5V)
Pin 5  (GPIO 3 / SCL)   [ . ]  [ . ]  Pin 6  (GND)
Pin 7  (GPIO 4)         [ . ]  [ . ]  Pin 8  (GPIO 14 / TXD)
Pin 9  (GND)            [ . ]  [ . ]  Pin 10 (GPIO 15 / RXD)
Pin 11 (GPIO 17) ------ [ * ]  [ . ]  Pin 12 (GPIO 18)
          |                |
          +---> [220Ω] --->|-(Anode +) YELLOW LED (Cathode -)--+
                                                                |
Pin 13 (GPIO 27) ------ [ * ]  [ * ]  Pin 14 (GND) <------------+ (Common Cathode Rail)
          |                |      |                             |
          +---> [220Ω] --->|-(Anode +) GREEN LED  (Cathode -)---+
                                                                |
Pin 15 (GPIO 22) ------ [ * ]  [ . ]  Pin 16 (GPIO 23)          |
          |                                                     |
          +---> [220Ω] --->|-(Anode +) RED LED    (Cathode -)---+
========================================================================
```

### Wiring Instructions:
1. **Yellow LED**:
   - Long leg (Anode `+`) connects to a **220&Omega; resistor**, then to **Physical Pin 11** (`GPIO 17`).
   - Short leg (Cathode `-`) connects to breadboard negative rail (Ground).
2. **Green LED**:
   - Long leg (Anode `+`) connects to a **220&Omega; resistor**, then to **Physical Pin 13** (`GPIO 27`).
   - Short leg (Cathode `-`) connects to breadboard negative rail (Ground).
3. **Red LED**:
   - Long leg (Anode `+`) connects to a **220&Omega; resistor**, then to **Physical Pin 15** (`GPIO 22`).
   - Short leg (Cathode `-`) connects to breadboard negative rail (Ground).
4. **Common Ground**:
   - Connect the breadboard negative rail to **Physical Pin 14** (or **Pin 9 / Pin 6**) on the Raspberry Pi 5.

## Validation checklist

- [ ] Record the Pi 5 RAM size and storage configuration.
- [ ] Record the exact Raspberry Pi OS release and kernel.
- [ ] Confirm the full camera product/variant name and interface.
- [ ] Confirm any required camera driver, firmware, power, and permissions.
- [ ] Connect Yellow LED to Pin 11, Green LED to Pin 13, Red LED to Pin 15, and GND to Pin 14 via 220&Omega; resistors.
- [ ] Run `python3 server.py` and verify all 3 LEDs toggle correctly in real-time according to detected PPE and are reflected on the dashboard.

