"""
test.py — Quick local test for EduQuiz backend (Groq-powered)
Run: python test.py
Requires: GROQ_API_KEY in your .env file
"""
from app import generate_quiz, summarize_transcript, generate_quiz_from_text

# ── Fake educational transcript ──────────────────────────────────────────────
transcript = """
Python is a high-level, interpreted programming language known for its
simplicity and readability. Created by Guido van Rossum and released in 1991,
it emphasizes code readability with its notable use of significant indentation.

Variables in Python are dynamically typed, meaning you don't need to declare
their type. For example: x = 5 creates an integer, name = "Alice" creates a string.

Lists are ordered, mutable collections: fruits = ["apple", "banana", "cherry"].
Dictionaries store key-value pairs: person = {"name": "Alice", "age": 30}.

Functions are defined with the def keyword:
    def greet(name):
        return f"Hello, {name}!"

Python supports object-oriented programming through classes:
    class Dog:
        def __init__(self, name):
            self.name = name
        def bark(self):
            return "Woof!"

Control flow uses if/elif/else statements and for/while loops.
Python's standard library is extensive, and the ecosystem includes popular
packages like NumPy, Pandas, Flask, and Django.
"""

print("=" * 60)
print("TEST 1: SUMMARIZE TRANSCRIPT")
print("=" * 60)
summary = summarize_transcript(transcript)
print(summary)

print("\n" + "=" * 60)
print("TEST 2: GENERATE QUIZ (3 questions, easy)")
print("=" * 60)
quiz = generate_quiz(transcript, num_questions=3, difficulty="easy")
for i, q in enumerate(quiz):
    print(f"\nQ{i+1}: {q['question']}")
    for key, val in q["options"].items():
        marker = " ✓" if key == q["answer"] else ""
        print(f"  {key}: {val}{marker}")
    print(f"  Explanation: {q['explanation']}")

print("\n" + "=" * 60)
print("TEST 3: GENERATE QUIZ FROM TEXT (end-to-end)")
print("=" * 60)
result = generate_quiz_from_text(transcript, num_questions=2, difficulty="medium")
print(f"Subject: {result['subject']}")
print(f"Questions generated: {len(result['quiz'])}")
print("✅ generate_quiz_from_text works!")

print("\n✅ All tests passed!")
