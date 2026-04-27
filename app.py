from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from io import BytesIO
from urllib.parse import quote_plus
import os
import re
import json
import pandas as pd
import requests
import fitz
from docx import Document
from playwright.sync_api import sync_playwright

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key")
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

ALLOWED_EXTENSIONS = {"pdf", "docx", "txt"}

DEFAULT_KEYWORDS = [
    "automation test engineer",
    "sdet",
    "qa automation",
    "devops",
    "vmware",
    "azure",
]

DEFAULT_LOCATION = "United States"


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


def create_excel_download(jobs, filename):
    output = BytesIO()
    df = pd.DataFrame(jobs)

    if df.empty:
        df = pd.DataFrame([{"Message": "No jobs found"}])

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Jobs")

    output.seek(0)

    return send_file(
        output,
        download_name=filename,
        as_attachment=True,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


def search_adzuna_jobs():
    jobs = []

    app_id = os.environ.get("ADZUNA_APP_ID")
    app_key = os.environ.get("ADZUNA_APP_KEY")

    if not app_id or not app_key:
        return jobs

    pages = 3
    max_days_old = 7

    for keyword in DEFAULT_KEYWORDS:
        for page in range(1, pages + 1):
            url = f"https://api.adzuna.com/v1/api/jobs/us/search/{page}"

            params = {
                "app_id": app_id.strip(),
                "app_key": app_key.strip(),
                "what": keyword,
                "where": DEFAULT_LOCATION,
                "results_per_page": 50,
                "max_days_old": max_days_old,
                "sort_by": "date",
                "content-type": "application/json"
            }

            try:
                response = requests.get(url, params=params, timeout=20)
                if response.status_code != 200:
                    continue

                data = response.json()

                for job in data.get("results", []):
                    jobs.append({
                        "Job Title": job.get("title", ""),
                        "Company": job.get("company", {}).get("display_name", ""),
                        "Location": job.get("location", {}).get("display_name", ""),
                        "Posted Date": job.get("created", ""),
                        "Source": "Adzuna",
                        "Job URL": job.get("redirect_url", "")
                    })

            except Exception:
                continue

    df = pd.DataFrame(jobs)
    if not df.empty:
        df.drop_duplicates(subset=["Job URL"], inplace=True)
        jobs = df.to_dict("records")

    return jobs


def search_jooble_jobs():
    jobs = []

    api_key = os.environ.get("JOOBLE_API_KEY")

    if not api_key:
        return jobs

    keywords = "engineer OR developer OR software OR analyst"
    pages = 5

    for page in range(1, pages + 1):
        url = f"https://jooble.org/api/{api_key}"

        payload = {
            "keywords": keywords,
            "location": DEFAULT_LOCATION,
            "page": page
        }

        try:
            response = requests.post(url, json=payload, timeout=20)

            if response.status_code != 200:
                continue

            data = response.json()

            for job in data.get("jobs", []):
                jobs.append({
                    "Job Title": job.get("title", ""),
                    "Company": job.get("company", ""),
                    "Location": job.get("location", ""),
                    "Posted Date": job.get("updated", ""),
                    "Source": "Jooble",
                    "Job URL": job.get("link", "")
                })

        except Exception:
            continue

    df = pd.DataFrame(jobs)
    if not df.empty:
        df.drop_duplicates(subset=["Job URL"], inplace=True)
        jobs = df.to_dict("records")

    return jobs


def scrape_dice_jobs(keyword="technology", location="United States", total_pages=5):
    results = []
    seen_urls = set()

    keyword_q = quote_plus(keyword)
    location_q = quote_plus(location)

    base_url = (
        f"https://www.dice.com/jobs?q={keyword_q}"
        f"&location={location_q}&radius=30&radiusUnit=mi&page="
    )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        for page_number in range(1, total_pages + 1):
            page_url = base_url + str(page_number)

            page.goto(page_url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(3000)

            for _ in range(3):
                page.mouse.wheel(0, 1500)
                page.wait_for_timeout(700)

            links = page.locator("a[href*='/job-detail/']").all()

            for link in links:
                try:
                    title = " ".join(link.inner_text().split())
                    url = link.get_attribute("href")

                    if not title or title.lower() in ["apply now", "easy apply"]:
                        continue

                    if url.startswith("/"):
                        url = "https://www.dice.com" + url

                    if url in seen_urls:
                        continue

                    seen_urls.add(url)

                    results.append({
                        "Job Title": title,
                        "Company": "",
                        "Location": location,
                        "Posted Date": "",
                        "Source": "Dice",
                        "Job URL": url
                    })

                except Exception:
                    continue

        browser.close()

    return results


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


@app.route("/adzuna-jobs")
@login_required
def adzuna_jobs():
    jobs = search_adzuna_jobs()
    return render_template("adzuna.html", jobs=jobs, error=None)


@app.route("/download-adzuna")
@login_required
def download_adzuna():
    jobs = search_adzuna_jobs()
    return create_excel_download(jobs, "adzuna_jobs_last_7_days.xlsx")


@app.route("/jooble-jobs")
@login_required
def jooble_jobs():
    jobs = search_jooble_jobs()
    return render_template("jooble.html", jobs=jobs, error=None)


@app.route("/download-jooble")
@login_required
def download_jooble():
    jobs = search_jooble_jobs()
    return create_excel_download(jobs, "jooble_tech_jobs.xlsx")


@app.route("/dice-jobs", methods=["GET", "POST"])
@login_required
def dice_jobs():
    jobs = []
    error = None

    if request.method == "POST":
        keyword = request.form.get("keyword", "technology").strip()
        location = request.form.get("location", "United States").strip()
        total_pages = int(request.form.get("total_pages", 5))

        if total_pages > 5:
            total_pages = 5

        try:
            jobs = scrape_dice_jobs(keyword, location, total_pages)
        except Exception as e:
            error = f"Dice scraping failed: {str(e)}"

    return render_template("dice.html", jobs=jobs, error=error)


@app.route("/download-dice")
@login_required
def download_dice():
    jobs = scrape_dice_jobs("technology", "United States", 5)
    return create_excel_download(jobs, "dice_jobs.xlsx")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
