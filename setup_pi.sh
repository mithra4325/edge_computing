#!/bin/bash
# AegisEdge - One-Click Automated Setup for Raspberry Pi 5 (RP1 GPIO & Vision)
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================================="
echo " AegisEdge - Raspberry Pi 5 Automated Setup Script"
echo "========================================================="
echo ""

echo "[1/4] Updating apt package lists..."
sudo apt update -y

echo "[2/4] Installing system dependencies (OpenCV, GPIO, Python)..."
sudo apt install -y python3-pip python3-venv python3-opencv python3-gpiozero python3-lgpio

echo "[3/4] Setting up Python virtual environment with system site packages..."
if [ ! -d "venv" ]; then
    python3 -m venv venv --system-site-packages
    echo "[Info] Virtual environment created at $SCRIPT_DIR/venv"
fi

source venv/bin/activate

echo "[4/4] Installing Python requirements..."
pip install --upgrade pip
pip install -r requirements.txt

# Make run script executable
chmod +x run_dashboard.sh

echo ""
echo "========================================================="
echo " SETUP COMPLETED SUCCESSFULLY!"
echo " You can now start the dashboard by running:"
echo "    ./run_dashboard.sh"
echo "========================================================="
