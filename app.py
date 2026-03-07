from flask import Flask, render_template, request, redirect, session, flash, url_for, send_from_directory, abort, jsonify, make_response
from psycopg2.extras import RealDictCursor
from authlib.integrations.flask_client import OAuth, OAuthError
from dotenv import load_dotenv
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.exceptions import HTTPException
from datetime import datetime
import hashlib
import os
import psycopg2

from utils.db import get_db
from utils.security import validate_password, hash_password, check_password
from utils.supabase_client import supabase
from utils.profile_utils import is_profile_complete
from supabase import create_client


# ---------------- LOAD ENV ----------------
load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
app.config['SESSION_COOKIE_SECURE'] = True
app.config["SESSION_COOKIE_SAMESITE"] = "None"
app.config["PREFERRED_URL_SCHEME"] = "https"
# ---------------- OAUTH SETUP ----------------
oauth = OAuth(app)

google = oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"}
)



# ---------------- LOGIN REQUIRED DECORATOR ----------------
def login_required(fn):
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect("/login")
        return fn(*args, **kwargs)
    wrapper.__name__ = fn.__name__
    return wrapper


# ---------------- HOME ----------------
@app.route("/")
def home():
    return render_template("home.html")


# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].lower()
        password = request.form["password"]

        conn = None
        cur = None
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, password_hash
                FROM users
                WHERE username = %s
                  AND auth_provider = 'local'
                  AND is_active = true
                """,
                (username,)
            )
            user = cur.fetchone()

            if not user or not check_password(password, user[1]):
                flash("Invalid credentials", "login_error")
                return redirect("/login")

            session["user_id"] = str(user[0])
            user_id = session["user_id"]

        except Exception as e:
            print(f"LOGIN ERROR (credentials fetch): {e}")
            flash("An error occurred. Please try again.", "login_error")
            return redirect("/login")
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()

        # Second query: fetch display name
        conn = None
        cur = None
        try:
            conn = get_db()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SELECT display_name FROM users WHERE id = %s", (user_id,))
            user_row = cur.fetchone()
            display_name = user_row["display_name"] if user_row else ""
            display_name = display_name.split()[0].capitalize()

            session["display_name"] = display_name
            session["auth_provider"] = "local"

        except Exception as e:
            print(f"LOGIN ERROR (display name fetch): {e}")
            # Non-critical — still let them in
            session["display_name"] = ""
            session["auth_provider"] = "local"
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()

        return redirect(url_for("dashboard"))

    return render_template("login.html")


# ---------------- SIGNUP ----------------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"].lower()
        password = request.form["password"]

        if not validate_password(password):
            flash(
                "Password must be at least 8 characters long and include uppercase, lowercase, and a number.",
                "signup_error"
            )
            return redirect("/signup")

        conn = None
        cur = None
        try:
            conn = get_db()
            cur = conn.cursor()

            cur.execute("SELECT id FROM users WHERE username = %s", (username,))
            if cur.fetchone():
                flash("Username already exists.", "signup_error")
                return redirect("/signup")

            cur.execute(
                """
                INSERT INTO users (username, display_name, password_hash, auth_provider)
                VALUES (%s, %s, %s, 'local')
                RETURNING id, display_name
                """,
                (username, username, hash_password(password))
            )
            user_id, display_name = cur.fetchone()
            conn.commit()

            display_name = display_name.split()[0].capitalize()
            session["user_id"] = str(user_id)
            session["display_name"] = display_name

        except Exception as e:
            print(f"SIGNUP ERROR: {e}")
            if conn:
                conn.rollback()
            flash("An error occurred during signup. Please try again.", "signup_error")
            return redirect("/signup")
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()

        return redirect("/dashboard")

    return render_template("signup.html")


# ---------------- GOOGLE AUTH ----------------
@app.route("/login/google")
def login_google():
    redirect_uri = url_for("google_callback", _external=True)
    return google.authorize_redirect(redirect_uri)


@app.route("/auth/google/callback")
def google_callback():
    try:
        token = google.authorize_access_token()
    except OAuthError as e:
        print(f"⚠️ OAuth Error: {e}")
        flash("Session expired or invalid. Please try logging in again.")
        return redirect(url_for('login'))

    user_info = token.get("userinfo")
    if not user_info:
        user_info = google.get("userinfo").json()

    email = user_info["email"]
    raw_name = user_info.get("name") or email.split("@")[0]
    display_name = raw_name.split()[0]

    conn = None
    cur = None
    try:
        supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

# Inside your callback function:
        user_data = supabase.table("users").select("*").eq("email", email).execute()

        if user_data:
            user_id, display_name,email = user_data
            print(f"✅ Existing user logged in: {email}")
        else:
            try:
                cur.execute(
                    """
                    INSERT INTO users (email, display_name, auth_provider)
                    VALUES (%s, %s, 'google')
                    RETURNING id, display_name
                    """,
                    (email, display_name)
                )
                user_id, display_name = cur.fetchone()
                conn.commit()
                print(f"🎉 New user created: {email}")
            except psycopg2.IntegrityError:
                conn.rollback()
                cur.execute("SELECT id, display_name FROM users WHERE email = %s", (email,))
                user_id, display_name = cur.fetchone()

        session.permanent = True
        session["user_id"] = str(user_id)
        session["display_name"] = display_name.split()[0].capitalize()
        session["email"]=email

        return redirect("/dashboard")

    except Exception as e:
        print(f"❌ Google Callback DB Error: {e}")
        if conn:
            conn.rollback()
        flash("An error occurred during login.")
        return redirect(url_for('login_google'))
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


# ---------------- EMPLOYER LANDING ----------------
@app.route("/employer/info")
def employer_landing():
    if "employer_id" in session:
        return redirect(url_for("employer_dashboard"))
    return render_template("employer_landing.html")


# ---------------- EMPLOYER REGISTER ----------------
@app.route("/employer/register", methods=["GET", "POST"])
def employer_register():
    if request.method == "POST":
        company_name = request.form.get("company_name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        cin_number = request.form.get("cin_number", "").strip()
        hashed_password = hash_password(password)

        conn = None
        cur = None
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO employers (company_name, email, password_hash, cin_number)
                VALUES (%s, %s, %s, %s)
                """,
                (company_name, email, hashed_password, cin_number)
            )
            conn.commit()
            flash("Registration successful! Your account is pending admin approval.", "success")
            return redirect(url_for("home"))

        except Exception as e:
            print(f"EMPLOYER REGISTRATION ERROR: {e}")
            if conn:
                conn.rollback()
            flash("Error: Email might already be registered.", "danger")
            return redirect(url_for("employer_register"))
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()

    return render_template("employer_register.html")


# ---------------- EMPLOYER LOGIN ----------------
@app.route("/employer/login", methods=["GET", "POST"])
def employer_login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        conn = None
        cur = None
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute(
                "SELECT id, company_name, password_hash, status FROM employers WHERE email = %s",
                (email,)
            )
            employer = cur.fetchone()

            if employer and check_password(password, employer[2]):
                session["employer_id"] = employer[0]
                session["employer_name"] = employer[1]
                session["employer_status"] = employer[3]
                flash(f"Welcome back, {employer[1]}!", "success")
                return redirect(url_for("employer_dashboard"))
            elif employer:
                flash("Invalid email or password.", "danger")
            else:
                flash("No employer account found with that email.", "danger")

        except Exception as e:
            print(f"EMPLOYER LOGIN ERROR: {e}")
            flash("An error occurred during login. Please try again.", "danger")
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()

    return render_template("employer_login.html")


# ---------------- EMPLOYER DASHBOARD ----------------
@app.route("/employer/dashboard")
def employer_dashboard():
    if "employer_id" not in session:
        flash("Please log in to access the employer dashboard.", "warning")
        return redirect(url_for("employer_login"))

    employer_id = session["employer_id"]
    employer_status = session.get("employer_status", "pending")
    employer_name = session.get("employer_name", "Company")
    posted_jobs = []

    if employer_status == "approved":
        conn = None
        cur = None
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, title, location, posted_on
                FROM internships WHERE employer_id = %s
                ORDER BY posted_on DESC
                """,
                (employer_id,)
            )
            posted_jobs = cur.fetchall()

        except Exception as e:
            print(f"EMPLOYER DASHBOARD ERROR: {e}")
            flash("Could not load your posted jobs.", "danger")
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()

    return render_template(
        "employer_dashboard.html",
        status=employer_status,
        company_name=employer_name,
        jobs=posted_jobs
    )


# ---------------- POST INTERNSHIP ----------------
@app.route("/employer/post-internship", methods=["GET", "POST"])
def post_internship():
    if "employer_id" not in session:
        flash("Please log in first.", "warning")
        return redirect(url_for("employer_login"))

    if session.get("employer_status") != "approved":
        flash("Your account must be approved before posting.", "danger")
        return redirect(url_for("employer_dashboard"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        location = request.form.get("location", "").strip()
        duration = request.form.get("duration", "").strip()
        stipend = request.form.get("stipend", "").strip()
        skills = request.form.get("skills_final", "").strip()
        apply_link = request.form.get("apply_link", "").strip()

        if apply_link and not apply_link.startswith(('http://', 'https://')):
            apply_link = 'https://' + apply_link

        employer_id = session["employer_id"]
        company_name = session.get("employer_name", "Unknown Company")
        posted_on = datetime.today().strftime('%Y-%m-%d')
        content_hash = hashlib.sha256(f"{title}_{company_name}_{location}".encode('utf-8')).hexdigest()

        conn = None
        cur = None
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO internships (
                    title, organization, location, duration, stipend,
                    skills_final, posted_on, type, source, apply_link,
                    content_hash, employer_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    title, company_name, location, duration, stipend,
                    skills, posted_on, "Internship", "SmartIntern Direct",
                    apply_link, content_hash, employer_id
                )
            )
            conn.commit()
            flash("Internship posted successfully!", "success")
            return redirect(url_for("employer_dashboard"))

        except Exception as e:
            print(f"POST INTERNSHIP ERROR: {e}")
            if conn:
                conn.rollback()
            flash("An error occurred while posting. Please try again.", "danger")
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()

    return render_template("post_internship.html")


# ---------------- EDIT INTERNSHIP ----------------
@app.route("/employer/edit-internship/<int:job_id>", methods=["GET", "POST"])
def edit_internship(job_id):
    if "employer_id" not in session:
        return redirect(url_for("employer_login"))

    employer_id = session["employer_id"]

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        location = request.form.get("location", "").strip()
        duration = request.form.get("duration", "").strip()
        stipend = request.form.get("stipend", "").strip()
        skills = request.form.get("skills_final", "").strip()
        apply_link = request.form.get("apply_link", "").strip()

        if apply_link and not apply_link.startswith(('http://', 'https://')):
            apply_link = 'https://' + apply_link

        conn = None
        cur = None
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE internships
                SET title = %s, location = %s, duration = %s, stipend = %s,
                    skills_final = %s, apply_link = %s
                WHERE id = %s AND employer_id = %s
                """,
                (title, location, duration, stipend, skills, apply_link, job_id, employer_id)
            )
            conn.commit()
            flash("Internship updated successfully!", "success")
            return redirect(url_for("employer_dashboard"))

        except Exception as e:
            print(f"EDIT INTERNSHIP ERROR: {e}")
            if conn:
                conn.rollback()
            flash("Error updating internship.", "danger")
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()

    # GET: fetch existing details
    conn = None
    cur = None
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, title, location, duration, stipend, skills_final, apply_link
            FROM internships WHERE id = %s AND employer_id = %s
            """,
            (job_id, employer_id)
        )
        job = cur.fetchone()

        if not job:
            flash("Job not found or unauthorized.", "danger")
            return redirect(url_for("employer_dashboard"))

        return render_template("edit_internship.html", job=job)

    except Exception as e:
        print(f"FETCH EDIT ERROR: {e}")
        flash("Error loading job details.", "danger")
        return redirect(url_for("employer_dashboard"))
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


# ---------------- DELETE INTERNSHIP ----------------
@app.route("/employer/delete-internship/<int:job_id>", methods=["POST"])
def delete_internship(job_id):
    if "employer_id" not in session:
        return redirect(url_for("employer_login"))

    conn = None
    cur = None
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM internships WHERE id = %s AND employer_id = %s",
            (job_id, session["employer_id"])
        )
        conn.commit()
        flash("Internship deleted permanently.", "info")

    except Exception as e:
        print(f"DELETE INTERNSHIP ERROR: {e}")
        if conn:
            conn.rollback()
        flash("Error deleting internship.", "danger")
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    return redirect(url_for("employer_dashboard"))

@app.route("/employer/logout")
def employer_logout():
    session.pop("employer_id", None)
    return redirect(url_for("employer_login"))

# ---------------- ADMIN LOGIN ----------------
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        password = request.form.get("password")
        correct_password = os.environ.get("ADMIN_PASSWORD")

        if correct_password and password == correct_password:
            session["is_admin"] = True
            flash("Admin access granted.", "success")
            return redirect(url_for("admin_dashboard"))
        else:
            flash("Invalid admin password.", "danger")

    return render_template("admin_login.html")


# ---------------- ADMIN DASHBOARD ----------------
@app.route("/admin/dashboard")
def admin_dashboard():
    if not session.get("is_admin"):
        flash("Unauthorized access. Please log in as admin.", "danger")
        return redirect(url_for("admin_login"))

    pending_employers = []
    approved_employers = []

    conn = None
    cur = None
    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute(
            """
            SELECT id, company_name, email, cin_number, created_at
            FROM employers WHERE status = 'pending'
            ORDER BY created_at ASC
            """
        )
        pending_employers = cur.fetchall()

        cur.execute(
            """
            SELECT id, company_name, email, cin_number, created_at
            FROM employers WHERE status = 'approved'
            ORDER BY created_at DESC
            """
        )
        approved_employers = cur.fetchall()

    except Exception as e:
        print(f"ADMIN DASHBOARD ERROR: {e}")
        flash("Could not load employer data.", "danger")
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    return render_template(
        "admin_dashboard.html",
        employers=pending_employers,
        approved_employers=approved_employers
    )


# ---------------- ADMIN APPROVE ----------------
@app.route("/admin/approve/<int:employer_id>", methods=["POST"])
def admin_approve(employer_id):
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))

    conn = None
    cur = None
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("UPDATE employers SET status = 'approved' WHERE id = %s", (employer_id,))
        conn.commit()
        flash("Employer approved successfully! They can now post jobs.", "success")

    except Exception as e:
        print(f"ADMIN APPROVE ERROR: {e}")
        if conn:
            conn.rollback()
        flash("Error approving employer.", "danger")
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    return redirect(url_for("admin_dashboard"))


# ---------------- ADMIN REJECT ----------------
@app.route("/admin/reject/<int:employer_id>", methods=["POST"])
def admin_reject(employer_id):
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))

    conn = None
    cur = None
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("DELETE FROM employers WHERE id = %s", (employer_id,))
        conn.commit()
        flash("Employer application rejected and permanently deleted.", "info")

    except Exception as e:
        print(f"ADMIN REJECT ERROR: {e}")
        if conn:
            conn.rollback()
        flash("Error rejecting employer.", "danger")
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    return redirect(url_for("admin_dashboard"))


# ---------------- ADMIN LOGOUT ----------------
@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    flash("Admin logged out successfully.", "info")
    return redirect(url_for("home"))


# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
@login_required
def dashboard():
    user_id = session["user_id"]
    display_name = session.get("display_name", "")
    profile_complete = is_profile_complete(user_id)

    return render_template(
        "dashboard.html",
        profile_complete=profile_complete,
        display_name=display_name
    )


# ---------------- RECOMMENDATIONS API ----------------
@app.route("/api/recommendations")
@login_required
def api_recommendations():
    user_id = session["user_id"]
    profile_complete = is_profile_complete(user_id)

    internships = []
    if profile_complete:
        from utils.recommendation_utils import get_internship_recommendations
        internships = get_internship_recommendations(user_id, top_n=10)

    from utils.recommendation_utils import get_scholarship_recommendations
    scholarships = get_scholarship_recommendations(user_id, top_n=10)

    return jsonify({"internships": internships, "scholarships": scholarships})


# ---------------- INTERNSHIPS LIST ----------------
@app.route("/internships")
def internships():
    page = request.args.get("page", 1, type=int)
    PER_PAGE = 12
    offset = (page - 1) * PER_PAGE
    location = request.args.get("location", "").strip()
    source = request.args.get("source", "").strip()

    internships = []
    saved_ids = set()

    conn = None
    cur = None
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        sql = "SELECT * FROM internships"
        conditions = []
        params = []

        if location:
            conditions.append("location ILIKE %s")
            params.append(f"%{location}%")
        if source:
            conditions.append("source ILIKE %s")
            params.append(f"%{source}%")

        if conditions:
            sql += " WHERE " + " AND ".join(conditions)

        sql += " ORDER BY created_at DESC, id DESC LIMIT %s OFFSET %s"
        params.extend([PER_PAGE, offset])

        cur.execute(sql, params)
        internships = cur.fetchall()

        user_id = session.get("user_id")
        if user_id:
            cur.execute(
                """
                SELECT opportunity_id
                FROM saved_opportunities
                WHERE user_id = %s AND opportunity_type = 'internship'
                """,
                (user_id,)
            )
            saved_ids = {int(row["opportunity_id"]) for row in cur.fetchall()}

    except Exception as e:
        print(f"INTERNSHIPS LIST ERROR: {e}")
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    return render_template(
        "internships.html",
        internships=internships,
        saved_ids=saved_ids,
        page=page,
        current_location=location,
        current_source=source
    )


# ---------------- SCHOLARSHIPS LIST ----------------
@app.route("/scholarships")
def scholarships():
    page = request.args.get("page", 1, type=int)
    search_query = request.args.get("search", "").strip()
    source_filter = request.args.get("source", "all").strip()
    PER_PAGE = 12
    offset = (page - 1) * PER_PAGE

    scholarships = []
    total_pages = 0

    conn = None
    cur = None
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        conditions = []
        params = []

        if search_query:
            conditions.append("(title ILIKE %s OR provider ILIKE %s)")
            params.extend([f"%{search_query}%", f"%{search_query}%"])
        if source_filter and source_filter != "all":
            conditions.append("source ILIKE %s")
            params.append(f"%{source_filter}%")

        where_clause = (" WHERE " + " AND ".join(conditions)) if conditions else ""

        cur.execute(f"SELECT COUNT(*) FROM scholarships{where_clause}", params)
        count_result = cur.fetchone()
        total_scholarships = count_result["count"] if count_result else 0
        total_pages = (total_scholarships + PER_PAGE - 1) // PER_PAGE

        cur.execute(
            f"SELECT * FROM scholarships{where_clause} ORDER BY created_at DESC LIMIT %s OFFSET %s",
            params + [PER_PAGE, offset]
        )
        scholarships = cur.fetchall()

    except Exception as e:
        print(f"SCHOLARSHIPS LIST ERROR: {e}")
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    return render_template(
        "scholarships.html",
        scholarships=scholarships,
        page=page,
        total_pages=total_pages,
        current_search=search_query,
        current_source=source_filter
    )


# ---------------- INTERNSHIP DETAIL ----------------
@app.route("/internships/<int:internship_id>")
def internship_details(internship_id):
    conn = None
    cur = None
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM internships WHERE id = %s", (internship_id,))
        internship = cur.fetchone()

        if not internship:
            abort(404)

        return render_template("internship_details.html", internship=internship)

    except HTTPException:
        raise
    except Exception as e:
        print(f"INTERNSHIP DETAIL ERROR: {e}")
        abort(500)
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


# ---------------- SCHOLARSHIP DETAIL ----------------
@app.route("/scholarships/<int:scholarship_id>")
def scholarship_details(scholarship_id):
    conn = None
    cur = None
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM scholarships WHERE id = %s", (scholarship_id,))
        scholarship = cur.fetchone()

        if not scholarship:
            abort(404)

        return render_template("scholarship_details.html", scholarship=scholarship)

    except HTTPException:
        raise
    except Exception as e:
        print(f"SCHOLARSHIP DETAIL ERROR: {e}")
        abort(500)
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


# ---------------- PROFILE SETUP ----------------
@app.route("/profile/setup", methods=["GET", "POST"])
@login_required
def profile_setup():
    user_id = session["user_id"]

    if request.method == "POST":
        print("RAW DATA RECEIVED:", request.get_json())
        try:
            data = request.get_json()
            from validators.profile_validator import validate_profile_payload
            from services.profile_service import upsert_profile

            profile, skills, interests = validate_profile_payload(data)
            upsert_profile(user_id, profile, skills, interests)

            flash("Profile updated successfully!", "success")
            return {"status": "OK", "redirect_url": url_for("dashboard")}, 200

        except Exception as e:
            print(f"PROFILE SAVE ERROR: {e}")
            return {"error": str(e)}, 400

    # GET: load existing profile
    profile = None
    skills = []
    interests = []
    email = "Error"

    conn = None
    cur = None
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute("SELECT * FROM user_profiles WHERE user_id = %s", (user_id,))
        profile = cur.fetchone()

        cur.execute("SELECT skill FROM user_skills WHERE user_id = %s", (user_id,))
        skills = [r["skill"] for r in cur.fetchall()]

        cur.execute("SELECT interest FROM user_interests WHERE user_id = %s", (user_id,))
        interests = [r["interest"] for r in cur.fetchall()]

        cur.execute("SELECT email FROM users WHERE id = %s", (user_id,))
        email_row = cur.fetchone()
        email = email_row["email"] if email_row else "Error"

    except Exception as e:
        print(f"PROFILE LOAD ERROR: {e}")
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    return render_template(
        "profile_setup.html",
        profile=profile,
        skills=", ".join(skills),
        interests=", ".join(interests),
        email=email
    )


# ---------------- SAVE OPPORTUNITY ----------------
@app.route("/save", methods=["POST"])
@login_required
def save_opportunity():
    user_id = session["user_id"]
    data = request.get_json()
    opportunity_id = data["opportunity_id"]
    opportunity_type = data["opportunity_type"]

    conn = None
    cur = None
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO saved_opportunities (user_id, opportunity_id, opportunity_type)
            VALUES (%s, %s, %s)
            ON CONFLICT DO NOTHING
            """,
            (user_id, opportunity_id, opportunity_type)
        )
        conn.commit()

    except Exception as e:
        print(f"SAVE OPPORTUNITY ERROR: {e}")
        if conn:
            conn.rollback()
        return {"status": "ERROR"}, 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    return {"status": "SAVED"}, 200


# ---------------- SAVED PAGE ----------------
@app.route("/saved")
@login_required
def saved_page():
    user_id = session["user_id"]
    internships = []
    scholarships = []

    conn = None
    cur = None
    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute(
            """
            SELECT i.*
            FROM saved_opportunities s
            JOIN internships i ON i.id = s.opportunity_id
            WHERE s.user_id = %s AND s.opportunity_type = 'internship'
            """,
            (user_id,)
        )
        rows = cur.fetchall()
        cols_i = [d[0] for d in cur.description]
        internships = [dict(zip(cols_i, r)) for r in rows]

    except Exception as e:
        print(f"SAVED PAGE ERROR: {e}")
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    return render_template("saved.html", internships=internships, scholarships=scholarships)


# ---------------- UNSAVE OPPORTUNITY ----------------
@app.route("/unsave", methods=["POST"])
@login_required
def unsave_opportunity():
    user_id = session["user_id"]
    data = request.get_json()
    opportunity_id = data["opportunity_id"]
    opportunity_type = data["opportunity_type"]

    conn = None
    cur = None
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """
            DELETE FROM saved_opportunities
            WHERE user_id = %s AND opportunity_id = %s AND opportunity_type = %s
            """,
            (user_id, opportunity_id, opportunity_type)
        )
        conn.commit()

    except Exception as e:
        print(f"UNSAVE ERROR: {e}")
        if conn:
            conn.rollback()
        return {"status": "ERROR"}, 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    return {"status": "UNSAVED"}, 200


# ---------------- STATIC PAGES ----------------
@app.route("/faqs")
def faqs():
    return render_template("faqs.html")

@app.route("/about")
def about_us():
    return render_template("about_us.html")

@app.route("/privacy")
def privacy():
    return render_template("privacy.html")

@app.route("/feedback")
def feedback():
    user_name = session.get("display_name", "")
    user_email = session.get("email", "")
    return render_template(
        "feedback.html", 
        prefill_name=user_name, 
        prefill_email=user_email
    )


# ---------------- SUBMIT FEEDBACK ----------------
@app.route("/submit-feedback", methods=["POST"])
def submit_feedback():
    data = {
        "name": request.form.get("name"),
        "email": request.form.get("email"),
        "satisfaction": request.form.get("satisfaction"),
        "relevance": request.form.get("relevance"),
        "used_type": request.form.get("used_type"),
        "time_saved": request.form.get("time_saved"),
        "ease": request.form.get("ease"),
        "overall_experience": request.form.get("overall_experience"),
        "improve": request.form.get("improve"),
        "recommend": request.form.get("recommend")
    }

    conn = None
    cur = None
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO feedback
            (name, email, satisfaction, relevance, used_type, time_saved,
             ease, overall_experience, improve, recommend)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                data["name"], data["email"], data["satisfaction"], data["relevance"],
                data["used_type"], data["time_saved"], data["ease"],
                data["overall_experience"], data["improve"], data["recommend"]
            )
        )
        conn.commit()
        flash("✅ Thank you! Your feedback has been submitted.", "feedback_success")
        return redirect(url_for("feedback"))

    except Exception as e:
        print(f"FEEDBACK ERROR: {e}")
        if conn:
            conn.rollback()
        return "An error occurred while saving feedback. Check console.", 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


# ---------------- CONTACT ----------------
@app.route("/contact")
def contacts():
    user_name = session.get("display_name", "")
    user_email = session.get("email", "")
    return render_template(
        "contacts.html", 
        prefill_name=user_name, 
        prefill_email=user_email
    )


@app.route("/send-message", methods=["POST"])
def send_message():
    data = {
        "name": request.form.get("name"),
        "email": request.form.get("email"),
        "category": request.form.get("category"),
        "message": request.form.get("message")
    }

    conn = None
    cur = None
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO contact_messages (name, email, category, message)
            VALUES (%s, %s, %s, %s)
            """,
            (data["name"], data["email"], data["category"], data["message"])
        )
        conn.commit()
        flash("Your message has been sent successfully!", "contact_success")
        return redirect(url_for("contacts"))

    except Exception as e:
        print(f"CONTACT MESSAGE ERROR: {e}")
        if conn:
            conn.rollback()
        return "An error occurred.", 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


# ---------------- DOCS ----------------
@app.route('/docs')
def download_documentation():
    directory = os.path.join(app.root_path, 'static', 'docs')
    return send_from_directory(directory, 'Documentation.pdf')


# ---------------- SITEMAP ----------------
@app.route('/sitemap.xml', methods=['GET'])
def sitemap():
    base_url = "https://smartintern-portal.onrender.com"
    static_urls = [
        "/", "/about", "/contact", "/faqs", "/privacy",
        "/internships", "/scholarships", "/employer/info",
        "/login", "/signup"
    ]

    today = datetime.today().strftime('%Y-%m-%d')
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    for url in static_urls:
        xml += '  <url>\n'
        xml += f'    <loc>{base_url}{url}</loc>\n'
        xml += f'    <lastmod>{today}</lastmod>\n'
        xml += '    <changefreq>weekly</changefreq>\n'
        xml += '    <priority>0.8</priority>\n'
        xml += '  </url>\n'
    xml += '</urlset>'

    response = make_response(xml)
    response.headers["Content-Type"] = "application/xml"
    return response


# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# ==========================================
# GLOBAL ERROR HANDLERS
# ==========================================
@app.errorhandler(HTTPException)
def handle_http_exception(e):
    return render_template("error.html", error_code=e.code, error_message=e.name), e.code


@app.errorhandler(Exception)
def handle_unknown_exception(e):
    print(f"🚨 CRITICAL UNHANDLED ERROR: {e}")
    try:
        conn = get_db()
        conn.rollback()
        conn.close()
    except Exception:
        pass
    return render_template("error.html", error_code=500, error_message="Internal Server Error"), 500


# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(debug=True)