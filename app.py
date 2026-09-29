import os
import sys
import json
import time
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, render_template, request, Response, jsonify, stream_with_context, session, redirect, url_for
from werkzeug.utils import secure_filename
from google import genai
from google.genai import types

import database

# Fix Windows console UTF-8 output
if sys.platform.startswith("win"):
    sys.stdout.reconfigure(encoding="utf-8")

# Load environment variables
load_dotenv()

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.getenv("FLASK_SECRET_KEY", "aivora_secure_secret_key_892348729384729384")

# Initialize database
database.init_db()

# Get API key from .env
api_key = (
    os.getenv("gemini_api_key")
    or os.getenv("GEMINI_API_KEY")
    or os.getenv("GOOGLE_API_KEY")
)

if not api_key:
    print("[WARNING] 'gemini_api_key' .env file me nahi mila! Kripya .env check karein.")

# Initialize Google GenAI client
client = genai.Client(api_key=api_key) if api_key else None

# Aivora System Persona Instruction
AIVORA_SYSTEM_INSTRUCTION = """You are Aivora, a state-of-the-art, hyper-intelligent, and perceptive AI assistant.
You possess deep expertise in coding, science, philosophy, creative writing, daily productivity, mathematics, and problem-solving.

Personality & Guidelines:
1. Identity: Your name is Aivora. Always introduce and refer to yourself as Aivora.
2. Tone & Temperament: Intellectual, articulate, warm, concise when needed, and profoundly insightful. You explain complex concepts with remarkable clarity and elegance.
3. Language: Fluent in both English and Hindi/Hinglish (as well as other languages). Naturally match the language and vibe of the user.
4. Formatting: Use structured Markdown with bold highlights, clean bullet points, and syntax-highlighted code blocks for all code.
"""

# Store chat sessions in memory: session_id -> chat instance
chat_sessions = {}

# Fallback models
FALLBACK_MODELS = [
    "gemma-4-26b-a4b-it",
    "gemma-4-31b-it",
    "gemini-3.8-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.7-flash"
]

# Subscription Plans definition
PLANS = [
    {
        "id": "gemini_trial",
        "name": "Gemini 3.8 Flash (Trial)",
        "price": "$0",
        "amount_usd": 0,
        "duration": "1-2 Weeks (14 Days)",
        "duration_days": 14,
        "model": "gemini-3.8-flash",
        "badge": "Free Starter",
        "features": [
            "14 Days Full Access",
            "Gemini 3.8 Flash Engine",
            "General Conversation & Questions",
            "Basic Coding & Explanations"
        ]
    },
    {
        "id": "aivora_normal",
        "name": "Aivora Normal",
        "price": "$10",
        "amount_usd": 10,
        "duration": "1 Month",
        "duration_days": 30,
        "model": "gemma-4-26b-a4b-it",
        "badge": "Standard",
        "features": [
            "1 Month Full Access",
            "Aivora Turbo Fast Engine",
            "Instant Coding & Problem Solving",
            "Voice Speech & TTS Readout",
            "Unlimited Daily Chats"
        ]
    },
    {
        "id": "aivora_medium",
        "name": "Aivora Medium",
        "price": "$20",
        "amount_usd": 20,
        "duration": "1 Month",
        "duration_days": 30,
        "model": "gemma-4-31b-it",
        "badge": "Popular",
        "features": [
            "1 Month Full Access",
            "Aivora High-Reasoning Model",
            "Advanced Multi-step Problem Solving",
            "Complex Architecture & Code Debugging",
            "Priority Response Speed"
        ]
    },
    {
        "id": "aivora_pro",
        "name": "Aivora Pro",
        "price": "$30",
        "amount_usd": 30,
        "duration": "3 Months",
        "duration_days": 90,
        "model": "gemma-4-31b-it",
        "badge": "Best Value 🔥",
        "features": [
            "3 Months Complete Access (90 Days)",
            "Maximum Pro Intelligence Core",
            "Zero Wait Time & Dedicated Priority",
            "Deep Thought Coding & Long Memory",
            "Save $30 vs monthly plans!"
        ]
    }
]

def get_chat_session(session_id: str, model_name: str = "gemma-4-26b-a4b-it"):
    """Returns an existing chat session or creates a new one with Aivora persona."""
    if not client:
        raise ValueError("Gemini API Client initialize nahi ho paya. API Key missing hai.")
    
    session_key = f"{session_id}_{model_name}"
    if session_key not in chat_sessions:
        chat_sessions[session_key] = client.chats.create(
            model=model_name,
            config=types.GenerateContentConfig(
                system_instruction=AIVORA_SYSTEM_INSTRUCTION
            )
        )
    return chat_sessions[session_key]

# ==========================================
# PUBLIC PAGES & AUTHENTICATION ENDPOINTS
# ==========================================

@app.route("/")
def index():
    """Renders the Aivora AI main chat interface."""
    return render_template("index.html")

@app.route("/api/auth/register", methods=["POST"])
def register():
    """Secure user registration (PBKDF2 SHA-256 hashed password)."""
    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    email = data.get("email", "").strip()
    password = data.get("password", "").strip()

    if not name or not email or not password:
        return jsonify({"error": "Please provide Name, Email, and Password"}), 400

    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400

    user, error = database.create_user(name, email, password)
    if error:
        return jsonify({"error": error}), 400

    session["user_id"] = user["id"]
    session["user_name"] = user["name"]
    session["user_email"] = user["email"]
    session["user_role"] = user["role"]

    return jsonify({"success": True, "user": user})

@app.route("/api/auth/login", methods=["POST"])
def login():
    """Secure user login."""
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip()
    password = data.get("password", "").strip()

    if not email or not password:
        return jsonify({"error": "Email and Password required"}), 400

    user = database.authenticate_user(email, password)
    if not user:
        return jsonify({"error": "Invalid email or password"}), 401

    session["user_id"] = user["id"]
    session["user_name"] = user["name"]
    session["user_email"] = user["email"]
    session["user_role"] = user["role"]

    # Remove password hash before returning
    user.pop("password_hash", None)
    return jsonify({"success": True, "user": user})

@app.route("/api/auth/logout", methods=["POST", "GET"])
def logout():
    """Logs out current user."""
    session.clear()
    return jsonify({"success": True})

@app.route("/api/auth/me", methods=["GET"])
def current_user_info():
    """Returns currently authenticated user with plan and validity status."""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"authenticated": False, "user": None})

    user = database.get_user_by_id(user_id)
    if not user:
        session.clear()
        return jsonify({"authenticated": False, "user": None})

    # Check if plan expired
    is_expired = False
    days_left = 0
    if user.get("plan_expiry"):
        try:
            expiry_dt = datetime.fromisoformat(user["plan_expiry"])
            now_dt = datetime.now()
            delta = expiry_dt - now_dt
            days_left = max(0, delta.days)
            if delta.total_seconds() <= 0:
                is_expired = True
        except Exception:
            pass

    user["is_expired"] = is_expired
    user["days_left"] = days_left
    return jsonify({"authenticated": True, "user": user})

# ==========================================
# PLANS & PAYMENT SCANNER ENDPOINTS
# ==========================================

@app.route("/api/plans", methods=["GET"])
def get_plans():
    """Returns all available subscription plans."""
    return jsonify({"plans": PLANS})

@app.route("/api/payment-info", methods=["GET"])
def payment_info():
    """Returns active QR Code scanner and UPI details for payment."""
    qr_image = database.get_setting("qr_image", "/static/qr_placeholder.svg")
    upi_id = database.get_setting("upi_id", "aivora@upi")
    return jsonify({"qr_image": qr_image, "upi_id": upi_id})

@app.route("/api/subscribe", methods=["POST"])
def submit_subscription():
    """Submits user payment proof (Transaction / UTR reference ID) for Admin verification."""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Please login to subscribe to a plan"}), 401

    user = database.get_user_by_id(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json(silent=True) or {}
    plan_id = data.get("plan_id")
    transaction_id = data.get("transaction_id", "").strip()

    if not plan_id or not transaction_id:
        return jsonify({"error": "Plan selection and Transaction Reference ID are required"}), 400

    target_plan = next((p for p in PLANS if p["id"] == plan_id), None)
    if not target_plan:
        return jsonify({"error": "Invalid plan selected"}), 400

    payment_id = database.record_payment_request(
        user_id=user["id"],
        user_name=user["name"],
        user_email=user["email"],
        plan_id=target_plan["id"],
        plan_name=target_plan["name"],
        amount=target_plan["price"],
        duration=target_plan["duration"],
        transaction_id=transaction_id
    )

    return jsonify({
        "success": True,
        "payment_id": payment_id,
        "message": f"Payment of {target_plan['price']} for {target_plan['name']} submitted! Admin will verify and activate your plan shortly."
    })

# ==========================================
# SECURE ADMIN PANEL
# ==========================================

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    """Admin Login Page."""
    if session.get("user_role") == "admin":
        return redirect(url_for("admin_dashboard"))

    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        user = database.authenticate_user(email, password)
        if user and user["role"] == "admin":
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            session["user_email"] = user["email"]
            session["user_role"] = user["role"]
            return redirect(url_for("admin_dashboard"))
        else:
            error = "Invalid administrator credentials."

    return render_template("admin_login.html", error=error)

@app.route("/admin")
def admin_dashboard():
    """Protected Admin Dashboard."""
    if session.get("user_role") != "admin":
        return redirect(url_for("admin_login"))

    users = database.get_all_users()
    payments = database.get_all_payments()
    qr_image = database.get_setting("qr_image", "/static/qr_placeholder.svg")
    upi_id = database.get_setting("upi_id", "aivora@upi")

    # Calculate total earnings from approved payments
    total_earnings = 0
    for p in payments:
        if p["status"] == "approved":
            # Extract number from '$30' -> 30
            try:
                amt = int(p["amount"].replace("$", "").strip())
                total_earnings += amt
            except Exception:
                pass

    current_user = database.get_user_by_id(session.get("user_id")) or {"name": "Admin"}
    msg = request.args.get("msg")

    return render_template(
        "admin.html",
        users=users,
        payments=payments,
        qr_image=qr_image,
        upi_id=upi_id,
        total_earnings=total_earnings,
        current_user=current_user,
        message=msg
    )

@app.route("/admin/approve-payment/<int:payment_id>", methods=["POST"])
def admin_approve_payment(payment_id):
    """Admin approves payment and activates user's plan."""
    if session.get("user_role") != "admin":
        return redirect(url_for("admin_login"))

    success, msg = database.approve_payment(payment_id)
    return redirect(url_for("admin_dashboard", msg=msg))

@app.route("/admin/reject-payment/<int:payment_id>", methods=["POST"])
def admin_reject_payment(payment_id):
    """Admin rejects invalid payment proof."""
    if session.get("user_role") != "admin":
        return redirect(url_for("admin_login"))

    database.reject_payment(payment_id)
    return redirect(url_for("admin_dashboard", msg="Payment request rejected."))

@app.route("/admin/update-settings", methods=["POST"])
def admin_update_settings():
    """Updates admin UPI ID and uploads custom QR Code image."""
    if session.get("user_role") != "admin":
        return redirect(url_for("admin_login"))

    upi_id = request.form.get("upi_id", "").strip()
    if upi_id:
        database.update_setting("upi_id", upi_id)

    # Handle QR code image file upload
    if "qr_file" in request.files:
        file = request.files["qr_file"]
        if file and file.filename != "":
            filename = secure_filename(f"custom_qr_{int(time.time())}.png")
            filepath = os.path.join(app.static_folder, filename)
            file.save(filepath)
            database.update_setting("qr_image", f"/static/{filename}")

    return redirect(url_for("admin_dashboard", msg="Payment QR settings saved successfully!"))

@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))

# ==========================================
# CHAT API ENDPOINT (STREAMING SSE)
# ==========================================

@app.route("/api/chat", methods=["POST"])
def chat():
    """Handles chat messages with Server-Sent Events (SSE) streaming."""
    data = request.get_json(silent=True) or {}
    message = data.get("message", "").strip()
    session_id = data.get("session_id", "default")
    requested_model = data.get("model", "gemma-4-26b-a4b-it")

    if not message:
        return jsonify({"error": "Message khali nahi ho sakta"}), 400

    if not client:
        return jsonify({"error": "Gemini API key missing hai. .env file me gemini_api_key check karein."}), 500

    # User plan validation
    user_id = session.get("user_id")
    if user_id:
        user = database.get_user_by_id(user_id)
        if user and user.get("plan_expiry"):
            try:
                expiry_dt = datetime.fromisoformat(user["plan_expiry"])
                if datetime.now() > expiry_dt:
                    return jsonify({
                        "error": f"Aapka plan ({user['plan_name']}) expire ho chuka hai. Kripya pricing section me jakar naya plan activate karein."
                    }), 403
            except Exception:
                pass

    def generate_stream():
        start_time = time.time()
        token_count = 0
        used_model = requested_model

        models_to_try = [requested_model] + [m for m in FALLBACK_MODELS if m != requested_model]
        response_stream = None
        last_error = None

        for model_candidate in models_to_try:
            try:
                chat_obj = get_chat_session(session_id, model_candidate)
                response_stream = chat_obj.send_message_stream(message)
                used_model = model_candidate
                break
            except Exception as e:
                err_str = str(e)
                last_error = err_str
                if "503" in err_str or "404" in err_str or "429" in err_str:
                    continue
                else:
                    break

        if not response_stream:
            err_msg = f"Aivora Engine Error: {last_error or 'All models unavailable'}"
            yield f"data: {json.dumps({'error': err_msg})}\n\n"
            return

        try:
            for chunk in response_stream:
                if chunk.text:
                    token_count += len(chunk.text.split())
                    yield f"data: {json.dumps({'chunk': chunk.text, 'model': used_model})}\n\n"

            latency_ms = int((time.time() - start_time) * 1000)
            yield f"data: {json.dumps({'done': True, 'latency_ms': latency_ms, 'token_count': token_count, 'model': used_model})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(
        stream_with_context(generate_stream()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )

@app.route("/api/reset", methods=["POST"])
def reset_session():
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id", "default")
    model_name = data.get("model", "gemma-4-26b-a4b-it")
    session_key = f"{session_id}_{model_name}"
    
    if session_key in chat_sessions:
        del chat_sessions[session_key]
    
    return jsonify({"status": "cleared", "session_id": session_id})

if __name__ == "__main__":
    print("=" * 65)
    print("✨ AIVORA // NEXT-GEN AI CONVERSATIONAL PLATFORM ✨")
    print("🌐 User Chat: http://127.0.0.1:5000")
    print("🛡️  Admin Panel: http://127.0.0.1:5000/admin (User: admin@aivora.ai | Pass: admin123)")
    print("=" * 65)
    app.run(debug=True, host="127.0.0.1", port=5000)
