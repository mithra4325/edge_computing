"""
Raspberry Pi 5 GPIO Manager for 3-LED PPE Indicator System
Controls 3 physical LEDs connected to Raspberry Pi 5 40-pin header:
- YELLOW LED: GPIO 17 (Pin 11) -> Turns ON when GLOVES ONLY detected
- GREEN LED:  GPIO 27 (Pin 13) -> Turns ON when HELMET ONLY detected
- RED LED:    GPIO 22 (Pin 15) -> Turns ON when BOTH HELMET & GLOVES detected
- GROUND:     Physical Pin 9 or Pin 14 (GND)

Supports real hardware execution on Raspberry Pi 5 (via gpiozero / RP1)
with automatic non-blocking simulated fallback on non-Pi development machines.
"""

import sys
from typing import Dict, Any

# Pin Definitions (BCM GPIO numbers and Physical Header Pins)
PIN_YELLOW_BCM = 17   # Physical Pin 11
PIN_GREEN_BCM = 27    # Physical Pin 13
PIN_RED_BCM = 22      # Physical Pin 15
PIN_GND_PHYSICAL = 14 # Physical Pin 14 (or Pin 9 / Pin 6)


class PiGPIOManager:
    def __init__(self):
        self.is_hardware = False
        self.hw_error = None
        self.led_yellow = None
        self.led_green = None
        self.led_red = None

        # Virtual state tracking
        self.state_yellow = False
        self.state_green = False
        self.state_red = False
        self.active_condition = "OFF"

        self._init_gpio()

    def _init_gpio(self):
        """Attempts to initialize Raspberry Pi 5 GPIO pins via gpiozero."""
        try:
            from gpiozero import LED
            self.led_yellow = LED(PIN_YELLOW_BCM)
            self.led_green = LED(PIN_GREEN_BCM)
            self.led_red = LED(PIN_RED_BCM)
            self.is_hardware = True
            print(f"[GPIO] Raspberry Pi 5 GPIO initialized successfully (Pins: Yellow={PIN_YELLOW_BCM}, Green={PIN_GREEN_BCM}, Red={PIN_RED_BCM})")
        except Exception as e:
            self.is_hardware = False
            self.hw_error = str(e)
            print(f"[GPIO] Physical GPIO not available ({e}). Running in Virtual/Simulated Mode for live dashboard.")

    def update(self, has_helmet: bool, has_gloves: bool) -> Dict[str, Any]:
        """
        Applies LED activation rules based on detection results:
        1. Both Helmet AND Gloves -> RED LED ON (Yellow & Green OFF)
        2. Gloves ONLY            -> YELLOW LED ON (Green & Red OFF)
        3. Helmet ONLY            -> GREEN LED ON (Yellow & Red OFF)
        4. Neither                -> ALL LEDS OFF
        """
        if has_helmet and has_gloves:
            # Rule 3: Both Helmet and Gloves identified -> RED ON
            self.state_red = True
            self.state_yellow = False
            self.state_green = False
            self.active_condition = "RED"
        elif has_gloves and not has_helmet:
            # Rule 1: Gloves ONLY identified -> YELLOW ON
            self.state_yellow = True
            self.state_green = False
            self.state_red = False
            self.active_condition = "YELLOW"
        elif has_helmet and not has_gloves:
            # Rule 2: Helmet ONLY identified -> GREEN ON
            self.state_green = True
            self.state_yellow = False
            self.state_red = False
            self.active_condition = "GREEN"
        else:
            # Neither identified -> ALL OFF
            self.state_yellow = False
            self.state_green = False
            self.state_red = False
            self.active_condition = "OFF"

        # Apply to physical hardware if running on Raspberry Pi 5
        if self.is_hardware:
            try:
                if self.state_yellow: self.led_yellow.on()
                else: self.led_yellow.off()

                if self.state_green: self.led_green.on()
                else: self.led_green.off()

                if self.state_red: self.led_red.on()
                else: self.led_red.off()
            except Exception as e:
                print(f"[GPIO] Hardware write error: {e}")

        return self.get_state()

    def get_state(self) -> Dict[str, Any]:
        """Returns structured LED status for WebSocket telemetry and live dashboard UI."""
        active_label = "ALL LEDS OFF"
        if self.active_condition == "RED":
            active_label = "RED LED ACTIVE (BOTH HELMET & GLOVES)"
        elif self.active_condition == "YELLOW":
            active_label = "YELLOW LED ACTIVE (GLOVES ONLY)"
        elif self.active_condition == "GREEN":
            active_label = "GREEN LED ACTIVE (HELMET ONLY)"

        return {
            "yellow": {
                "active": self.state_yellow,
                "pin_bcm": PIN_YELLOW_BCM,
                "pin_physical": 11,
                "condition": "Gloves Only",
                "color": "#ffd600"
            },
            "green": {
                "active": self.state_green,
                "pin_bcm": PIN_GREEN_BCM,
                "pin_physical": 13,
                "condition": "Helmet Only",
                "color": "#00e676"
            },
            "red": {
                "active": self.state_red,
                "pin_bcm": PIN_RED_BCM,
                "pin_physical": 15,
                "condition": "Both Helmet & Gloves",
                "color": "#ff1744"
            },
            "gnd_pin_physical": PIN_GND_PHYSICAL,
            "active_condition": self.active_condition,
            "active_label": active_label,
            "is_hardware": self.is_hardware,
            "mode_label": "Raspberry Pi 5 (RP1 GPIO Active)" if self.is_hardware else "Simulated GPIO Mode"
        }

    def cleanup(self):
        """Turn off all LEDs and close GPIO handles safely."""
        self.state_yellow = False
        self.state_green = False
        self.state_red = False
        if self.is_hardware:
            try:
                self.led_yellow.off()
                self.led_green.off()
                self.led_red.off()
                self.led_yellow.close()
                self.led_green.close()
                self.led_red.close()
            except Exception:
                pass
        print("[GPIO] Pins reset and released.")


# Global instance
gpio_controller = PiGPIOManager()
