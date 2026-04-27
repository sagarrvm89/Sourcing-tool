from flask import Flask, render_template, request
import os
import re
import fitz  # PyMuPDF
from docx import Document

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5 MB upload limit

ALLOWED_EXTENSIONS = {"pdf", "docx", "txt"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def clean_words(text):
    text = text.lower()
    text = re.sub(r"[^a-zA-Z0-9+#.\- ]", " ", text)
    words = text.split()

    stop_words = {
        "the", "and", "or", "a", "an", "to", "for", "of", "in", "on", "with",
        "is", "are", "was", "were", "be", "as", "by", "at", "from", "this",
        "that", "you", "your", "we", "our", "they", "their", "will", "can",
        "must", "have", "has", "had", "it", "not", "but", "if", "then"
    }

    return [word for word in words if len(word) > 2 and word not in stop_words]


def extract_text_from_file(file):
    filename = file.filename.lower()

    if filename.endswith(".pdf"):
        resume_text = ""
        pdf = fitz.open(stream=file.read(), filetype="pdf")
        for page in pdf:
            resume_text += page.get_text()
        return resume_text

    if filename.endswith(".docx"):
        resume_text = ""
        doc = Document(file)
        for para in doc.paragraphs:
            resume_text += para.text + "\n"
        return resume_text

    if filename.endswith(".txt"):
        return file.read().decode("utf-8", errors="ignore")

    return ""


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/resume-analyzer")
def resume_analyzer():
    return render_template("analyzer.html")


@app.route("/adzuna-jobs")
def adzuna_jobs():
    return render_template("adzuna.html")


@app.route("/jooble-jobs")
def jooble_jobs():
    return render_template("jooble.html")


@app.route("/dice-jobs")
def dice_jobs():
    return render_template("dice.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    job_desc = request.form.get("job_desc", "")
    file = request.files.get("resume_file")

    if not file or file.filename == "":
        return "Please upload a resume file."

    if not allowed_file(file.filename):
        return "Invalid file type. Please upload PDF, DOCX, or TXT."

    resume_text = extract_text_from_file(file)

    if not resume_text.strip():
        return "Could not read resume content. Please try another file."

    job_words = set(clean_words(job_desc))
    resume_words = set(clean_words(resume_text))

    matched = sorted(job_words & resume_words)
    missing = sorted(job_words - resume_words)

    score = 0
    if job_words:
        score = int((len(matched) / len(job_words)) * 100)

    return render_template(
        "results.html",
        score=score,
        matched=matched[:50],
        missing=missing[:50]
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
