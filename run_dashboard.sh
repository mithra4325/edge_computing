#!/bin/bash
# AegisEdge Industrial AI Vision & Safety Dashboard
# For Raspberry Pi OS / Linux Edge Gateway

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================================"
echo " AegisEdge Industrial AI Vision & Safety Dashboard"
echo " Raspberry Pi 5 / Arducam UC-844 Edge Pipeline"
echo "========================================================"

# Auto-activate venv if it exists
if [ -d "venv" ]; then
    echo "[Info] Activating Python virtual environment (venv)..."
    source venv/bin/activate
fi

# Detect local IP address
LOCAL_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
if [ -z "$LOCAL_IP" ]; then
    LOCAL_IP="localhost"
fi

echo ""
echo ">> Dashboard will be accessible at:"
echo "   Local Pi Browser: http://localhost:8000"
echo "   Laptop / Network: http://${LOCAL_IP}:8000"
echo ""
echo "Press Ctrl+C to stop the server."
echo "========================================================"
echo ""

python3 -m uvicorn server:app --host 0.0.0.0 --port 8000

