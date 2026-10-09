#!/bin/bash
# AegisEdge Industrial AI Vision & Safety Dashboard
# For Raspberry Pi OS / Linux Edge Gateway

echo "========================================================"
echo " AegisEdge Industrial AI Vision & Safety Dashboard"
echo " Raspberry Pi 5 / Arducam UC-844 Edge Pipeline"
echo "========================================================"
echo ""

python3 -m uvicorn server:app --host 0.0.0.0 --port 8000
