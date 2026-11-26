import os
import re
from datetime import datetime
from functools import wraps

from dotenv import load_dotenv
load_dotenv()

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    abort
)
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from google import genai

from config import Config
from db import db
from models import User, Resume, CareerReport
from utils.resume_parser import extract_resume_text


# --------------------------------------------------
# FLASK APP SETUP
# --------------------------------------------------

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)


# --------------------------------------------------
# GEMINI AI CLIENT
# --------------------------------------------------

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)


# --------------------------------------------------
# UPLOAD SETTINGS
# --------------------------------------------------

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {"pdf", "docx"}


def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


# --------------------------------------------------
# AUTH HELPERS & CONTEXT
# --------------------------------------------------

EMAIL_REGEX = r"^[\w\.-]+@[\w\.-]+\.\w+$"


def is_valid_email(email):
    return bool(re.match(EMAIL_REGEX, email.strip()))


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


@app.context_processor
def inject_current_user():
    user_id = session.get("user_id")
    current_user = None
    if user_id:
        current_user = db.session.get(User, user_id)
    return dict(current_user=current_user)


# --------------------------------------------------
# 1. HOME / LANDING PAGE
# --------------------------------------------------

@app.route("/")
def home():
    return render_template("index.html")


# --------------------------------------------------
# 2. SIGNUP
# --------------------------------------------------

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        # Validation
        if not name or not email or not password or not confirm_password:
            flash("All fields are required. Please fill in all information.", "danger")
            return render_template("signup.html", name=name, email=email)

        if not is_valid_email(email):
            flash("Please provide a valid email address.", "danger")
            return render_template("signup.html", name=name, email=email)

        if len(password) < 6:
            flash("Password must be at least 6 characters long.", "danger")
            return render_template("signup.html", name=name, email=email)

        if password != confirm_password:
            flash("Passwords do not match. Please re-enter.", "danger")
            return render_template("signup.html", name=name, email=email)

        # Unique email check
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash("An account with this email already exists. Please log in.", "danger")
            return redirect(url_for("login"))

        # Password hashing & user creation
        hashed_password = generate_password_hash(password)
        new_user = User(
            name=name,
            email=email,
            password=hashed_password
        )

        db.session.add(new_user)
        db.session.commit()

        flash("Account created successfully! Please log in with your credentials.", "success")
        return redirect(url_for("login"))

    return render_template("signup.html")


# --------------------------------------------------
# 3. LOGIN
# --------------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            flash("Please enter both email and password.", "danger")
            return render_template("login.html", email=email)

        user = User.query.filter_by(email=email).first()

        # Check password hash (with legacy plain-text migration fallback)
        if user:
            is_valid = check_password_hash(user.password, password)
            if not is_valid and user.password == password:
                # Upgrade legacy unhashed password to hashed
                user.password = generate_password_hash(password)
                db.session.commit()
                is_valid = True

            if is_valid:
                session["user_id"] = user.id
                flash(f"Welcome back, {user.name}!", "success")
                return redirect(url_for("dashboard"))

        flash("Invalid email or password. Please check your credentials.", "danger")
        return render_template("login.html", email=email)

    return render_template("login.html")


# --------------------------------------------------
# 4. LOGOUT
# --------------------------------------------------

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out successfully.", "info")
    return redirect(url_for("home"))


# --------------------------------------------------
# 5. USER DASHBOARD
# --------------------------------------------------

@app.route("/dashboard")
@login_required
def dashboard():
    user = db.session.get(User, session["user_id"])
    if not user:
        session.clear()
        return redirect(url_for("login"))

    # Fetch only this logged-in user's records
    resumes = Resume.query.filter_by(user_id=user.id).order_by(Resume.created_at.desc()).all()
    reports = CareerReport.query.filter_by(user_id=user.id).order_by(CareerReport.created_at.desc()).all()

    has_resume = len(resumes) > 0
    latest_resume = resumes[0] if resumes else None
    latest_report = reports[0] if reports else None

    return render_template(
        "dashboard.html",
        user=user,
        has_resume=has_resume,
        latest_resume=latest_resume,
        reports_count=len(reports),
        latest_report=latest_report,
        reports=reports
    )


# --------------------------------------------------
# 6. RESUME UPLOAD + AI ANALYSIS
# --------------------------------------------------

@app.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    user = db.session.get(User, session["user_id"])

    if request.method == "POST":
        resume_file = request.files.get("resume")

        if not resume_file or resume_file.filename == "":
            flash("Please select a resume file to upload.", "danger")
            return redirect(url_for("upload"))

        if not allowed_file(resume_file.filename):
            flash("Only PDF (.pdf) and Word (.docx) files are allowed.", "danger")
            return redirect(url_for("upload"))

        # Save resume file securely
        filename = secure_filename(resume_file.filename)
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        saved_filename = f"user_{user.id}_{timestamp}_{filename}"

        file_path = os.path.join(
            app.config["UPLOAD_FOLDER"],
            saved_filename
        )
        resume_file.save(file_path)

        # Extract text
        resume_text = extract_resume_text(file_path)

        if not resume_text.strip():
            flash("Could not extract text from this resume. Please ensure the document is not an image or corrupted.", "danger")
            return redirect(url_for("upload"))

        # Save Resume to database for current user
        resume = Resume(
            user_id=user.id,
            filename=filename,
            resume_text=resume_text
        )
        db.session.add(resume)
        db.session.commit()

        # Prompt for AI analysis
        prompt = f"""
You are an AI Career Copilot.

Analyze the following candidate resume for {user.name}.

RESUME:

{resume_text[:15000]}

Create a clear and practical career report.

Use exactly these sections:

1. Candidate Summary
2. Detected Skills
3. Strengths
4. Missing Skills
5. Suitable Job Roles
6. Skill Gap Analysis
7. Learning Roadmap
8. Recommended Projects
9. Interview Questions
10. Resume Improvement Suggestions
11. Motivation Speech

Use simple language.
Give practical recommendations suitable for a college student preparing for placements.
Make the answer well structured and easy to understand.
"""

        # AI Request
        try:
            response = client.models.generate_content(
                model="gemini-flash-lite-latest",
                contents=prompt
            )
            ai_result = response.text
        except Exception as error:
            flash("AI Analysis Error: " + str(error), "danger")
            return redirect(url_for("upload"))

        # Save Career Report to database
        report = CareerReport(
            user_id=user.id,
            resume_id=resume.id,
            skills="Generated by AI",
            skill_gaps="Generated by AI",
            recommendations=ai_result,
            interview_questions=ai_result,
            roadmap=ai_result
        )

        db.session.add(report)
        db.session.commit()

        flash("Resume analyzed successfully!", "success")
        return redirect(url_for("view_report", report_id=report.id))

    return render_template("upload.html", user=user)


# --------------------------------------------------
# 7. VIEW SPECIFIC REPORT (OWNERSHIP CHECKED)
# --------------------------------------------------

@app.route("/report/<int:report_id>")
@login_required
def view_report(report_id):
    report = db.session.get(CareerReport, report_id)
    if not report:
        abort(404)

    # Ownership security check
    if report.user_id != session["user_id"]:
        flash("Unauthorized access. You can only view your own career reports.", "danger")
        return redirect(url_for("dashboard"))

    user = db.session.get(User, session["user_id"])
    return render_template(
        "report.html",
        report=report,
        user=user
    )


# --------------------------------------------------
# RUN APPLICATION
# --------------------------------------------------

if __name__ == "__main__":
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    with app.app_context():
        db.create_all()

    app.run(debug=True)