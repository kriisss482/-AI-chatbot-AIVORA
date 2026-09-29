import sqlite3
import os
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

DB_PATH = os.path.join(os.path.dirname(__file__), "aivora.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes tables and default admin account if not exists."""
    conn = get_db()
    cursor = conn.cursor()
    
    # Users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'user',
        plan TEXT NOT NULL DEFAULT 'gemini_trial',
        plan_name TEXT NOT NULL DEFAULT 'Gemini 3.8 Flash (14 Days Free)',
        plan_expiry TEXT,
        created_at TEXT NOT NULL
    )
    """)

    # Payments / Subscription requests table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        user_name TEXT NOT NULL,
        user_email TEXT NOT NULL,
        plan_id TEXT NOT NULL,
        plan_name TEXT NOT NULL,
        amount TEXT NOT NULL,
        duration TEXT NOT NULL,
        transaction_id TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        created_at TEXT NOT NULL
    )
    """)

    # Admin Settings table (e.g. for custom QR code, UPI ID, etc.)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)

    # Check if default admin exists
    cursor.execute("SELECT * FROM users WHERE role = 'admin'")
    admin = cursor.fetchone()
    if not admin:
        # Default admin account for Chirag / Admin
        admin_pass_hash = generate_password_hash("admin123")
        now_str = datetime.now().isoformat()
        expiry_str = (datetime.now() + timedelta(days=3650)).isoformat()
        cursor.execute("""
        INSERT INTO users (name, email, password_hash, role, plan, plan_name, plan_expiry, created_at)
        VALUES (?, ?, ?, 'admin', 'aivora_pro', 'Aivora Pro (Admin Lifetime)', ?, ?)
        """, ("Chirag (Admin)", "admin@aivora.ai", admin_pass_hash, expiry_str, now_str))

    # Initialize default settings if missing
    cursor.execute("SELECT * FROM settings WHERE key = 'upi_id'")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO settings (key, value) VALUES ('upi_id', 'aivora@upi')")
        cursor.execute("INSERT INTO settings (key, value) VALUES ('qr_image', '/static/qr_placeholder.svg')")

    conn.commit()
    conn.close()

def create_user(name, email, password):
    """Registers a new user with standard 14-day Gemini 3.8 Flash Free Trial."""
    conn = get_db()
    cursor = conn.cursor()
    email_clean = email.strip().lower()
    
    cursor.execute("SELECT id FROM users WHERE email = ?", (email_clean,))
    if cursor.fetchone():
        conn.close()
        return None, "Email address already registered"

    pwd_hash = generate_password_hash(password)
    now = datetime.now()
    # 14 days free trial for Gemini 3.8 Flash
    trial_expiry = (now + timedelta(days=14)).isoformat()

    cursor.execute("""
    INSERT INTO users (name, email, password_hash, role, plan, plan_name, plan_expiry, created_at)
    VALUES (?, ?, ?, 'user', 'gemini_trial', 'Gemini 3.8 Flash (14 Days Free)', ?, ?)
    """, (name.strip(), email_clean, pwd_hash, trial_expiry, now.isoformat()))
    
    user_id = cursor.lastrowid
    conn.commit()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = dict(cursor.fetchone())
    conn.close()
    return user, None

def authenticate_user(email, password):
    """Authenticates email and password."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email.strip().lower(),))
    user_row = cursor.fetchone()
    conn.close()

    if not user_row:
        return None
    user = dict(user_row)
    if check_password_hash(user["password_hash"], password):
        return user
    return None

def get_user_by_id(user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, email, role, plan, plan_name, plan_expiry, created_at FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def record_payment_request(user_id, user_name, user_email, plan_id, plan_name, amount, duration, transaction_id):
    """Records a new payment submission for admin approval."""
    conn = get_db()
    cursor = conn.cursor()
    now_str = datetime.now().isoformat()
    cursor.execute("""
    INSERT INTO payments (user_id, user_name, user_email, plan_id, plan_name, amount, duration, transaction_id, status, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
    """, (user_id, user_name, user_email, plan_id, plan_name, amount, duration, transaction_id.strip(), now_str))
    payment_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return payment_id

def approve_payment(payment_id):
    """Approves payment and upgrades user's plan."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM payments WHERE id = ?", (payment_id,))
    payment_row = cursor.fetchone()
    if not payment_row:
        conn.close()
        return False, "Payment request not found"
    
    payment = dict(payment_row)
    user_id = payment["user_id"]
    plan_id = payment["plan_id"]
    plan_name = payment["plan_name"]
    duration = payment["duration"]

    # Calculate expiry
    days = 30
    if "3 month" in duration.lower() or "90" in duration:
        days = 90
    elif "2 week" in duration.lower() or "14" in duration:
        days = 14
    
    new_expiry = (datetime.now() + timedelta(days=days)).isoformat()

    # Update user plan
    cursor.execute("""
    UPDATE users SET plan = ?, plan_name = ?, plan_expiry = ? WHERE id = ?
    """, (plan_id, plan_name, new_expiry, user_id))

    # Update payment status
    cursor.execute("UPDATE payments SET status = 'approved' WHERE id = ?", (payment_id,))
    conn.commit()
    conn.close()
    return True, "Plan activated successfully"

def reject_payment(payment_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE payments SET status = 'rejected' WHERE id = ?", (payment_id,))
    conn.commit()
    conn.close()
    return True

def get_all_users():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, email, role, plan, plan_name, plan_expiry, created_at FROM users ORDER BY id DESC")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def get_all_payments():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM payments ORDER BY id DESC")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def get_setting(key, default=""):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row["value"] if row else default

def update_setting(key, value):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()
