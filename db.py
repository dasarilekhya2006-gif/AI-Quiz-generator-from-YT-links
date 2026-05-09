"""
db.py — MongoDB database layer for EduQuiz
==========================================
Collections:
  - users         : email, name, hashed password, joined date
  - quiz_results  : user_email, subject, score, total, pct, date, title
"""

from pymongo import MongoClient, DESCENDING
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone
import os

# ── Connection ──────────────────────────────────────────────────────────────
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME   = os.getenv("MONGO_DB",  "eduquiz")

_client = None

def get_db():
    global _client
    if _client is None:
        _client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    return _client[DB_NAME]


# ── USER FUNCTIONS ───────────────────────────────────────────────────────────

def create_user(fname: str, lname: str, email: str, password: str) -> dict:
    """
    Register a new user.
    Returns {"success": True, "user": {...}} or {"success": False, "error": "..."}
    """
    db = get_db()
    email = email.lower().strip()

    if db.users.find_one({"email": email}):
        return {"success": False, "error": "An account with this email already exists."}

    user = {
        "fname":      fname.strip(),
        "lname":      lname.strip(),
        "email":      email,
        "password":   generate_password_hash(password),
        "joined":     datetime.now(timezone.utc).isoformat(),
        "quiz_count": 0,
        "avg_score":  0.0,
        "best_score": 0,
        "streak":     0,
        "streak_last": None,
    }
    db.users.insert_one(user)
    return {"success": True, "user": _safe_user(user)}


def login_user(email: str, password: str) -> dict:
    """
    Authenticate a user.
    Returns {"success": True, "user": {...}} or {"success": False, "error": "..."}
    """
    db = get_db()
    email = email.lower().strip()
    user = db.users.find_one({"email": email})

    if not user:
        return {"success": False, "error": "No account found with this email."}
    if not check_password_hash(user["password"], password):
        return {"success": False, "error": "Incorrect password."}

    return {"success": True, "user": _safe_user(user)}


def get_user(email: str) -> dict | None:
    """Fetch a user by email (without password)."""
    db = get_db()
    user = db.users.find_one({"email": email.lower().strip()})
    return _safe_user(user) if user else None


def _safe_user(user: dict) -> dict:
    """Strip sensitive fields before sending to client."""
    return {
        "fname":      user.get("fname", ""),
        "lname":      user.get("lname", ""),
        "email":      user.get("email", ""),
        "joined":     user.get("joined", ""),
        "quiz_count": user.get("quiz_count", 0),
        "avg_score":  user.get("avg_score", 0.0),
        "best_score": user.get("best_score", 0),
        "streak":     user.get("streak", 0),
    }


# ── QUIZ RESULT FUNCTIONS ────────────────────────────────────────────────────

def save_quiz_result(email: str, subject: str, title: str, score: int, total: int) -> dict:
    """
    Save a completed quiz result and update user stats.
    Returns the saved result document.
    """
    db = get_db()
    email = email.lower().strip()
    pct = round((score / total) * 100, 1) if total > 0 else 0

    result = {
        "user_email": email,
        "subject":    subject or "General",
        "title":      title or "Quiz",
        "score":      score,
        "total":      total,
        "pct":        pct,
        "date":       datetime.now(timezone.utc).isoformat(),
    }
    db.quiz_results.insert_one(result)

    # Update user aggregate stats
    all_results = list(db.quiz_results.find({"user_email": email}))
    quiz_count  = len(all_results)
    avg_score   = round(sum(r["pct"] for r in all_results) / quiz_count, 1)
    best_score  = max(r["pct"] for r in all_results)

    # Streak logic
    user = db.users.find_one({"email": email}) or {}
    streak      = user.get("streak", 0)
    streak_last = user.get("streak_last")
    today       = datetime.now(timezone.utc).date().isoformat()

    if streak_last == today:
        pass  # already played today, keep streak
    elif streak_last == _yesterday():
        streak += 1
    else:
        streak = 1

    db.users.update_one(
        {"email": email},
        {"$set": {
            "quiz_count":   quiz_count,
            "avg_score":    avg_score,
            "best_score":   best_score,
            "streak":       streak,
            "streak_last":  today,
        }}
    )

    return {k: v for k, v in result.items() if k != "_id"}


def get_quiz_history(email: str, limit: int = 20) -> list:
    """Return the most recent quiz results for a user."""
    db = get_db()
    results = db.quiz_results.find(
        {"user_email": email.lower().strip()},
        {"_id": 0}
    ).sort("date", DESCENDING).limit(limit)
    return list(results)


def get_stats(email: str) -> dict:
    """Return full stats for a user (profile + recent history)."""
    user    = get_user(email)
    history = get_quiz_history(email, limit=5)
    return {
        "user":    user,
        "history": history,
    }


# ── HELPERS ──────────────────────────────────────────────────────────────────

def _yesterday() -> str:
    from datetime import timedelta
    return (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
