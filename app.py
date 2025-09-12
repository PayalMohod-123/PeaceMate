from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import sqlite3
import os
import random
from dotenv import load_dotenv
import google.generativeai as genai
from werkzeug.security import generate_password_hash, check_password_hash

# ---------------- Load Environment ----------------
load_dotenv()

app = Flask(__name__)                                                                                                                                                       
app.secret_key = os.getenv("SECRET_KEY", "fallbacksecret")   # .env me set hoga

# ---------------- Multiple API Keys Setup ----------------
API_KEYS = os.getenv("GOOGLE_API_KEYS", "").split(",")
current_index = 0

def get_api_key():
    """Round-robin se API key return karega"""
    global current_index
    if not API_KEYS or API_KEYS == [""]:
        raise ValueError("❌ No API keys found! Please add GOOGLE_API_KEYS in .env")
    key = API_KEYS[current_index].strip()
    current_index = (current_index + 1) % len(API_KEYS)
    return key

def get_model():
    """Gemini model ko configure karega"""
    api_key = get_api_key()
    genai.configure(api_key=api_key)
    return genai.GenerativeModel("gemini-1.5-flash")

# ---------------- Database Setup ----------------
def init_db():
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ---------------- YouTube Links ----------------
YOUTUBE_LINKS = {
    "relax": [
        "https://www.youtube.com/watch?v=2OEL4P1Rz04",
        "https://www.youtube.com/watch?v=lFcSrYw-ARY",
        "https://www.youtube.com/watch?v=2Jj8XJnx9l4"
    ],
    "study": [
        "https://www.youtube.com/watch?v=WPni755-Krg",
        "https://www.youtube.com/watch?v=mk48xRzuNvA",
        "https://www.youtube.com/watch?v=hHW1oY26kxQ"
    ],
    "motivation": [
        "https://www.youtube.com/watch?v=mgmVOuLgFB0",
        "https://www.youtube.com/watch?v=ZXsQAXx_ao0",
        "https://www.youtube.com/watch?v=wnHW6o8WMas"
    ]
}

# ---------------- Routes ----------------

# Home (Chatbot)
@app.route("/")
def index():
    if "user" in session:
        return render_template("index.html", username=session["user"])
    else:
        return redirect(url_for("login"))

# Signup
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]

        if password != confirm_password:
            flash("Passwords do not match ❌", "danger")
            return redirect(url_for("signup"))

        hashed_password = generate_password_hash(password)

        conn = sqlite3.connect("users.db")
        c = conn.cursor()

        try:
            c.execute("INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
                      (name, email, hashed_password))
            conn.commit()
            flash("Signup successful! Please log in.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Email already exists. Try a different one.", "danger")
        finally:
            conn.close()

    return render_template("signup.html")

# Login
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = sqlite3.connect("users.db")
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE email=?", (email,))
        user = c.fetchone()
        conn.close()

        if user and check_password_hash(user[3], password):
            session["user"] =  user[1]
            flash("Login successful!", "success")
            return redirect(url_for("index"))
        else:
            flash("Invalid email or password.", "danger")

    return render_template("login.html")

# Logout
@app.route("/logout")
def logout():
    session.pop("user", None)
    flash("Logged out successfully.", "info")
    return redirect(url_for("login"))

# Chatbot API
# Chatbot API
@app.route("/chat", methods=["POST"])
def chat():
    if "user" not in session:
        return jsonify({"reply": "Please login first."})

    user_message = request.json.get("message", "").strip()
    if not user_message:
        return jsonify({"reply": "Message cannot be empty."})

    try:
        msg = user_message.lower()

        # 🚫 User ne bola no music
        if any(phrase in msg for phrase in ["don't give music", "no music", "without music", "just talk"]):
            prompt = f"""
            You are PeaceMate, a friendly Stress Relief and Motivation Assistant.  

            - The user does NOT want music or video links.  
            - Reply in **short chat-style lines** with line breaks.  
            - Example:  
              Take a deep breath 🌸  
              Inhale slowly (4 sec)  
              Hold (4 sec)  
              Exhale (4 sec)  
            - Always reply in the same language.  

            User: {user_message}
            PeaceMate:
            """
            model = get_model()
            response = model.generate_content(prompt)
            bot_reply = getattr(response, "text", "").strip().replace("\n", "\n")
            if not bot_reply:
                bot_reply = "💜 I hear you.\nLet’s just talk.\nTell me what’s on your mind."
            return jsonify({"reply": bot_reply})

        # 🎯 Keyword-based replies
        if any(word in msg for word in ["stress", "tense", "pressure"]):
            return jsonify({"reply": "😌 I understand, stress can be heavy.\nTry this:\n1. Close your eyes\n2. Breathe deeply\n3. Count to 4 on inhale & exhale"})
        elif "study" in msg:
            return jsonify({"reply": "📚 Study tip:\n- 25 min focus\n- 5 min break\nRepeat ×4 = Great results 💡"})
        elif any(word in msg for word in ["motivation", "inspire", "boost", "video"]):
            return jsonify({"reply": f"🔥 Stay strong champ!\nWatch this: {random.choice(YOUTUBE_LINKS['motivation'])}"})
        elif any(word in msg for word in ["music", "song"]):
            return jsonify({"reply": f"🎶 Here's something peaceful for you:\n{random.choice(YOUTUBE_LINKS['relax'])}"})

        # 🌸 Default Gemini reply
        prompt = f"""
        You are PeaceMate, a friendly Stress Relief and Motivation Assistant.  

        Rules:
        - Reply in short, simple chat-style lines.  
        - Use **line breaks for steps and lists**.  
        - Keep tone warm and empathetic.  
        - Reply in the same language as the user.  

        User: {user_message}
        PeaceMate:
        """
        model = get_model()
        response = model.generate_content(prompt)
        bot_reply = getattr(response, "text", "").strip().replace("\n", "\n")

        if not bot_reply:
            bot_reply = "🌸 I hear you.\nTake a deep breath.\nInhale... Hold... Exhale..."

    except Exception as e:
        bot_reply = f"⚠️ Error: {str(e)}"

    return jsonify({"reply": bot_reply})

# ---------------- Admin Route (Check Users) ----------------
@app.route("/admin/users")
def admin_users():
    # Sirf tum login karke dekh sako (ek simple check)
    admin_secret = os.getenv("ADMIN_SECRET", "admin123")  # .env me rakho
    if request.args.get("key") != admin_secret:
        return "❌ Unauthorized access"

    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("SELECT id, name, email FROM users")
    users = c.fetchall()
    conn.close()

    html = "<h2>Total Users: {}</h2>".format(len(users))
    html += "<ul>"
    for u in users:
        html += "<li>{} - {} ({})</li>".format(u[0], u[1], u[2])
    html += "</ul>"
    return html



# ---------------- Run ----------------
if __name__ == "__main__":
    app.run(debug=True)                                                                                                                                             HA isme add karo 
