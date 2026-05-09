from flask import Flask, request, jsonify, session
from flask_cors import CORS
import os
from app import (
    process_video,
    process_youtube,
    evaluate_answer,
    generate_quiz_from_text,
    ALLOWED_EXTENSIONS
)
from db import create_user, login_user, save_quiz_result, get_stats, get_quiz_history
 
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "eduquiz-secret-change-in-production")
CORS(app, supports_credentials=True, origins=["http://127.0.0.1:5500", "http://localhost:5500"])
 
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
 
 
# ── HELPERS ──────────────────────────────────────────────────────────────────
def current_user_email():
    """Return logged-in user's email from session, or None."""
    return session.get("user_email")
 
def require_login():
    """Return error response if not logged in, else None."""
    if not current_user_email():
        return jsonify({"success": False, "error": "Not logged in."}), 401
    return None
 
 
# ──────────────────────────────────────────
# ROUTE 1 — Health Check
# ──────────────────────────────────────────
@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "running",
        "message": "EduQuiz API is live! (Powered by Groq 🚀)",
        "logged_in_as": current_user_email()
    }), 200
 
 
# ──────────────────────────────────────────
# ROUTE 2 — Register
# ──────────────────────────────────────────
@app.route("/register", methods=["POST"])
def register():
    """
    JSON body: { "fname", "lname", "email", "password" }
    """
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "No data provided."}), 400
 
    fname    = data.get("fname", "").strip()
    lname    = data.get("lname", "").strip()
    email    = data.get("email", "").strip()
    password = data.get("password", "")
 
    if not all([fname, lname, email, password]):
        return jsonify({"success": False, "error": "All fields are required."}), 400
    if len(password) < 8:
        return jsonify({"success": False, "error": "Password must be at least 8 characters."}), 400
 
    result = create_user(fname, lname, email, password)
    if result["success"]:
        session["user_email"] = result["user"]["email"]
        return jsonify(result), 201
    return jsonify(result), 409
 
 
# ──────────────────────────────────────────
# ROUTE 3 — Login
# ──────────────────────────────────────────
@app.route("/login", methods=["POST"])
def login():
    """
    JSON body: { "email", "password" }
    """
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "No data provided."}), 400
 
    email    = data.get("email", "").strip()
    password = data.get("password", "")
 
    if not email or not password:
        return jsonify({"success": False, "error": "Email and password are required."}), 400
 
    result = login_user(email, password)
    if result["success"]:
        session["user_email"] = result["user"]["email"]
        return jsonify(result), 200
    return jsonify(result), 401
 
 
# ──────────────────────────────────────────
# ROUTE 4 — Logout
# ──────────────────────────────────────────
@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"success": True, "message": "Logged out."}), 200
 
 
# ──────────────────────────────────────────
# ROUTE 5 — Get current user session
# ──────────────────────────────────────────
@app.route("/me", methods=["GET"])
def me():
    """Check if user is logged in and return their profile."""
    from db import get_user
    email = current_user_email()
    if not email:
        return jsonify({"success": False, "logged_in": False}), 200
    user = get_user(email)
    if not user:
        session.clear()
        return jsonify({"success": False, "logged_in": False}), 200
    return jsonify({"success": True, "logged_in": True, "user": user}), 200
 
 
# ──────────────────────────────────────────
# ROUTE 6 — Save Quiz Result
# ──────────────────────────────────────────
@app.route("/save-result", methods=["POST"])
def save_result():
    """
    Save a completed quiz result for the logged-in user.
    JSON body: { "subject", "title", "score", "total" }
    """
    err = require_login()
    if err: return err
 
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "No data provided."}), 400
 
    subject = data.get("subject", "General")
    title   = data.get("title", "Quiz")
    score   = int(data.get("score", 0))
    total   = int(data.get("total", 0))
 
    if total <= 0:
        return jsonify({"success": False, "error": "Invalid quiz data."}), 400
 
    result = save_quiz_result(current_user_email(), subject, title, score, total)
    return jsonify({"success": True, "result": result}), 200
 
 
# ──────────────────────────────────────────
# ROUTE 7 — Get User Stats + History
# ──────────────────────────────────────────
@app.route("/stats", methods=["GET"])
def stats():
    """Return the logged-in user's stats and recent quiz history."""
    err = require_login()
    if err: return err
 
    data = get_stats(current_user_email())
    return jsonify({"success": True, **data}), 200
 
 
# ──────────────────────────────────────────
# ROUTE 8 — Full Quiz History
# ──────────────────────────────────────────
@app.route("/history", methods=["GET"])
def history():
    """Return full quiz history for logged-in user."""
    err = require_login()
    if err: return err
 
    limit   = int(request.args.get("limit", 20))
    results = get_quiz_history(current_user_email(), limit=limit)
    return jsonify({"success": True, "history": results}), 200
 
 
# ──────────────────────────────────────────
# ROUTE 9 — Upload Video File
# ──────────────────────────────────────────
@app.route("/upload-video", methods=["POST"])
def upload_video():
    if "video" not in request.files:
        return jsonify({"success": False, "error": "No video file provided."}), 400
 
    video = request.files['video']
    if video.filename == "":
        return jsonify({"success": False, "error": "No file selected."}), 400
 
    ext = os.path.splitext(video.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({
            "success": False,
            "error": f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        }), 400
 
    num_questions = int(request.form.get("num_questions", 5))
    difficulty    = request.form.get("difficulty", "medium").lower()
    num_questions = max(1, min(20, num_questions))
 
    video_path = os.path.join(UPLOAD_FOLDER, video.filename)
    video.save(video_path)
 
    try:
        result = process_video(video_path, num_questions, difficulty)
        return jsonify(result), 200
    except Exception as e:
        error_msg = str(e)
        if "NON_EDUCATIONAL" in error_msg:
            return jsonify({"success": False, "error": "non_educational",
                            "message": error_msg.replace("NON_EDUCATIONAL: ", "")}), 422
        return jsonify({"success": False, "error": error_msg}), 500
    finally:
        if os.path.exists(video_path):
            os.remove(video_path)
 
 
# ──────────────────────────────────────────
# ROUTE 10 — Generate from YouTube
# ──────────────────────────────────────────
@app.route("/generate-from-youtube", methods=["POST"])
def generate_from_youtube():
    data = request.get_json()
    if not data or not data.get("url", "").strip():
        return jsonify({"success": False, "error": "No YouTube URL provided."}), 400
 
    url = data["url"].strip()
    if "youtube.com" not in url and "youtu.be" not in url:
        return jsonify({"success": False, "error": "Invalid YouTube URL."}), 400
 
    num_questions = int(data.get("num_questions", 5))
    difficulty    = data.get("difficulty", "medium").lower()
    num_questions = max(1, min(20, num_questions))
 
    try:
        result = process_youtube(url, num_questions, difficulty)
        return jsonify(result), 200
    except Exception as e:
        error_msg = str(e)
        if "NON_EDUCATIONAL" in error_msg:
            return jsonify({"success": False, "error": "non_educational",
                            "message": error_msg.replace("NON_EDUCATIONAL: ", "")}), 422
        if "25 MB" in error_msg:
            return jsonify({"success": False, "error": "file_too_large",
                            "message": error_msg}), 413
        return jsonify({"success": False, "error": error_msg}), 500
 
 
# ──────────────────────────────────────────
# ROUTE 11 — Generate from Text
# ──────────────────────────────────────────
@app.route("/generate-from-text", methods=["POST"])
def generate_from_text():
    data = request.get_json()
    if not data or not data.get("text", "").strip():
        return jsonify({"success": False, "error": "No text provided."}), 400
 
    text = data["text"].strip()
    if len(text) < 100:
        return jsonify({"success": False,
                        "error": "Text too short. Please provide at least 100 characters."}), 400
 
    num_questions = int(data.get("num_questions", 5))
    difficulty    = data.get("difficulty", "medium").lower()
    num_questions = max(1, min(20, num_questions))
 
    try:
        result = generate_quiz_from_text(text, num_questions, difficulty)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
 
 
# ──────────────────────────────────────────
# ROUTE 12 — Evaluate Single Answer
# ──────────────────────────────────────────
@app.route("/evaluate", methods=["POST"])
def evaluate():
    data = request.get_json()
    required = ["question", "user_answer", "correct_answer", "explanation"]
    missing = [f for f in required if f not in data]
    if missing:
        return jsonify({"success": False, "error": f"Missing: {', '.join(missing)}"}), 400
 
    result = evaluate_answer(
        data["question"], data["user_answer"],
        data["correct_answer"], data["explanation"]
    )
    return jsonify(result), 200
 
 
# ──────────────────────────────────────────
# RUN
# ──────────────────────────────────────────
if __name__ == "__main__":
    print("🚀 EduQuiz Flask API starting...")
    print("📍 http://localhost:5000")
    print()
    print("Auth routes:")
    print("  POST /register   POST /login   POST /logout   GET /me")
    print("Quiz routes:")
    print("  POST /generate-from-youtube   POST /generate-from-text")
    print("  POST /upload-video")
    print("Data routes:")
    print("  POST /save-result   GET /stats   GET /history")
    app.run(debug=True, port=5000)