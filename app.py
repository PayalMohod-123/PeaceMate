from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from pymongo import MongoClient
from bson.objectid import ObjectId
import os, random
from dotenv import load_dotenv
import google.generativeai as genai
from werkzeug.security import generate_password_hash, check_password_hash

# ---------------- Load Environment ----------------
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "fallbacksecret")

# ---------------- MongoDB Setup ----------------
mongo_uri = os.getenv("MONGO_URI")
client = MongoClient(mongo_uri)
db = client["PeaceMateDB"]  # apne project ka DB
users_collection = db["users"]

# ---------------- Multiple API Keys Setup ----------------
API_KEYS = os.getenv("GOOGLE_API_KEYS", "").split(",")
current_index = 0

def get_api_key():
    global current_index
    if not API_KEYS or API_KEYS == [""]:
        raise ValueError("❌ No API keys found! Please add GOOGLE_API_KEYS in .env")
    key = API_KEYS[current_index].strip()
    current_index = (current_index + 1) % len(API_KEYS)
    return key

def get_model():
    api_key = get_api_key()
    genai.configure(api_key=api_key)
    return genai.GenerativeModel("gemini-1.5-flash")

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

        # MongoDB insert
        if users_collection.find_one({"email": email}):
            flash("Email already exists. Try a different one.", "danger")
            return redirect(url_for("signup"))

        users_collection.insert_one({
            "name": name,
            "email": email,
            "password": hashed_password
        })

        flash("Signup successful! Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("signup.html")

# Login
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        user = users_collection.find_one({"email": email})

        if user and check_password_hash(user["password"], password):
            session["user"] = user["name"]
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
@app.route("/chat", methods=["POST"])
def chat():
    if "user" not in session:
        return jsonify({"reply": "Please login first."})

    user_message = request.json.get("message", "").strip()
    if not user_message:
        return jsonify({"reply": "Message cannot be empty."})

    try:
        msg = user_message.lower()

        if any(phrase in msg for phrase in ["don't give music", "no music", "without music", "just talk"]):
            prompt = f"""
            You are PeaceMate, a friendly Stress Relief and Motivation Assistant.  
            User: {user_message}
            PeaceMate:
            """
            model = get_model()
            response = model.generate_content(prompt)
            bot_reply = getattr(response, "text", "").strip()
            if not bot_reply:
                bot_reply = "💜 I hear you.\nLet’s just talk.\nTell me what’s on your mind."
            return jsonify({"reply": bot_reply})

        if any(word in msg for word in ["stress", "tense", "pressure"]):
            return jsonify({"reply": "😌 Stress relief:\n1. Close your eyes\n2. Breathe deeply\n3. Count to 4 while inhaling & exhaling"})
        elif "study" in msg:
            return jsonify({"reply": "📚 Study tip:\n- 25 min focus\n- 5 min break\nRepeat ×4 = Great results 💡"})
        elif any(word in msg for word in ["motivation", "inspire", "boost", "video"]):
            return jsonify({"reply": f"🔥 Stay strong!\nWatch this: {random.choice(YOUTUBE_LINKS['motivation'])}"})
        elif any(word in msg for word in ["music", "song"]):
            return jsonify({"reply": f"🎶 Here's something peaceful:\n{random.choice(YOUTUBE_LINKS['relax'])}"})

        prompt = f"""
        You are PeaceMate, a friendly Stress Relief and Motivation Assistant.  
        User: {user_message}
        PeaceMate:
        """
        model = get_model()
        response = model.generate_content(prompt)
        bot_reply = getattr(response, "text", "").strip()

        if not bot_reply:
            bot_reply = "🌸 I hear you.\nTake a deep breath.\nInhale... Hold... Exhale..."

    except Exception as e:
        bot_reply = f"⚠️ Error: {str(e)}"

    return jsonify({"reply": bot_reply})

# ---------------- Admin Route (Check Users) ----------------
@app.route("/admin/users")
def admin_users():
    admin_secret = os.getenv("ADMIN_SECRET", "admin123")
    if request.args.get("key") != admin_secret:
        return "❌ Unauthorized access"

    users = list(users_collection.find({}, {"name": 1, "email": 1}))
    html = "<h2>Total Users: {}</h2>".format(len(users))
    html += "<ul>"
    for u in users:
        html += f"<li>{u.get('name')} ({u.get('email')})</li>"
    html += "</ul>"
    return html

# ---------------- Run ----------------
if __name__ == "__main__":
    app.run(debug=True)
