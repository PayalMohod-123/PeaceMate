from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from pymongo import MongoClient
from dotenv import load_dotenv
import google.generativeai as genai
import os
import pyttsx3
import re
import threading
from langdetect import detect

# ---------- ENV ----------
load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "peace-secret")

# ---------- MONGO ----------
client = MongoClient(os.getenv("MONGO_URI"))
db = client.peacemate
users = db.users

# ---------- GEMINI ----------
API_KEYS = os.getenv("GOOGLE_API_KEYS").split(",")
key_index = 0

def get_model():
    global key_index
    genai.configure(api_key=API_KEYS[key_index].strip())
    key_index = (key_index + 1) % len(API_KEYS)
    return genai.GenerativeModel("gemini-2.5-flash")

# ---------- OFFLINE TTS ----------
tts_engine = pyttsx3.init()
tts_engine.setProperty('rate', 150)
tts_engine.setProperty('volume', 1.0)
voices = tts_engine.getProperty('voices')
tts_engine.setProperty('voice', voices[0].id)

def speak_text_async(text, lang='en'):
    """Speak text in a thread, emojis removed"""
    def run():
        # Remove emojis
        clean_text = re.sub(r'([\U00010000-\U0010FFFF]|[\u2600-\u27BF])', '', text)
        # Pick voice based on language if available
        if lang.startswith("hi"):
            for v in voices:
                if "Hindi" in v.name:
                    tts_engine.setProperty('voice', v.id)
                    break
        elif lang.startswith("mr"):
            for v in voices:
                if "Marathi" in v.name:
                    tts_engine.setProperty('voice', v.id)
                    break
        else:
            tts_engine.setProperty('voice', voices[0].id)

        tts_engine.say(clean_text)
        tts_engine.runAndWait()
    threading.Thread(target=run).start()

# ---------- HOME ----------
@app.route("/")
def index():
    if "user" in session:
        return render_template(
            "index.html",
            username=session["user"],
            age_group=session["age_group"]
        )
    return redirect(url_for("login"))

# ---------- SIGNUP ----------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        data = request.form

        name = data.get("name", "").strip()
        email = data.get("email", "").lower().strip()
        password = data.get("password")
        confirm = data.get("confirm_password")
        age_group = data.get("age_group")

        email_pattern = r'^[a-z0-9._%+-]+@(gmail|yahoo|outlook)\.com$'
        if not re.match(email_pattern, email):
            flash("❌ Enter a valid email (gmail / yahoo / outlook only)")
            return redirect("/signup")

        allowed_age_groups = ["13-17", "18-22", "23-30", "30+"]
        if age_group not in allowed_age_groups:
            flash("❌ Please select a valid age group")
            return redirect("/signup")

        if password != confirm:
            flash("❌ Passwords do not match")
            return redirect("/signup")

        if users.find_one({"email": email}):
            flash("❌ Email already exists")
            return redirect("/signup")

        users.insert_one({
            "name": name,
            "email": email,
            "password": generate_password_hash(password),
            "age_group": age_group
        })

        flash("Signup successful 🌸 Please login")
        return redirect("/login")

    return render_template("signup.html")

# ---------- LOGIN ----------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].lower().strip()
        password = request.form["password"]

        user = users.find_one({"email": email})
        if user and check_password_hash(user["password"], password):
            session["user"] = user["name"]
            session["age_group"] = user["age_group"]
            return redirect("/")

        flash("❌ Invalid email or password")

    return render_template("login.html")

# ---------- LOGOUT ----------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ---------- CHAT ----------
@app.route("/chat", methods=["POST"])
def chat():
    if "user" not in session:
        return jsonify({"reply": "Please login first 😔"})

    data = request.get_json()
    user_msg = data.get("message", "").strip()
    is_voice = data.get("isVoice", False)
    age = session.get("age_group", "18-22")

    if not user_msg:
        return jsonify({"reply": "Say something 🌸 I’m listening."})

    # Language detection
    SUPPORTED_LANGS = ["en", "hi", "mr", "pa", "rj"]
    try:
        if len(user_msg) < 5:
            lang_code = "en"
        else:
            detected = detect(user_msg)
            lang_code = detected if detected in SUPPORTED_LANGS else "en"
    except:
        lang_code = "en"

    # Age-based tone
    if age == "13-17":
        tone = "Playful, supportive, simple, fun emojis 😄🌸✨"
    elif age == "18-22":
        tone = "Empathetic, friendly, encouraging 💪🌸😊"
    elif age == "23-30":
        tone = "Calm, motivating, supportive 🌟💖"
    else:
        tone = "Warm, caring, emotionally supportive 💖🌿"

    prompt = f"""
You are PeaceMate, a friendly mental-health chatbot.

User age group: {age}
User language: {lang_code}

Rules:
- Reply like a supportive friend
- {tone}
- 2–3 sentences only
- Age-appropriate advice
- Respond ONLY in English, Hindi, Marathi, Punjabi, or Marwadi
- If unsure, respond in English
- Focus on emotions, stress, life balance

User message:
{user_msg}

PeaceMate reply:
"""

    try:
        model = get_model()
        response = model.generate_content(prompt)
        reply_text = response.text.strip()
    except:
        reply_text = "I’m here for you 🌸 Please try again."

    if is_voice:
        speak_text_async(reply_text, lang=lang_code)

    return jsonify({"reply": reply_text, "lang": lang_code})

# ---------- RUN ----------
if __name__ == "__main__":
    app.run(debug=True)
