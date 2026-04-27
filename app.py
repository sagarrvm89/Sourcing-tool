from flask import Flask, render_template, request
import os

app = Flask(__name__)

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


# ✅ THIS IS THE NEW ANALYZER ROUTE
@app.route("/analyze", methods=["POST"])
def analyze():
    job_desc = request.form.get("job_desc", "")
    resume_text = request.form.get("resume_text", "")

    job_words = set(job_desc.lower().split())
    resume_words = set(resume_text.lower().split())

    matched = job_words & resume_words
    missing = job_words - resume_words

    score = 0
    if len(job_words) > 0:
        score = int(len(matched) / len(job_words) * 100)

    return render_template(
        "results.html",
        score=score,
        matched=", ".join(list(matched)),
        missing=", ".join(list(missing))
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
