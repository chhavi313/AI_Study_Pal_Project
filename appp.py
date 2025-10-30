from flask import Flask, render_template, request, send_file, redirect, url_for
import io
import csv
import pandas as pd
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize, sent_tokenize
from collections import Counter
import os
import json
import datetime

# Ensure NLTK resources exist (downloads once at runtime)
nltk_data_dir = os.path.join(os.path.dirname(__file__), "nltk_data")
os.makedirs(nltk_data_dir, exist_ok=True)
nltk.data.path.append(nltk_data_dir)
try:
    stopwords.words("english")
except:
    nltk.download("punkt", download_dir=nltk_data_dir)
    nltk.download("stopwords", download_dir=nltk_data_dir)

app = Flask(__name__)

# --- Minimal question bank (expand later) ---
QUESTION_BANK = {
    "math": [
        {"q": "What is 2+2?", "options": ["3","4","5","6"], "answer": "4", "difficulty":"easy"},
        {"q": "What is derivative of x^2?", "options":["2x","x","x^2","2"], "answer":"2x", "difficulty":"medium"},
        {"q": "Integral of 1/x dx is?", "options":["ln|x| + C","x + C","1/x + C","e^x + C"], "answer":"ln|x| + C", "difficulty":"medium"}
    ],
    "cs": [
        {"q": "Which data structure uses FIFO?", "options":["Stack","Queue","Tree","Graph"], "answer":"Queue", "difficulty":"easy"},
        {"q": "What does HTTP stand for?", "options":["HyperText Transfer Protocol","Hyperlink Transfer Protocol","HighText Transfer Protocol","HyperText Translate Protocol"], "answer":"HyperText Transfer Protocol", "difficulty":"easy"}
    ],
    "english": [
        {"q": "Choose the correct past tense of 'go'.", "options":["goed","went","gone","goes"], "answer":"went", "difficulty":"easy"}
    ]
}

# --- Study plan generator (simple) ---
def generate_study_plan(subject: str, total_hours: int):
    days = min(7, max(1, total_hours // 1))  # up to 7 days schedule
    # Simple split: divide hours into sessions
    sessions = []
    remaining = total_hours
    for d in range(1, days+1):
        hrs = max(1, remaining // (days - d + 1))
        sessions.append({"day": f"Day {d}", "hours": int(hrs), "focus": f"{subject} - topic {d}"})
        remaining -= hrs
    # If leftover, add to last
    if remaining > 0:
        sessions[-1]["hours"] += remaining
    return sessions

# --- Simple quiz generator (random-ish) ---
def generate_quiz(subject: str, count=5, difficulty=None):
    bank = QUESTION_BANK.get(subject.lower(), [])
    # simple filter by difficulty if provided
    if difficulty:
        bank = [q for q in bank if q.get("difficulty")==difficulty]
    # if not enough questions, just repeat or fall back to all
    if not bank:
        bank = [q for qs in QUESTION_BANK.values() for q in qs]
    # pick up to count (simple deterministic selection)
    quiz = bank[:count]
    return quiz

# --- Basic summarizer: pick top sentences by word-frequency scores ---
def summarize_text(text: str, max_sentences=2):
    if not text or len(text.strip()) < 30:
        return text
    sents = sent_tokenize(text)
    words = [w.lower() for w in word_tokenize(text) if w.isalpha()]
    stops = set(stopwords.words("english"))
    words = [w for w in words if w not in stops]
    freq = Counter(words)
    # score each sentence
    sent_scores = []
    for sent in sents:
        score = 0
        for w in word_tokenize(sent.lower()):
            if w.isalpha():
                score += freq.get(w, 0)
        sent_scores.append((score, sent))
    # choose top sentences in original order
    top = sorted(sent_scores, key=lambda x: x[0], reverse=True)[:max_sentences]
    # preserve original order:
    chosen = [s for _, s in sorted(top, key=lambda x: sents.index(x[1]))]
    return " ".join(chosen)

# --- Keyword extraction / tips ---
def extract_tips(text: str, topk=5):
    words = [w.lower() for w in word_tokenize(text) if w.isalpha()]
    stops = set(stopwords.words("english"))
    words = [w for w in words if w not in stops]
    freq = Counter(words)
    keywords = [w for w,_ in freq.most_common(topk)]
    tips = [f"Review the keyword: '{k}' daily for 10 minutes." for k in keywords]
    return keywords, tips

@app.route("/", methods=["GET"])
def home():
    return render_template("index.html")

@app.route("/generate", methods=["POST"])
def generate():
    subject = request.form.get("subject", "General")
    hours = int(request.form.get("hours", "3"))
    sample_text = request.form.get("sample_text", "")
    difficulty = request.form.get("difficulty", "")

    plan = generate_study_plan(subject, hours)
    quiz = generate_quiz(subject, count=5, difficulty=(difficulty or None))
    summary = summarize_text(sample_text or f"This is a placeholder description about {subject}. Add your notes here to summarize.")
    keywords, tips = extract_tips(sample_text or f"{subject} important topics: basics, practice, examples.")

    # Save CSV to memory for download link
    df = pd.DataFrame(plan)
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    csv_str = csv_buffer.getvalue()

    # store results temporarily in session-like file (simple approach)
    # For simplicity, we return data directly to template and provide a download route that regenerates CSV.
    return render_template("results.html",
                           subject=subject, hours=hours,
                           plan=plan, quiz=quiz, summary=summary,
                           keywords=keywords, tips=tips)

@app.route("/download_schedule")
def download_schedule():
    # simple demo schedule
    subject = request.args.get("subject", "General")
    hours = int(request.args.get("hours", 4))
    plan = generate_study_plan(subject, hours)
    df = pd.DataFrame(plan)
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    filename = f"study_schedule_{subject}_{datetime.datetime.now().strftime('%Y%m%d%H%M')}.csv"
    return send_file(buf, as_attachment=True, attachment_filename=filename, mimetype="text/csv")

if __name__ == "__main__":
    app.run(debug=True)
