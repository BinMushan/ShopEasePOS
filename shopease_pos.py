#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║           ShopEase POS — v2.0  (SQLite Edition)             ║
║   Data saved in: shopease.db  (same folder as this file)   ║
╠══════════════════════════════════════════════════════════════╣
║  INSTALL (run once):  pip install customtkinter fpdf2       ║
║  RUN:                 python shopease_pos.py                ║
╠══════════════════════════════════════════════════════════════╣
║  DEFAULT LOGIN:  admin / 1234                               ║
╚══════════════════════════════════════════════════════════════╝

WHAT'S NEW IN v2.0
  • Login screen — every user must log in
  • Admin panel — create users, set tab permissions
  • Shop settings — customize name, address, currency
  • FIXED: Credit sales are NOT counted as cash received
  • FIXED: Revenue = cash only | Credit given = separate column
  • FIXED: All POS math verified (stock, totals, balances)
"""

import os, sys, hashlib, json, datetime, sqlite3
import tkinter as tk
from tkinter import ttk, messagebox

try:
    import customtkinter as ctk
except ImportError:
    print("ERROR: Please run:  pip install customtkinter fpdf2")
    input("Press Enter to exit...")
    sys.exit(1)

try:
    from fpdf import FPDF
    PDF_OK = True
except ImportError:
    PDF_OK = False

# ──────────────────────────────────────────────────────────────
#  APPEARANCE
# ──────────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

BG      = "#0f1117"
SURFACE = "#181c27"
CARD    = "#1e2335"
BORDER  = "#2a304a"
ACCENT  = "#4f8cff"
ACCENT2 = "#38e2b8"
DANGER  = "#ff5c6a"
WARN    = "#ffb347"
TEXT    = "#e8ecf5"
MUTED   = "#7a85a3"

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shopease.db")

# All navigable tabs and their display names
ALL_TABS = [
    ("dashboard", "Dashboard"),
    ("billing",   "Billing / POS"),
    ("stock",     "Stock / Items"),
    ("sales",     "Sales History"),
    ("credits",   "Credits"),
    ("suppliers", "Suppliers"),
    ("reports",   "Reports"),
    ("profits",   "Profits"),
    ("daily",     "Daily Bills"),
]


# ══════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════

def hash_password(plain: str) -> str:
    """SHA-256 hash. Not for banking but fine for a local shop app."""
    return hashlib.sha256(plain.strip().encode()).hexdigest()


def apply_tree_style():
    s = ttk.Style()
    s.theme_use("default")
    s.configure("Dark.Treeview",
        background=CARD, foreground=TEXT, fieldbackground=CARD,
        rowheight=28, borderwidth=0, font=("Segoe UI", 10))
    s.configure("Dark.Treeview.Heading",
        background=SURFACE, foreground=MUTED, borderwidth=0,
        font=("Segoe UI", 9, "bold"), relief="flat")
    s.map("Dark.Treeview",
        background=[("selected", ACCENT)],
        foreground=[("selected", "#ffffff")])


# ══════════════════════════════════════════════════════════════
#  DATABASE
# ══════════════════════════════════════════════════════════════
class Database:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self._create_tables()
        self._migrate()
        self._seed_defaults()

    # ── Schema ────────────────────────────────────────────────

    def _create_tables(self):
        self.conn.executescript("""
            -- Shop settings (key/value store)
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT DEFAULT ''
            );

            -- Users / accounts
            CREATE TABLE IF NOT EXISTS users (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                username     TEXT    NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT   NOT NULL,
                role         TEXT    DEFAULT 'staff',
                permissions  TEXT    DEFAULT 'dashboard,billing',
                active       INTEGER DEFAULT 1,
                created_at   TEXT    DEFAULT ''
            );

            -- Suppliers
            CREATE TABLE IF NOT EXISTS suppliers (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                name    TEXT NOT NULL,
                contact TEXT DEFAULT '',
                phone   TEXT DEFAULT '',
                email   TEXT DEFAULT '',
                address TEXT DEFAULT ''
            );

            -- Stock / Inventory
            CREATE TABLE IF NOT EXISTS stock (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                name           TEXT    NOT NULL,
                supplier_id    INTEGER DEFAULT NULL,
                quantity       INTEGER DEFAULT 0,
                buy_price      REAL    DEFAULT 0,
                min_sell_price REAL    DEFAULT 0,
                sell_price     REAL    DEFAULT 0,
                FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
            );

            -- Credit accounts
            CREATE TABLE IF NOT EXISTS credit_accounts (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                name             TEXT NOT NULL,
                phone            TEXT DEFAULT '',
                notes            TEXT DEFAULT '',
                balance          REAL DEFAULT 0,
                last_transaction TEXT DEFAULT ''
            );

            -- Sales header
            CREATE TABLE IF NOT EXISTS sales (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                customer          TEXT    DEFAULT 'Walk-in',
                total             REAL    DEFAULT 0,
                sale_type         TEXT    DEFAULT 'cash',
                credit_account_id INTEGER DEFAULT NULL,
                served_by         TEXT    DEFAULT '',
                amount_paid       REAL    DEFAULT 0,
                date              TEXT    DEFAULT ''
            );

            -- Sale line items
            CREATE TABLE IF NOT EXISTS sale_items (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                sale_id    INTEGER,
                stock_id   INTEGER,
                item_name  TEXT,
                quantity   INTEGER,
                sell_price REAL,
                FOREIGN KEY (sale_id) REFERENCES sales(id)
            );

            -- Credit payment history
            CREATE TABLE IF NOT EXISTS credit_payments (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER,
                amount     REAL,
                date       TEXT,
                FOREIGN KEY (account_id) REFERENCES credit_accounts(id)
            );
        """)
        self.conn.commit()

    def _migrate(self):
        """
        Safe upgrade for users who have an older shopease.db.
        Uses ALTER TABLE ... ADD COLUMN IF NOT EXISTS pattern.
        SQLite does not support IF NOT EXISTS on ALTER TABLE,
        so we check the column list manually first.
        """
        def has_col(table, col):
            cols = [r[1] for r in self.conn.execute(
                f"PRAGMA table_info({table})").fetchall()]
            return col in cols

        def add_col(table, col, definition):
            if not has_col(table, col):
                self.conn.execute(
                    f"ALTER TABLE {table} ADD COLUMN {col} {definition}")

        # v1 → v2 : sales.served_by was added
        add_col("sales", "served_by",    "TEXT DEFAULT ''")
        # v3 : amount paid by customer (for change calculation)
        add_col("sales", "amount_paid",  "REAL DEFAULT 0")

        # v1 → v2 : users table — entire table is new, already handled by
        #           CREATE TABLE IF NOT EXISTS, but add any missing columns:
        add_col("users", "permissions", "TEXT DEFAULT 'dashboard,billing'")
        add_col("users", "active",      "INTEGER DEFAULT 1")
        add_col("users", "created_at",  "TEXT DEFAULT ''")

        # v1 → v2 : credit_payments table is new, also handled by CREATE IF NOT EXISTS

        # ── Permission migration ──────────────────────────────
        # RULE:
        #   admin role  → always gets ALL tabs (auto-updated every startup)
        #   staff role  → permissions are NEVER touched here — only the admin
        #                 panel can change staff permissions.  Touching them
        #                 here would wipe whatever the admin configured.
        all_tab_keys = [k for k, _ in ALL_TABS]

        admins = self.conn.execute(
            "SELECT id, permissions FROM users WHERE role='admin'").fetchall()

        for u in admins:
            new_perms = ",".join(all_tab_keys)
            if new_perms != (u["permissions"] or ""):
                self.conn.execute(
                    "UPDATE users SET permissions=? WHERE id=?",
                    (new_perms, u["id"]))

        self.conn.commit()

    def _seed_defaults(self):
        """
        First-run only:
        • Create the default admin account (admin / 1234)
        • Insert default shop settings
        """
        today = str(datetime.date.today())

        # Default admin — only if no users exist
        count = self.conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if count == 0:
            self.conn.execute(
                "INSERT INTO users (username,password_hash,role,permissions,active,created_at)"
                " VALUES (?,?,?,?,1,?)",
                ("admin", hash_password("1234"), "admin",
                 ",".join(k for k, _ in ALL_TABS), today))
            self.conn.commit()

        # Default settings — only if missing
        defaults = {
            "shop_name":     "My Shop",
            "shop_address":  "No. 1, Main Street",
            "shop_phone":    "+94 77 000 0000",
            "currency":      "LKR",
            "receipt_note":  "Thank you for shopping with us!",
        }
        for k, v in defaults.items():
            self.conn.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?,?)", (k, v))
        self.conn.commit()

    # ── Settings ──────────────────────────────────────────────

    def get_setting(self, key, default=""):
        row = self.conn.execute(
            "SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

    def set_setting(self, key, value):
        self.conn.execute(
            "INSERT OR REPLACE INTO settings (key,value) VALUES (?,?)", (key, value))
        self.conn.commit()

    def get_all_settings(self):
        rows = self.conn.execute("SELECT key, value FROM settings").fetchall()
        return {r["key"]: r["value"] for r in rows}

    # ── Users ─────────────────────────────────────────────────

    def get_users(self):
        return self.conn.execute(
            "SELECT * FROM users ORDER BY role DESC, username").fetchall()

    def get_user_by_username(self, username):
        return self.conn.execute(
            "SELECT * FROM users WHERE username=? COLLATE NOCASE",
            (username,)).fetchone()

    def authenticate(self, username, password):
        """
        Returns the user row if credentials are correct and account is active.
        Returns None otherwise.
        """
        user = self.get_user_by_username(username)
        if user and user["active"] and user["password_hash"] == hash_password(password):
            return user
        return None

    def add_user(self, username, password, role, permissions):
        try:
            self.conn.execute(
                "INSERT INTO users (username,password_hash,role,permissions,active,created_at)"
                " VALUES (?,?,?,?,1,?)",
                (username, hash_password(password), role,
                 permissions, str(datetime.date.today())))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False  # username already exists

    def update_user(self, uid, username, role, permissions, active):
        self.conn.execute(
            "UPDATE users SET username=?,role=?,permissions=?,active=? WHERE id=?",
            (username, role, permissions, active, uid))
        self.conn.commit()

    def change_password(self, uid, new_password):
        self.conn.execute(
            "UPDATE users SET password_hash=? WHERE id=?",
            (hash_password(new_password), uid))
        self.conn.commit()

    def delete_user(self, uid):
        self.conn.execute("DELETE FROM users WHERE id=?", (uid,))
        self.conn.commit()

    # ── Stock ─────────────────────────────────────────────────

    def get_stock(self, search=""):
        q = f"%{search}%"
        return self.conn.execute("""
            SELECT s.id, s.name, s.quantity, s.buy_price,
                   s.min_sell_price, s.sell_price, s.supplier_id,
                   COALESCE(sup.name,'—') AS supplier_name
            FROM   stock s
            LEFT JOIN suppliers sup ON s.supplier_id = sup.id
            WHERE  s.name LIKE ? OR COALESCE(sup.name,'') LIKE ?
            ORDER  BY s.name
        """, (q, q)).fetchall()

    def get_stock_by_id(self, sid):
        return self.conn.execute(
            "SELECT * FROM stock WHERE id=?", (sid,)).fetchone()

    def add_stock(self, name, supplier_id, qty, buy, min_sell, sell):
        self.conn.execute(
            "INSERT INTO stock(name,supplier_id,quantity,buy_price,min_sell_price,sell_price)"
            " VALUES(?,?,?,?,?,?)",
            (name, supplier_id or None, qty, buy, min_sell, sell))
        self.conn.commit()

    def update_stock(self, sid, name, supplier_id, qty, buy, min_sell, sell):
        self.conn.execute(
            "UPDATE stock SET name=?,supplier_id=?,quantity=?,"
            "buy_price=?,min_sell_price=?,sell_price=? WHERE id=?",
            (name, supplier_id or None, qty, buy, min_sell, sell, sid))
        self.conn.commit()

    def delete_stock(self, sid):
        self.conn.execute("DELETE FROM stock WHERE id=?", (sid,))
        self.conn.commit()

    def deduct_stock(self, sid, qty):
        self.conn.execute(
            "UPDATE stock SET quantity = quantity - ? WHERE id=?", (qty, sid))
        self.conn.commit()

    # ── Suppliers ─────────────────────────────────────────────

    def get_suppliers(self):
        return self.conn.execute(
            "SELECT * FROM suppliers ORDER BY name").fetchall()

    def add_supplier(self, name, contact, phone, email, address):
        self.conn.execute(
            "INSERT INTO suppliers(name,contact,phone,email,address) VALUES(?,?,?,?,?)",
            (name, contact, phone, email, address))
        self.conn.commit()

    def update_supplier(self, sid, name, contact, phone, email, address):
        self.conn.execute(
            "UPDATE suppliers SET name=?,contact=?,phone=?,email=?,address=? WHERE id=?",
            (name, contact, phone, email, address, sid))
        self.conn.commit()

    def delete_supplier(self, sid):
        self.conn.execute("DELETE FROM suppliers WHERE id=?", (sid,))
        self.conn.commit()

    # ── Credit Accounts ───────────────────────────────────────

    def get_credits(self):
        return self.conn.execute(
            "SELECT * FROM credit_accounts ORDER BY name").fetchall()

    def get_credit_by_id(self, cid):
        return self.conn.execute(
            "SELECT * FROM credit_accounts WHERE id=?", (cid,)).fetchone()

    def add_credit(self, name, phone, notes, opening_balance):
        today = str(datetime.date.today())
        self.conn.execute(
            "INSERT INTO credit_accounts(name,phone,notes,balance,last_transaction)"
            " VALUES(?,?,?,?,?)",
            (name, phone, notes, opening_balance, today))
        self.conn.commit()

    def update_credit_info(self, cid, name, phone, notes):
        self.conn.execute(
            "UPDATE credit_accounts SET name=?,phone=?,notes=? WHERE id=?",
            (name, phone, notes, cid))
        self.conn.commit()

    def increase_credit_balance(self, cid, amount):
        """
        Called when a CREDIT sale is made.
        Increases the outstanding debt (money customer owes the shop).
        This is NOT cash — the shop has NOT received this money yet.
        """
        today = str(datetime.date.today())
        self.conn.execute(
            "UPDATE credit_accounts SET balance = balance + ?, last_transaction=? WHERE id=?",
            (amount, today, cid))
        self.conn.commit()

    def receive_credit_payment(self, cid, amount):
        """
        Called when a customer pays back their debt.
        Reduces the outstanding balance.
        """
        today = str(datetime.date.today())
        # Clamp to 0 — balance cannot go negative
        self.conn.execute("""
            UPDATE credit_accounts
            SET balance = MAX(0, balance - ?),
                last_transaction = ?
            WHERE id = ?
        """, (amount, today, cid))
        # Record in payment history
        self.conn.execute(
            "INSERT INTO credit_payments(account_id,amount,date) VALUES(?,?,?)",
            (cid, amount, today))
        self.conn.commit()

    def delete_credit(self, cid):
        self.conn.execute("DELETE FROM credit_accounts WHERE id=?", (cid,))
        self.conn.commit()

    def get_credit_payments(self, cid):
        return self.conn.execute(
            "SELECT * FROM credit_payments WHERE account_id=? ORDER BY id DESC",
            (cid,)).fetchall()

    # ── Sales ─────────────────────────────────────────────────

    def add_sale(self, customer, total, sale_type, credit_id, items, served_by="", amount_paid=0):
        """
        Save a complete sale transaction.

        PAYMENT TYPE LOGIC:
        • sale_type = 'cash'  → money received in cash NOW.
        • sale_type = 'bank'  → money received via bank transfer NOW.
        • sale_type = 'credit'→ money NOT received. Added to customer's debt.

        amount_paid = what the customer actually handed over (for change calc).
                      For credit sales this is 0.
        """
        today = str(datetime.date.today())
        cur   = self.conn.cursor()
        cur.execute(
            "INSERT INTO sales(customer,total,sale_type,credit_account_id,served_by,amount_paid,date)"
            " VALUES(?,?,?,?,?,?,?)",
            (customer, total, sale_type, credit_id or None, served_by, amount_paid, today))
        sale_id = cur.lastrowid
        for it in items:
            cur.execute(
                "INSERT INTO sale_items(sale_id,stock_id,item_name,quantity,sell_price)"
                " VALUES(?,?,?,?,?)",
                (sale_id, it["stock_id"], it["name"], it["qty"], it["price"]))
        self.conn.commit()
        return sale_id

    def get_sales(self, search=""):
        q = f"%{search}%"
        return self.conn.execute("""
            SELECT s.id, s.customer, s.total, s.sale_type,
                   s.served_by, s.date,
                   GROUP_CONCAT(si.item_name || ' x' || si.quantity, ' | ') AS items
            FROM   sales s
            LEFT JOIN sale_items si ON s.id = si.sale_id
            WHERE  s.customer LIKE ? OR si.item_name LIKE ?
            GROUP  BY s.id
            ORDER  BY s.id DESC
        """, (q, q)).fetchall()

    def get_sale(self, sale_id):
        return self.conn.execute(
            "SELECT * FROM sales WHERE id=?", (sale_id,)).fetchone()

    def get_sale_items(self, sale_id):
        return self.conn.execute(
            "SELECT * FROM sale_items WHERE sale_id=?", (sale_id,)).fetchall()

    # ── Dashboard Stats ───────────────────────────────────────

    def get_stats(self):
        """
        CASH REVENUE = cash sales + credit payments collected from customers.
        When a credit customer pays you back, that money IS cash and must be counted.

        cash_sales_rev     = money from direct cash sales only
        credit_payments_in = money received when credit customers paid back their debt
        cash_revenue       = cash_sales_rev + credit_payments_in  (total cash in till)

        credit_given   = total value of goods sold on credit (not yet received at time of sale)
        outstanding    = what customers STILL owe right now (live unpaid balances)
        """
        # 1. Direct cash sales
        cash_sales_rev = self.conn.execute(
            "SELECT COALESCE(SUM(total),0) FROM sales WHERE sale_type='cash'"
        ).fetchone()[0]

        # 2. Bank transfer sales (received electronically — NOT credit)
        bank_sales_rev = self.conn.execute(
            "SELECT COALESCE(SUM(total),0) FROM sales WHERE sale_type='bank'"
        ).fetchone()[0]

        # 3. Cash collected when credit customers paid back their debt
        credit_payments_in = self.conn.execute(
            "SELECT COALESCE(SUM(amount),0) FROM credit_payments"
        ).fetchone()[0]

        # 4. Total revenue received = cash + bank + credit repayments
        total_received = round(cash_sales_rev + bank_sales_rev + credit_payments_in, 2)

        # 5. Goods given on credit (not yet received at time of sale)
        credit_given = self.conn.execute(
            "SELECT COALESCE(SUM(total),0) FROM sales WHERE sale_type='credit'"
        ).fetchone()[0]

        # 6. Outstanding = what credit customers still owe now
        outstanding = self.conn.execute(
            "SELECT COALESCE(SUM(balance),0) FROM credit_accounts"
        ).fetchone()[0]

        return {
            "stock":              self.conn.execute("SELECT COUNT(*) FROM stock").fetchone()[0],
            "total_sales":        self.conn.execute("SELECT COUNT(*) FROM sales").fetchone()[0],
            "cash_sales_rev":     round(cash_sales_rev, 2),
            "bank_sales_rev":     round(bank_sales_rev, 2),
            "credit_payments_in": round(credit_payments_in, 2),
            "cash_revenue":       round(cash_sales_rev + credit_payments_in, 2),
            "bank_revenue":       round(bank_sales_rev, 2),
            "total_received":     total_received,
            "credit_given":       round(credit_given, 2),
            "outstanding":        round(outstanding, 2),
            "low_stock":          self.conn.execute("SELECT COUNT(*) FROM stock WHERE quantity<=5").fetchone()[0],
            "suppliers":          self.conn.execute("SELECT COUNT(*) FROM suppliers").fetchone()[0],
            "users":              self.conn.execute("SELECT COUNT(*) FROM users WHERE active=1").fetchone()[0],
        }

    def get_low_stock(self):
        return self.conn.execute("""
            SELECT s.name, s.quantity, s.sell_price,
                   COALESCE(sup.name,'—') AS supplier
            FROM   stock s
            LEFT JOIN suppliers sup ON s.supplier_id = sup.id
            WHERE  s.quantity <= 5
            ORDER  BY s.quantity ASC
        """).fetchall()



    # ── Profit & Daily queries ────────────────────────────────

    def get_profit_by_item(self, date_from="", date_to=""):
        """
        Per-item profit report.
        Profit per line = (sell_price - buy_price_at_time) * qty
        We join sale_items with stock to get the current buy price.
        If stock was deleted we fall back to 0 buy price.
        """
        filters = []
        params  = []
        if date_from:
            filters.append("s.date >= ?")
            params.append(date_from)
        if date_to:
            filters.append("s.date <= ?")
            params.append(date_to)
        where = ("WHERE " + " AND ".join(filters)) if filters else ""

        return self.conn.execute(f"""
            SELECT
                si.item_name,
                SUM(si.quantity)                                   AS total_qty,
                SUM(si.quantity * si.sell_price)                   AS total_revenue,
                SUM(si.quantity * COALESCE(st.buy_price, 0))       AS total_cost,
                SUM(si.quantity * (si.sell_price
                    - COALESCE(st.buy_price, 0)))                  AS total_profit,
                AVG(si.sell_price)                                 AS avg_sell,
                COALESCE(st.buy_price, 0)                          AS buy_price
            FROM   sale_items si
            JOIN   sales s ON si.sale_id = s.id
            LEFT JOIN stock st ON si.stock_id = st.id
            {where}
            GROUP  BY si.item_name
            ORDER  BY total_profit DESC
        """, params).fetchall()

    def get_profit_summary(self, date_from="", date_to=""):
        """Overall profit totals for the period."""
        filters = []
        params  = []
        if date_from:
            filters.append("s.date >= ?")
            params.append(date_from)
        if date_to:
            filters.append("s.date <= ?")
            params.append(date_to)
        where = ("WHERE " + " AND ".join(filters)) if filters else ""

        row = self.conn.execute(f"""
            SELECT
                COUNT(DISTINCT s.id)                                  AS num_sales,
                SUM(si.quantity * si.sell_price)                      AS total_revenue,
                SUM(si.quantity * COALESCE(st.buy_price, 0))          AS total_cost,
                SUM(si.quantity * (si.sell_price
                    - COALESCE(st.buy_price, 0)))                     AS total_profit
            FROM   sale_items si
            JOIN   sales s ON si.sale_id = s.id
            LEFT JOIN stock st ON si.stock_id = st.id
            {where}
        """, params).fetchone()
        return dict(row) if row else {}

    def get_sales_dates(self):
        """Return all distinct sale dates, newest first."""
        rows = self.conn.execute(
            "SELECT DISTINCT date FROM sales ORDER BY date DESC"
        ).fetchall()
        return [r["date"] for r in rows]

    def get_sales_for_date(self, date):
        """All sales (with line items) for one specific date."""
        return self.conn.execute("""
            SELECT s.id, s.customer, s.total, s.sale_type,
                   s.served_by, s.date,
                   GROUP_CONCAT(si.item_name || ' x' || si.quantity
                       || ' @ ' || si.sell_price, ' | ') AS items
            FROM   sales s
            LEFT JOIN sale_items si ON s.id = si.sale_id
            WHERE  s.date = ?
            GROUP  BY s.id
            ORDER  BY s.id DESC
        """, (date,)).fetchall()

    def get_daily_summary(self, date):
        """Cash, credit, total, profit for one date."""
        row = self.conn.execute("""
            SELECT
                COALESCE(SUM(CASE WHEN s.sale_type='cash'
                    THEN s.total ELSE 0 END), 0)               AS cash_total,
                COALESCE(SUM(CASE WHEN s.sale_type='bank'
                    THEN s.total ELSE 0 END), 0)               AS bank_total,
                COALESCE(SUM(CASE WHEN s.sale_type='credit'
                    THEN s.total ELSE 0 END), 0)               AS credit_total,
                COALESCE(SUM(s.total), 0)                      AS grand_total,
                COALESCE(SUM(si.quantity * (si.sell_price
                    - COALESCE(st.buy_price,0))), 0)           AS profit,
                COUNT(DISTINCT s.id)                           AS num_sales
            FROM   sales s
            LEFT JOIN sale_items si ON s.id = si.sale_id
            LEFT JOIN stock st ON si.stock_id = st.id
            WHERE  s.date = ?
        """, (date,)).fetchone()
        return dict(row) if row else {}

# ══════════════════════════════════════════════════════════════
#  LOGIN WINDOW
# ══════════════════════════════════════════════════════════════
class LoginWindow(ctk.CTk):
    """
    The first window the user sees.
    Validates username + password against the database.
    On success, destroys itself and launches the main app.
    """
    def __init__(self, db: Database):
        super().__init__()
        self.db         = db
        self.logged_user = None   # set on successful login

        self.title("ShopEase POS — Login")
        self.geometry("420x540")
        self.resizable(False, False)
        self.configure(fg_color=BG)

        # Center the window on screen
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x  = (sw - 420) // 2
        y  = (sh - 540) // 2
        self.geometry(f"420x540+{x}+{y}")

        self._build()
        self.bind("<Return>", lambda e: self._login())

    def _build(self):
        # App logo / name
        shop_name = self.db.get_setting("shop_name", "My Shop")

        frame = ctk.CTkFrame(self, fg_color=CARD, corner_radius=16)
        frame.place(relx=0.5, rely=0.5, anchor="center",
                    relwidth=0.85, relheight=0.88)

        ctk.CTkLabel(frame, text="🛒",
                     font=ctk.CTkFont(size=48)).pack(pady=(32, 4))
        ctk.CTkLabel(frame, text=shop_name,
                     font=ctk.CTkFont(size=22, weight="bold"),
                     text_color=ACCENT).pack()
        ctk.CTkLabel(frame, text="Point of Sale System",
                     font=ctk.CTkFont(size=11), text_color=MUTED).pack(pady=(2, 28))

        # Username
        ctk.CTkLabel(frame, text="Username",
                     font=ctk.CTkFont(size=12), text_color=MUTED).pack(anchor="w", padx=28)
        self.user_entry = ctk.CTkEntry(frame, placeholder_text="Enter username",
                                        height=42, font=ctk.CTkFont(size=13))
        self.user_entry.pack(fill="x", padx=28, pady=(4, 14))
        self.user_entry.focus()

        # Password
        ctk.CTkLabel(frame, text="Password",
                     font=ctk.CTkFont(size=12), text_color=MUTED).pack(anchor="w", padx=28)
        self.pass_entry = ctk.CTkEntry(frame, placeholder_text="Enter password",
                                        show="●", height=42, font=ctk.CTkFont(size=13))
        self.pass_entry.pack(fill="x", padx=28, pady=(4, 6))

        # Error label (hidden until login fails)
        self.error_var = ctk.StringVar(value="")
        ctk.CTkLabel(frame, textvariable=self.error_var,
                     font=ctk.CTkFont(size=11), text_color=DANGER).pack(pady=4)

        # Login button
        ctk.CTkButton(frame, text="Login  →",
                      fg_color=ACCENT, hover_color="#3a78f0",
                      height=44, font=ctk.CTkFont(size=13, weight="bold"),
                      command=self._login).pack(fill="x", padx=28, pady=(4, 0))

        ctk.CTkLabel(frame, text="Default:  admin / 1234",
                     font=ctk.CTkFont(size=10), text_color=MUTED).pack(pady=(10, 0))

    def _login(self):
        username = self.user_entry.get().strip()
        password = self.pass_entry.get().strip()

        if not username or not password:
            self.error_var.set("Please enter both username and password.")
            return

        user = self.db.authenticate(username, password)
        if user:
            self.logged_user = dict(user)
            self.destroy()   # close login → main app will open
        else:
            self.error_var.set("❌  Incorrect username or password.")
            self.pass_entry.delete(0, "end")


# ══════════════════════════════════════════════════════════════
#  BASE TAB
# ══════════════════════════════════════════════════════════════
class BaseTab(ctk.CTkFrame):
    def __init__(self, parent, db, app, user):
        super().__init__(parent, corner_radius=0, fg_color=BG)
        self.db   = db
        self.app  = app
        self.user = user   # currently logged-in user dict

    def refresh(self):
        pass

    @property
    def currency(self):
        return self.db.get_setting("currency", "LKR")

    def page_header(self, title, subtitle="", btn_text=None, btn_cmd=None):
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=28, pady=(24, 0))
        lf = ctk.CTkFrame(bar, fg_color="transparent")
        lf.pack(side="left")
        ctk.CTkLabel(lf, text=title,
                     font=ctk.CTkFont(size=22, weight="bold"), text_color=TEXT).pack(anchor="w")
        if subtitle:
            ctk.CTkLabel(lf, text=subtitle,
                         font=ctk.CTkFont(size=11), text_color=MUTED).pack(anchor="w")
        if btn_text and btn_cmd:
            ctk.CTkButton(bar, text=btn_text, command=btn_cmd,
                          width=160, fg_color=ACCENT,
                          hover_color="#3a78f0").pack(side="right")

    def make_tree(self, parent, columns, row_count=20):
        frame = ctk.CTkFrame(parent, fg_color=CARD, corner_radius=8)
        tree  = ttk.Treeview(frame, columns=columns,
                              show="headings", height=row_count,
                              style="Dark.Treeview")
        vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        return frame, tree

    def is_admin(self):
        return self.user.get("role") == "admin"


# ══════════════════════════════════════════════════════════════
#  DASHBOARD TAB
# ══════════════════════════════════════════════════════════════
class DashboardTab(BaseTab):
    def __init__(self, parent, db, app, user):
        super().__init__(parent, db, app, user)
        self._build()

    def _build(self):
        shop_name = self.db.get_setting("shop_name", "My Shop")
        self.page_header(f"Welcome to {shop_name}",
                         f"Logged in as: {self.user['username']}  ({self.user['role']})")

        self.stats_row = ctk.CTkFrame(self, fg_color="transparent")
        self.stats_row.pack(fill="x", padx=28, pady=14)

        # ── Row 1: 4 main stat cards ────────────────────────
        # ROW 1
        stat_defs_r1 = [
            ("Total Sales",        "total_sales",        ACCENT),
            ("💵 Cash Revenue",    "cash_revenue",       ACCENT2),
            ("🏦 Bank Transfers",  "bank_revenue",       ACCENT2),
            ("🔄 Credit Collected","credit_payments_in", ACCENT2),
            ("📤 Credit Given",    "credit_given",       WARN),
        ]
        self.stat_vars = {}
        for label, key, color in stat_defs_r1:
            card = ctk.CTkFrame(self.stats_row, fg_color=CARD, corner_radius=10)
            card.pack(side="left", expand=True, fill="x", padx=4)
            ctk.CTkLabel(card, text=label,
                         font=ctk.CTkFont(size=9, weight="bold"),
                         text_color=MUTED).pack(anchor="w", padx=12, pady=(12, 2))
            var = ctk.StringVar(value="0")
            self.stat_vars[key] = var
            ctk.CTkLabel(card, textvariable=var,
                         font=ctk.CTkFont(size=18, weight="bold"),
                         text_color=color).pack(anchor="w", padx=12, pady=(0, 12))

        # ROW 2: outstanding, stock, low stock
        self.stats_row2 = ctk.CTkFrame(self, fg_color="transparent")
        self.stats_row2.pack(fill="x", padx=28, pady=(0, 4))
        stat_defs_r2 = [
            ("⚠ Outstanding Debt", "outstanding", DANGER),
            ("📦 Stock Items",     "stock",        ACCENT),
            ("🔴 Low Stock",       "low_stock",    WARN),
        ]
        for label, key, color in stat_defs_r2:
            card = ctk.CTkFrame(self.stats_row2, fg_color=CARD, corner_radius=10)
            card.pack(side="left", expand=False, fill="x", padx=4, ipadx=18)
            ctk.CTkLabel(card, text=label,
                         font=ctk.CTkFont(size=9, weight="bold"),
                         text_color=MUTED).pack(anchor="w", padx=12, pady=(12, 2))
            var = ctk.StringVar(value="0")
            self.stat_vars[key] = var
            ctk.CTkLabel(card, textvariable=var,
                         font=ctk.CTkFont(size=18, weight="bold"),
                         text_color=color).pack(anchor="w", padx=12, pady=(0, 12))

        # ── Cash vs Credit explanation banner ───────────────
        info = ctk.CTkFrame(self, fg_color="#1a2440", corner_radius=8)
        info.pack(fill="x", padx=28, pady=(0, 8))
        ctk.CTkLabel(info,
            text="💡  Cash = cash sales + credit repayments  |  "
                 "Bank = bank transfer sales  |  "
                 "Credit Collected = debt repayments received  |  "
                 "Outstanding = still owed to you",
            font=ctk.CTkFont(size=10), text_color=MUTED).pack(padx=14, pady=8)

        # ── Low stock table ──────────────────────────────────
        ctk.CTkLabel(self, text="⚠  Low Stock (Qty ≤ 5)",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=WARN).pack(anchor="w", padx=28, pady=(4, 4))
        f, self.low_tree = self.make_tree(self, ("Item","Qty","Price","Supplier"), 5)
        f.pack(fill="x", padx=28)
        for col, w in [("Item",220),("Qty",70),("Price",110),("Supplier",200)]:
            self.low_tree.heading(col, text=col)
            self.low_tree.column(col, width=w)

        # ── Recent sales ─────────────────────────────────────
        ctk.CTkLabel(self, text="🕐  Recent Sales",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=TEXT).pack(anchor="w", padx=28, pady=(14, 4))
        f2, self.rec_tree = self.make_tree(
            self, ("Customer","Items","Total","Type","By","Date"), 6)
        f2.pack(fill="x", padx=28, pady=(0, 16))
        for col, w in [("Customer",130),("Items",280),("Total",80),
                       ("Type",70),("By",80),("Date",100)]:
            self.rec_tree.heading(col, text=col)
            self.rec_tree.column(col, width=w)

    def refresh(self):
        cur   = self.db.get_setting("currency", "LKR")
        stats = self.db.get_stats()

        # Row 1 stats
        self.stat_vars["total_sales"].set(str(stats["total_sales"]))
        self.stat_vars["cash_revenue"].set(f"{cur} {stats['cash_revenue']:.2f}")
        self.stat_vars["bank_revenue"].set(f"{cur} {stats['bank_revenue']:.2f}")
        self.stat_vars["credit_payments_in"].set(f"{cur} {stats['credit_payments_in']:.2f}")
        self.stat_vars["credit_given"].set(f"{cur} {stats['credit_given']:.2f}")
        # Row 2 stats
        self.stat_vars["outstanding"].set(f"{cur} {stats['outstanding']:.2f}")
        self.stat_vars["stock"].set(str(stats["stock"]))
        self.stat_vars["low_stock"].set(str(stats["low_stock"]))

        for t in (self.low_tree, self.rec_tree):
            for r in t.get_children(): t.delete(r)

        for item in self.db.get_low_stock():
            self.low_tree.insert("","end", values=(
                item["name"], item["quantity"],
                f"{cur} {item['sell_price']:.2f}", item["supplier"]))

        for s in self.db.get_sales()[:6]:
            self.rec_tree.insert("","end", values=(
                s["customer"], s["items"] or "—",
                f"{cur} {s['total']:.2f}",
                s["sale_type"].upper(),
                s["served_by"] or "—",
                s["date"]))


# ══════════════════════════════════════════════════════════════
#  BILLING TAB — with editable price
# ══════════════════════════════════════════════════════════════
class BillingTab(BaseTab):
    def __init__(self, parent, db, app, user):
        super().__init__(parent, db, app, user)
        self.cart     = []
        self.item_map = {}
        self._build()

    def _build(self):
        self.page_header("Billing / POS", "Select items, adjust price if needed, complete the sale")

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=28, pady=12)

        # ── LEFT: item selector ──────────────────────────────
        left = ctk.CTkFrame(body, fg_color=CARD, corner_radius=10)
        left.pack(side="left", fill="both", expand=True, padx=(0,10))

        ctk.CTkLabel(left, text="Customer Info",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=TEXT).pack(anchor="w", padx=16, pady=(14,6))
        r1 = ctk.CTkFrame(left, fg_color="transparent")
        r1.pack(fill="x", padx=16)

        # Customer name
        ctk.CTkLabel(r1, text="Customer Name", font=ctk.CTkFont(size=11),
                     text_color=MUTED).pack(anchor="w")
        self.customer_var = ctk.StringVar(value="Walk-in Customer")
        ctk.CTkEntry(r1, textvariable=self.customer_var, width=340).pack(anchor="w", pady=(2,8))

        # Payment type — Cash / Bank Transfer / Credit
        ctk.CTkLabel(r1, text="Payment Type", font=ctk.CTkFont(size=11),
                     text_color=MUTED).pack(anchor="w")
        self.sale_type_var = ctk.StringVar(value="Cash")
        ctk.CTkOptionMenu(r1, variable=self.sale_type_var,
                          values=["Cash", "Bank Transfer", "Credit"],
                          command=self._on_sale_type,
                          width=340).pack(anchor="w", pady=(2,8))

        # Credit account selector (only for Credit)
        ctk.CTkLabel(r1, text="Credit Account  (Credit sales only)",
                     font=ctk.CTkFont(size=11), text_color=MUTED).pack(anchor="w")
        self.credit_var  = ctk.StringVar(value="-")
        self.credit_menu = ctk.CTkOptionMenu(r1, variable=self.credit_var,
                                              values=["-"], width=340)
        self.credit_menu.pack(anchor="w", pady=(2,8))
        self.credit_menu.configure(state="disabled")

        ctk.CTkFrame(left, height=1, fg_color=BORDER).pack(fill="x", padx=16, pady=8)

        # Item selector
        ctk.CTkLabel(left, text="Add Item to Cart",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=TEXT).pack(anchor="w", padx=16, pady=(0,6))
        ir = ctk.CTkFrame(left, fg_color="transparent")
        ir.pack(fill="x", padx=16)

        ctk.CTkLabel(ir, text="Select Item", font=ctk.CTkFont(size=11),
                     text_color=MUTED).pack(anchor="w")
        self.item_var  = ctk.StringVar()
        self.item_menu = ctk.CTkOptionMenu(ir, variable=self.item_var,
                                            values=["No items in stock"],
                                            command=self._on_item_select, width=340)
        self.item_menu.pack(anchor="w", pady=(2,4))

        # Item info bar — shows Min Sell and Default Sell only (NO buy price)
        self.info_var = ctk.StringVar(value="")
        ctk.CTkLabel(ir, textvariable=self.info_var,
                     font=ctk.CTkFont(size=10), text_color=ACCENT2).pack(anchor="w", pady=(0,4))

        # Qty + price row
        num_row = ctk.CTkFrame(ir, fg_color="transparent")
        num_row.pack(fill="x", pady=(0,8))

        qf = ctk.CTkFrame(num_row, fg_color="transparent")
        qf.pack(side="left", padx=(0,16))
        ctk.CTkLabel(qf, text="Quantity", font=ctk.CTkFont(size=11),
                     text_color=MUTED).pack(anchor="w")
        self.qty_var = ctk.StringVar(value="1")
        ctk.CTkEntry(qf, textvariable=self.qty_var, width=110).pack()

        pf = ctk.CTkFrame(num_row, fg_color="transparent")
        pf.pack(side="left")
        ctk.CTkLabel(pf, text="Selling Price  (editable)",
                     font=ctk.CTkFont(size=11), text_color=WARN).pack(anchor="w")
        self.price_var = ctk.StringVar(value="0.00")
        ctk.CTkEntry(pf, textvariable=self.price_var, width=150).pack()

        # Min price warning
        self.min_warn_var = ctk.StringVar(value="")
        ctk.CTkLabel(ir, textvariable=self.min_warn_var,
                     font=ctk.CTkFont(size=10), text_color=DANGER).pack(anchor="w", pady=(2,0))

        ctk.CTkButton(ir, text="+ Add to Cart",
                      fg_color=ACCENT, hover_color="#3a78f0",
                      command=self._add_to_cart, width=160).pack(anchor="w", pady=10)

        # ── RIGHT: cart ───────────────────────────────────────
        right = ctk.CTkFrame(body, fg_color=CARD, corner_radius=10, width=390)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)

        ctk.CTkLabel(right, text="Cart",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=TEXT).pack(anchor="w", padx=16, pady=(14,8))

        tf = ctk.CTkFrame(right, fg_color=SURFACE, corner_radius=6)
        tf.pack(fill="both", expand=True, padx=12)
        self.cart_tree = ttk.Treeview(tf,
            columns=("Item","Qty","Unit","Total"),
            show="headings", style="Dark.Treeview")
        for col, w, anch in [
            ("Item",130,"w"),("Qty",38,"center"),("Unit",78,"e"),("Total",80,"e")]:
            self.cart_tree.heading(col, text=col)
            self.cart_tree.column(col, width=w, anchor=anch)
        self.cart_tree.pack(fill="both", expand=True, pady=4)

        ctk.CTkButton(right, text="Remove Selected",
                      fg_color=DANGER, hover_color="#cc3344",
                      command=self._remove_selected).pack(pady=(6,2), padx=12, fill="x")

        ctk.CTkFrame(right, height=1, fg_color=BORDER).pack(fill="x", padx=12, pady=6)

        # Total
        self.total_var = ctk.StringVar(value="Total:  0.00")
        ctk.CTkLabel(right, textvariable=self.total_var,
                     font=ctk.CTkFont(size=17, weight="bold"),
                     text_color=ACCENT2).pack(padx=16, pady=(0,4))

        # Payment type badge
        self.type_indicator = ctk.StringVar(value="")
        ctk.CTkLabel(right, textvariable=self.type_indicator,
                     font=ctk.CTkFont(size=10), text_color=MUTED).pack(padx=16, pady=(0,6))

        ctk.CTkFrame(right, height=1, fg_color=BORDER).pack(fill="x", padx=12, pady=4)

        # ── Amount Paid + Change section ─────────────────────
        pay_frame = ctk.CTkFrame(right, fg_color="transparent")
        pay_frame.pack(fill="x", padx=12, pady=(4,2))

        ctk.CTkLabel(pay_frame, text="Amount Given by Customer",
                     font=ctk.CTkFont(size=11), text_color=MUTED).pack(anchor="w")
        self.paid_var = ctk.StringVar(value="")
        self.paid_entry = ctk.CTkEntry(pay_frame, textvariable=self.paid_var,
                                        placeholder_text="Enter amount paid...",
                                        width=340, font=ctk.CTkFont(size=13))
        self.paid_entry.pack(anchor="w", pady=(3,6))
        self.paid_var.trace_add("write", lambda *a: self._update_change())

        # Change / Balance due
        self.change_var = ctk.StringVar(value="")
        self.change_label = ctk.CTkLabel(right, textvariable=self.change_var,
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=ACCENT2)
        self.change_label.pack(padx=16, pady=(0,6))

        # Complete / Clear buttons
        ctk.CTkButton(right, text="Complete Sale",
                      fg_color=ACCENT2, text_color="#0f1117",
                      hover_color="#28c29a", height=44,
                      command=self._complete_sale).pack(fill="x", padx=12, pady=4)
        ctk.CTkButton(right, text="Clear Cart",
                      fg_color="transparent", border_color=BORDER, border_width=1,
                      hover_color=CARD,
                      command=self._clear_cart).pack(fill="x", padx=12, pady=(0,12))

    # ── Callbacks ─────────────────────────────────────────────

    def _on_sale_type(self, val):
        """Show/hide credit account selector; update payment hint."""
        if val == "Credit":
            self.credit_menu.configure(state="normal")
            self.paid_entry.configure(state="disabled", placeholder_text="N/A for credit")
            self.paid_var.set("")
            self.change_var.set("")
        else:
            self.credit_menu.configure(state="disabled")
            self.paid_entry.configure(state="normal",
                                       placeholder_text="Enter amount paid...")
        self._render_cart()

    def _on_item_select(self, name):
        item = self.item_map.get(name)
        if not item: return
        cur = self.currency
        self.price_var.set(f"{item['sell_price']:.2f}")
        # Show Min Sell and Default Sell — NO buy price shown to cashier
        self.info_var.set(
            f"Min Sell: {cur} {item['min_sell_price']:.2f}  |  "
            f"Default Sell: {cur} {item['sell_price']:.2f}  |  "
            f"In Stock: {item['quantity']}")
        self.min_warn_var.set(
            f"Cannot sell below min: {cur} {item['min_sell_price']:.2f}")

    def _add_to_cart(self):
        name = self.item_var.get()
        item = self.item_map.get(name)
        if not item:
            messagebox.showwarning("No Item", "Please select an item first.")
            return
        try:
            qty = int(self.qty_var.get())
            assert qty >= 1
        except Exception:
            messagebox.showerror("Qty Error", "Enter a valid quantity (minimum 1).")
            return
        try:
            price = round(float(self.price_var.get()), 2)
        except Exception:
            messagebox.showerror("Price Error", "Enter a valid selling price.")
            return
        if price < item["min_sell_price"]:
            messagebox.showerror("Price Too Low",
                f"Entered:  {self.currency} {price:.2f}\n"
                f"Minimum:  {self.currency} {item['min_sell_price']:.2f}")
            return
        in_cart   = sum(c["qty"] for c in self.cart if c["stock_id"] == item["id"])
        available = item["quantity"] - in_cart
        if qty > available:
            messagebox.showerror("Not Enough Stock",
                f"Only {available} unit(s) available for '{name}'.")
            return
        for c in self.cart:
            if c["stock_id"] == item["id"] and c["price"] == price:
                c["qty"] += qty
                self._render_cart()
                return
        self.cart.append({
            "stock_id": item["id"],
            "name":     item["name"],
            "qty":      qty,
            "price":    price,
            "min":      item["min_sell_price"],
        })
        self._render_cart()

    def _render_cart(self):
        for r in self.cart_tree.get_children():
            self.cart_tree.delete(r)
        cur   = self.currency
        total = 0
        for entry in self.cart:
            line  = round(entry["qty"] * entry["price"], 2)
            total = round(total + line, 2)
            self.cart_tree.insert("", "end", values=(
                entry["name"], entry["qty"],
                f"{entry['price']:.2f}", f"{line:.2f}"))
        self.total_var.set(f"Total:  {cur} {total:.2f}")
        stype = self.sale_type_var.get()
        if stype == "Credit":
            self.type_indicator.set(
                f"CREDIT — {cur} {total:.2f} added to customer debt")
        elif stype == "Bank Transfer":
            self.type_indicator.set(
                f"BANK TRANSFER — {cur} {total:.2f} received electronically")
        else:
            self.type_indicator.set(
                f"CASH — {cur} {total:.2f} received in hand")
        self._update_change()

    def _update_change(self):
        """Recalculate and display change / balance due."""
        cur   = self.currency
        stype = self.sale_type_var.get()
        if stype == "Credit":
            self.change_var.set("")
            return
        total = round(sum(c["qty"] * c["price"] for c in self.cart), 2)
        paid_str = self.paid_var.get().strip()
        if not paid_str:
            self.change_var.set("")
            return
        try:
            paid = round(float(paid_str), 2)
        except ValueError:
            self.change_var.set("  Invalid amount")
            self.change_label.configure(text_color=DANGER)
            return
        change = round(paid - total, 2)
        if change >= 0:
            self.change_var.set(f"  Change to return:  {cur} {change:.2f}")
            self.change_label.configure(text_color=ACCENT2)
        else:
            self.change_var.set(f"  Balance still due:  {cur} {abs(change):.2f}")
            self.change_label.configure(text_color=DANGER)

    def _remove_selected(self):
        sel = self.cart_tree.selection()
        if not sel: return
        idx = self.cart_tree.index(sel[0])
        self.cart.pop(idx)
        self._render_cart()

    def _clear_cart(self):
        self.cart.clear()
        self.paid_var.set("")
        self.change_var.set("")
        self._render_cart()

    def _complete_sale(self):
        if not self.cart:
            messagebox.showwarning("Empty Cart", "Add items to the cart first.")
            return

        customer  = self.customer_var.get().strip() or "Walk-in Customer"
        stype_raw = self.sale_type_var.get()   # "Cash", "Bank Transfer", "Credit"
        # Normalise to DB value
        sale_type_map = {"Cash": "cash", "Bank Transfer": "bank", "Credit": "credit"}
        sale_type = sale_type_map.get(stype_raw, "cash")
        credit_id = None

        # Total
        total = round(sum(c["qty"] * c["price"] for c in self.cart), 2)

        # ── Validate amount paid for cash/bank ────────────
        amount_paid = 0.0
        if sale_type in ("cash", "bank"):
            paid_str = self.paid_var.get().strip()
            if paid_str:
                try:
                    amount_paid = round(float(paid_str), 2)
                except ValueError:
                    messagebox.showerror("Invalid Amount",
                        "The amount paid is not a valid number.")
                    return
                if amount_paid < total:
                    if not messagebox.askyesno("Underpayment",
                        f"Amount paid ({self.currency} {amount_paid:.2f}) is less than "
                        f"total ({self.currency} {total:.2f}).\n\n"
                        f"Balance due: {self.currency} {total - amount_paid:.2f}\n\n"
                        f"Complete sale anyway?"):
                        return
            # If left blank, assume exact payment
            else:
                amount_paid = total

        # ── Credit account validation ─────────────────────
        if sale_type == "credit":
            ca = self.credit_var.get()
            if ca == "-" or not ca:
                messagebox.showwarning("No Account",
                    "Please select a credit account for a credit sale.")
                return
            acct_name = ca.split(" (Bal:")[0].strip()
            for rec in self.db.get_credits():
                if rec["name"] == acct_name:
                    credit_id = rec["id"]
                    break
            if not credit_id:
                messagebox.showerror("Error", "Could not find the credit account.")
                return

        # ── Check & deduct stock ──────────────────────────
        for c in self.cart:
            live = self.db.get_stock_by_id(c["stock_id"])
            if not live or live["quantity"] < c["qty"]:
                messagebox.showerror("Stock Error",
                    f"Not enough stock for '{c['name']}'.\n"
                    f"Available: {live['quantity'] if live else 0}, Needed: {c['qty']}")
                return
            self.db.deduct_stock(c["stock_id"], c["qty"])

        # ── Save sale ─────────────────────────────────────
        sale_id = self.db.add_sale(
            customer, total, sale_type, credit_id,
            self.cart, served_by=self.user["username"],
            amount_paid=amount_paid)

        # ── Post-sale actions ─────────────────────────────
        change = round(amount_paid - total, 2)
        if sale_type == "credit":
            self.db.increase_credit_balance(credit_id, total)
            note = (f"Credit:  {self.currency} {total:.2f} "
                    f"added to {acct_name}'s account.\n"
                    f"NOT counted as received cash.")
        elif sale_type == "bank":
            note = (f"Bank Transfer:  {self.currency} {total:.2f} received.")
        else:
            if change >= 0:
                note = (f"Cash received:  {self.currency} {amount_paid:.2f}\n"
                        f"Total:          {self.currency} {total:.2f}\n"
                        f"Change:         {self.currency} {change:.2f}")
            else:
                note = (f"Cash received:  {self.currency} {amount_paid:.2f}\n"
                        f"Total:          {self.currency} {total:.2f}\n"
                        f"Balance due:    {self.currency} {abs(change):.2f}")

        # ── Show receipt ──────────────────────────────────
        sale  = self.db.get_sale(sale_id)
        items = self.db.get_sale_items(sale_id)
        BillWindow(self.app, self.db, sale, items)

        messagebox.showinfo("Sale Complete", note)

        # Reset
        self._clear_cart()
        self.customer_var.set("Walk-in Customer")
        self.sale_type_var.set("Cash")
        self.credit_menu.configure(state="disabled")
        self.paid_entry.configure(state="normal",
                                   placeholder_text="Enter amount paid...")
        self.type_indicator.set("")

    def refresh(self):
        stock    = self.db.get_stock()
        in_stock = [s for s in stock if s["quantity"] > 0]
        self.item_map = {s["name"]: dict(s) for s in in_stock}
        names = list(self.item_map.keys())
        self.item_menu.configure(values=names if names else ["No items in stock"])
        if names:
            self.item_var.set(names[0])
            self._on_item_select(names[0])
        else:
            self.item_var.set("No items in stock")
            self.info_var.set("")
            self.min_warn_var.set("")
        credits = self.db.get_credits()
        cnames  = [f"{c['name']} (Bal: {c['balance']:.2f})" for c in credits]
        self.credit_menu.configure(values=cnames if cnames else ["-"])
        self.credit_var.set(cnames[0] if cnames else "-")

class StockTab(BaseTab):
    def __init__(self, parent, db, app, user):
        super().__init__(parent, db, app, user)
        self._build()

    def _build(self):
        self.page_header("Stock / Items", "Manage your inventory",
                         "+ Add Item", self._open_add)
        sf = ctk.CTkFrame(self, fg_color="transparent")
        sf.pack(fill="x", padx=28, pady=(10,6))
        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", lambda *a: self.refresh())
        ctk.CTkEntry(sf, textvariable=self.search_var,
                     placeholder_text="🔍  Search items...",
                     width=400).pack(side="left")

        cols = ("ID","Item Name","Supplier","Qty","Buy Price","Min Sell","Sell Price","Status")
        f, self.tree = self.make_tree(self, cols, 20)
        f.pack(fill="both", expand=True, padx=28, pady=(0,8))
        for col, w in zip(cols, [40,200,140,55,80,80,90,110]):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=w)

        bf = ctk.CTkFrame(self, fg_color="transparent")
        bf.pack(fill="x", padx=28, pady=(0,16))
        ctk.CTkButton(bf, text="✏  Edit",    fg_color=ACCENT,   hover_color="#3a78f0",
                      command=self._edit).pack(side="left", padx=(0,8))
        ctk.CTkButton(bf, text="🗑  Delete", fg_color=DANGER,   hover_color="#cc3344",
                      command=self._delete).pack(side="left")
        ctk.CTkButton(bf, text="📄  Export PDF", fg_color=SURFACE,
                      border_color=BORDER, border_width=1, hover_color=CARD,
                      command=lambda: export_stock_pdf(self.db)).pack(side="right")

    def refresh(self):
        for r in self.tree.get_children(): self.tree.delete(r)
        cur = self.currency
        for item in self.db.get_stock(self.search_var.get()):
            q = item["quantity"]
            s = ("Out of Stock" if q <= 0 else
                 "Low Stock"    if q <= 5 else "In Stock")
            self.tree.insert("","end", values=(
                item["id"], item["name"], item["supplier_name"], q,
                f"{cur} {item['buy_price']:.2f}",
                f"{cur} {item['min_sell_price']:.2f}",
                f"{cur} {item['sell_price']:.2f}", s))

    def _sel_id(self):
        sel = self.tree.selection()
        return int(self.tree.item(sel[0])["values"][0]) if sel else None

    def _open_add(self):
        StockDialog(self.app, self.db, callback=self.refresh)

    def _edit(self):
        sid = self._sel_id()
        if not sid: messagebox.showinfo("Select","Select a row first."); return
        StockDialog(self.app, self.db, item=self.db.get_stock_by_id(sid),
                    callback=self.refresh)

    def _delete(self):
        sid = self._sel_id()
        if not sid: messagebox.showinfo("Select","Select a row first."); return
        if messagebox.askyesno("Delete","Delete this stock item?"):
            self.db.delete_stock(sid)
            self.refresh()


# ══════════════════════════════════════════════════════════════
#  SALES TAB
# ══════════════════════════════════════════════════════════════
class SalesTab(BaseTab):
    def __init__(self, parent, db, app, user):
        super().__init__(parent, db, app, user)
        self._build()

    def _build(self):
        self.page_header("Sales History", "All recorded transactions")
        sf = ctk.CTkFrame(self, fg_color="transparent")
        sf.pack(fill="x", padx=28, pady=(10,6))
        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", lambda *a: self.refresh())
        ctk.CTkEntry(sf, textvariable=self.search_var,
                     placeholder_text="🔍  Search...", width=400).pack(side="left")
        ctk.CTkButton(sf, text="📄  Export PDF",
                      fg_color=SURFACE, border_color=BORDER, border_width=1,
                      hover_color=CARD,
                      command=lambda: export_sales_pdf(self.db)).pack(side="right")

        cols = ("#","Customer","Items","Total","Type","By","Date")
        f, self.tree = self.make_tree(self, cols, 22)
        f.pack(fill="both", expand=True, padx=28, pady=(0,8))
        for col, w in [("#",40),("Customer",130),("Items",340),
                       ("Total",90),("Type",70),("By",80),("Date",100)]:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=w)

        ctk.CTkButton(self, text="🧾  View Bill for Selected",
                      fg_color=ACCENT, hover_color="#3a78f0",
                      command=self._view_bill).pack(padx=28, pady=(0,16), anchor="w")

    def refresh(self):
        for r in self.tree.get_children(): self.tree.delete(r)
        cur = self.currency
        for i, s in enumerate(self.db.get_sales(self.search_var.get()), 1):
            self.tree.insert("","end", iid=str(s["id"]), values=(
                i, s["customer"], s["items"] or "—",
                f"{cur} {s['total']:.2f}",
                s["sale_type"].upper(), s["served_by"] or "—", s["date"]))

    def _view_bill(self):
        sel = self.tree.selection()
        if not sel: messagebox.showinfo("Select","Select a sale first."); return
        sid   = int(sel[0])
        sale  = self.db.get_sale(sid)
        items = self.db.get_sale_items(sid)
        BillWindow(self.app, self.db, sale, items)


# ══════════════════════════════════════════════════════════════
#  CREDITS TAB — fixed math
# ══════════════════════════════════════════════════════════════
class CreditsTab(BaseTab):
    def __init__(self, parent, db, app, user):
        super().__init__(parent, db, app, user)
        self._build()

    def _build(self):
        self.page_header("Credit Accounts",
                         "Track customer debts — credit sales increase balance, payments decrease it",
                         "+ Add Account", self._add)

        # Info banner explaining cash vs credit
        info = ctk.CTkFrame(self, fg_color="#2a1c10", corner_radius=8)
        info.pack(fill="x", padx=28, pady=(8,4))
        ctk.CTkLabel(info,
            text="💡  Balance = money the customer OWES you.  "
                 "It increases on credit sales.  It decreases when they pay you back.",
            font=ctk.CTkFont(size=10), text_color=WARN).pack(padx=14, pady=7)

        cols = ("ID","Customer","Phone","Balance","Last Transaction","Notes")
        f, self.tree = self.make_tree(self, cols, 20)
        f.pack(fill="both", expand=True, padx=28, pady=(0,8))
        for col, w in [("ID",40),("Customer",160),("Phone",110),
                       ("Balance",100),("Last Transaction",130),("Notes",260)]:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=w)

        bf = ctk.CTkFrame(self, fg_color="transparent")
        bf.pack(fill="x", padx=28, pady=(0,16))
        ctk.CTkButton(bf, text="💵  Record Payment",
                      fg_color=ACCENT2, text_color="#0f1117",
                      hover_color="#28c29a",
                      command=self._payment).pack(side="left", padx=(0,8))
        ctk.CTkButton(bf, text="📋  Payment History",
                      fg_color=SURFACE, border_color=BORDER, border_width=1,
                      hover_color=CARD,
                      command=self._history).pack(side="left", padx=(0,8))
        ctk.CTkButton(bf, text="✏  Edit",
                      fg_color=ACCENT, hover_color="#3a78f0",
                      command=self._edit).pack(side="left", padx=(0,8))
        ctk.CTkButton(bf, text="🗑  Delete",
                      fg_color=DANGER, hover_color="#cc3344",
                      command=self._delete).pack(side="left", padx=(0,8))
        ctk.CTkButton(bf, text="📄  Export PDF",
                      fg_color=SURFACE, border_color=BORDER, border_width=1,
                      hover_color=CARD,
                      command=lambda: export_credits_pdf(self.db)).pack(side="right")

    def refresh(self):
        for r in self.tree.get_children(): self.tree.delete(r)
        cur = self.currency
        for c in self.db.get_credits():
            self.tree.insert("","end", iid=str(c["id"]), values=(
                c["id"], c["name"], c["phone"] or "—",
                f"{cur} {c['balance']:.2f}",
                c["last_transaction"] or "—",
                c["notes"] or "—"))

    def _sel_id(self):
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _add(self):
        CreditDialog(self.app, self.db, callback=self.refresh)

    def _edit(self):
        cid = self._sel_id()
        if not cid: messagebox.showinfo("Select","Select an account."); return
        rec = self.db.get_credit_by_id(cid)
        CreditDialog(self.app, self.db, record=rec, callback=self.refresh)

    def _payment(self):
        cid = self._sel_id()
        if not cid: messagebox.showinfo("Select","Select an account."); return
        rec = self.db.get_credit_by_id(cid)
        if not rec: return
        cur = self.currency

        dlg = ctk.CTkInputDialog(
            text=(f"Customer:  {rec['name']}\n"
                  f"Outstanding Balance:  {cur} {rec['balance']:.2f}\n\n"
                  f"Enter payment amount ({cur}):"),
            title="Record Credit Payment")
        amt_str = dlg.get_input()
        if amt_str is None: return  # cancelled

        try:
            amt = round(float(amt_str), 2)
            assert amt > 0
        except Exception:
            messagebox.showerror("Error","Enter a valid positive amount.")
            return

        if amt > rec["balance"]:
            if not messagebox.askyesno(
                "Overpayment?",
                f"Payment {cur} {amt:.2f} is more than balance {cur} {rec['balance']:.2f}.\n"
                f"Balance will be set to 0.\nContinue?"):
                return

        self.db.receive_credit_payment(cid, amt)
        messagebox.showinfo(
            "Payment Recorded",
            f"✔  {cur} {amt:.2f} received from {rec['name']}.\n"
            f"New balance: {cur} {max(0, rec['balance'] - amt):.2f}")
        self.refresh()

    def _history(self):
        cid = self._sel_id()
        if not cid: messagebox.showinfo("Select","Select an account."); return
        rec      = self.db.get_credit_by_id(cid)
        payments = self.db.get_credit_payments(cid)
        win = ctk.CTkToplevel(self.app)
        win.title(f"Payment History — {rec['name']}")
        win.geometry("420x420")
        win.configure(fg_color=CARD)
        win.grab_set()
        ctk.CTkLabel(win, text=f"Payment History: {rec['name']}",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=TEXT).pack(padx=20, pady=(16,8))
        f, tree = self.make_tree(win, ("ID","Amount","Date"), 12)
        f.pack(fill="both", expand=True, padx=16, pady=(0,16))
        for col, w in [("ID",50),("Amount",180),("Date",150)]:
            tree.heading(col, text=col)
            tree.column(col, width=w)
        for p in payments:
            tree.insert("","end", values=(p["id"],
                f"{self.currency} {p['amount']:.2f}", p["date"]))

    def _delete(self):
        cid = self._sel_id()
        if not cid: messagebox.showinfo("Select","Select an account."); return
        if messagebox.askyesno("Delete","Delete this credit account?"):
            self.db.delete_credit(cid)
            self.refresh()


# ══════════════════════════════════════════════════════════════
#  SUPPLIERS TAB
# ══════════════════════════════════════════════════════════════
class SuppliersTab(BaseTab):
    def __init__(self, parent, db, app, user):
        super().__init__(parent, db, app, user)
        self._build()

    def _build(self):
        self.page_header("Supplier Accounts","Manage your suppliers",
                         "+ Add Supplier", self._add)
        cols = ("ID","Name","Contact","Phone","Email","Address")
        f, self.tree = self.make_tree(self, cols, 22)
        f.pack(fill="both", expand=True, padx=28, pady=(12,8))
        for col, w in [("ID",40),("Name",150),("Contact",120),
                       ("Phone",110),("Email",160),("Address",220)]:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=w)
        bf = ctk.CTkFrame(self, fg_color="transparent")
        bf.pack(fill="x", padx=28, pady=(0,16))
        ctk.CTkButton(bf, text="✏  Edit",  fg_color=ACCENT,   hover_color="#3a78f0",
                      command=self._edit).pack(side="left", padx=(0,8))
        ctk.CTkButton(bf, text="🗑  Delete", fg_color=DANGER, hover_color="#cc3344",
                      command=self._delete).pack(side="left", padx=(0,8))
        ctk.CTkButton(bf, text="📄  Export PDF",
                      fg_color=SURFACE, border_color=BORDER, border_width=1,
                      hover_color=CARD,
                      command=lambda: export_suppliers_pdf(self.db)).pack(side="right")

    def refresh(self):
        for r in self.tree.get_children(): self.tree.delete(r)
        for s in self.db.get_suppliers():
            self.tree.insert("","end", iid=str(s["id"]),
                values=(s["id"],s["name"],s["contact"] or "—",
                        s["phone"] or "—",s["email"] or "—",s["address"] or "—"))

    def _sel_id(self):
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _add(self):
        SupplierDialog(self.app, self.db, callback=self.refresh)

    def _edit(self):
        sid = self._sel_id()
        if not sid: messagebox.showinfo("Select","Select a row."); return
        rec = next((s for s in self.db.get_suppliers() if s["id"]==sid), None)
        SupplierDialog(self.app, self.db, record=rec, callback=self.refresh)

    def _delete(self):
        sid = self._sel_id()
        if not sid: messagebox.showinfo("Select","Select a row."); return
        if messagebox.askyesno("Delete","Delete this supplier?"):
            self.db.delete_supplier(sid)
            self.refresh()


# ══════════════════════════════════════════════════════════════
#  REPORTS TAB
# ══════════════════════════════════════════════════════════════
class ReportsTab(BaseTab):
    def __init__(self, parent, db, app, user):
        super().__init__(parent, db, app, user)
        self._build()

    def _build(self):
        self.page_header("Export & Reports","Download PDF reports")
        grid = ctk.CTkFrame(self, fg_color="transparent")
        grid.pack(fill="x", padx=28, pady=16)

        exports = [
            ("📦  Stock Report",    ACCENT,  export_stock_pdf),
            ("💰  Sales Report",    ACCENT2, export_sales_pdf),
            ("💳  Credit Report",   DANGER,  export_credits_pdf),
            ("🏭  Supplier Report", WARN,    export_suppliers_pdf),
        ]
        for title, color, fn in exports:
            card = ctk.CTkFrame(grid, fg_color=CARD, corner_radius=10)
            card.pack(side="left", expand=True, fill="x", padx=5)
            ctk.CTkLabel(card, text=title,
                         font=ctk.CTkFont(size=12, weight="bold"),
                         text_color=color).pack(anchor="w", padx=14, pady=(14,6))
            ctk.CTkButton(card, text="Export PDF", fg_color=color,
                          text_color="#0f1117" if color in (ACCENT2, WARN) else "#fff",
                          command=lambda f=fn: self._export(f),
                          width=130).pack(anchor="w", padx=14, pady=(0,14))

        # Summary
        self.sum_card = ctk.CTkFrame(self, fg_color=CARD, corner_radius=10)
        self.sum_card.pack(fill="x", padx=28, pady=8)
        ctk.CTkLabel(self.sum_card, text="📊  Financial Summary",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=TEXT).pack(anchor="w", padx=16, pady=(14,8))
        self.sum_vars = {}
        row = ctk.CTkFrame(self.sum_card, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(0,14))
        for label, key, color in [
            ("Total Transactions",   "total_sales",        ACCENT),
            ("Cash Revenue",         "cash_revenue",       ACCENT2),
            ("Bank Revenue",         "bank_revenue",       ACCENT2),
            ("Credit Collected",     "credit_payments_in", ACCENT2),
            ("Credit Given Out",     "credit_given",       WARN),
            ("Still Outstanding",    "outstanding",        DANGER),
        ]:
            col = ctk.CTkFrame(row, fg_color="transparent")
            col.pack(side="left", expand=True)
            ctk.CTkLabel(col, text=label, font=ctk.CTkFont(size=10),
                         text_color=MUTED).pack(anchor="w")
            v = ctk.StringVar(value="0")
            self.sum_vars[key] = v
            ctk.CTkLabel(col, textvariable=v,
                         font=ctk.CTkFont(size=18, weight="bold"),
                         text_color=color).pack(anchor="w")

    def _export(self, fn):
        if not PDF_OK:
            messagebox.showerror("Not Installed",
                "fpdf2 is not installed.\n\nRun:  pip install fpdf2\n\nThen restart.")
            return
        fn(self.db)

    def refresh(self):
        stats = self.db.get_stats()
        cur   = self.currency
        self.sum_vars["total_sales"].set(str(stats["total_sales"]))
        self.sum_vars["cash_revenue"].set(f"{cur} {stats['cash_revenue']:.2f}")
        self.sum_vars["bank_revenue"].set(f"{cur} {stats['bank_revenue']:.2f}")
        self.sum_vars["credit_payments_in"].set(f"{cur} {stats['credit_payments_in']:.2f}")
        self.sum_vars["credit_given"].set(f"{cur} {stats['credit_given']:.2f}")
        self.sum_vars["outstanding"].set(f"{cur} {stats['outstanding']:.2f}")


# ══════════════════════════════════════════════════════════════
#  ADMIN PANEL TAB
# ══════════════════════════════════════════════════════════════
class AdminTab(BaseTab):
    """
    Only visible to users with role = 'admin'.
    • Manage all user accounts (create, edit, delete, reset password)
    • Set tab permissions per user
    • Customize shop settings (name, address, currency, etc.)
    """
    def __init__(self, parent, db, app, user):
        super().__init__(parent, db, app, user)
        self._build()

    def _build(self):
        self.page_header("Admin Panel",
                         "Manage users, permissions & shop settings")

        # ── Tab switcher ─────────────────────────────────────
        tabs_bar = ctk.CTkFrame(self, fg_color="transparent")
        tabs_bar.pack(fill="x", padx=28, pady=(12,0))
        self.admin_view = ctk.StringVar(value="users")
        for label, key in [("👥  User Management","users"),("⚙️  Shop Settings","settings")]:
            ctk.CTkButton(tabs_bar, text=label, width=200,
                          fg_color=CARD,
                          command=lambda k=key: self._switch(k)).pack(side="left", padx=(0,8))

        self.users_frame    = self._build_users_frame()
        self.settings_frame = self._build_settings_frame()
        self._switch("users")

    def _switch(self, key):
        self.users_frame.pack_forget()
        self.settings_frame.pack_forget()
        if key == "users":
            self.users_frame.pack(fill="both", expand=True, padx=28, pady=12)
            self._refresh_users()
        else:
            self.settings_frame.pack(fill="both", expand=True, padx=28, pady=12)
            self._refresh_settings()

    # ── Users section ─────────────────────────────────────────

    def _build_users_frame(self):
        f = ctk.CTkFrame(self, fg_color="transparent")

        top = ctk.CTkFrame(f, fg_color="transparent")
        top.pack(fill="x", pady=(0,8))
        ctk.CTkLabel(top, text="User Accounts",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=TEXT).pack(side="left")
        ctk.CTkButton(top, text="+ Create User",
                      fg_color=ACCENT, hover_color="#3a78f0",
                      command=self._create_user).pack(side="right")

        # User table
        cols = ("ID","Username","Role","Permissions","Active","Created")
        uf, self.user_tree = self.make_tree(f, cols, 12)
        uf.pack(fill="both", expand=True)
        for col, w in [("ID",40),("Username",130),("Role",70),
                       ("Permissions",320),("Active",60),("Created",100)]:
            self.user_tree.heading(col, text=col)
            self.user_tree.column(col, width=w)

        # Action buttons
        bf = ctk.CTkFrame(f, fg_color="transparent")
        bf.pack(fill="x", pady=(8,0))
        ctk.CTkButton(bf, text="✏  Edit User",
                      fg_color=ACCENT, hover_color="#3a78f0",
                      command=self._edit_user).pack(side="left", padx=(0,8))
        ctk.CTkButton(bf, text="🔑  Reset Password",
                      fg_color=WARN, text_color="#0f1117",
                      hover_color="#e6a030",
                      command=self._reset_password).pack(side="left", padx=(0,8))
        ctk.CTkButton(bf, text="🗑  Delete User",
                      fg_color=DANGER, hover_color="#cc3344",
                      command=self._delete_user).pack(side="left")
        return f

    def _refresh_users(self):
        for r in self.user_tree.get_children(): self.user_tree.delete(r)
        for u in self.db.get_users():
            perms = u["permissions"] or ""
            # Show tab names as readable labels
            perm_labels = []
            for key, label in ALL_TABS:
                if key in perms.split(","):
                    perm_labels.append(label.split("/")[0].strip())
            self.user_tree.insert("","end", iid=str(u["id"]), values=(
                u["id"], u["username"], u["role"].upper(),
                ", ".join(perm_labels) if perm_labels else "None",
                "✔ Yes" if u["active"] else "✖ No",
                u["created_at"]))

    def _sel_user_id(self):
        sel = self.user_tree.selection()
        return int(sel[0]) if sel else None

    def _create_user(self):
        UserDialog(self.app, self.db, callback=self._refresh_users)

    def _edit_user(self):
        uid = self._sel_user_id()
        if not uid: messagebox.showinfo("Select","Select a user first."); return
        rec = next((u for u in self.db.get_users() if u["id"] == uid), None)
        # Prevent editing the main admin record
        if rec and rec["username"].lower() == "admin" and self.user["username"].lower() != "admin":
            messagebox.showerror("Not Allowed","You cannot edit the main admin account.")
            return
        UserDialog(self.app, self.db, record=rec, callback=self._refresh_users)

    def _reset_password(self):
        uid = self._sel_user_id()
        if not uid: messagebox.showinfo("Select","Select a user first."); return
        rec = next((u for u in self.db.get_users() if u["id"] == uid), None)
        dlg = ctk.CTkInputDialog(
            text=f"Enter new password for  '{rec['username']}':",
            title="Reset Password")
        new_pw = dlg.get_input()
        if new_pw is None: return
        if len(new_pw.strip()) < 3:
            messagebox.showerror("Error","Password must be at least 3 characters.")
            return
        self.db.change_password(uid, new_pw.strip())
        messagebox.showinfo("Done", f"Password updated for '{rec['username']}'.")

    def _delete_user(self):
        uid = self._sel_user_id()
        if not uid: messagebox.showinfo("Select","Select a user first."); return
        rec = next((u for u in self.db.get_users() if u["id"] == uid), None)
        if rec and rec["username"].lower() == "admin":
            messagebox.showerror("Not Allowed","Cannot delete the main admin account.")
            return
        if rec and rec["id"] == self.user["id"]:
            messagebox.showerror("Not Allowed","You cannot delete your own account.")
            return
        if messagebox.askyesno("Delete User", f"Delete user '{rec['username']}'?"):
            self.db.delete_user(uid)
            self._refresh_users()

    # ── Settings section ──────────────────────────────────────

    def _build_settings_frame(self):
        f = ctk.CTkScrollableFrame(self, fg_color="transparent")

        ctk.CTkLabel(f, text="Shop Settings",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=TEXT).pack(anchor="w", pady=(0,12))

        self.setting_widgets = {}
        settings_fields = [
            ("shop_name",     "Shop Name",             "My Shop"),
            ("shop_address",  "Address",               "No. 1, Main Street"),
            ("shop_phone",    "Phone Number",           "+94 77 000 0000"),
            ("currency",      "Currency Code",          "LKR"),
            ("receipt_note",  "Receipt Footer Message", "Thank you for shopping with us!"),
        ]
        for key, label, placeholder in settings_fields:
            ctk.CTkLabel(f, text=label,
                         font=ctk.CTkFont(size=11), text_color=MUTED).pack(anchor="w", pady=(6,1))
            var = ctk.StringVar()
            ctk.CTkEntry(f, textvariable=var,
                         placeholder_text=placeholder, width=500).pack(anchor="w", pady=(0,4))
            self.setting_widgets[key] = var

        ctk.CTkButton(f, text="💾  Save Settings",
                      fg_color=ACCENT2, text_color="#0f1117",
                      hover_color="#28c29a", width=200,
                      command=self._save_settings).pack(anchor="w", pady=16)

        ctk.CTkFrame(f, height=1, fg_color=BORDER).pack(fill="x", pady=8)
        ctk.CTkLabel(f, text="⚠  Danger Zone",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=DANGER).pack(anchor="w", pady=(8,4))
        ctk.CTkLabel(f,
            text="Change your admin password below.",
            font=ctk.CTkFont(size=11), text_color=MUTED).pack(anchor="w")
        self.new_pw_var = ctk.StringVar()
        ctk.CTkEntry(f, textvariable=self.new_pw_var,
                     show="●", placeholder_text="New admin password",
                     width=300).pack(anchor="w", pady=(4,4))
        ctk.CTkButton(f, text="🔑  Change My Password",
                      fg_color=DANGER, hover_color="#cc3344", width=200,
                      command=self._change_own_pw).pack(anchor="w", pady=(4,20))
        return f

    def _refresh_settings(self):
        s = self.db.get_all_settings()
        for key, var in self.setting_widgets.items():
            var.set(s.get(key, ""))

    def _save_settings(self):
        for key, var in self.setting_widgets.items():
            val = var.get().strip()
            if val:
                self.db.set_setting(key, val)
        messagebox.showinfo("Saved","Shop settings updated.\n\n"
                            "Some changes (like shop name) will show after restarting.")

    def _change_own_pw(self):
        new_pw = self.new_pw_var.get().strip()
        if len(new_pw) < 3:
            messagebox.showerror("Error","Password must be at least 3 characters.")
            return
        self.db.change_password(self.user["id"], new_pw)
        messagebox.showinfo("Done","Password changed. Please login again next time.")
        self.new_pw_var.set("")

    def refresh(self):
        pass  # called on tab switch, children refresh themselves


# ══════════════════════════════════════════════════════════════
#  DIALOGS (pop-up forms)
# ══════════════════════════════════════════════════════════════

class FormDialog(ctk.CTkToplevel):
    def __init__(self, parent, title, width=520, height=440):
        super().__init__(parent)
        self.title(title)
        self.geometry(f"{width}x{height}")
        self.configure(fg_color=CARD)
        self.resizable(False, False)
        self.grab_set()
        ctk.CTkLabel(self, text=title,
                     font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=TEXT).pack(padx=20, pady=(18,10))
        ctk.CTkFrame(self, height=1, fg_color=BORDER).pack(fill="x", padx=20)
        self.body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True, padx=20, pady=10)

    def field(self, label, var, placeholder="", show=""):
        ctk.CTkLabel(self.body, text=label,
                     font=ctk.CTkFont(size=11), text_color=MUTED).pack(anchor="w", pady=(6,1))
        ctk.CTkEntry(self.body, textvariable=var, placeholder_text=placeholder,
                     show=show, width=460).pack(anchor="w", pady=(0,4))

    def dropdown(self, label, var, values):
        ctk.CTkLabel(self.body, text=label,
                     font=ctk.CTkFont(size=11), text_color=MUTED).pack(anchor="w", pady=(6,1))
        ctk.CTkOptionMenu(self.body, variable=var, values=values, width=460).pack(anchor="w", pady=(0,4))

    def footer(self, save_cmd):
        f = ctk.CTkFrame(self, fg_color="transparent")
        f.pack(fill="x", padx=20, pady=(0,14))
        ctk.CTkButton(f, text="Cancel",
                      fg_color=SURFACE, hover_color=BORDER,
                      command=self.destroy).pack(side="right", padx=(6,0))
        ctk.CTkButton(f, text="Save",
                      fg_color=ACCENT, hover_color="#3a78f0",
                      command=save_cmd).pack(side="right")


class UserDialog(ctk.CTkToplevel):
    """
    Create or edit a user account.
    Built as a standalone Toplevel (not using FormDialog) so we have
    full control over layout — the permission checkboxes need a proper
    scrollable area with the Save button always visible at the bottom.

    KEY FIX: uses tk.BooleanVar (not ctk.BooleanVar which does not exist)
    so that checkbox .get() returns correct True/False values.
    """
    def __init__(self, parent, db, record=None, callback=None):
        super().__init__(parent)
        self.db       = db
        self.record   = record
        self.callback = callback

        title = "Edit User" if record else "Create New User"
        self.title(title)
        self.geometry("520x680")
        self.configure(fg_color=CARD)
        self.resizable(True, True)
        self.grab_set()
        self.lift()
        self.focus_force()

        # ── Title bar ────────────────────────────────────────
        ctk.CTkLabel(self, text=title,
                     font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=TEXT).pack(padx=20, pady=(16, 6))
        ctk.CTkFrame(self, height=1, fg_color=BORDER).pack(fill="x", padx=20)

        # ── Scrollable body ──────────────────────────────────
        body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=8)

        def lbl(text):
            ctk.CTkLabel(body, text=text, font=ctk.CTkFont(size=11),
                         text_color=MUTED).pack(anchor="w", pady=(8, 1))

        def entry(var, placeholder="", show=""):
            ctk.CTkEntry(body, textvariable=var,
                         placeholder_text=placeholder,
                         show=show, width=460).pack(anchor="w", pady=(0, 2))

        # Username
        self.uname_v = ctk.StringVar(value=record["username"] if record else "")
        lbl("Username  *")
        entry(self.uname_v, "e.g. cashier1")

        # Password (only for new users)
        self.pw_v = ctk.StringVar()
        if not record:
            lbl("Password  *  (min 3 characters)")
            entry(self.pw_v, "Enter password", show="●")

        # Role
        self.role_v = ctk.StringVar(value=(record["role"] if record else "staff"))
        lbl("Role")
        ctk.CTkOptionMenu(body, variable=self.role_v,
                          values=["staff", "admin"],
                          command=self._on_role_change,
                          width=460).pack(anchor="w", pady=(0, 2))

        # Active
        self.active_v = ctk.StringVar(
            value="Yes" if (not record or record["active"]) else "No")
        lbl("Account Active")
        ctk.CTkOptionMenu(body, variable=self.active_v,
                          values=["Yes", "No"],
                          width=460).pack(anchor="w", pady=(0, 2))

        # ── Permissions ──────────────────────────────────────
        ctk.CTkFrame(body, height=1, fg_color=BORDER).pack(fill="x", pady=(12, 4))
        ctk.CTkLabel(body, text="Tab Permissions",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=TEXT).pack(anchor="w")
        ctk.CTkLabel(body,
                     text="Tick which tabs this user is allowed to see and use.",
                     font=ctk.CTkFont(size=10), text_color=MUTED).pack(anchor="w", pady=(0, 6))

        # IMPORTANT: use tk.BooleanVar, NOT ctk.BooleanVar
        existing_perms = set()
        if record and record["permissions"]:
            existing_perms = set(record["permissions"].split(","))
        else:
            existing_perms = {"dashboard", "billing"}   # sensible default for new staff

        self.perm_vars = {}
        self.perm_checks = {}
        for key, label in ALL_TABS:
            var = tk.BooleanVar(value=(key in existing_perms))
            self.perm_vars[key] = var
            cb = ctk.CTkCheckBox(
                body, text=label, variable=var,
                onvalue=True, offvalue=False,
                checkbox_width=20, checkbox_height=20,
                fg_color=ACCENT, hover_color="#3a78f0",
                font=ctk.CTkFont(size=12))
            cb.pack(anchor="w", padx=8, pady=3)
            self.perm_checks[key] = cb

        # If editing an admin, lock checkboxes (admin always has all)
        if record and record["role"] == "admin":
            self._lock_checkboxes(True)

        # ── Footer (always visible, outside the scroll area) ─
        ctk.CTkFrame(self, height=1, fg_color=BORDER).pack(fill="x", padx=20)
        foot = ctk.CTkFrame(self, fg_color="transparent")
        foot.pack(fill="x", padx=20, pady=12)

        ctk.CTkButton(foot, text="Cancel",
                      fg_color=SURFACE, hover_color=BORDER,
                      command=self.destroy,
                      width=100).pack(side="right", padx=(6, 0))
        ctk.CTkButton(foot, text="💾  Save User",
                      fg_color=ACCENT, hover_color="#3a78f0",
                      command=self._save,
                      width=140).pack(side="right")

    def _on_role_change(self, val):
        """When role is set to admin, check all boxes and lock them."""
        if val == "admin":
            for var in self.perm_vars.values():
                var.set(True)
            self._lock_checkboxes(True)
        else:
            self._lock_checkboxes(False)

    def _lock_checkboxes(self, lock: bool):
        state = "disabled" if lock else "normal"
        for cb in self.perm_checks.values():
            cb.configure(state=state)

    def _save(self):
        username = self.uname_v.get().strip()
        if not username:
            messagebox.showerror("Error", "Username is required.", parent=self)
            return

        role   = self.role_v.get()
        active = 1 if self.active_v.get() == "Yes" else 0

        # Collect checked permissions
        if role == "admin":
            perms = ",".join(k for k, _ in ALL_TABS)
        else:
            perms = ",".join(k for k, v in self.perm_vars.items() if v.get())

        if not perms:
            messagebox.showerror("Error",
                "Please tick at least one tab permission.", parent=self)
            return

        if self.record:
            # Editing existing user
            self.db.update_user(self.record["id"], username, role, perms, active)
            messagebox.showinfo("Saved",
                f"User '{username}' updated successfully.", parent=self)
        else:
            # Creating new user
            pw = self.pw_v.get().strip()
            if len(pw) < 3:
                messagebox.showerror("Error",
                    "Password must be at least 3 characters.", parent=self)
                return
            ok = self.db.add_user(username, pw, role, perms)
            if not ok:
                messagebox.showerror("Error",
                    f"Username '{username}' already exists. Please choose a different name.",
                    parent=self)
                return
            messagebox.showinfo("Created",
                f"User '{username}' created.  Role: {role}",
                parent=self)

        if self.callback:
            self.callback()
        self.destroy()

class StockDialog(FormDialog):
    def __init__(self, parent, db, item=None, callback=None):
        super().__init__(parent, "Edit Item" if item else "Add Stock Item", height=520)
        self.db = db; self.item = item; self.callback = callback

        self.name_v = ctk.StringVar(value=item["name"]           if item else "")
        self.qty_v  = ctk.StringVar(value=str(item["quantity"])   if item else "0")
        self.buy_v  = ctk.StringVar(value=str(item["buy_price"])  if item else "0.00")
        self.min_v  = ctk.StringVar(value=str(item["min_sell_price"]) if item else "0.00")
        self.sell_v = ctk.StringVar(value=str(item["sell_price"]) if item else "0.00")

        self.field("Item Name  *", self.name_v, "e.g. Rice 5kg")

        suppliers = [("None", None)] + [(s["name"], s["id"]) for s in db.get_suppliers()]
        self.sup_map = {s[0]: s[1] for s in suppliers}
        cur_sup = "None"
        if item and item["supplier_id"]:
            for s in db.get_suppliers():
                if s["id"] == item["supplier_id"]:
                    cur_sup = s["name"]; break
        self.sup_var = ctk.StringVar(value=cur_sup)
        self.dropdown("Supplier", self.sup_var, list(self.sup_map.keys()))

        self.field("Quantity  *",              self.qty_v,  "e.g. 50")
        self.field("Buying Price  *",          self.buy_v,  "e.g. 100.00")
        self.field("Minimum Selling Price  *", self.min_v,  "e.g. 110.00")
        self.field("Default Selling Price  *", self.sell_v, "e.g. 125.00")
        self.footer(self._save)

    def _save(self):
        name = self.name_v.get().strip()
        if not name: messagebox.showerror("Error","Item name required."); return
        try:
            qty  = int(float(self.qty_v.get()))
            buy  = round(float(self.buy_v.get()), 2)
            mn   = round(float(self.min_v.get()), 2)
            sell = round(float(self.sell_v.get()), 2)
        except Exception:
            messagebox.showerror("Error","Enter valid numbers for price and quantity.")
            return
        if sell < mn:
            messagebox.showerror(
                "Price Error",
                f"Selling price ({sell:.2f}) cannot be less than\n"
                f"minimum selling price ({mn:.2f})!")
            return
        sup_id = self.sup_map.get(self.sup_var.get())
        if self.item:
            self.db.update_stock(self.item["id"], name, sup_id, qty, buy, mn, sell)
        else:
            self.db.add_stock(name, sup_id, qty, buy, mn, sell)
        if self.callback: self.callback()
        self.destroy()


class CreditDialog(FormDialog):
    def __init__(self, parent, db, record=None, callback=None):
        super().__init__(parent, "Edit Account" if record else "Add Credit Account", height=380)
        self.db = db; self.record = record; self.callback = callback

        self.name_v  = ctk.StringVar(value=record["name"]  if record else "")
        self.phone_v = ctk.StringVar(value=record["phone"] if record else "")
        self.notes_v = ctk.StringVar(value=record["notes"] if record else "")
        self.bal_v   = ctk.StringVar(value=str(record["balance"]) if record else "0")

        self.field("Customer Name  *", self.name_v)
        self.field("Phone",            self.phone_v, "+94 77 000 0000")
        self.field("Notes",            self.notes_v, "Any notes")
        if not record:
            self.field("Opening Balance (owed from before)", self.bal_v, "0.00")
        self.footer(self._save)

    def _save(self):
        name = self.name_v.get().strip()
        if not name: messagebox.showerror("Error","Name required."); return
        if self.record:
            self.db.update_credit_info(self.record["id"], name,
                                       self.phone_v.get(), self.notes_v.get())
        else:
            try: bal = round(float(self.bal_v.get() or 0), 2)
            except: bal = 0.0
            self.db.add_credit(name, self.phone_v.get(), self.notes_v.get(), bal)
        if self.callback: self.callback()
        self.destroy()


class SupplierDialog(FormDialog):
    def __init__(self, parent, db, record=None, callback=None):
        super().__init__(parent, "Edit Supplier" if record else "Add Supplier", height=460)
        self.db = db; self.record = record; self.callback = callback

        self.name_v    = ctk.StringVar(value=record["name"]    if record else "")
        self.contact_v = ctk.StringVar(value=record["contact"] if record else "")
        self.phone_v   = ctk.StringVar(value=record["phone"]   if record else "")
        self.email_v   = ctk.StringVar(value=record["email"]   if record else "")
        self.addr_v    = ctk.StringVar(value=record["address"] if record else "")

        self.field("Company / Name  *", self.name_v, "ABC Distributors")
        self.field("Contact Person",    self.contact_v)
        self.field("Phone",             self.phone_v)
        self.field("Email",             self.email_v)
        self.field("Address",           self.addr_v)
        self.footer(self._save)

    def _save(self):
        name = self.name_v.get().strip()
        if not name: messagebox.showerror("Error","Name required."); return
        if self.record:
            self.db.update_supplier(self.record["id"], name,
                self.contact_v.get(), self.phone_v.get(),
                self.email_v.get(), self.addr_v.get())
        else:
            self.db.add_supplier(name, self.contact_v.get(),
                self.phone_v.get(), self.email_v.get(), self.addr_v.get())
        if self.callback: self.callback()
        self.destroy()


# ══════════════════════════════════════════════════════════════
#  BILL RECEIPT WINDOW
# ══════════════════════════════════════════════════════════════
class BillWindow(ctk.CTkToplevel):
    def __init__(self, parent, db, sale, items):
        super().__init__(parent)
        self.db    = db
        self.sale  = sale
        self.items = items
        self.title(f"Receipt — Sale #{sale['id']}")
        self.geometry("500x580")
        self.configure(fg_color="#ffffff")
        self.grab_set()
        self._build()

    def _build(self):
        cur       = self.db.get_setting("currency","LKR")
        shop_name = self.db.get_setting("shop_name","My Shop")
        shop_addr = self.db.get_setting("shop_address","")
        shop_ph   = self.db.get_setting("shop_phone","")
        footer_msg= self.db.get_setting("receipt_note","Thank you!")

        # Calculate grand total FIRST so we can use it in the receipt header
        self._grand = round(sum(it["quantity"] * it["sell_price"] for it in self.items), 2)

        scroll = ctk.CTkScrollableFrame(self, fg_color="#ffffff",
                                         scrollbar_button_color="#e0e0e0")
        scroll.pack(fill="both", expand=True, padx=24, pady=16)

        ctk.CTkLabel(scroll, text=f"🛒  {shop_name}",
                     font=ctk.CTkFont(size=20, weight="bold"),
                     text_color="#1a1a2e").pack(pady=(8,1))
        if shop_addr:
            ctk.CTkLabel(scroll, text=shop_addr,
                         font=ctk.CTkFont(size=10), text_color="#888").pack()
        if shop_ph:
            ctk.CTkLabel(scroll, text=f"Tel: {shop_ph}",
                         font=ctk.CTkFont(size=10), text_color="#888").pack()
        ctk.CTkLabel(scroll, text="─────────────────────",
                     text_color="#ddd").pack(pady=4)

        sale_type_label = {
            "cash": "CASH", "bank": "BANK TRANSFER", "credit": "CREDIT"
        }.get(self.sale["sale_type"], self.sale["sale_type"].upper())

        receipt_rows = [
            ("Receipt #", str(self.sale["id"])),
            ("Customer",  self.sale["customer"]),
            ("Date",      self.sale["date"]),
            ("Payment",   sale_type_label),
            ("Served by", self.sale["served_by"] or "-"),
        ]
        # Show amount paid and change for cash/bank sales
        amt_paid = self.sale["amount_paid"] if "amount_paid" in self.sale.keys() else 0
        if self.sale["sale_type"] in ("cash", "bank") and amt_paid > 0:
            change = round(amt_paid - self._grand, 2)
            receipt_rows.append(("Amount Paid", f"{cur} {amt_paid:.2f}"))
            if change >= 0:
                receipt_rows.append(("Change",      f"{cur} {change:.2f}"))
            else:
                receipt_rows.append(("Balance Due", f"{cur} {abs(change):.2f}"))
        for label, val in receipt_rows:
            row = ctk.CTkFrame(scroll, fg_color="#f5f7fa", corner_radius=5)
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=f"{label}:", font=ctk.CTkFont(size=11),
                         text_color="#777", width=90).pack(side="left", padx=10, pady=5)
            ctk.CTkLabel(row, text=str(val), font=ctk.CTkFont(size=11, weight="bold"),
                         text_color="#222").pack(side="left")

        ctk.CTkLabel(scroll, text="─────────────────────",
                     text_color="#ddd").pack(pady=6)

        # Item headers
        hrow = ctk.CTkFrame(scroll, fg_color="#e8eeff", corner_radius=5)
        hrow.pack(fill="x")
        for h, w in [("Item",185),("Qty",55),("Price",90),("Total",90)]:
            ctk.CTkLabel(hrow, text=h, font=ctk.CTkFont(size=10, weight="bold"),
                         text_color="#444", width=w).pack(side="left", padx=6, pady=5)

        for it in self.items:
            line = round(it["quantity"] * it["sell_price"], 2)
            r = ctk.CTkFrame(scroll, fg_color="#fafafa")
            r.pack(fill="x")
            ctk.CTkFrame(r, height=1, fg_color="#f0f0f0").pack(fill="x")
            inner = ctk.CTkFrame(r, fg_color="transparent")
            inner.pack(fill="x")
            for val, w in [
                (it["item_name"], 185),
                (str(it["quantity"]), 55),
                (f"{cur} {it['sell_price']:.2f}", 90),
                (f"{cur} {line:.2f}", 90),
            ]:
                ctk.CTkLabel(inner, text=val, font=ctk.CTkFont(size=11),
                             text_color="#333", width=w).pack(side="left", padx=6, pady=5)

        ctk.CTkLabel(scroll, text="-" * 21, text_color="#ddd").pack(pady=6)
        ctk.CTkLabel(scroll, text=f"Grand Total:   {cur} {self._grand:.2f}",
                     font=ctk.CTkFont(size=16, weight="bold"),
                     text_color="#1a1a2e").pack(anchor="e", padx=12)

        if self.sale["sale_type"] == "credit":
            ctk.CTkLabel(scroll,
                text="[CREDIT SALE - Amount owed by customer]",
                font=ctk.CTkFont(size=10, weight="bold"),
                text_color="#cc4400").pack(pady=(4,0))

        ctk.CTkLabel(scroll, text=footer_msg,
                     font=ctk.CTkFont(size=10), text_color="#bbb").pack(pady=(10,4))

        bf = ctk.CTkFrame(self, fg_color="#fff")
        bf.pack(fill="x", padx=24, pady=(0,14))
        ctk.CTkButton(bf, text="Close",
                      fg_color="#e0e0e0", text_color="#333", hover_color="#ccc",
                      command=self.destroy).pack(side="right", padx=(6,0))
        ctk.CTkButton(bf, text="📄  Download PDF",
                      fg_color=ACCENT, hover_color="#3a78f0",
                      command=self._pdf).pack(side="right")

    def _pdf(self):
        if not PDF_OK:
            messagebox.showerror("Not Installed","Run:  pip install fpdf2")
            return
        generate_bill_pdf(self.db, self.sale, self.items, self._grand)


# ══════════════════════════════════════════════════════════════
#  PDF EXPORT
# ══════════════════════════════════════════════════════════════

def safe_text(val):
    """
    Convert any value to a Latin-1 safe string for fpdf2.
    fpdf2 uses Latin-1 (ISO-8859-1) by default.
    Characters outside that range (em dash, smart quotes, emoji, etc.)
    are replaced with plain ASCII equivalents so the PDF never crashes.
    """
    text = str(val)
    replacements = {
        "—": "-",   # em dash
        "–": "-",   # en dash
        "‘": "'",   # left single quote
        "’": "'",   # right single quote
        "“": '"',   # left double quote
        "”": '"',   # right double quote
        "…": "...", # ellipsis
        " ": " ",   # non-breaking space
        "€": "EUR", # euro sign (not in Latin-1 positions fpdf uses)
        "™": "TM",  # trademark
        "®": "(R)", # registered
        "©": "(C)", # copyright
    }
    for char, replacement in replacements.items():
        text = text.replace(char, replacement)
    # Final pass: drop any remaining non-Latin-1 characters
    return text.encode("latin-1", errors="replace").decode("latin-1")


class ShopPDF(FPDF if PDF_OK else object):
    def __init__(self, db):
        if PDF_OK: super().__init__()
        self._db = db

    def header(self):
        shop_name = safe_text(self._db.get_setting("shop_name","My Shop"))
        self.set_font("Helvetica","B",14)
        self.set_text_color(30,30,80)
        self.cell(0,9,shop_name, new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica","",8)
        self.set_text_color(130,130,130)
        self.cell(0,5,f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}",
                  new_x="LMARGIN", new_y="NEXT")
        self.ln(2)
        self.set_draw_color(79,140,255)
        self.set_line_width(0.5)
        self.line(10,self.get_y(),200,self.get_y())
        self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica","I",8)
        self.set_text_color(160,160,160)
        self.cell(0,10,f"Page {self.page_no()}", align="C")

    def section_title(self, title):
        self.set_font("Helvetica","B",12)
        self.set_text_color(79,140,255)
        self.cell(0,8,safe_text(title), new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def th(self, cols):
        """Table header row — blue background, white text."""
        self.set_fill_color(79,140,255)
        self.set_text_color(255,255,255)
        self.set_font("Helvetica","B",9)
        for text, w in cols:
            self.cell(w, 8, safe_text(text), border=0, fill=True)
        self.ln()

    def tr(self, cols, shade=False):
        """Table data row — alternating shading."""
        if shade:
            self.set_fill_color(245,247,255)
        else:
            self.set_fill_color(255,255,255)
        self.set_text_color(30,30,60)
        self.set_font("Helvetica","",9)
        for text, w in cols:
            self.cell(w, 7, safe_text(text), border=0, fill=True)
        self.ln()

    def info_line(self, text):
        """Single info/summary line below a section title."""
        self.set_font("Helvetica","",9)
        self.set_text_color(60,60,60)
        self.cell(0, 6, safe_text(text), new_x="LMARGIN", new_y="NEXT")
        self.ln(3)


def _save(pdf, name):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), name)
    pdf.output(path)
    messagebox.showinfo("✔ PDF Saved", f"Saved to:\n{path}")


def generate_bill_pdf(db, sale, items, total):
    cur       = db.get_setting("currency","LKR")
    shop_name = safe_text(db.get_setting("shop_name","My Shop"))
    shop_addr = safe_text(db.get_setting("shop_address",""))
    shop_ph   = safe_text(db.get_setting("shop_phone",""))
    note      = safe_text(db.get_setting("receipt_note","Thank you!"))

    pdf = ShopPDF(db)
    pdf.add_page()
    pdf.set_font("Helvetica","B",14)
    pdf.set_text_color(30,30,80)
    pdf.cell(0,8,shop_name, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica","",8)
    pdf.set_text_color(100,100,100)
    if shop_addr: pdf.cell(0,5,shop_addr, new_x="LMARGIN", new_y="NEXT")
    if shop_ph:   pdf.cell(0,5,f"Tel: {shop_ph}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    type_label = {"cash":"CASH","bank":"BANK TRANSFER","credit":"CREDIT"}.get(
        sale["sale_type"], sale["sale_type"].upper())
    bill_rows = [
        ("Receipt #", sale["id"]),
        ("Customer",  safe_text(sale["customer"])),
        ("Date",      sale["date"]),
        ("Payment",   type_label),
        ("Served by", safe_text(sale["served_by"] or "-")),
    ]
    amt_paid = sale["amount_paid"] if "amount_paid" in sale.keys() else 0
    if sale["sale_type"] in ("cash","bank") and amt_paid > 0:
        change = round(amt_paid - total, 2)
        bill_rows.append(("Amount Paid", f"{cur} {amt_paid:.2f}"))
        bill_rows.append(("Change" if change >= 0 else "Balance Due",
                          f"{cur} {abs(change):.2f}"))
    for label, val in bill_rows:
        pdf.set_font("Helvetica","",9)
        pdf.cell(38,6,f"{label}:")
        pdf.cell(0,6,safe_text(str(val)), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    pdf.th([("Item",65),("Qty",14),(f"Price ({cur})",28),(f"Total ({cur})",28)])
    for i, it in enumerate(items):
        line = round(it["quantity"] * it["sell_price"], 2)
        pdf.tr([(safe_text(it["item_name"])[:25],65),(it["quantity"],14),
                (f"{it['sell_price']:.2f}",28),(f"{line:.2f}",28)], i%2==0)
    pdf.ln(3)
    pdf.set_font("Helvetica","B",11)
    pdf.set_text_color(30,30,80)
    pdf.cell(0,8,f"Grand Total: {cur} {total:.2f}", align="R",
             new_x="LMARGIN", new_y="NEXT")
    if sale["sale_type"] == "credit":
        pdf.set_font("Helvetica","B",9)
        pdf.set_text_color(200,60,0)
        pdf.cell(0,6,"[CREDIT SALE - Amount owed by customer]", align="R",
                 new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica","I",8)
    pdf.set_text_color(160,160,160)
    pdf.cell(0,6,note, align="C")
    _save(pdf, f"Receipt_{sale['id']}_{sale['date']}.pdf")


def export_stock_pdf(db):
    cur = db.get_setting("currency","LKR")
    pdf = ShopPDF(db); pdf.add_page()
    pdf.section_title("Stock / Inventory Report")
    pdf.th([("Item",58),("Supplier",38),("Qty",16),(f"Buy ({cur})",24),
            (f"Min Sell ({cur})",30),(f"Sell ({cur})",26)])
    for i, item in enumerate(db.get_stock()):
        pdf.tr([(safe_text(item["name"])[:24],58),
                (safe_text(item["supplier_name"])[:15],38),
                (item["quantity"],16),(f"{item['buy_price']:.2f}",24),
                (f"{item['min_sell_price']:.2f}",30),(f"{item['sell_price']:.2f}",26)], i%2==0)
    _save(pdf, f"ShopEase_Stock_{datetime.date.today()}.pdf")


def export_sales_pdf(db):
    cur   = db.get_setting("currency","LKR")
    stats = db.get_stats()
    pdf   = ShopPDF(db); pdf.add_page()
    pdf.section_title("Sales Report")
    pdf.info_line(
        f"Cash Revenue: {cur} {stats['cash_revenue']:.2f}   |   "
        f"Credit Given: {cur} {stats['credit_given']:.2f}   |   "
        f"Total Transactions: {stats['total_sales']}")
    pdf.th([("#",12),("Customer",38),("Items",70),(f"Total ({cur})",26),("Type",20),("Date",28)])
    for i, s in enumerate(db.get_sales()):
        items_str = safe_text(s["items"] or "-")[:34]
        pdf.tr([(i+1,12),(safe_text(s["customer"])[:15],38),(items_str,70),
                (f"{s['total']:.2f}",26),(s["sale_type"].upper(),20),(s["date"],28)], i%2==0)
    _save(pdf, f"ShopEase_Sales_{datetime.date.today()}.pdf")


def export_credits_pdf(db):
    cur = db.get_setting("currency","LKR")
    pdf = ShopPDF(db); pdf.add_page()
    pdf.section_title("Credit Accounts Report")
    total_outstanding = sum(c["balance"] for c in db.get_credits())
    pdf.info_line(f"Total Outstanding: {cur} {total_outstanding:.2f}")
    pdf.th([("Customer",52),("Phone",34),(f"Balance ({cur})",36),("Last Tx",30),("Notes",38)])
    for i, c in enumerate(db.get_credits()):
        pdf.tr([(safe_text(c["name"])[:20],52),
                (safe_text(c["phone"] or "-"),34),
                (f"{c['balance']:.2f}",36),
                (c["last_transaction"] or "-",30),
                (safe_text(c["notes"] or "-")[:16],38)], i%2==0)
    _save(pdf, f"ShopEase_Credits_{datetime.date.today()}.pdf")


def export_suppliers_pdf(db):
    pdf = ShopPDF(db); pdf.add_page()
    pdf.section_title("Supplier Report")
    pdf.th([("Name",44),("Contact",32),("Phone",34),("Email",50),("Address",30)])
    for i, s in enumerate(db.get_suppliers()):
        pdf.tr([(safe_text(s["name"])[:18],44),
                (safe_text(s["contact"] or "-"),32),
                (safe_text(s["phone"] or "-"),34),
                (safe_text(s["email"] or "-"),50),
                (safe_text(s["address"] or "-")[:12],30)], i%2==0)
    _save(pdf, f"ShopEase_Suppliers_{datetime.date.today()}.pdf")



# ══════════════════════════════════════════════════════════════
#  PROFITS TAB
# ══════════════════════════════════════════════════════════════
class ProfitsTab(BaseTab):
    """
    Shows profit per item and overall totals.
    Profit = Selling Price - Buying Price (per unit), multiplied by qty sold.
    Can be filtered by date range.
    """
    def __init__(self, parent, db, app, user):
        super().__init__(parent, db, app, user)
        self._build()

    def _build(self):
        self.page_header("Profit Analysis",
                         "Profit = Sell Price - Buy Price, per item sold")

        # ── Filter bar ───────────────────────────────────────
        fbar = ctk.CTkFrame(self, fg_color=CARD, corner_radius=8)
        fbar.pack(fill="x", padx=28, pady=(10, 6))

        ctk.CTkLabel(fbar, text="Filter by date:",
                     font=ctk.CTkFont(size=11), text_color=MUTED).pack(
                         side="left", padx=(14, 6), pady=10)

        self.from_var = ctk.StringVar()
        self.to_var   = ctk.StringVar()

        ctk.CTkLabel(fbar, text="From (YYYY-MM-DD)",
                     font=ctk.CTkFont(size=10), text_color=MUTED).pack(side="left")
        ctk.CTkEntry(fbar, textvariable=self.from_var, width=130).pack(
            side="left", padx=(4, 12), pady=8)

        ctk.CTkLabel(fbar, text="To (YYYY-MM-DD)",
                     font=ctk.CTkFont(size=10), text_color=MUTED).pack(side="left")
        ctk.CTkEntry(fbar, textvariable=self.to_var, width=130).pack(
            side="left", padx=(4, 12), pady=8)

        ctk.CTkButton(fbar, text="🔍 Apply Filter",
                      fg_color=ACCENT, hover_color="#3a78f0", width=130,
                      command=self.refresh).pack(side="left", padx=(0, 8))
        ctk.CTkButton(fbar, text="Clear",
                      fg_color=SURFACE, border_color=BORDER, border_width=1,
                      hover_color=CARD, width=80,
                      command=self._clear_filter).pack(side="left")
        ctk.CTkButton(fbar, text="📄 Export PDF",
                      fg_color=SURFACE, border_color=BORDER, border_width=1,
                      hover_color=CARD, width=120,
                      command=self._export_pdf).pack(side="right", padx=10)

        # ── Summary stat cards ───────────────────────────────
        self.sum_row = ctk.CTkFrame(self, fg_color="transparent")
        self.sum_row.pack(fill="x", padx=28, pady=(4, 6))

        self.sum_vars = {}
        for label, key, color in [
            ("Total Revenue",  "revenue", ACCENT),
            ("Total Cost",     "cost",    WARN),
            ("Total Profit",   "profit",  ACCENT2),
            ("Profit Margin",  "margin",  ACCENT2),
            ("Sales Count",    "count",   ACCENT),
        ]:
            card = ctk.CTkFrame(self.sum_row, fg_color=CARD, corner_radius=10)
            card.pack(side="left", expand=True, fill="x", padx=4)
            ctk.CTkLabel(card, text=label,
                         font=ctk.CTkFont(size=9, weight="bold"),
                         text_color=MUTED).pack(anchor="w", padx=12, pady=(10, 2))
            var = ctk.StringVar(value="0")
            self.sum_vars[key] = var
            ctk.CTkLabel(card, textvariable=var,
                         font=ctk.CTkFont(size=16, weight="bold"),
                         text_color=color).pack(anchor="w", padx=12, pady=(0, 10))

        # ── Per-item profit table ────────────────────────────
        ctk.CTkLabel(self, text="Profit Per Item",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=TEXT).pack(anchor="w", padx=28, pady=(4, 4))

        cols = ("Item", "Qty Sold", "Buy Price", "Avg Sell", "Revenue", "Cost", "Profit", "Margin %")
        f, self.tree = self.make_tree(self, cols, 18)
        f.pack(fill="both", expand=True, padx=28, pady=(0, 16))
        for col, w in [("Item",180),("Qty Sold",75),("Buy Price",90),("Avg Sell",90),
                       ("Revenue",100),("Cost",100),("Profit",100),("Margin %",85)]:
            self.tree.heading(col, text=col,
                command=lambda c=col: self._sort_by(c))
            self.tree.column(col, width=w, anchor="e" if col != "Item" else "w")

        self._sort_col = "Profit"
        self._sort_rev = True

    def _clear_filter(self):
        self.from_var.set("")
        self.to_var.set("")
        self.refresh()

    def _sort_by(self, col):
        if self._sort_col == col:
            self._sort_rev = not self._sort_rev
        else:
            self._sort_col = col
            self._sort_rev = True
        self.refresh()

    def refresh(self):
        cur       = self.currency
        date_from = self.from_var.get().strip()
        date_to   = self.to_var.get().strip()

        # Summary
        s = self.db.get_profit_summary(date_from, date_to)
        rev    = s.get("total_revenue", 0) or 0
        cost   = s.get("total_cost",    0) or 0
        profit = s.get("total_profit",  0) or 0
        count  = s.get("num_sales",     0) or 0
        margin = (profit / rev * 100) if rev else 0

        self.sum_vars["revenue"].set(f"{cur} {rev:.2f}")
        self.sum_vars["cost"].set(f"{cur} {cost:.2f}")
        self.sum_vars["profit"].set(f"{cur} {profit:.2f}")
        self.sum_vars["margin"].set(f"{margin:.1f}%")
        self.sum_vars["count"].set(str(count))

        # Per-item rows
        for r in self.tree.get_children():
            self.tree.delete(r)

        rows = self.db.get_profit_by_item(date_from, date_to)

        # Sort
        col_map = {
            "Item":      lambda r: r["item_name"],
            "Qty Sold":  lambda r: r["total_qty"],
            "Buy Price": lambda r: r["buy_price"],
            "Avg Sell":  lambda r: r["avg_sell"],
            "Revenue":   lambda r: r["total_revenue"],
            "Cost":      lambda r: r["total_cost"],
            "Profit":    lambda r: r["total_profit"],
            "Margin %":  lambda r: (r["total_profit"] / r["total_revenue"] * 100
                                    if r["total_revenue"] else 0),
        }
        key_fn = col_map.get(self._sort_col, col_map["Profit"])
        rows = sorted(rows, key=key_fn, reverse=self._sort_rev)

        for item in rows:
            rev_i    = item["total_revenue"] or 0
            cost_i   = item["total_cost"]    or 0
            profit_i = item["total_profit"]  or 0
            margin_i = (profit_i / rev_i * 100) if rev_i else 0

            # Color profit column: green if positive, red if negative
            tag = "profit_pos" if profit_i >= 0 else "profit_neg"
            self.tree.insert("", "end", tags=(tag,), values=(
                item["item_name"],
                item["total_qty"],
                f"{cur} {item['buy_price']:.2f}",
                f"{cur} {item['avg_sell']:.2f}",
                f"{cur} {rev_i:.2f}",
                f"{cur} {cost_i:.2f}",
                f"{cur} {profit_i:.2f}",
                f"{margin_i:.1f}%",
            ))

        self.tree.tag_configure("profit_pos", foreground=ACCENT2)
        self.tree.tag_configure("profit_neg", foreground=DANGER)

    def _export_pdf(self):
        if not PDF_OK:
            messagebox.showerror("Not Installed", "Run:  pip install fpdf2")
            return
        cur       = self.currency
        date_from = self.from_var.get().strip()
        date_to   = self.to_var.get().strip()
        s         = self.db.get_profit_summary(date_from, date_to)
        rows      = self.db.get_profit_by_item(date_from, date_to)
        rev    = s.get("total_revenue", 0) or 0
        cost   = s.get("total_cost",    0) or 0
        profit = s.get("total_profit",  0) or 0
        margin = (profit / rev * 100) if rev else 0
        pdf = ShopPDF(self.db)
        pdf.add_page()
        period = f"{date_from or 'All'} to {date_to or 'Today'}"
        pdf.section_title(f"Profit Report - {period}")
        pdf.info_line(
            f"Revenue: {cur} {rev:.2f}  |  Cost: {cur} {cost:.2f}  |  "
            f"Profit: {cur} {profit:.2f}  |  Margin: {margin:.1f}%"
        )
        pdf.th([("Item",55),("Qty",16),("Buy",24),("Avg Sell",26),
                ("Revenue",28),("Cost",28),("Profit",28),("Margin%",20)])
        for i, item in enumerate(rows):
            rev_i    = item["total_revenue"] or 0
            cost_i   = item["total_cost"]    or 0
            profit_i = item["total_profit"]  or 0
            margin_i = (profit_i / rev_i * 100) if rev_i else 0
            pdf.tr([
                (safe_text(item["item_name"])[:22], 55),
                (item["total_qty"],                 16),
                (f"{item['buy_price']:.2f}",        24),
                (f"{item['avg_sell']:.2f}",         26),
                (f"{rev_i:.2f}",                    28),
                (f"{cost_i:.2f}",                   28),
                (f"{profit_i:.2f}",                 28),
                (f"{margin_i:.1f}%",                20),
            ], i % 2 == 0)
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            f"ShopEase_Profit_{datetime.date.today()}.pdf")
        pdf.output(path)
        messagebox.showinfo("Saved", f"Profit report saved to:\n{path}")

        pdf = ShopPDF(self.db)
        pdf.add_page()
        period = f"{date_from or 'All'} to {date_to or 'Today'}"
        pdf.section_title(f"Profit Report — {period}")

        # Summary line
        rev    = s.get("total_revenue", 0) or 0
        cost   = s.get("total_cost",    0) or 0
        profit = s.get("total_profit",  0) or 0
        margin = (profit / rev * 100) if rev else 0
        pdf.set_font("Helvetica","",9); pdf.set_text_color(60,60,60)
        pdf.cell(0,6,
            f"Revenue: {cur} {rev:.2f}  |  Cost: {cur} {cost:.2f}  |  "
            f"Profit: {cur} {profit:.2f}  |  Margin: {margin:.1f}%",
            new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)

        pdf.th([("Item",55),("Qty",16),(f"Buy",24),(f"Avg Sell",26),
                (f"Revenue",28),(f"Cost",28),(f"Profit",28),("Margin%",20)])
        for i, item in enumerate(rows):
            rev_i    = item["total_revenue"] or 0
            cost_i   = item["total_cost"]    or 0
            profit_i = item["total_profit"]  or 0
            margin_i = (profit_i / rev_i * 100) if rev_i else 0
            pdf.tr([(item["item_name"][:22],55),(item["total_qty"],16),
                    (f"{item['buy_price']:.2f}",24),(f"{item['avg_sell']:.2f}",26),
                    (f"{rev_i:.2f}",28),(f"{cost_i:.2f}",28),
                    (f"{profit_i:.2f}",28),(f"{margin_i:.1f}%",20)], i%2==0)

        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            f"ShopEase_Profit_{datetime.date.today()}.pdf")
        pdf.output(path)
        messagebox.showinfo("Saved", f"Profit report saved to:\n{path}")


# ══════════════════════════════════════════════════════════════
#  DAILY BILLS TAB
# ══════════════════════════════════════════════════════════════
class DailyBillsTab(BaseTab):
    """
    Shows all sales grouped by day.
    Left side: calendar-style list of all days.
    Right side: sales for the selected day + daily totals.
    """
    def __init__(self, parent, db, app, user):
        super().__init__(parent, db, app, user)
        self._selected_date = None
        self._build()

    def _build(self):
        self.page_header("Daily Bills",
                         "Select a day to see all sales and totals for that day")

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=28, pady=10)

        # ── LEFT: date list ──────────────────────────────────
        left = ctk.CTkFrame(body, fg_color=CARD, corner_radius=10, width=200)
        left.pack(side="left", fill="y", padx=(0, 10))
        left.pack_propagate(False)

        ctk.CTkLabel(left, text="📅  Select Day",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=TEXT).pack(padx=14, pady=(14, 6))

        df, self.date_tree = self.make_tree(left, ("Date", "Sales", "Total"), 28)
        df.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        for col, w in [("Date", 90), ("Sales", 40), ("Total", 68)]:
            self.date_tree.heading(col, text=col)
            self.date_tree.column(col, width=w, anchor="w" if col=="Date" else "e")
        self.date_tree.bind("<<TreeviewSelect>>", self._on_date_select)

        # ── RIGHT: sales for selected day ────────────────────
        right = ctk.CTkFrame(body, fg_color="transparent")
        right.pack(side="left", fill="both", expand=True)

        # Day summary cards
        self.day_sum_row = ctk.CTkFrame(right, fg_color="transparent")
        self.day_sum_row.pack(fill="x", pady=(0, 8))
        self.day_vars = {}
        for label, key, color in [
            ("Date",           "date",   TEXT),
            ("Cash Sales",     "cash",   ACCENT2),
            ("Bank Transfer",  "bank",   ACCENT2),
            ("Credit Sales",   "credit", WARN),
            ("Day Total",      "total",  ACCENT),
            ("Day Profit",     "profit", ACCENT2),
            ("No. of Bills",   "count",  ACCENT),
        ]:
            card = ctk.CTkFrame(self.day_sum_row, fg_color=CARD, corner_radius=10)
            card.pack(side="left", expand=True, fill="x", padx=3)
            ctk.CTkLabel(card, text=label,
                         font=ctk.CTkFont(size=9, weight="bold"),
                         text_color=MUTED).pack(anchor="w", padx=10, pady=(10, 2))
            var = ctk.StringVar(value="—")
            self.day_vars[key] = var
            ctk.CTkLabel(card, textvariable=var,
                         font=ctk.CTkFont(size=14, weight="bold"),
                         text_color=color).pack(anchor="w", padx=10, pady=(0, 10))

        # Sales table for the day
        ctk.CTkLabel(right, text="Bills for Selected Day",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=TEXT).pack(anchor="w", pady=(0, 4))

        cols = ("#", "Customer", "Items", "Total", "Type", "By")
        sf, self.sales_tree = self.make_tree(right, cols, 16)
        sf.pack(fill="both", expand=True)
        for col, w in [("#",40),("Customer",130),("Items",320),
                       ("Total",90),("Type",70),("By",80)]:
            self.sales_tree.heading(col, text=col)
            self.sales_tree.column(col, width=w)
        self.sales_tree.bind("<<TreeviewSelect>>", self._on_sale_select)

        # Bottom buttons
        bf = ctk.CTkFrame(right, fg_color="transparent")
        bf.pack(fill="x", pady=(8, 0))
        ctk.CTkButton(bf, text="🧾  View Bill",
                      fg_color=ACCENT, hover_color="#3a78f0",
                      command=self._view_bill).pack(side="left", padx=(0, 8))
        ctk.CTkButton(bf, text="📄  Export Day PDF",
                      fg_color=SURFACE, border_color=BORDER, border_width=1,
                      hover_color=CARD,
                      command=self._export_day_pdf).pack(side="left")

    def refresh(self):
        """Reload the date list."""
        for r in self.date_tree.get_children():
            self.date_tree.delete(r)
        cur   = self.currency
        dates = self.db.get_sales_dates()
        for d in dates:
            summary = self.db.get_daily_summary(d)
            self.date_tree.insert("", "end", iid=d, values=(
                d,
                summary.get("num_sales", 0),
                f"{cur} {summary.get('grand_total', 0):.2f}",
            ))
        # Re-select previously selected date if still present
        if self._selected_date and self._selected_date in dates:
            self.date_tree.selection_set(self._selected_date)
            self._load_day(self._selected_date)
        elif dates:
            self.date_tree.selection_set(dates[0])
            self._load_day(dates[0])

    def _on_date_select(self, event):
        sel = self.date_tree.selection()
        if sel:
            self._load_day(sel[0])

    def _load_day(self, date):
        self._selected_date = date
        cur     = self.currency
        summary = self.db.get_daily_summary(date)
        sales   = self.db.get_sales_for_date(date)

        # Update summary cards
        self.day_vars["date"].set(date)
        self.day_vars["cash"].set(f"{cur} {summary.get('cash_total',0):.2f}")
        self.day_vars["bank"].set(f"{cur} {summary.get('bank_total',0):.2f}")
        self.day_vars["credit"].set(f"{cur} {summary.get('credit_total',0):.2f}")
        self.day_vars["total"].set(f"{cur} {summary.get('grand_total',0):.2f}")
        self.day_vars["profit"].set(f"{cur} {summary.get('profit',0):.2f}")
        self.day_vars["count"].set(str(summary.get("num_sales", 0)))

        # Fill sales table
        for r in self.sales_tree.get_children():
            self.sales_tree.delete(r)
        for i, s in enumerate(sales, 1):
            self.sales_tree.insert("", "end", iid=str(s["id"]), values=(
                i, s["customer"], s["items"] or "—",
                f"{cur} {s['total']:.2f}",
                s["sale_type"].upper(),
                s["served_by"] or "—",
            ))

    def _on_sale_select(self, event):
        pass  # just highlight, view on button press

    def _view_bill(self):
        sel = self.sales_tree.selection()
        if not sel:
            messagebox.showinfo("Select", "Select a bill from the table first.")
            return
        sid   = int(sel[0])
        sale  = self.db.get_sale(sid)
        items = self.db.get_sale_items(sid)
        BillWindow(self.app, self.db, sale, items)

    def _export_day_pdf(self):
        if not self._selected_date:
            messagebox.showinfo("No Date", "Select a day first.")
            return
        if not PDF_OK:
            messagebox.showerror("Not Installed", "Run:  pip install fpdf2")
            return
        cur     = self.currency
        date    = self._selected_date
        summary = self.db.get_daily_summary(date)
        sales   = self.db.get_sales_for_date(date)
        pdf = ShopPDF(self.db)
        pdf.add_page()
        pdf.section_title(f"Daily Sales Report - {date}")
        pdf.info_line(
            f"Cash: {cur} {summary.get('cash_total',0):.2f}  |  "
            f"Bank: {cur} {summary.get('bank_total',0):.2f}  |  "
            f"Credit: {cur} {summary.get('credit_total',0):.2f}  |  "
            f"Total: {cur} {summary.get('grand_total',0):.2f}  |  "
            f"Profit: {cur} {summary.get('profit',0):.2f}  |  "
            f"Bills: {summary.get('num_sales',0)}"
        )
        pdf.th([("#",12),("Customer",38),("Items",74),(f"Total ({cur})",26),("Type",20),("By",20)])
        for i, s in enumerate(sales):
            pdf.tr([
                (i + 1,                                12),
                (safe_text(s["customer"])[:14],         38),
                (safe_text(s["items"] or "-")[:36],     74),
                (f"{s['total']:.2f}",                  26),
                (s["sale_type"].upper(),               20),
                (safe_text(s["served_by"] or "-")[:8], 20),
            ], i % 2 == 0)
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            f"ShopEase_Daily_{date}.pdf")
        pdf.output(path)
        messagebox.showinfo("Saved", f"Daily report saved to:\n{path}")

        pdf = ShopPDF(self.db)
        pdf.add_page()
        pdf.section_title(f"Daily Sales Report — {date}")

        # Summary line
        pdf.set_font("Helvetica","",9); pdf.set_text_color(60,60,60)
        pdf.cell(0,6,
            f"Cash: {cur} {summary.get('cash_total',0):.2f}  |  "
            f"Credit: {cur} {summary.get('credit_total',0):.2f}  |  "
            f"Total: {cur} {summary.get('grand_total',0):.2f}  |  "
            f"Profit: {cur} {summary.get('profit',0):.2f}  |  "
            f"Bills: {summary.get('num_sales',0)}",
            new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)

        pdf.th([("#",12),("Customer",38),("Items",74),(f"Total ({cur})",26),("Type",20),("By",20)])
        for i, s in enumerate(sales):
            items_str = (s["items"] or "—")[:36]
            pdf.tr([(i+1,12),(s["customer"][:14],38),(items_str,74),
                    (f"{s['total']:.2f}",26),(s["sale_type"].upper(),20),
                    ((s["served_by"] or "—")[:8],20)], i%2==0)

        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            f"ShopEase_Daily_{date}.pdf")
        pdf.output(path)
        messagebox.showinfo("Saved", f"Daily report saved to:\n{path}")


# ══════════════════════════════════════════════════════════════
#  MAIN APPLICATION WINDOW
# ══════════════════════════════════════════════════════════════
class ShopEaseApp(ctk.CTk):
    def __init__(self, db: Database, user: dict):
        super().__init__()
        self.db   = db
        self.user = user

        shop_name = db.get_setting("shop_name","My Shop")
        self.title(f"{shop_name} — POS  ({user['username']}  |  {user['role']})")
        self.geometry("1300x800")
        self.minsize(900,600)

        apply_tree_style()
        self._build_ui()
        self.show_tab("dashboard")

    def _build_ui(self):
        # ── Sidebar ──────────────────────────────────────────
        sidebar = ctk.CTkFrame(self, width=215, corner_radius=0, fg_color=SURFACE)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        shop_name = self.db.get_setting("shop_name","My Shop")
        ctk.CTkLabel(sidebar, text=shop_name,
                     font=ctk.CTkFont(size=18, weight="bold"),
                     text_color=ACCENT).pack(pady=(20,2))
        ctk.CTkLabel(sidebar, text="Point of Sale",
                     font=ctk.CTkFont(size=10), text_color=MUTED).pack()
        ctk.CTkFrame(sidebar, height=1, fg_color=BORDER).pack(fill="x", padx=14, pady=12)

        # Logged-in user badge
        role_color = ACCENT if self.user["role"] == "admin" else ACCENT2
        ctk.CTkLabel(sidebar,
                     text=f"👤  {self.user['username']}",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=role_color).pack()
        ctk.CTkLabel(sidebar, text=f"Role: {self.user['role']}",
                     font=ctk.CTkFont(size=10), text_color=MUTED).pack(pady=(0,10))
        ctk.CTkFrame(sidebar, height=1, fg_color=BORDER).pack(fill="x", padx=14, pady=(0,8))

        # Navigation — only show tabs the user has permission for
        user_perms = set(self.user.get("permissions","").split(","))

        self.nav_btns = {}
        nav_items = [
            ("🏠   Dashboard",   "dashboard"),
            ("🛒   Billing/POS", "billing"),
            ("📦   Stock",       "stock"),
            ("💰   Sales",       "sales"),
            ("💳   Credits",     "credits"),
            ("🏭   Suppliers",   "suppliers"),
            ("📊   Reports",     "reports"),
            ("📈   Profits",     "profits"),
            ("📅   Daily Bills", "daily"),
        ]
        for label, key in nav_items:
            if key not in user_perms:
                continue  # hide tabs the user has no access to
            btn = ctk.CTkButton(
                sidebar, text=label, anchor="w",
                fg_color="transparent", hover_color=CARD,
                command=lambda k=key: self.show_tab(k), height=38)
            btn.pack(fill="x", padx=10, pady=2)
            self.nav_btns[key] = btn

        # Admin panel — only for admin role
        if self.user["role"] == "admin":
            ctk.CTkFrame(sidebar, height=1, fg_color=BORDER).pack(fill="x", padx=14, pady=8)
            btn = ctk.CTkButton(sidebar, text="🔧   Admin Panel",
                                anchor="w", fg_color="transparent",
                                hover_color=CARD,
                                command=lambda: self.show_tab("admin"), height=38)
            btn.pack(fill="x", padx=10, pady=2)
            self.nav_btns["admin"] = btn

        # Logout button
        ctk.CTkButton(sidebar, text="🚪  Logout",
                      fg_color="transparent", hover_color=CARD,
                      text_color=DANGER,
                      command=self._logout, height=36).pack(
                          side="bottom", fill="x", padx=10, pady=(0,14))

        ctk.CTkLabel(sidebar,
                     text=f"💾  shopease.db",
                     font=ctk.CTkFont(size=9), text_color=BORDER).pack(
                         side="bottom", pady=(0,6))

        # ── Content area ─────────────────────────────────────
        self.content = ctk.CTkFrame(self, corner_radius=0, fg_color=BG)
        self.content.pack(side="left", fill="both", expand=True)

        # Build only the tabs the user can access
        self.tabs = {}
        tab_classes = {
            "dashboard": DashboardTab,
            "billing":   BillingTab,
            "stock":     StockTab,
            "sales":     SalesTab,
            "credits":   CreditsTab,
            "suppliers": SuppliersTab,
            "reports":   ReportsTab,
            "profits":   ProfitsTab,
            "daily":     DailyBillsTab,
        }
        for key, cls in tab_classes.items():
            if key in user_perms:
                self.tabs[key] = cls(self.content, self.db, self, self.user)
        if self.user["role"] == "admin":
            self.tabs["admin"] = AdminTab(self.content, self.db, self, self.user)

    def show_tab(self, key):
        for tab in self.tabs.values(): tab.pack_forget()
        if key in self.tabs:
            self.tabs[key].pack(fill="both", expand=True)
            self.tabs[key].refresh()
        for k, btn in self.nav_btns.items():
            btn.configure(fg_color=ACCENT if k == key else "transparent")

    def _logout(self):
        if messagebox.askyesno("Logout", "Log out and return to the login screen?"):
            self.destroy()
            main()   # restart the app (shows login again)


# ══════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════
def main():
    db    = Database()
    login = LoginWindow(db)
    login.mainloop()

    # If user closed the login window without logging in → exit
    if not login.logged_user:
        return

    app = ShopEaseApp(db, login.logged_user)
    app.mainloop()


if __name__ == "__main__":
    main()
