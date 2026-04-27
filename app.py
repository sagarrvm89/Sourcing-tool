from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    logout_user,
    login_required,
    current_user,
)
from werkzeug.security import check_password_hash
import os
import re
import json
import fitz
import requests
from docx import Document

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key")
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5 MB upload limit

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

ALLOWED_EXTENSIONS = {"pdf", "docx", "txt"}


class User(UserMixin):
    def __init__(self, username):
        self.id = username


def get_users():
    users_json = os.environ.get("USERS_JSON", "{}")
    return json.loads(users_json)


@login_manager.user_loader
def load_user(user_id):
    users = get_users()
    if user_id in users:
        return User(user_id)
    return None


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def clean_words(text):
    text = text.lower()
    text = re.sub(r"[^a-zA-Z0-9+#.\- ]", " ", text)

    stop_words = {
        "the", "and", "or", "a", "an", "to", "for", "of", "in", "on", "with",
        "is", "are", "was", "were", "be", "as", "by", "at", "from", "this",
        "that", "you", "your", "we", "our", "they", "their", "will", "can",
        "must", "have", "has", "had", "it", "not", "but", "if", "then",
        "about", "into", "using", "use", "used", "work", "working"
    }

    return [word for word in text.split() if len(word) > 2 and word not in stop_words]


def extract_text_from_file(file):
    filename = file.filename.lower()

    if filename.endswith(".pdf"):
        text = ""
        pdf = fitz.open(stream=file.read(), filetype="pdf")
        for page in pdf:
            text += page.get_text()
        return text

    if filename.endswith(".docx"):
        text = ""
        doc = Document(file)
        for para in doc.paragraphs:
            text += para.text + "\n"
        return text

    if filename.endswith(".txt"):
        return file.read().decode("utf-8", errors="ignore")

    return ""


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        users = get_users()

        if username in users and check_password_hash(users[username], password):
            login_user(User(username))
            return redirect(url_for("home"))

        flash("Invalid username or password")

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def home():
    return render_template("home.html", user=current_user.id)


@app.route("/resume-analyzer")
@login_required
def resume_analyzer():
    return render_template("analyzer.html")


@app.route("/analyze", methods=["POST"])
@login_required
def analyze():
    job_desc = request.form.get("job_desc", "")
    file = request.files.get("resume_file")

    if not file or file.filename == "":
        return "Please upload a resume file."

    if not allowed_file(file.filename):
        return "Invalid file type. Please upload PDF, DOCX, or TXT."

    resume_text = extract_text_from_file(file)

    if not resume_text.strip():
        return "Could not read resume content."

    job_words = set(clean_words(job_desc))
    resume_words = set(clean_words(resume_text))

    matched = sorted(job_words & resume_words)
    missing = sorted(job_words - resume_words)

    score = int((len(matched) / len(job_words)) * 100) if job_words else 0

    return render_template(
        "results.html",
        score=score,
        matched=matched[:50],
        missing=missing[:50]
    )


@app.route("/adzuna-jobs", methods=["GET", "POST"])
@login_required
def adzuna_jobs():
    jobs = []
    error = None

    if request.method == "POST":
        keyword = request.form.get("keyword", "")
        location = request.form.get("location", "")

        app_id = os.environ.get("ADZUNA_APP_ID")
        app_key = os.environ.get("ADZUNA_APP_KEY")

        if not app_id or not app_key:
            error = "Adzuna API credentials are missing."
        else:
            url = "https://api.adzuna.com/v1/api/jobs/us/search/1"

            params = {
                "app_id": app_id,
                "app_key": app_key,
                "what": keyword,
                "where": location,
                "results_per_page": 10,
            }

            try:
                response = requests.get(url, params=params, timeout=20)

                if response.status_code == 200:
                    data = response.json()
                    jobs = data.get("results", [])
                else:
                    error = f"Adzuna API error: {response.status_code}"
            except Exception as e:
                error = f"Adzuna request failed: {str(e)}"

    return render_template("adzuna.html", jobs=jobs, error=error)


@app.route("/jooble-jobs", methods=["GET", "POST"])
@login_required
def jooble_jobs():
    jobs = []
    error = None

    if request.method == "POST":
        keyword = request.form.get("keyword", "")
        location = request.form.get("location", "")

        api_key = os.environ.get("JOOBLE_API_KEY")

        if not api_key:
            error = "Jooble API key is missing."
        else:
            url = f"https://jooble.org/api/{api_key}"

            payload = {
                "keywords": keyword,
                "location": location,
            }

            try:
                response = requests.post(url, json=payload, timeout=20)

                if response.status_code == 200:
                    data = response.json()
                    jobs = data.get("jobs", [])
                else:
                    error = f"Jooble API error: {response.status_code}"
            except Exception as e:
                error = f"Jooble request failed: {str(e)}"

    return render_template("jooble.html", jobs=jobs, error=error)


@app.route("/dice-jobs", methods=["GET", "POST"])
@login_required
def dice_jobs():
    search_url = None

    if request.method == "POST":
        keyword = request.form.get("keyword", "")
        location = request.form.get("location", "")

        search_url = (
            "https://www.dice.com/jobs?"
            f"q={keyword.replace(' ', '+')}&location={location.replace(' ', '+')}"
        )

    return render_template("dice.html", search_url=search_url)


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
