#!/bin/bash
echo "============================================"
echo "  ShopEase POS - Installing & Starting..."
echo "============================================"
echo ""

# Install libraries
echo "[1/2] Installing required libraries..."
pip3 install customtkinter fpdf2 --quiet

echo "[2/2] Starting ShopEase POS..."
echo ""
python3 shopease_pos.py
