# ShopEase POS

A lightweight, offline Point-of-Sale system for small shops — built with Python, customtkinter, and SQLite. No internet required, no subscription fees. Everything runs and stores data locally on your machine.

---

## Screenshots Overview

| Module | Description |
|---|---|
| **Login** | Secure SHA-256 password authentication |
| **Dashboard** | Live stats — cash, bank, credit, outstanding |
| **Billing / POS** | Cart-based billing with cash/bank/credit payment |
| **Stock** | Item management with buy/sell/min price control |
| **Sales History** | Browse and reprint past bills |
| **Credits** | Credit customer accounts and repayment tracking |
| **Suppliers** | Supplier directory |
| **Reports** | Financial summary + PDF exports |
| **Profits** | Per-item profit analysis with date filter |
| **Daily Bills** | Sales grouped by day with daily totals |
| **Admin Panel** | User accounts, tab permissions, shop settings |

---

## Requirements

- Python 3.8 or newer
- Windows, macOS, or Linux

### Python packages

```
pip install customtkinter fpdf2
```

| Package | Purpose |
|---|---|
| `customtkinter` | Modern dark-themed UI framework |
| `fpdf2` | PDF receipt and report generation |

> PDF export is optional. The app runs without `fpdf2` but export buttons will show an install prompt.

---

## Installation & Running

```bash
# 1. Clone or download the project
# 2. Install dependencies
pip install customtkinter fpdf2

# 3. Run
python shopease_pos.py
```

The database file `shopease.db` is created automatically in the same folder as the script on first run.

### Default Login

| Username | Password |
|---|---|
| `admin` | `1234` |

> Change the admin password immediately after first login via **Admin Panel → Change Password**.

---

## Building a Standalone EXE (Windows)

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name "ShopEase POS" shopease_pos.py
```

The `.exe` will be in the `dist/` folder. Copy it alongside `shopease.db` (or let it create a fresh one on first launch).

---

## Features

### Billing / POS

- Search and select stock items from a dropdown
- Editable selling price per line item — enforces minimum sell price floor
- Cart merges duplicate items automatically
- **Three payment types:**
  - **Cash** — money received in hand
  - **Bank Transfer** — received electronically (tracked separately from cash)
  - **Credit** — goods given on account; linked to a credit customer
- **Amount Paid field** — enter what the customer handed over and the change or balance due is calculated live
- Underpayment warning before completing a sale
- Receipt popup shown immediately after every sale
- Receipt PDF download from the popup

### Stock Management

- Add, edit, and delete stock items
- Fields: Item Name, Supplier, Quantity, Buy Price, Min Selling Price, Default Selling Price
- Min Selling Price is enforced at the billing screen — cashier cannot sell below it
- Buy Price is hidden from the billing/cashier view (visible only in Stock and Profit tabs)
- Low-stock alert threshold: 5 units (highlighted on Dashboard)
- Export full stock list to PDF

### Sales History

- Full history of all transactions
- Search and filter
- Reopen any past bill as a receipt popup
- Export to PDF

### Credit Accounts

- Create named credit accounts for regular customers
- Credit sales add to the customer's outstanding balance
- Record repayments — each payment reduces the balance and is logged with a date
- View full payment history per account
- Export to PDF

### Reports & Statistics

The Dashboard and Reports tab track:

| Stat | What it means |
|---|---|
| **Cash Revenue** | Direct cash sales + credit repayments received |
| **Bank Revenue** | Sales paid by bank transfer |
| **Credit Collected** | Money received from credit customers paying back debt |
| **Credit Given** | Total value of goods sold on credit (historical) |
| **Outstanding** | Current unpaid balances across all credit accounts |

### Profit Analysis

- Filter by date range
- Summary cards: Revenue, Cost, Profit, Margin %, Transaction Count
- Per-item breakdown: Qty Sold, Buy Price, Avg Sell Price, Revenue, Cost, Profit, Margin
- Click any column header to sort
- Rows colour-coded: green = profit, red = loss
- Export to PDF

### Daily Bills

- Left panel: list of all sale dates with bill count and daily total
- Right panel: summary cards (Cash, Bank, Credit, Total, Profit, Bill count) for the selected day
- Full sales table for that day
- View / reprint any bill
- Export the selected day's report to PDF

### Admin Panel (Admin only)

**User Management:**
- Create, edit, and disable user accounts
- Set a role — `staff` or `admin`
- Per-user tab permissions via checkboxes (control which tabs each staff member can see)
- Admin accounts always have access to all tabs
- Reset any user's password
- Change your own password

**Shop Settings:**
- Shop name (shown on receipts and PDF headers)
- Address and phone number
- Currency label (e.g. LKR, USD, EUR)
- Receipt footer message

---

## Payment Type Logic

| Payment Type | Cash Revenue | Bank Revenue | Credit Balance |
|---|---|---|---|
| Cash sale | ✅ +amount | — | no change |
| Bank Transfer sale | — | ✅ +amount | no change |
| Credit sale | — | — | ✅ +amount (debt increases) |
| Credit customer pays back | ✅ +amount | — | ✅ −amount (debt decreases) |

---

## Database

SQLite database (`shopease.db`) — single file, no server needed.

| Table | Contents |
|---|---|
| `settings` | Shop name, address, currency, etc. |
| `users` | Login accounts, roles, permissions |
| `suppliers` | Supplier directory |
| `stock` | Items — name, qty, buy/min/sell prices |
| `credit_accounts` | Credit customer records and balances |
| `sales` | Sale headers — customer, total, type, date, amount paid |
| `sale_items` | Line items linked to each sale |
| `credit_payments` | Repayment log for credit accounts |

The app runs a safe migration on every startup — it adds any missing columns to existing databases without destroying data. You can update the script and restart without losing anything.

---

## PDF Exports

All PDFs are saved to the same folder as `shopease_pos.py`.

| Export | Filename format |
|---|---|
| Receipt | `Receipt_{id}_{date}.pdf` |
| Stock list | `ShopEase_Stock_{date}.pdf` |
| Sales history | `ShopEase_Sales_{date}.pdf` |
| Credit accounts | `ShopEase_Credits_{date}.pdf` |
| Suppliers | `ShopEase_Suppliers_{date}.pdf` |
| Profit report | `ShopEase_Profit_{date}.pdf` |
| Daily report | `ShopEase_Daily_{date}.pdf` |

---

## Project Structure

```
shopease_pos.py      ← entire application (single file)
shopease.db          ← SQLite database (auto-created on first run)
README.md            ← this file
```

All logic — database, UI, PDF generation — lives in one file for easy distribution and deployment.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3 |
| UI Framework | customtkinter (tkinter-based dark UI) |
| Database | SQLite 3 (built into Python) |
| PDF Generation | fpdf2 |
| Packaging | PyInstaller (optional, for .exe) |

---

## Changelog

| Version | Changes |
|---|---|
| v1.0 | Initial build — billing, stock, sales, credits, suppliers, reports |
| v1.1 | Admin panel, user permissions, shop settings |
| v1.2 | Profits tab, Daily Bills tab |
| v1.3 | Cash/credit revenue calculation fix |
| v1.4 | Bank Transfer payment type, Amount Paid + Change calculator, buy price hidden from billing |
| v1.5 | Permission system fix (migration no longer overwrites staff permissions) |
| v1.6 | PDF safe-text encoding fix, receipt grand total ordering fix |
