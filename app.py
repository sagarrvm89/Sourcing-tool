from flask import Flask, render_template
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

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
