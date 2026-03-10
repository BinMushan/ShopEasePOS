╔══════════════════════════════════════════════════════════════╗
║              ShopEase POS — SQLite Edition                   ║
║         Point of Sale for Small Shops & Businesses          ║
╚══════════════════════════════════════════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 WHAT'S IN THIS FOLDER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  shopease_pos.py    →  Main program file
  requirements.txt   →  List of required libraries
  run_windows.bat    →  Double-click to run on Windows
  run_mac_linux.sh   →  Run on Mac or Linux
  README.txt         →  This file

After you run the app the first time, a new file appears:
  shopease.db        →  YOUR DATA (keep this file safe!)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 STEP 1: INSTALL PYTHON (do this once)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  1. Go to:  https://www.python.org/downloads/
  2. Click the big yellow "Download Python" button
  3. Run the installer
  4. IMPORTANT: Check the box that says "Add Python to PATH"
  5. Click Install Now

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 STEP 2: RUN THE APP
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Windows:  Double-click  run_windows.bat
  Mac:      Open Terminal → type:  bash run_mac_linux.sh
  Linux:    Open Terminal → type:  bash run_mac_linux.sh

  The first time it runs, it will automatically install
  the two required libraries (customtkinter and fpdf2).
  This takes about 30 seconds and requires internet.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 HOW TO USE — QUICK GUIDE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  FIRST TIME SETUP:
  1. Go to "Suppliers" → Add your suppliers
  2. Go to "Stock/Items" → Add your items (link to supplier)
  3. Go to "Credits" → Add any customer credit accounts

  DAILY USE — MAKING A SALE:
  1. Click "Billing/POS" in the sidebar
  2. Enter customer name (or leave as "Walk-in Customer")
  3. Select item from the dropdown
  4. Change quantity if needed
  5. ✏ You can EDIT the selling price — it just cannot
     go below the minimum selling price you set
  6. Click "+ Add to Cart"
  7. Repeat for more items
  8. Click "✔ Complete Sale"
  9. A receipt appears — click "Download PDF" to save it

  CREDIT SALES:
  - Change "Sale Type" to "Credit"
  - Select the customer's credit account
  - Complete the sale — their balance updates automatically
  - Record payments under "Credits" tab → select account → "💵 Record Payment"

  EXPORTING REPORTS:
  - Go to "Reports" tab
  - Click any "Export PDF" button
  - PDF is saved in the same folder as shopease_pos.py

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 BACKUP YOUR DATA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  All your data is in ONE file:  shopease.db

  To backup: just COPY this file to a USB drive,
  Google Drive, or email it to yourself regularly.

  To move to another computer: copy shopease.db
  and shopease_pos.py to the new computer.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 NEED HELP?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  If the app doesn't open, try running in terminal:
    python shopease_pos.py
  and look at the error message shown.

  Common fix:  pip install customtkinter fpdf2

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
