import os
import json
import tempfile
import yt_dlp
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Supported video/audio file extensions
ALLOWED_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4a", ".wav", ".mp3"}


# ──────────────────────────────────────────
# 1. EXTRACT AUDIO FROM LOCAL VIDEO FILE
# ──────────────────────────────────────────
def extract_audio(video_path: str, output_path: str = "temp_audio.mp3") -> str:
    """Extract audio using FFmpeg directly — works with .mov, .mp4, .avi etc."""
    try:
        import subprocess
        command = [
            "ffmpeg", "-y",           # overwrite output
            "-i", video_path,         # input file
            "-vn",                    # no video
            "-acodec", "libmp3lame",  # mp3 codec
            "-q:a", "2",              # good quality
            output_path               # output file
        ]
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        if result.returncode != 0:
            raise Exception(result.stderr.decode())
        print(f"✅ Audio extracted: {output_path}")
        return output_path
    except FileNotFoundError:
        raise Exception(
            "FFmpeg not found! Install it with: winget install ffmpeg"
        )
    except Exception as e:
        raise Exception(f"Audio extraction failed: {str(e)}")

# ──────────────────────────────────────────
# 2. DOWNLOAD AUDIO FROM YOUTUBE URL
# ──────────────────────────────────────────
def download_youtube_audio(url: str, output_dir: str) -> str:
    """
    Download audio from a YouTube URL using yt-dlp.
    Returns path to the downloaded mp3 file.
    Requires ffmpeg installed on the system.
    """
    output_path = os.path.join(output_dir, "yt_audio.mp3")

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(output_dir, "yt_audio.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "128",
        }],
    }

    print(f"⏳ Downloading YouTube audio: {url}")
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        title = info.get("title", "Unknown")
        duration = info.get("duration", 0)

    print(f"✅ Downloaded: '{title}' ({duration}s)")

    if not os.path.exists(output_path):
        raise Exception("YouTube audio download failed — file not found after download.")

    return output_path


# ──────────────────────────────────────────
# 3. TRANSCRIBE AUDIO USING GROQ WHISPER
# ──────────────────────────────────────────
def transcribe_audio(audio_path: str) -> str:
    """
    Transcribe audio using Groq Whisper API (free, ultra-fast).
    Max file size: 25 MB
    """
    print("⏳ Transcribing audio with Groq Whisper...")

    # Check file size (Groq limit: 25 MB)
    file_size_mb = os.path.getsize(audio_path) / (1024 * 1024)
    if file_size_mb > 25:
        raise Exception(
            f"Audio file is {file_size_mb:.1f} MB — Groq Whisper limit is 25 MB. "
            "Please use a shorter video (under ~30 minutes)."
        )

    with open(audio_path, "rb") as audio_file:
        transcription = client.audio.transcriptions.create(
            file=(os.path.basename(audio_path), audio_file.read()),
            model="whisper-large-v3",
            response_format="verbose_json",
            language="en",
            temperature=0.0
        )

    transcript = transcription.text.strip()
    if not transcript:
        raise Exception("Empty transcript returned from Groq Whisper.")

    print(f"✅ Transcription complete ({len(transcript.split())} words).")
    return transcript


# ──────────────────────────────────────────
# 4. VALIDATE IF CONTENT IS EDUCATIONAL
# ──────────────────────────────────────────
def validate_educational(transcript: str) -> dict:
    """Use Groq LLaMA3 to check if the transcript is from an educational video."""

    prompt = f"""You are an educational content validator.
Read the transcript below and determine if it is from an EDUCATIONAL video.

Educational content includes: lectures, tutorials, courses, documentaries,
science explanations, history lessons, coding tutorials, math lessons,
language learning, academic content.

NOT educational: music videos, entertainment, movies, gaming, vlogs,
comedy skits, sports commentary, gossip, advertisements.

Transcript (first 500 chars):
{transcript[:500]}

Reply ONLY with valid JSON, no extra text, no markdown fences:
{{
    "is_educational": true or false,
    "subject": "detected subject like Biology, Python, History etc or Unknown",
    "confidence": "high or medium or low",
    "reason": "one sentence explanation"
}}"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=200,
    )

    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    result = json.loads(raw.strip())
    print(f"✅ Validation: {result}")
    return result


# ──────────────────────────────────────────
# 5. SUMMARIZE TRANSCRIPT
# ──────────────────────────────────────────
def summarize_transcript(transcript: str) -> str:
    """Generate a structured summary of the transcript using Groq LLaMA3."""

    prompt = f"""You are an expert educational content summarizer.
Summarize the following video transcript clearly and concisely.

Structure your summary like this:
**Main Topic:** (one line)
**Key Points:**
- Point 1
- Point 2
- Point 3
**Important Takeaways:** (2-3 sentences)

Transcript:
{transcript[:4000]}"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=600,
    )

    summary = response.choices[0].message.content.strip()
    print("✅ Summary generated.")
    return summary


# ──────────────────────────────────────────
# 6. GENERATE QUIZ
# ──────────────────────────────────────────
def generate_quiz(transcript: str, num_questions: int = 5, difficulty: str = "medium") -> list:
    """Generate MCQ quiz questions from a transcript using Groq LLaMA3."""

    difficulty_guide = {
        "easy": "basic recall and recognition of facts",
        "medium": "comprehension and understanding of concepts",
        "hard": "analysis, application, and critical thinking"
    }
    diff_desc = difficulty_guide.get(difficulty.lower(), "comprehension and understanding")

    prompt = f"""You are an expert quiz creator for educational content.
Based on the transcript below, generate exactly {num_questions} multiple choice questions.

Difficulty: {difficulty} — focus on {diff_desc}.

Rules:
- Each question must have exactly 4 options: A, B, C, D
- Only ONE correct answer per question
- Questions must test real understanding, not just memory
- Questions must be strictly based on the transcript content
- Do NOT repeat the same concept across questions

Transcript:
{transcript[:4000]}

Reply ONLY with a valid JSON array. No extra text, no markdown fences:
[
  {{
    "question": "Question text here?",
    "options": {{
      "A": "Option A text",
      "B": "Option B text",
      "C": "Option C text",
      "D": "Option D text"
    }},
    "answer": "A",
    "explanation": "Why this answer is correct."
  }}
]"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
        max_tokens=2000,
    )

    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    quiz = json.loads(raw.strip())
    print(f"✅ Quiz generated: {len(quiz)} questions.")
    return quiz


# ──────────────────────────────────────────
# 7. EVALUATE A SINGLE ANSWER
# ──────────────────────────────────────────
def evaluate_answer(question: str, user_answer: str, correct_answer: str, explanation: str) -> dict:
    is_correct = user_answer.strip().upper() == correct_answer.strip().upper()
    return {
        "is_correct": is_correct,
        "your_answer": user_answer,
        "correct_answer": correct_answer,
        "explanation": explanation,
        "feedback": "✅ Correct!" if is_correct else f"❌ Incorrect. The correct answer is {correct_answer}."
    }


# ──────────────────────────────────────────
# 8. GENERATE QUIZ FROM RAW TEXT
# ──────────────────────────────────────────
def generate_quiz_from_text(text: str, num_questions: int = 5, difficulty: str = "medium") -> dict:
    """Directly generate quiz from pasted text — no video needed."""
    summary = summarize_transcript(text)
    quiz = generate_quiz(text, num_questions, difficulty)
    return {
        "success": True,
        "summary": summary,
        "quiz": quiz,
        "subject": "Text Input",
        "confidence": "high"
    }


# ──────────────────────────────────────────
# 9. PROCESS LOCAL VIDEO FILE (.mov, .mp4, etc.)
# ──────────────────────────────────────────
def process_video(video_path: str, num_questions: int = 5, difficulty: str = "medium") -> dict:
    """Full pipeline: local video file → audio → transcript → validate → summarize → quiz."""
    
    # Use a unique temp file instead of fixed "temp_audio.mp3"
    import uuid
    audio_path = f"temp_audio_{uuid.uuid4().hex}.mp3"

    try:
        extract_audio(video_path, audio_path)
        transcript = transcribe_audio(audio_path)

        validation = validate_educational(transcript)
        if not validation.get("is_educational", False):
            raise Exception(
                f"NON_EDUCATIONAL: This video does not appear to be educational. "
                f"Reason: {validation.get('reason', 'Unknown')}"
            )

        summary = summarize_transcript(transcript)
        quiz = generate_quiz(transcript, num_questions, difficulty)

        return {
            "success": True,
            "transcript": transcript,
            "summary": summary,
            "quiz": quiz,
            "subject": validation.get("subject", "Unknown"),
            "confidence": validation.get("confidence", "medium"),
            "source": "upload"
        }

    except Exception as e:
        raise e

    finally:
        if os.path.exists(audio_path):
            os.remove(audio_path)
            print("🗑️ Temp audio cleaned up.")
''' def process_video(video_path: str, num_questions: int = 5, difficulty: str = "medium") -> dict:
    """Full pipeline: local video file → audio → transcript → validate → summarize → quiz."""
    audio_path = "temp_audio.mp3"

    try:
        extract_audio(video_path, audio_path)
        transcript = transcribe_audio(audio_path)

        validation = validate_educational(transcript)
        if not validation.get("is_educational", False):
            raise Exception(
                f"NON_EDUCATIONAL: This video does not appear to be educational. "
                f"Reason: {validation.get('reason', 'Unknown')}"
            )

        summary = summarize_transcript(transcript)
        quiz = generate_quiz(transcript, num_questions, difficulty)

        return {
            "success": True,
            "transcript": transcript,
            "summary": summary,
            "quiz": quiz,
            "subject": validation.get("subject", "Unknown"),
            "confidence": validation.get("confidence", "medium"),
            "source": "upload"
        }

    except Exception as e:
        raise e

    finally:
        if os.path.exists(audio_path):
            os.remove(audio_path)
            print("🗑️ Temp audio cleaned up.")

'''
# ──────────────────────────────────────────
# 10. PROCESS YOUTUBE URL
# ──────────────────────────────────────────
def process_youtube(url: str, num_questions: int = 5, difficulty: str = "medium") -> dict:
    """Full pipeline: YouTube URL → download audio → transcribe → validate → summarize → quiz."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        audio_path = download_youtube_audio(url, tmp_dir)
        transcript = transcribe_audio(audio_path)

        validation = validate_educational(transcript)
        if not validation.get("is_educational", False):
            raise Exception(
                f"NON_EDUCATIONAL: This video does not appear to be educational. "
                f"Reason: {validation.get('reason', 'Unknown')}"
            )

        summary = summarize_transcript(transcript)
        quiz = generate_quiz(transcript, num_questions, difficulty)

        return {
            "success": True,
            "transcript": transcript,
            "summary": summary,
            "quiz": quiz,
            "subject": validation.get("subject", "Unknown"),
            "confidence": validation.get("confidence", "medium"),
            "source": "youtube"
        }
