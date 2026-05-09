# 🎓 EduQuiz — AI-Powered Quiz Generator

> Transform any educational YouTube video into an intelligent quiz in seconds, powered by Groq AI.

---

## ✨ What It Does

EduQuiz takes a YouTube URL, downloads the audio, transcribes it using **Groq Whisper**, validates it as educational content using **LLaMA 3.3 70B**, and generates a multiple-choice quiz — all in under a minute.

- 🔗 **YouTube URL → Quiz** in one click
- 🛡️ **Edu-Only Guard** — non-educational content is automatically rejected
- 📊 **User Dashboard** — track your scores, streaks, and subject progress
- 🗄️ **MongoDB** — all users and quiz results stored in a real database
- 🌙 **Dark/Light mode** toggle

---

## 🏗️ Project Structure

```
quiz-project/
├── app.py              # Core pipeline — audio extraction, transcription, quiz generation
├── flask_api.py        # Flask REST API — all routes
├── db.py               # MongoDB layer — users, quiz results, stats
├── index.html          # Frontend — single-page app (no framework)
├── requirements.txt    # Python dependencies
├── .env                # API keys (never commit this!)
└── uploads/            # Temp folder for video uploads (auto-created)
```

---

## ⚙️ Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Vanilla HTML/CSS/JS (single page) |
| Backend | Python + Flask |
| AI — Transcription | Groq Whisper Large v3 |
| AI — Quiz Generation | Groq LLaMA 3.3 70B |
| Database | MongoDB (local) |
| YouTube Download | yt-dlp |
| Audio Processing | FFmpeg |

---

## 🚀 Getting Started

### Prerequisites

- Python 3.10+
- MongoDB installed and running locally
- FFmpeg installed
- A free [Groq API key](https://console.groq.com)

### 1. Clone the repo

```bash
git clone https://github.com/your-username/eduquiz.git
cd eduquiz
```

### 2. Create a virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set up environment variables

Create a `.env` file in the project root:

```env
GROQ_API_KEY=your_groq_api_key_here
SECRET_KEY=any_random_string_here
MONGO_URI=mongodb://localhost:27017
MONGO_DB=eduquiz
```

> Get your free Groq API key at [console.groq.com](https://console.groq.com)

### 5. Start MongoDB

```bash
# Windows (if not running as a service)
mongod --dbpath C:\data\db

# Mac/Linux
mongod
```

### 6. Start the Flask server

```bash
python flask_api.py
```

Server runs at `http://localhost:5000`

### 7. Open the frontend

Open `index.html` with VS Code Live Server (port 5500) or any local server.

---

## 🔌 API Routes

### Auth
| Method | Route | Description |
|---|---|---|
| `POST` | `/register` | Create a new account |
| `POST` | `/login` | Sign in |
| `POST` | `/logout` | Sign out |
| `GET` | `/me` | Get current session user |

### Quiz Generation
| Method | Route | Description |
|---|---|---|
| `POST` | `/generate-from-youtube` | YouTube URL → Quiz |
| `POST` | `/generate-from-text` | Paste text → Quiz |
| `POST` | `/upload-video` | Upload video file → Quiz |

### Data
| Method | Route | Description |
|---|---|---|
| `POST` | `/save-result` | Save a completed quiz result |
| `GET` | `/stats` | Get user stats + recent history |
| `GET` | `/history` | Get full quiz history |

### Example request — Generate from YouTube

```bash
curl -X POST http://localhost:5000/generate-from-youtube \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.youtube.com/watch?v=example",
    "num_questions": 5,
    "difficulty": "medium"
  }'
```

---

## 🗄️ Database Schema

### `users` collection
```json
{
  "fname": "Dasari",
  "lname": "Lekhya",
  "email": "user@example.com",
  "password": "<bcrypt hash>",
  "joined": "2026-05-09T00:00:00Z",
  "quiz_count": 12,
  "avg_score": 78.5,
  "best_score": 100,
  "streak": 7,
  "streak_last": "2026-05-09"
}
```

### `quiz_results` collection
```json
{
  "user_email": "user@example.com",
  "subject": "Computer Science",
  "title": "Quiz — Python Basics",
  "score": 4,
  "total": 5,
  "pct": 80.0,
  "date": "2026-05-09T12:00:00Z"
}
```

---

## 🛡️ Edu-Only Guard

EduQuiz uses **LLaMA 3.3 70B** to validate every video before generating a quiz. Non-educational content (music, movies, gaming, vlogs, entertainment) is automatically rejected with an explanation.

Educational content that passes includes: lectures, tutorials, documentaries, science explanations, history lessons, coding tutorials, math lessons, and academic content.

---

## 📈 User Progression System

| Level | Name | Quizzes Required |
|---|---|---|
| 1 | Beginner | 0+ |
| 2 | Novice | 5+ |
| 3 | Learner | 10+ |
| 4 | Student | 15+ |
| 5 | Scholar | 20+ |
| 6 | Thinker | 25+ |
| 7 | Expert | 30+ |
| 8 | Master | 35+ |
| 9 | Champion | 40+ |
| 10 | Legend | 45+ |

### Achievements
| Badge | Requirement |
|---|---|
| 🏆 First Quiz | Complete 1 quiz |
| 🔥 7-Day Streak | 7 consecutive days |
| 💯 Perfect Score | Score 100% on a quiz |
| 📚 Multi-Subject | Quiz on 3+ subjects |
| 🚀 Speed Learner | Complete 20+ quizzes |
| 🎯 Sharpshooter | Average score ≥ 85% |
| 🌟 Top 10% | Average ≥ 90% with 10+ quizzes |

---

## ⚠️ Important Notes

- **Never commit your `.env` file** — add it to `.gitignore`
- Groq Whisper has a **25 MB audio limit** — videos should be under ~30 minutes
- MongoDB must be running before starting Flask
- The frontend uses cookies for session management — Flask and Live Server must both be running

---

## 📄 .gitignore

Make sure your `.gitignore` includes:

```
.env
venv/
__pycache__/
uploads/
*.pyc
*.mp3
temp_audio*
```

---

## 👩‍💻 Author

**Dasari Lekhya**  
Built with ❤️ using Groq AI, Flask, and MongoDB

---

## 📜 License

MIT License — feel free to use, modify, and share.
Give it star.
