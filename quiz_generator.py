"""
Quiz Generator Backend
======================
Supports:
  - Local video files (.mov, .mp4, etc.)
  - YouTube links

Pipeline:
  1. Extract audio  → Whisper transcription
  2. Extract frames → base64 encode key frames
  3. Send transcript + frames to Claude API
  4. Claude returns MCQ, True/False, Fill-in-the-Blank questions as JSON

Dependencies (add to requirements.txt):
  anthropic
  openai-whisper
  yt-dlp
  opencv-python
  flask
  moviepy
"""

import os
import cv2
import base64
import json
import tempfile
import whisper
import yt_dlp
from pathlib import Path
from moviepy.editor import VideoFileClip
import anthropic

# ─────────────────────────────────────────────
# 1. AUDIO EXTRACTION + TRANSCRIPTION
# ─────────────────────────────────────────────

def extract_audio(video_path: str, output_audio_path: str) -> str:
    """Extract audio track from a local video file."""
    clip = VideoFileClip(video_path)
    clip.audio.write_audiofile(output_audio_path, verbose=False, logger=None)
    clip.close()
    return output_audio_path


def download_youtube_video(url: str, output_dir: str) -> str:
    """Download a YouTube video to output_dir, return local file path."""
    ydl_opts = {
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "outtmpl": os.path.join(output_dir, "%(id)s.%(ext)s"),
        "quiet": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
    return filename


def transcribe_audio(audio_path: str, model_size: str = "base") -> str:
    """Transcribe audio using OpenAI Whisper (runs locally, free)."""
    model = whisper.load_model(model_size)
    result = model.transcribe(audio_path)
    return result["text"]


# ─────────────────────────────────────────────
# 2. FRAME EXTRACTION
# ─────────────────────────────────────────────

def extract_key_frames(video_path: str, num_frames: int = 6) -> list[str]:
    """
    Extract `num_frames` evenly spaced frames from the video.
    Returns a list of base64-encoded JPEG strings.
    """
    cap = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    indices = [int(i * total_frames / num_frames) for i in range(num_frames)]

    b64_frames = []
    for idx in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if not ret:
            continue
        _, buffer = cv2.imencode(".jpg", frame)
        b64 = base64.b64encode(buffer).decode("utf-8")
        b64_frames.append(b64)

    cap.release()
    return b64_frames


# ─────────────────────────────────────────────
# 3. AI QUIZ GENERATION VIA CLAUDE
# ─────────────────────────────────────────────

QUIZ_SYSTEM_PROMPT = """You are an expert quiz creator. 
Given a video transcript and key frames from the video, generate a comprehensive quiz.

Return ONLY valid JSON in this exact format (no extra text):
{
  "title": "Quiz title based on content",
  "questions": [
    {
      "type": "mcq",
      "question": "Question text?",
      "options": ["A) ...", "B) ...", "C) ...", "D) ..."],
      "answer": "A) ...",
      "explanation": "Brief explanation"
    },
    {
      "type": "true_false",
      "question": "Statement to evaluate.",
      "answer": "True",
      "explanation": "Brief explanation"
    },
    {
      "type": "fill_blank",
      "question": "The process of _____ is key to understanding this topic.",
      "answer": "correct word or phrase",
      "explanation": "Brief explanation"
    }
  ]
}

Guidelines:
- Generate a balanced mix: ~50% MCQ, ~25% True/False, ~25% Fill-in-the-blank
- Total questions: as specified by the user (default 10)
- Questions must be directly based on the transcript/video content
- MCQ options should be plausible but clearly distinguishable
- Difficulty should be moderate (not trivial, not overly obscure)
"""


def generate_quiz(
    transcript: str,
    b64_frames: list[str],
    num_questions: int = 10,
    difficulty: str = "medium"
) -> dict:
    """
    Send transcript + frames to Claude and get back a structured quiz.
    Returns parsed JSON dict.
    """
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    # Build the content array: text first, then images
    content = [
        {
            "type": "text",
            "text": (
                f"Generate {num_questions} quiz questions at {difficulty} difficulty "
                f"based on this video content.\n\n"
                f"TRANSCRIPT:\n{transcript}\n\n"
                f"Key frames from the video are attached below."
            )
        }
    ]

    # Add up to 6 frames as vision inputs
    for b64 in b64_frames[:6]:
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": b64
            }
        })

    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=4096,
        system=QUIZ_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": content}]
    )

    raw = response.content[0].text.strip()

    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    return json.loads(raw)


# ─────────────────────────────────────────────
# 4. MAIN ORCHESTRATOR
# ─────────────────────────────────────────────

def generate_quiz_from_video(
    source: str,           # local file path OR YouTube URL
    num_questions: int = 10,
    difficulty: str = "medium",  # "easy" | "medium" | "hard"
    whisper_model: str = "base"  # "tiny" | "base" | "small" | "medium" | "large"
) -> dict:
    """
    Full pipeline: video source → quiz JSON.

    Args:
        source:         Path to .mov/.mp4 file or a YouTube URL
        num_questions:  How many questions to generate
        difficulty:     Quiz difficulty level
        whisper_model:  Whisper model size (larger = more accurate but slower)

    Returns:
        dict with keys: title, questions (list of question dicts)
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        is_youtube = source.startswith("http://") or source.startswith("https://")

        # Step 1: Get local video path
        if is_youtube:
            print("[1/4] Downloading YouTube video...")
            video_path = download_youtube_video(source, tmp_dir)
        else:
            print("[1/4] Using local video file...")
            video_path = source

        # Step 2: Extract audio & transcribe
        print("[2/4] Extracting audio and transcribing...")
        audio_path = os.path.join(tmp_dir, "audio.mp3")
        extract_audio(video_path, audio_path)
        transcript = transcribe_audio(audio_path, model_size=whisper_model)
        print(f"      Transcript length: {len(transcript.split())} words")

        # Step 3: Extract key frames
        print("[3/4] Extracting key frames...")
        frames = extract_key_frames(video_path, num_frames=6)
        print(f"      Extracted {len(frames)} frames")

        # Step 4: Generate quiz via Claude
        print("[4/4] Generating quiz with Claude AI...")
        quiz = generate_quiz(transcript, frames, num_questions, difficulty)
        print(f"      Generated {len(quiz.get('questions', []))} questions")

    return quiz


# ─────────────────────────────────────────────
# 5. FLASK ROUTES (add these to your flask_api.py)
# ─────────────────────────────────────────────

"""
Paste these routes into your existing flask_api.py:

from flask import Flask, request, jsonify
from quiz_generator import generate_quiz_from_video
import os

@app.route('/api/quiz/generate', methods=['POST'])
def api_generate_quiz():
    data = request.get_json()
    
    # YouTube URL or local path
    source      = data.get('source')          # required
    num_q       = data.get('num_questions', 10)
    difficulty  = data.get('difficulty', 'medium')
    
    if not source:
        return jsonify({'error': 'source is required'}), 400
    
    try:
        quiz = generate_quiz_from_video(
            source=source,
            num_questions=num_q,
            difficulty=difficulty
        )
        return jsonify({'success': True, 'quiz': quiz})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/quiz/upload', methods=['POST'])
def api_upload_video():
    \"\"\"Handle .mov / .mp4 file uploads.\"\"\"
    if 'video' not in request.files:
        return jsonify({'error': 'No video file uploaded'}), 400

    file = request.files['video']
    upload_dir = os.path.join(os.getcwd(), 'uploads')
    os.makedirs(upload_dir, exist_ok=True)
    
    save_path = os.path.join(upload_dir, file.filename)
    file.save(save_path)

    num_q      = int(request.form.get('num_questions', 10))
    difficulty = request.form.get('difficulty', 'medium')

    try:
        quiz = generate_quiz_from_video(
            source=save_path,
            num_questions=num_q,
            difficulty=difficulty
        )
        return jsonify({'success': True, 'quiz': quiz})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
"""


# ─────────────────────────────────────────────
# 6. QUICK LOCAL TEST
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    source = sys.argv[1] if len(sys.argv) > 1 else "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    quiz = generate_quiz_from_video(source, num_questions=10, difficulty="medium")

    print("\n" + "=" * 50)
    print(f"QUIZ: {quiz['title']}")
    print("=" * 50)
    for i, q in enumerate(quiz["questions"], 1):
        print(f"\nQ{i} [{q['type'].upper()}]: {q['question']}")
        if q["type"] == "mcq":
            for opt in q["options"]:
                print(f"   {opt}")
        print(f"   ✓ Answer: {q['answer']}")
        print(f"   💡 {q['explanation']}")