"""
app.py
------
Main Flask application. Contains:
  - Auth routes (register/login/logout) — shared by parents and admins
  - Parent App routes (dashboard, children, timeline, OCR, chatbot)
  - Admin Portal routes (dashboard, children/parents list, reminders, chatbot logs)
  - Shared Vaccine Info page + Parent/ASHA messaging
  - Dropout Prevention (risk scoring + outreach) for ASHA workers and admins
  - In-app notification routes (the "Push" bell icon)

Kept as one flat file (no blueprints) on purpose, so every route is a
short, readable function you can explain individually in a viva.

Run with:  python3 app.py
"""

import os
import time
from datetime import date, timedelta

from dotenv import load_dotenv
load_dotenv()  # reads variables from a local .env file, if present

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from db import run_query, refresh_overdue_statuses
from ocr_utils import extract_text_from_image, guess_vaccine_names
from chatbot_utils import ask_chatbot
from reminders import run_reminder_engine
from regions import REGION_COORDINATES, REGION_NAMES
from vaccine_info import VACCINE_GUIDE, BEFORE_TIPS, AFTER_TIPS
from dropout import get_child_risks, summarize, reminder_text

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-this")

# Brand name shown on every portal (available in all templates).
SITE_NAME = "SmartVax"
SITE_TAGLINE = "AI based Vaccination Tracking and dropout prevention"
app.jinja_env.globals.update(SITE_NAME=SITE_NAME, SITE_TAGLINE=SITE_TAGLINE)

_status_refresh = {"last": 0.0}


@app.before_request
def keep_statuses_fresh():
    """Marks late doses as 'overdue' (at most once every 10 minutes)."""
    if request.endpoint in (None, "static"):
        return
    now = time.time()
    if now - _status_refresh["last"] > 600:
        _status_refresh["last"] = now
        try:
            refresh_overdue_statuses()
        except Exception as error:  # never block a page because of this
            print(f"[app.py] Could not refresh statuses: {error}")

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png"}


# =====================================================================
# SMALL HELPER FUNCTIONS
# =====================================================================

def allowed_file(filename):
    """Only allow image files to be uploaded (OCR scan feature)."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def login_required(view_function):
    """Only lets logged-in users (any role) through."""
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.")
            return redirect(url_for("login"))
        return view_function(*args, **kwargs)
    wrapper.__name__ = view_function.__name__
    return wrapper


def admin_required(view_function):
    """Only lets logged-in ADMINS through — everyone else is bounced out."""
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.")
            return redirect(url_for("login"))
        if session.get("role") != "admin":
            flash("Admin access only.")
            return redirect(url_for("dashboard"))
        return view_function(*args, **kwargs)
    wrapper.__name__ = view_function.__name__
    return wrapper


def worker_required(view_function):
    """Only lets logged-in ASHA WORKERS through."""
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.")
            return redirect(url_for("login"))
        if session.get("role") != "asha":
            flash("ASHA Worker access only.")
            return redirect(url_for("dashboard"))
        return view_function(*args, **kwargs)
    wrapper.__name__ = view_function.__name__
    return wrapper


def calculate_status(due_date, completed_date):
    """Works out whether a vaccine dose is completed, due, or overdue."""
    if completed_date is not None:
        return "completed"
    if due_date < date.today():
        return "overdue"
    return "due"


def create_vaccination_schedule_for_child(child_id, date_of_birth):
    """
    Called once, right after a child is added. Reads every vaccine in
    vaccine_master and creates one vaccination_records row per vaccine,
    with the correct due_date calculated from the child's date of birth.
    This is what makes the "Personalized Vaccine Timeline" automatic.
    """
    vaccines = run_query("SELECT * FROM vaccine_master ORDER BY dose_order", fetch=True)

    for vaccine in vaccines:
        due_date = date_of_birth + timedelta(days=vaccine["due_age_days"])
        status = calculate_status(due_date, None)
        run_query(
            """INSERT INTO vaccination_records (child_id, vaccine_id, due_date, status)
               VALUES (%s, %s, %s, %s)""",
            (child_id, vaccine["vaccine_id"], due_date, status),
        )


@app.context_processor
def inject_notifications():
    """
    Makes 'unread_notification_count' available in EVERY template
    automatically, so the bell icon badge works without repeating this
    query in every single route.
    """
    if "user_id" in session:
        row = run_query(
            "SELECT COUNT(*) AS total FROM notifications WHERE user_id = %s AND is_read = FALSE",
            (session["user_id"],), fetch_one=True,
        )
        msg_row = run_query(
            "SELECT COUNT(*) AS total FROM messages WHERE receiver_id = %s AND is_read = FALSE",
            (session["user_id"],), fetch_one=True,
        )
        return {
            "unread_notification_count": row["total"] if row else 0,
            "unread_message_count": msg_row["total"] if msg_row else 0,
        }
    return {"unread_notification_count": 0, "unread_message_count": 0}


# =====================================================================
# AUTH ROUTES: register / login / logout
# =====================================================================

@app.route("/")
def home():
    if "user_id" in session:
        role = session.get("role")
        if role == "admin":
            return redirect(url_for("admin_dashboard"))
        if role == "asha":
            return redirect(url_for("worker_dashboard"))
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        full_name = request.form["full_name"]
        email = request.form["email"]
        phone = request.form["phone"]
        password = request.form["password"]

        existing_user = run_query(
            "SELECT user_id FROM users WHERE email = %s", (email,), fetch_one=True
        )
        if existing_user:
            flash("An account with that email already exists.")
            return redirect(url_for("register"))

        password_hash = generate_password_hash(password)
        user_id = run_query(
            """INSERT INTO users (full_name, email, password_hash, phone, role)
               VALUES (%s, %s, %s, %s, 'parent')""",
            (full_name, email, password_hash, phone),
        )

        session["user_id"] = user_id
        session["full_name"] = full_name
        session["role"] = "parent"
        flash(f"Account created! Welcome to {SITE_NAME}.")
        return redirect(url_for("dashboard"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        # No role filter here anymore — parents AND admins share this
        # one login form. We branch AFTER checking the password.
        user = run_query("SELECT * FROM users WHERE email = %s", (email,), fetch_one=True)

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["user_id"]
            session["full_name"] = user["full_name"]
            session["role"] = user["role"]

            session["area_sector"] = user.get("area_sector")

            if user["role"] == "admin":
                return redirect(url_for("admin_dashboard"))
            elif user["role"] == "asha":
                return redirect(url_for("worker_dashboard"))
            else:
                return redirect(url_for("dashboard"))

        flash("Invalid email or password.")
        return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# =====================================================================
# NOTIFICATIONS ("Push" bell icon)
# =====================================================================

@app.route("/notifications")
@login_required
def notifications():
    notes = run_query(
        "SELECT * FROM notifications WHERE user_id = %s ORDER BY created_at DESC LIMIT 30",
        (session["user_id"],), fetch=True,
    )
    # Opening the notifications page marks everything as read.
    run_query(
        "UPDATE notifications SET is_read = TRUE WHERE user_id = %s", (session["user_id"],)
    )
    return render_template("notifications.html", notes=notes)


# =====================================================================
# DASHBOARD ("Hello, Priya" home screen) — now with stat cards + chart
# =====================================================================

@app.route("/dashboard")
@login_required
def dashboard():
    parent_id = session["user_id"]

    children = run_query(
        "SELECT * FROM children WHERE parent_id = %s", (parent_id,), fetch=True
    )

    for child in children:
        next_dose = run_query(
            """SELECT vr.due_date, vm.vaccine_name
               FROM vaccination_records vr
               JOIN vaccine_master vm ON vr.vaccine_id = vm.vaccine_id
               WHERE vr.child_id = %s AND vr.status != 'completed'
               ORDER BY vr.due_date ASC LIMIT 1""",
            (child["child_id"],), fetch_one=True,
        )
        child["next_dose"] = next_dose

    upcoming_vaccine = run_query(
        """SELECT vr.due_date, vm.vaccine_name, c.full_name AS child_name,
                  DATEDIFF(vr.due_date, CURDATE()) AS days_left
           FROM vaccination_records vr
           JOIN vaccine_master vm ON vr.vaccine_id = vm.vaccine_id
           JOIN children c ON vr.child_id = c.child_id
           WHERE c.parent_id = %s AND vr.status != 'completed'
           ORDER BY vr.due_date ASC LIMIT 1""",
        (parent_id,), fetch_one=True,
    )

    # Stat cards + doughnut chart data: how many doses (across ALL of
    # this parent's children) are completed / due / overdue.
    status_counts = run_query(
        """SELECT vr.status, COUNT(*) AS total
           FROM vaccination_records vr
           JOIN children c ON vr.child_id = c.child_id
           WHERE c.parent_id = %s
           GROUP BY vr.status""",
        (parent_id,), fetch=True,
    )
    chart_data = {"completed": 0, "due": 0, "overdue": 0}
    for row in status_counts:
        chart_data[row["status"]] = row["total"]

    # Dropout-prevention status per child (shown to parents in friendly words).
    risk_by_child = {r["child_id"]: r for r in get_child_risks(parent_id=parent_id)}
    for child in children:
        child["risk"] = risk_by_child.get(child["child_id"])

    return render_template(
        "dashboard.html",
        children=children,
        upcoming_vaccine=upcoming_vaccine,
        full_name=session["full_name"],
        chart_data=chart_data,
    )


# =====================================================================
# CHILD MANAGEMENT
# =====================================================================

@app.route("/children/add", methods=["GET", "POST"])
@login_required
def add_child():
    if request.method == "POST":
        full_name = request.form["full_name"]
        dob = request.form["date_of_birth"]  # comes in as "YYYY-MM-DD"
        gender = request.form["gender"]
        region = request.form["region"]

        child_id = run_query(
            """INSERT INTO children (parent_id, full_name, date_of_birth, gender, region)
               VALUES (%s, %s, %s, %s, %s)""",
            (session["user_id"], full_name, dob, gender, region),
        )

        dob_date = date.fromisoformat(dob)
        create_vaccination_schedule_for_child(child_id, dob_date)

        flash(f"{full_name} added, and their vaccine timeline is ready!")
        return redirect(url_for("dashboard"))

    return render_template("add_child.html", regions=REGION_NAMES)


@app.route("/children/<int:child_id>/timeline")
@login_required
def timeline(child_id):
    child = run_query(
        "SELECT * FROM children WHERE child_id = %s AND parent_id = %s",
        (child_id, session["user_id"]), fetch_one=True,
    )
    if not child:
        flash("Child not found.")
        return redirect(url_for("dashboard"))

    records = run_query(
        """SELECT vr.*, vm.vaccine_name, vm.description
           FROM vaccination_records vr
           JOIN vaccine_master vm ON vr.vaccine_id = vm.vaccine_id
           WHERE vr.child_id = %s
           ORDER BY vr.due_date ASC""",
        (child_id,), fetch=True,
    )

    return render_template("timeline.html", child=child, records=records)


# NOTE: There is deliberately NO parent route to mark a dose as given.
# Only ASHA workers can edit a child's vaccination record (see the
# /worker/... routes below), so the record stays trustworthy.


# =====================================================================
# OCR SCAN — upload a photo of a vaccination card
# =====================================================================

@app.route("/children/<int:child_id>/ocr-scan", methods=["GET", "POST"])
@login_required
def ocr_scan(child_id):
    child = run_query(
        "SELECT * FROM children WHERE child_id = %s AND parent_id = %s",
        (child_id, session["user_id"]), fetch_one=True,
    )
    if not child:
        flash("Child not found.")
        return redirect(url_for("dashboard"))

    extracted_text = None
    matched_vaccines = None

    if request.method == "POST":
        uploaded_file = request.files.get("card_image")

        if uploaded_file and allowed_file(uploaded_file.filename):
            filename = secure_filename(uploaded_file.filename)
            unique_name = f"{child_id}_{int(date.today().strftime('%Y%m%d'))}_{filename}"
            save_path = os.path.join(app.config["UPLOAD_FOLDER"], unique_name)
            uploaded_file.save(save_path)

            extracted_text = extract_text_from_image(save_path)

            all_vaccine_names = [
                v["vaccine_name"]
                for v in run_query("SELECT vaccine_name FROM vaccine_master", fetch=True)
            ]
            matched_vaccines = guess_vaccine_names(extracted_text, all_vaccine_names)

            run_query(
                """INSERT INTO ocr_uploads (child_id, image_path, extracted_text)
                   VALUES (%s, %s, %s)""",
                (child_id, save_path, extracted_text),
            )
        else:
            flash("Please upload a JPG or PNG image.")

    return render_template(
        "ocr_upload.html",
        child=child,
        extracted_text=extracted_text,
        matched_vaccines=matched_vaccines,
    )


# =====================================================================
# CHATBOT
# =====================================================================

@app.route("/chatbot", methods=["GET", "POST"])
@login_required
def chatbot():
    answer = None
    question = None

    if request.method == "POST":
        question = request.form["question"]
        answer = ask_chatbot(question)

        run_query(
            "INSERT INTO chatbot_logs (user_id, question, answer) VALUES (%s, %s, %s)",
            (session["user_id"], question, answer),
        )

    history = run_query(
        """SELECT question, answer, created_at FROM chatbot_logs
           WHERE user_id = %s ORDER BY created_at DESC LIMIT 10""",
        (session["user_id"],), fetch=True,
    )
    history.reverse()

    return render_template("chatbot.html", history=history)


# =====================================================================
# ADMIN PORTAL
# =====================================================================

@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    total_parents = run_query(
        "SELECT COUNT(*) AS total FROM users WHERE role = 'parent'", fetch_one=True
    )["total"]
    total_children = run_query("SELECT COUNT(*) AS total FROM children", fetch_one=True)["total"]

    status_counts = run_query(
        "SELECT status, COUNT(*) AS total FROM vaccination_records GROUP BY status", fetch=True
    )
    chart_data = {"completed": 0, "due": 0, "overdue": 0}
    for row in status_counts:
        chart_data[row["status"]] = row["total"]

    total_doses = sum(chart_data.values())
    coverage_percent = round((chart_data["completed"] / total_doses) * 100) if total_doses else 0

    # Which vaccines have the most overdue doses — for the bar chart.
    overdue_by_vaccine = run_query(
        """SELECT vm.vaccine_name, COUNT(*) AS total
           FROM vaccination_records vr
           JOIN vaccine_master vm ON vr.vaccine_id = vm.vaccine_id
           WHERE vr.status = 'overdue'
           GROUP BY vm.vaccine_name
           ORDER BY total DESC LIMIT 6""",
        fetch=True,
    )

    recent_children = run_query(
        """SELECT c.full_name AS child_name, c.created_at, u.full_name AS parent_name
           FROM children c JOIN users u ON c.parent_id = u.user_id
           ORDER BY c.created_at DESC LIMIT 5""",
        fetch=True,
    )

    # --- Region-wise breakdown: powers both the "Coverage by Region"
    # cards and the Leaflet map markers. ---
    region_rows = run_query(
        """SELECT c.region,
                  COUNT(DISTINCT c.child_id) AS child_count,
                  SUM(CASE WHEN vr.status = 'completed' THEN 1 ELSE 0 END) AS completed_count,
                  SUM(CASE WHEN vr.status = 'overdue' THEN 1 ELSE 0 END) AS overdue_count,
                  COUNT(vr.record_id) AS total_doses
           FROM children c
           LEFT JOIN vaccination_records vr ON vr.child_id = c.child_id
           GROUP BY c.region""",
        fetch=True,
    )

    region_stats = []
    for row in region_rows:
        coords = REGION_COORDINATES.get(row["region"])
        if not coords:
            continue  # skip any legacy/unknown region name gracefully
        coverage = round((row["completed_count"] / row["total_doses"]) * 100) if row["total_doses"] else 0
        region_stats.append({
            "name": row["region"],
            "lat": coords["lat"],
            "lng": coords["lng"],
            "child_count": row["child_count"],
            "overdue_count": row["overdue_count"] or 0,
            "coverage_percent": coverage,
        })
    region_stats.sort(key=lambda r: r["child_count"], reverse=True)

    risk_summary = summarize(get_child_risks())

    return render_template(
        "admin/dashboard.html",
        risk_summary=risk_summary,
        total_parents=total_parents,
        total_children=total_children,
        chart_data=chart_data,
        coverage_percent=coverage_percent,
        high_risk_count=chart_data["overdue"],
        overdue_by_vaccine=overdue_by_vaccine,
        recent_children=recent_children,
        region_stats=region_stats,
        active_page="dashboard",
    )


@app.route("/admin/children")
@admin_required
def admin_children():
    rows = run_query(
        """SELECT c.child_id, c.full_name AS child_name, c.date_of_birth, c.region,
                  u.full_name AS parent_name, u.email AS parent_email, u.phone AS parent_phone,
                  SUM(CASE WHEN vr.status = 'completed' THEN 1 ELSE 0 END) AS completed_count,
                  SUM(CASE WHEN vr.status = 'due' THEN 1 ELSE 0 END) AS due_count,
                  SUM(CASE WHEN vr.status = 'overdue' THEN 1 ELSE 0 END) AS overdue_count,
                  COUNT(vr.record_id) AS total_count
           FROM children c
           JOIN users u ON c.parent_id = u.user_id
           LEFT JOIN vaccination_records vr ON vr.child_id = c.child_id
           GROUP BY c.child_id, c.full_name, c.date_of_birth, c.region, u.full_name, u.email, u.phone
           ORDER BY overdue_count DESC, c.full_name ASC""",
        fetch=True,
    )
    return render_template("admin/children.html", children=rows, active_page="children")


@app.route("/admin/send-reminders", methods=["POST"])
@admin_required
def admin_send_reminders():
    """Manually triggers the same reminder engine that a cron job would run."""
    sent_count = run_reminder_engine()
    flash(f"Reminder run complete — {sent_count} email(s) sent.")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/chatbot-logs")
@admin_required
def admin_chatbot_logs():
    logs = run_query(
        """SELECT cl.question, cl.answer, cl.created_at, u.full_name AS parent_name
           FROM chatbot_logs cl JOIN users u ON cl.user_id = u.user_id
           ORDER BY cl.created_at DESC LIMIT 50""",
        fetch=True,
    )
    return render_template("admin/chatbot_logs.html", logs=logs, active_page="chatbot")


@app.route("/admin/workers", methods=["GET", "POST"])
@admin_required
def admin_workers():
    """Admin creates ASHA Worker logins here — this is the ONLY way a
    worker account gets created, same idea as create_admin.py for admins."""
    if request.method == "POST":
        full_name = request.form["full_name"]
        email = request.form["email"]
        phone = request.form["phone"]
        area_sector = request.form["area_sector"]
        password = request.form["password"]

        existing_user = run_query(
            "SELECT user_id FROM users WHERE email = %s", (email,), fetch_one=True
        )
        if existing_user:
            flash("A user with that email already exists.")
            return redirect(url_for("admin_workers"))

        password_hash = generate_password_hash(password)
        run_query(
            """INSERT INTO users (full_name, email, password_hash, phone, role, area_sector)
               VALUES (%s, %s, %s, %s, 'asha', %s)""",
            (full_name, email, password_hash, phone, area_sector),
        )
        flash(f"ASHA Worker account created for {full_name} ({area_sector}).")
        return redirect(url_for("admin_workers"))

    workers = run_query(
        "SELECT full_name, email, phone, area_sector, created_at FROM users WHERE role = 'asha' ORDER BY full_name",
        fetch=True,
    )
    return render_template(
        "admin/workers.html", workers=workers, regions=REGION_NAMES, active_page="workers"
    )


# =====================================================================
# ASHA WORKER PORTAL
# =====================================================================

@app.route("/worker/dashboard")
@worker_required
def worker_dashboard():
    area = session.get("area_sector")

    status_counts = run_query(
        """SELECT vr.status, COUNT(*) AS total
           FROM vaccination_records vr
           JOIN children c ON vr.child_id = c.child_id
           WHERE c.region = %s
           GROUP BY vr.status""",
        (area,), fetch=True,
    )
    stats = {"completed": 0, "due": 0, "overdue": 0}
    for row in status_counts:
        stats[row["status"]] = row["total"]

    total_children = run_query(
        "SELECT COUNT(*) AS total FROM children WHERE region = %s", (area,), fetch_one=True
    )["total"]

    # A short preview list on the dashboard itself (full list on /worker/defaulters)
    preview = run_query(
        """SELECT c.child_id, c.full_name AS child_name, vr.due_date, vr.status, vm.vaccine_name
           FROM vaccination_records vr
           JOIN children c ON vr.child_id = c.child_id
           JOIN vaccine_master vm ON vr.vaccine_id = vm.vaccine_id
           WHERE c.region = %s AND vr.status IN ('due', 'overdue')
           ORDER BY vr.due_date ASC LIMIT 5""",
        (area,), fetch=True,
    )

    risks = get_child_risks(region=area)
    top_risks = [r for r in risks if r["level"] != "low"][:3]

    return render_template(
        "worker/dashboard.html",
        risk_summary=summarize(risks),
        top_risks=top_risks,
        area=area,
        stats=stats,
        total_children=total_children,
        preview=preview,
    )


@app.route("/worker/defaulters")
@worker_required
def worker_defaulters():
    area = session.get("area_sector")
    filter_type = request.args.get("filter", "all")  # all / due / overdue

    query = """SELECT vr.record_id, c.child_id, c.full_name AS child_name, c.date_of_birth,
                      vr.due_date, vr.status, vm.vaccine_name,
                      u.full_name AS parent_name, u.phone AS parent_phone
               FROM vaccination_records vr
               JOIN children c ON vr.child_id = c.child_id
               JOIN vaccine_master vm ON vr.vaccine_id = vm.vaccine_id
               JOIN users u ON c.parent_id = u.user_id
               WHERE c.region = %s AND vr.status IN ('due', 'overdue')"""
    params = [area]

    if filter_type in ("due", "overdue"):
        query += " AND vr.status = %s"
        params.append(filter_type)

    query += " ORDER BY vr.due_date ASC"
    records = run_query(query, tuple(params), fetch=True)

    return render_template(
        "worker/defaulters.html", records=records, area=area, filter_type=filter_type
    )


@app.route("/worker/records/<int:record_id>/mark-visit", methods=["POST"])
@worker_required
def worker_mark_visit(record_id):
    """
    An ASHA worker's version of 'mark complete'. Checks that the child
    actually belongs to the worker's own area before allowing the
    update, so a worker can never edit another region's records just
    by guessing a record_id in the URL.
    """
    area = session.get("area_sector")
    notes = request.form.get("notes", "")

    record = run_query(
        """SELECT vr.record_id FROM vaccination_records vr
           JOIN children c ON vr.child_id = c.child_id
           WHERE vr.record_id = %s AND c.region = %s""",
        (record_id, area), fetch_one=True,
    )
    if not record:
        flash("Record not found in your area.")
        return redirect(url_for("worker_defaulters"))

    run_query(
        """UPDATE vaccination_records
           SET status = 'completed', completed_date = CURDATE(),
               administered_by = %s, notes = %s
           WHERE record_id = %s""",
        (session["full_name"], notes, record_id),
    )
    flash("Visit recorded — dose marked as given.")
    return redirect(request.referrer or url_for("worker_defaulters"))


@app.route("/worker/children")
@worker_required
def worker_children():
    """Every child registered in this worker's area, with progress."""
    area = session.get("area_sector")
    children = run_query(
        """SELECT c.child_id, c.full_name AS child_name, c.date_of_birth,
                  u.full_name AS parent_name, u.phone AS parent_phone,
                  SUM(CASE WHEN vr.status = 'completed' THEN 1 ELSE 0 END) AS completed_count,
                  SUM(CASE WHEN vr.status = 'overdue' THEN 1 ELSE 0 END) AS overdue_count,
                  COUNT(vr.record_id) AS total_count
           FROM children c
           JOIN users u ON c.parent_id = u.user_id
           LEFT JOIN vaccination_records vr ON vr.child_id = c.child_id
           WHERE c.region = %s
           GROUP BY c.child_id, c.full_name, c.date_of_birth, u.full_name, u.phone
           ORDER BY overdue_count DESC, c.full_name ASC""",
        (area,), fetch=True,
    )
    return render_template("worker/children.html", children=children, area=area)


def get_child_in_worker_area(child_id):
    """Returns the child only if they live in the logged-in worker's area."""
    return run_query(
        """SELECT c.*, u.full_name AS parent_name, u.phone AS parent_phone
           FROM children c JOIN users u ON c.parent_id = u.user_id
           WHERE c.child_id = %s AND c.region = %s""",
        (child_id, session.get("area_sector")), fetch_one=True,
    )


@app.route("/worker/children/<int:child_id>/timeline")
@worker_required
def worker_timeline(child_id):
    """The EDITABLE version of a child's timeline. Only ASHA workers get this."""
    child = get_child_in_worker_area(child_id)
    if not child:
        flash("Child not found in your area.")
        return redirect(url_for("worker_children"))

    records = run_query(
        """SELECT vr.*, vm.vaccine_name
           FROM vaccination_records vr
           JOIN vaccine_master vm ON vr.vaccine_id = vm.vaccine_id
           WHERE vr.child_id = %s
           ORDER BY vr.due_date ASC, vm.dose_order ASC""",
        (child_id,), fetch=True,
    )
    return render_template(
        "worker/timeline.html", child=child, records=records, today=date.today().isoformat()
    )


@app.route("/worker/records/<int:record_id>/update", methods=["POST"])
@worker_required
def worker_update_record(record_id):
    """
    Edit one dose on a child's timeline (ASHA workers only).
    action = 'given'  -> mark given on the chosen date (+ optional notes)
    action = 'undo'   -> mark as not given again (fixes a mistaken entry)
    Scoped to the worker's own area, same as worker_mark_visit().
    """
    record = run_query(
        """SELECT vr.record_id, vr.child_id, vr.due_date
           FROM vaccination_records vr
           JOIN children c ON vr.child_id = c.child_id
           WHERE vr.record_id = %s AND c.region = %s""",
        (record_id, session.get("area_sector")), fetch_one=True,
    )
    if not record:
        flash("Record not found in your area.")
        return redirect(url_for("worker_children"))

    action = request.form.get("action")
    back = url_for("worker_timeline", child_id=record["child_id"])

    if action == "given":
        given_raw = request.form.get("completed_date") or date.today().isoformat()
        try:
            given_date = date.fromisoformat(given_raw)
        except ValueError:
            flash("Invalid date.")
            return redirect(back)
        if given_date > date.today():
            flash("The given date cannot be in the future.")
            return redirect(back)

        run_query(
            """UPDATE vaccination_records
               SET status = 'completed', completed_date = %s,
                   administered_by = %s, notes = %s
               WHERE record_id = %s""",
            (given_date, session["full_name"], request.form.get("notes", "").strip(), record_id),
        )
        flash("Dose saved as given.")
    elif action == "undo":
        new_status = calculate_status(record["due_date"], None)
        run_query(
            """UPDATE vaccination_records
               SET status = %s, completed_date = NULL, administered_by = NULL, notes = NULL
               WHERE record_id = %s""",
            (new_status, record_id),
        )
        flash("Dose changed back to not given.")
    else:
        flash("Unknown action.")

    return redirect(back)


# =====================================================================
# VACCINE INFORMATION — one shared page, visible in EVERY portal
# =====================================================================

def base_template_for_role():
    """Picks the layout (navbar/sidebar) that matches who is logged in."""
    role = session.get("role")
    if role == "admin":
        return "admin/base.html"
    if role == "asha":
        return "worker/base.html"
    return "base.html"


@app.route("/vaccines")
@login_required
def vaccine_info():
    schedule = run_query(
        "SELECT vaccine_name, dose_order, due_age_days, description FROM vaccine_master ORDER BY dose_order",
        fetch=True,
    )
    for row in schedule:
        days = row["due_age_days"]
        if days == 0:
            row["age_label"] = "At birth"
        elif days < 84:
            row["age_label"] = f"{round(days / 7)} weeks"
        else:
            row["age_label"] = f"{round(days / 30.4)} months"

    return render_template(
        "vaccine_info.html",
        base_template=base_template_for_role(),
        guide=VACCINE_GUIDE,
        schedule=schedule,
        before_tips=BEFORE_TIPS,
        after_tips=AFTER_TIPS,
        active_page="vaccines",
    )


# =====================================================================
# MESSAGES — Parent <-> ASHA Worker direct chat
# A parent and a worker are "connected" when the parent has a child
# registered in the worker's area. Nobody else can message each other.
# =====================================================================

def get_message_contacts():
    """People the logged-in user is allowed to chat with."""
    if session.get("role") == "parent":
        return run_query(
            """SELECT DISTINCT w.user_id, w.full_name, w.area_sector AS subtitle
               FROM users w
               JOIN children c ON c.region = w.area_sector
               WHERE w.role = 'asha' AND c.parent_id = %s
               ORDER BY w.full_name""",
            (session["user_id"],), fetch=True,
        )
    if session.get("role") == "asha":
        return run_query(
            """SELECT DISTINCT p.user_id, p.full_name, p.phone AS subtitle
               FROM users p
               JOIN children c ON c.parent_id = p.user_id
               WHERE p.role = 'parent' AND c.region = %s
               ORDER BY p.full_name""",
            (session.get("area_sector"),), fetch=True,
        )
    return []


def get_allowed_contact(other_id):
    for contact in get_message_contacts():
        if contact["user_id"] == other_id:
            return contact
    return None


def message_base_template():
    return "worker/base.html" if session.get("role") == "asha" else "base.html"


def messages_allowed(view_function):
    """Parents and ASHA workers only (admins don't take part in chats)."""
    def wrapper(*args, **kwargs):
        if session.get("role") not in ("parent", "asha"):
            flash("Messaging is for parents and ASHA workers.")
            return redirect(url_for("home"))
        return view_function(*args, **kwargs)
    wrapper.__name__ = view_function.__name__
    return wrapper


@app.route("/messages")
@login_required
@messages_allowed
def messages_inbox():
    contacts = get_message_contacts()
    for contact in contacts:
        last = run_query(
            """SELECT body, created_at FROM messages
               WHERE (sender_id = %s AND receiver_id = %s) OR (sender_id = %s AND receiver_id = %s)
               ORDER BY message_id DESC LIMIT 1""",
            (session["user_id"], contact["user_id"], contact["user_id"], session["user_id"]),
            fetch_one=True,
        )
        unread = run_query(
            "SELECT COUNT(*) AS total FROM messages WHERE sender_id = %s AND receiver_id = %s AND is_read = FALSE",
            (contact["user_id"], session["user_id"]), fetch_one=True,
        )
        contact["last"] = last
        contact["unread"] = unread["total"]

    return render_template(
        "messages_inbox.html", base_template=message_base_template(), contacts=contacts,
        is_worker=session.get("role") == "asha", active_page="messages",
    )


@app.route("/messages/<int:other_id>", methods=["GET", "POST"])
@login_required
@messages_allowed
def messages_thread(other_id):
    contact = get_allowed_contact(other_id)
    if not contact:
        flash("You can only message your own ASHA worker / the parents in your area.")
        return redirect(url_for("messages_inbox"))

    if request.method == "POST":
        body = request.form.get("body", "").strip()
        if body:
            run_query(
                "INSERT INTO messages (sender_id, receiver_id, body) VALUES (%s, %s, %s)",
                (session["user_id"], other_id, body[:2000]),
            )
        return redirect(url_for("messages_thread", other_id=other_id))

    run_query(
        "UPDATE messages SET is_read = TRUE WHERE sender_id = %s AND receiver_id = %s",
        (other_id, session["user_id"]),
    )
    thread = run_query(
        """SELECT message_id, sender_id, body, created_at FROM messages
           WHERE (sender_id = %s AND receiver_id = %s) OR (sender_id = %s AND receiver_id = %s)
           ORDER BY message_id ASC""",
        (session["user_id"], other_id, other_id, session["user_id"]), fetch=True,
    )
    return render_template(
        "messages_thread.html", base_template=message_base_template(),
        contact=contact, thread=thread, active_page="messages",
    )


@app.route("/messages/<int:other_id>/poll")
@login_required
@messages_allowed
def messages_poll(other_id):
    """Small JSON endpoint the chat page calls every few seconds for new messages."""
    if not get_allowed_contact(other_id):
        return jsonify([]), 403
    after_id = request.args.get("after", 0, type=int)
    rows = run_query(
        """SELECT message_id, sender_id, body, created_at FROM messages
           WHERE sender_id = %s AND receiver_id = %s AND message_id > %s
           ORDER BY message_id ASC""",
        (other_id, session["user_id"], after_id), fetch=True,
    )
    if rows:
        run_query(
            "UPDATE messages SET is_read = TRUE WHERE sender_id = %s AND receiver_id = %s",
            (other_id, session["user_id"]),
        )
    return jsonify([
        {"id": r["message_id"], "body": r["body"], "time": r["created_at"].strftime("%d %b, %I:%M %p")}
        for r in rows
    ])



# =====================================================================
# DROPOUT PREVENTION (see dropout.py for how the risk score works)
# =====================================================================

def send_outreach(parent_id, text):
    """ASHA worker -> parent: a normal chat message plus a bell notification."""
    run_query(
        "INSERT INTO messages (sender_id, receiver_id, body) VALUES (%s, %s, %s)",
        (session["user_id"], parent_id, text[:2000]),
    )
    run_query(
        "INSERT INTO notifications (user_id, title, message) VALUES (%s, %s, %s)",
        (parent_id, f"Message from your ASHA worker, {session['full_name']}", text[:200]),
    )


@app.route("/worker/dropout")
@worker_required
def worker_dropout():
    """Children in this worker's area, ranked by dropout risk (highest first)."""
    area = session.get("area_sector")
    level = request.args.get("level", "attention")  # attention / high / medium / low / all

    risks = get_child_risks(region=area)
    summary = summarize(risks)

    if level == "attention":
        shown = [r for r in risks if r["level"] in ("high", "medium")]
    elif level in ("high", "medium", "low"):
        shown = [r for r in risks if r["level"] == level]
    else:
        shown = risks

    for r in shown:
        r["draft"] = reminder_text(
            r["child_name"], r["parent_name"], r["next_overdue_vaccine"],
            r["max_days_overdue"], session["full_name"],
        )

    return render_template(
        "worker/dropout.html", risks=shown, summary=summary, area=area, level=level,
    )


@app.route("/worker/dropout/<int:child_id>/nudge", methods=["POST"])
@worker_required
def worker_dropout_nudge(child_id):
    child = get_child_in_worker_area(child_id)
    if not child:
        flash("Child not found in your area.")
        return redirect(url_for("worker_dropout"))

    text = request.form.get("message", "").strip()
    if not text:
        flash("Please write a message first.")
    else:
        send_outreach(child["parent_id"], text)
        flash(f"Message sent to {child['parent_name']}.")
    return redirect(request.referrer or url_for("worker_dropout"))


@app.route("/worker/dropout/nudge-all", methods=["POST"])
@worker_required
def worker_dropout_nudge_all():
    """One click: send the default reminder to every HIGH-risk child's parent
    who hasn't been contacted in the last 3 days (so nobody gets spammed)."""
    area = session.get("area_sector")
    cutoff = date.today() - timedelta(days=3)
    sent_to = set()

    for r in get_child_risks(region=area):
        if r["level"] != "high" or r["parent_id"] in sent_to:
            continue
        last = r["last_contact"]
        if last is not None and (last.date() if hasattr(last, "date") else last) > cutoff:
            continue
        send_outreach(r["parent_id"], reminder_text(
            r["child_name"], r["parent_name"], r["next_overdue_vaccine"],
            r["max_days_overdue"], session["full_name"],
        ))
        sent_to.add(r["parent_id"])

    flash(f"Reminder sent to {len(sent_to)} parent(s) of high-risk children.")
    return redirect(url_for("worker_dropout"))


@app.route("/admin/dropout")
@admin_required
def admin_dropout():
    """Region-wide view of dropout risk for the admin / health officer."""
    risks = get_child_risks()
    summary = summarize(risks)

    # Which ASHA worker(s) cover each region? (A region with none is a gap.)
    workers = run_query(
        "SELECT full_name, area_sector FROM users WHERE role = 'asha'", fetch=True
    )
    workers_by_region = {}
    for w in workers:
        workers_by_region.setdefault(w["area_sector"], []).append(w["full_name"])

    by_region = {}
    for r in risks:
        row = by_region.setdefault(r["region"], {"high": 0, "medium": 0, "low": 0})
        row[r["level"]] += 1
    region_labels = sorted(by_region.keys(), key=lambda k: -(by_region[k]["high"] * 100 + by_region[k]["medium"]))

    for r in risks:
        r["workers"] = ", ".join(workers_by_region.get(r["region"], []))

    watchlist = [r for r in risks if r["level"] in ("high", "medium")][:25]

    return render_template(
        "admin/dropout.html",
        summary=summary,
        watchlist=watchlist,
        region_labels=region_labels,
        region_high=[by_region[k]["high"] for k in region_labels],
        region_medium=[by_region[k]["medium"] for k in region_labels],
        uncovered=[k for k in region_labels if k not in workers_by_region],
        active_page="dropout",
    )


if __name__ == "__main__":
    app.run(debug=True, port=5000)
