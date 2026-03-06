from flask import Flask, render_template, request, redirect, session, flash, url_for,send_from_directory,abort
from psycopg2.extras import RealDictCursor
from authlib.integrations.flask_client import OAuth,OAuthError
from dotenv import load_dotenv
import os
import psycopg2
from utils.db import get_db
from utils.security import validate_password, hash_password, check_password
from utils.supabase_client import supabase
from utils.profile_utils import is_profile_complete
from utils.recommendation_utils import get_internship_recommendations,get_scholarship_recommendations
from supabase import create_client
from werkzeug.middleware.proxy_fix import ProxyFix # Add this import
from werkzeug.exceptions import HTTPException







# ---------------- LOAD ENV ----------------
load_dotenv()
app = Flask(__name__)
app.secret_key = "dev-secret"

# Add these two lines immediately after creating your app
# This forces Flask to recognize that it is running on HTTPS behind a proxy
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Secure your session cookies for production
app.config['SESSION_COOKIE_SECURE'] = True

# ---------------- OAUTH SETUP ----------------
oauth = OAuth(app)

google = oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={
        "scope": "openid email profile"
    }
)

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
        cur.close()
        conn.close()

        if not user or not check_password(password, user[1]):
            flash("Invalid credentials","login_error")
            return redirect("/login")

        # FIX: This was commented out, which broke the login session. 
        # Uncommented and casting ID to string for consistency.
        session["user_id"] = str(user[0])
        user_id = session.get("user_id")
        
        # if not user_id:
        #     return redirect(url_for("login"))
        
        #get user name for displaying on dashboard:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute(
            "SELECT display_name FROM users WHERE id = %s",
            (user_id,)
        )

        user_row = cur.fetchone()
        display_name = user_row["display_name"] if user_row else ""
        display_name=display_name.split()[0].capitalize()

        # FIX: Save display_name to session so it persists after redirect
        session["display_name"] = display_name
        session["auth_provider"] = "local"

        # FIX: Use redirect instead of render_template to prevent URL issues
        return redirect(url_for("dashboard"))

    return render_template("login.html")


# @app.route("/send-otp", methods=["POST"])
# def send_otp():
#     email = request.form["email"]

#     supabase.auth.sign_in_with_otp({
#         "email": email
#     })

#     session["email"] = email
#     return redirect("/verify-otp")

# @app.route("/auth-success", methods=["POST"])
# def auth_success():
#     data = request.get_json()
#     session["user_id"] = data["user_id"]
#     session["email"] = data["email"]
#     return {"status": "ok"}


# @app.route("/verify-otp", methods=["GET", "POST"])
# def verify_otp():
#     if request.method == "POST":
#         otp = request.form["otp"]
#         email = session.get("email")

#         supabase.auth.verify_otp({
#             "email": email,
#             "token": otp,
#             "type": "email"
#         })

#         return redirect("/dashboard")

#     return render_template("verify_otp.html")


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

        conn = get_db()
        cur = conn.cursor()

        cur.execute(
            "SELECT id FROM users WHERE username = %s",
            (username,)
        )
        if cur.fetchone():
            flash("Username already exists.", "signup_error")
            cur.close()
            conn.close()
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
        cur.close()
        conn.close()
        display_name=display_name.split()[0].capitalize()

        session["user_id"] = str(user_id)
        session["display_name"] = display_name

        return redirect(
            "/dashboard"

            )

    return render_template("signup.html")

# ---------------- GOOGLE AUTH (LOGIN + SIGNUP) ----------------
@app.route("/login/google")
def login_google():
    # Force HTTPS for the callback if you are in production (Render/Heroku/Vercel)
    # _external=True ensures it sends the full URL (https://your-site.com/auth/...)
    redirect_uri = url_for("google_callback", _external=True)
    return google.authorize_redirect(redirect_uri)


@app.route("/auth/google/callback")
def google_callback():
    # 1️⃣ SAFE TOKEN EXCHANGE (Fixes "invalid_grant" crash)
    try:
        token = google.authorize_access_token()
    except OAuthError as e:
        # If the code was used twice or expired, don't crash.
        print(f"⚠️ OAuth Error: {e}")
        flash("Session expired or invalid. Please try logging in again.")
        return redirect(url_for('login')) # Change 'login_page' to your actual login route function name

    # 2️⃣ ROBUST USER INFO FETCHING
    # Sometimes userinfo is inside the token, sometimes we need to fetch it.
    user_info = token.get("userinfo")
    if not user_info:
        user_info = google.get("userinfo").json()

    email = user_info["email"]
    # Get name, fallback to email prefix if name is missing
    raw_name = user_info.get("name") or email.split("@")[0]
    display_name = raw_name.split()[0] # Take first name only

    conn = None
    try:
        conn = get_db()
        cur = conn.cursor()

        # 3️⃣ DATABASE LOGIC (Upsert / Check-Exist Pattern)
        
        # First, check if user exists
        cur.execute("SELECT id, display_name FROM users WHERE email = %s", (email,))
        row = cur.fetchone()

        if row:
            # --- SCENARIO A: Existing User ---
            user_id, db_display_name = row
            display_name = db_display_name # Use the name we have in DB
            print(f"✅ Existing user logged in: {email}")
        else:
            # --- SCENARIO B: New User ---
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
                conn.commit() # Commit immediately after creation
                print(f"🎉 New user created: {email}")

            except psycopg2.IntegrityError:
                # --- SCENARIO C: Race Condition Safety ---
                # If 2 requests happen at once, the INSERT fails because email exists.
                # We catch this error, rollback the failed insert, and just select the user.
                conn.rollback()
                cur.execute("SELECT id, display_name FROM users WHERE email = %s", (email,))
                user_id, display_name = cur.fetchone()

        # 4️⃣ SET SESSION
        session.permanent = True # Keep user logged in even if they close browser
        session["user_id"] = str(user_id)
        display_name=display_name.split()[0].capitalize()
        session["display_name"] = display_name
        
        cur.close()
        # conn.close() is handled in finally block

        return redirect("/dashboard")

    except Exception as e:
        print(f"❌ Database/Login Error: {e}")
        if conn:
            conn.rollback()
        flash("An error occurred during login.")
        return redirect(url_for('login_google'))

    finally:
        # 5️⃣ PREVENT CONNECTION LEAKS
        # Always close the connection, even if the code crashes above.
        if conn:
            conn.close()

@app.route("/employer/info")
def employer_landing():
    # If an employer is already logged in, you might want to just send them to their dashboard
    if "employer_id" in session:
        return redirect(url_for("employer_dashboard"))
        
    return render_template("employer_landing.html")

@app.route("/employer/register", methods=["GET", "POST"])
def employer_register():
    if request.method == "POST":
        company_name = request.form.get("company_name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        cin_number = request.form.get("cin_number", "").strip()

        # Optional: If your validate_password function returns a boolean and an error message, 
        # you can use it here to enforce strong passwords for employers!
        # is_valid, error_msg = validate_password(password)
        # if not is_valid:
        #     flash(error_msg, "danger")
        #     return redirect(url_for("employer_register"))

        # Use YOUR custom hash function instead of Werkzeug's
        hashed_password = hash_password(password)

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
            cur.close()
            conn.close()

            flash("Registration successful! Your account is pending admin approval.", "success")
            
            # Redirecting to home for now until we build the employer login page
            return redirect(url_for("home")) 

        except Exception as e:
            print("EMPLOYER REGISTRATION ERROR:", e)
            flash("Error: Email might already be registered.", "danger")
            return redirect(url_for("employer_register"))

    # GET request: show the form
    return render_template("employer_register.html")

@app.route("/employer/login", methods=["GET", "POST"])
def employer_login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        try:
            conn = get_db()
            cur = conn.cursor()
            
            # Fetch the employer by email
            cur.execute(
                "SELECT id, company_name, password_hash, status FROM employers WHERE email = %s", 
                (email,)
            )
            employer = cur.fetchone()
            cur.close()
            conn.close()

            # employer tuple indexes: 0=id, 1=company_name, 2=password_hash, 3=status
            if employer:
                # Use YOUR custom check_password function
                # Note: Adjust the parameter order if your function expects (hash, password) instead
                if check_password(password, employer[2]): 
                    
                    # Set the employer session variables
                    session["employer_id"] = employer[0]
                    session["employer_name"] = employer[1]
                    session["employer_status"] = employer[3] # We'll use this to block unapproved posts!

                    flash(f"Welcome back, {employer[1]}!", "success")
                    return redirect(url_for("employer_dashboard"))
                else:
                    flash("Invalid email or password.", "danger")
            else:
                flash("No employer account found with that email.", "danger")

        except Exception as e:
            print("EMPLOYER LOGIN ERROR:", e)
            flash("An error occurred during login. Please try again.", "danger")

    # If it's a GET request, just show the login form
    return render_template("employer_login.html")

@app.route("/employer/dashboard")
def employer_dashboard():
    # Security check: Kick them out if they aren't logged in as an employer
    if "employer_id" not in session:
        flash("Please log in to access the employer dashboard.", "warning")
        return redirect(url_for("employer_login"))

    employer_id = session["employer_id"]
    employer_status = session.get("employer_status", "pending")
    employer_name = session.get("employer_name", "Company")

    posted_jobs = []

    # Only query the database for jobs if the employer is approved
    if employer_status == "approved":
        try:
            conn = get_db()
            cur = conn.cursor() 
            
            # Fetch the jobs posted by THIS specific employer
            cur.execute(
                """
                SELECT id, title, location, posted_on 
                FROM internships WHERE employer_id = %s 
                ORDER BY posted_on DESC
                """,
                (employer_id,)
            )
            posted_jobs = cur.fetchall()
            
            cur.close()
            conn.close()
        except Exception as e:
            print("DASHBOARD ERROR:", e)
            flash("Could not load your posted jobs.", "danger")

    return render_template(
        "employer_dashboard.html", 
        status=employer_status, 
        company_name=employer_name,
        jobs=posted_jobs
    )

from datetime import datetime
import hashlib

@app.route("/employer/post-internship", methods=["GET", "POST"])
def post_internship():
    # 1. SECURITY CHECK: Must be logged in AND approved
    if "employer_id" not in session:
        flash("Please log in first.", "warning")
        return redirect(url_for("employer_login"))
        
    if session.get("employer_status") != "approved":
        flash("Your account must be approved before posting.", "danger")
        return redirect(url_for("employer_dashboard"))

    # 2. HANDLE FORM SUBMISSION
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        location = request.form.get("location", "").strip()
        duration = request.form.get("duration", "").strip()
        stipend = request.form.get("stipend", "").strip()
        skills = request.form.get("skills_final", "").strip()
        apply_link = request.form.get("apply_link", "").strip()
        # Force absolute URL if the employer forgot http:// or https://
        if apply_link and not apply_link.startswith(('http://', 'https://')):
            apply_link = 'https://' + apply_link
        
        employer_id = session["employer_id"]
        company_name = session.get("employer_name", "Unknown Company")
        posted_on = datetime.today().strftime('%Y-%m-%d')
        
        # Generate a content hash just like the scraper does to prevent duplicates
        hash_input = f"{title}_{company_name}_{location}"
        content_hash = hashlib.sha256(hash_input.encode('utf-8')).hexdigest()

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
            cur.close()
            conn.close()

            flash("Internship posted successfully!", "success")
            return redirect(url_for("employer_dashboard"))

        except Exception as e:
            print("POST INTERNSHIP ERROR:", e)
            flash("An error occurred while posting. Please try again.", "danger")

    # 3. IF GET REQUEST: Show the form
    return render_template("post_internship.html")

# --- UPDATE (EDIT) INTERNSHIP ---
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
        # Force absolute URL if the employer forgot http:// or https://
        if apply_link and not apply_link.startswith(('http://', 'https://')):
            apply_link = 'https://' + apply_link

        try:
            conn = get_db()
            cur = conn.cursor()
            # Update the specific job, making sure it belongs to this employer
            cur.execute("""
                UPDATE internships 
                SET title = %s, location = %s, duration = %s, stipend = %s, skills_final = %s, apply_link = %s
                WHERE id = %s AND employer_id = %s
            """, (title, location, duration, stipend, skills, apply_link, job_id, employer_id))
            
            conn.commit()
            cur.close()
            conn.close()
            
            flash("Internship updated successfully!", "success")
            return redirect(url_for("employer_dashboard"))
        except Exception as e:
            print("EDIT ERROR:", e)
            flash("Error updating internship.", "danger")

    # If GET request: Fetch the existing job details to pre-fill the form
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, title, location, duration, stipend, skills_final, apply_link 
            FROM internships WHERE id = %s AND employer_id = %s
        """, (job_id, employer_id))
        job = cur.fetchone()
        cur.close()
        conn.close()

        if not job:
            flash("Job not found or unauthorized.", "danger")
            return redirect(url_for("employer_dashboard"))

        return render_template("edit_internship.html", job=job)
    except Exception as e:
        print("FETCH EDIT ERROR:", e)
        flash("Error loading job details.", "danger")
        return redirect(url_for("employer_dashboard"))


# --- DELETE INTERNSHIP ---
@app.route("/employer/delete-internship/<int:job_id>", methods=["POST"])
def delete_internship(job_id):
    if "employer_id" not in session:
        return redirect(url_for("employer_login"))

    try:
        conn = get_db()
        cur = conn.cursor()
        # Delete only if the job ID and employer ID match
        cur.execute("DELETE FROM internships WHERE id = %s AND employer_id = %s", (job_id, session["employer_id"]))
        conn.commit()
        cur.close()
        conn.close()
        
        flash("Internship deleted permanently.", "info")
    except Exception as e:
        print("DELETE ERROR:", e)
        flash("Error deleting internship.", "danger")

    return redirect(url_for("employer_dashboard"))

# --- 1. ADMIN LOGIN ---
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
            # Note: We removed the render_template from here so it falls through to the bottom

    # THIS handles both the GET request (showing the form for the first time) 
    # AND the failed POST request (showing the form again after a wrong password)
    return render_template("admin_login.html")


# --- 2. ADMIN DASHBOARD ---
@app.route("/admin/dashboard")
def admin_dashboard():
    # Security: Kick out anyone who isn't the admin
    if not session.get("is_admin"):
        flash("Unauthorized access. Please log in as admin.", "danger")
        return redirect(url_for("admin_login"))

    pending_employers = []
    approved_employers = []
    
    try:
        conn = get_db()
        cur = conn.cursor()
        
        # 1. Fetch PENDING employers
        cur.execute("""
            SELECT id, company_name, email, cin_number, created_at 
            FROM employers 
            WHERE status = 'pending' 
            ORDER BY created_at ASC
        """)
        pending_employers = cur.fetchall()

        # 2. Fetch APPROVED (Existing) employers
        cur.execute("""
            SELECT id, company_name, email, cin_number, created_at 
            FROM employers 
            WHERE status = 'approved' 
            ORDER BY created_at DESC
        """)
        approved_employers = cur.fetchall()
        
        cur.close()
        conn.close()
    except Exception as e:
        print("ADMIN DASHBOARD ERROR:", e)
        flash("Could not load employer data.", "danger")

    # Pass BOTH lists to the template
    return render_template(
        "admin_dashboard.html", 
        employers=pending_employers,
        approved_employers=approved_employers
    )
# --- 3. APPROVE ACTION ---
@app.route("/admin/approve/<int:employer_id>", methods=["POST"])
def admin_approve(employer_id):
    # Security check again
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))

    try:
        conn = get_db()
        cur = conn.cursor()
        
        # Change their status to approved!
        cur.execute("UPDATE employers SET status = 'approved' WHERE id = %s", (employer_id,))
        
        conn.commit()
        cur.close()
        conn.close()
        
        flash("Employer approved successfully! They can now post jobs.", "success")
    except Exception as e:
        print("ADMIN APPROVE ERROR:", e)
        flash("Error approving employer.", "danger")

    return redirect(url_for("admin_dashboard"))

# --- 4. REJECT ACTION ---
@app.route("/admin/reject/<int:employer_id>", methods=["POST"])
def admin_reject(employer_id):
    # Security check: Must be admin
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))

    try:
        conn = get_db()
        cur = conn.cursor()
        
        # Completely remove the fake/rejected employer from the database
        cur.execute("DELETE FROM employers WHERE id = %s", (employer_id,))
        
        conn.commit()
        cur.close()
        conn.close()
        
        flash("Employer application rejected and permanently deleted.", "info")
    except Exception as e:
        print("ADMIN REJECT ERROR:", e)
        flash("Error rejecting employer.", "danger")

    return redirect(url_for("admin_dashboard"))

# --- Optional: ADMIN LOGOUT ---
@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    flash("Admin logged out successfully.", "info")
    return redirect(url_for("home"))

# ---------------- DASHBOARD ----------------

def login_required(fn):
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect("/login")
        return fn(*args, **kwargs)
    wrapper.__name__ = fn.__name__
    return wrapper

@app.route("/dashboard")
@login_required
def dashboard():

    user_id = session["user_id"]
    display_name = session.get("display_name", "")

    # ---------------- PROFILE CHECK ----------------
    profile_complete = is_profile_complete(user_id)

    # ---------------- INTERNSHIPS ----------------
    internships = []
    if profile_complete:
        internships = get_internship_recommendations(user_id,top_n=10)

    # ---------------- SCHOLARSHIPS ----------------
    scholarships = get_scholarship_recommendations(user_id,top_n=10)



    return render_template(
        "dashboard.html",
        profile_complete=profile_complete,
        internships=internships,
        scholarships=scholarships,
        display_name=display_name
    )


@app.route("/internships")
def internships():
    page = request.args.get("page", 1, type=int)
    PER_PAGE = 12
    offset = (page - 1) * PER_PAGE

    location = request.args.get("location", "").strip()
    source = request.args.get("source", "").strip()

    conn = None
    internships = []
    saved_ids = set()

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

        # Add WHERE only if filters exist
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)

        # FIX: Changed scraped_at back to created_at (Matches your earlier Supabase logic)
        sql += " ORDER BY created_at DESC, id DESC"

        # THEN pagination
        sql += " LIMIT %s OFFSET %s"
        params.extend([PER_PAGE, offset])
        
        cur.execute(sql, params)
        internships = cur.fetchall()

        # Fetch saved internships
        user_id = session.get("user_id")
        if user_id:
            cur.execute(
                """
                SELECT opportunity_id 
                FROM saved_opportunities
                WHERE user_id = %s
                AND opportunity_type = 'internship'
                """,
                (user_id,)
            )
            saved_ids = {int(row["opportunity_id"]) for row in cur.fetchall()}

        cur.close()
        conn.close()

    except Exception as e:
        print("DB ERROR:", e)

    return render_template(
        "internships.html",
        internships=internships,
        saved_ids=saved_ids,
        page=page,
        # PRO TIP: Pass the active filters back to the template so the search bars don't clear out!
        current_location=location, 
        current_source=source
    )

@app.route("/scholarships")
def scholarships():
    page = request.args.get("page", 1, type=int)
    search_query = request.args.get("search", "").strip()
    source_filter = request.args.get("source", "all").strip()

    PER_PAGE = 12
    offset = (page - 1) * PER_PAGE

    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # 1️⃣ Build the dynamic WHERE clause
        conditions = []
        params = []

        if search_query:
            # Assumes your table has 'title' and 'provider' columns. Adjust if needed!
            conditions.append("(title ILIKE %s OR provider ILIKE %s)")
            params.extend([f"%{search_query}%", f"%{search_query}%"])

        if source_filter and source_filter != "all":
            # Assumes your table has a 'source' column
            conditions.append("source ILIKE %s")
            params.append(f"%{source_filter}%")

        where_clause = ""
        if conditions:
            where_clause = " WHERE " + " AND ".join(conditions)

        # 2️⃣ Get total count (with filters applied!)
        count_sql = f"SELECT COUNT(*) FROM scholarships {where_clause}"
        cur.execute(count_sql, params)
        total_scholarships = cur.fetchone()["count"]

        total_pages = (total_scholarships + PER_PAGE - 1) // PER_PAGE

        # 3️⃣ Get paginated records (with filters applied!)
        data_sql = f"""
            SELECT *
            FROM scholarships
            {where_clause}
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """
        cur.execute(data_sql, params + [PER_PAGE, offset])
        scholarships = cur.fetchall()

        cur.close()
        conn.close()

        return render_template(
            "scholarships.html",
            scholarships=scholarships,
            page=page,
            total_pages=total_pages,
            # Send these back so the HTML remembers what the user selected
            current_search=search_query,
            current_source=source_filter
        )

    except Exception as e:
        print("SCHOLARSHIP ERROR:", e)
        return "Error loading scholarships", 500
@app.route("/internships/<int:internship_id>")
def internship_details(internship_id):

    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute(
            "SELECT * FROM internships WHERE id = %s",
            (internship_id,)
        )

        internship = cur.fetchone()

        cur.close()
        conn.close()

        if not internship:
            # This instantly stops the code and triggers your custom 404 error.html!
            abort(404)

        return render_template(
            "internship_details.html",
            internship=internship
        )

    except Exception as e:
            print("ERROR:", e)
            # If the database actually breaks, trigger a 500 error
            abort(500)

@app.route("/scholarships/<int:scholarship_id>")
def scholarship_details(scholarship_id):

    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute(
            "SELECT * FROM scholarships WHERE id = %s",
            (scholarship_id,)
        )

        scholarship = cur.fetchone()

        cur.close()
        conn.close()

        if not scholarship:
            # This instantly stops the code and triggers your custom 404 error.html!
            abort(404)

        return render_template(
            "scholarship_details.html",
            scholarship=scholarship
        )

        
    except Exception as e:
            print("ERROR:", e)
            # If the database actually breaks, trigger a 500 error
            abort(500)

@app.route("/profile/setup", methods=["GET", "POST"])
@login_required
def profile_setup():
    user_id = session["user_id"]

    # ---------- SAVE / UPDATE PROFILE ----------
    if request.method == "POST":
        print("RAW DATA RECEIVED:", request.get_json())

        try:
            data = request.get_json()

            from validators.profile_validator import validate_profile_payload
            from services.profile_service import upsert_profile

            profile, skills, interests = validate_profile_payload(data)
            upsert_profile(user_id, profile, skills, interests)

            flash("Profile updated successfully!", "success")

            return {
                "status": "OK",
                "redirect_url": url_for("dashboard")
            }, 200

        except Exception as e:
            print("PROFILE ERROR:", e)
            return {"error": str(e)}, 400

    # ---------- LOAD EXISTING PROFILE ----------
    

    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # -------- profile --------
    cur.execute(
        "SELECT * FROM user_profiles WHERE user_id = %s",
        (user_id,)
    )
    profile = cur.fetchone()   # dict or None

    # -------- skills --------
    cur.execute(
        "SELECT skill FROM user_skills WHERE user_id = %s",
        (user_id,)
    )
    skills = [r["skill"] for r in cur.fetchall()]

    # -------- interests --------
    cur.execute(
        "SELECT interest FROM user_interests WHERE user_id = %s",
        (user_id,)
    )
    interests = [r["interest"] for r in cur.fetchall()]

    # -------- email --------
    cur.execute(
        "SELECT email FROM users WHERE id = %s",
        (user_id,)
    )
    email_row = cur.fetchone()
    email = email_row["email"] if email_row else "Error"
    print(email)

    cur.close()
    conn.close()

    return render_template(
        "profile_setup.html",
        profile=profile,
        skills=", ".join(skills),
        interests=", ".join(interests),
        email=email
    )


#Saved Opportunities
@app.route("/save", methods=["POST"])
@login_required
def save_opportunity():
    user_id = session["user_id"]
    data = request.get_json()

    opportunity_id = data["opportunity_id"]
    opportunity_type = data["opportunity_type"]

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
    cur.close()
    conn.close()

    return {"status": "SAVED"}, 200

#saved page route
@app.route("/saved")
@login_required
def saved_page():
    user_id = session["user_id"]

    conn = get_db()
    cur = conn.cursor()

    # Saved internships
    cur.execute(
        """
        SELECT i.*
        FROM saved_opportunities s
        JOIN internships i ON i.id = s.opportunity_id
        WHERE s.user_id = %s
          AND s.opportunity_type = 'internship'
        """,
        (user_id,)
    )
    internships = cur.fetchall()
    cols_i = [d[0] for d in cur.description]
    internships = [dict(zip(cols_i, r)) for r in internships]

    # # Saved scholarships
    # cur.execute(
    #     """
    #     SELECT sc.*
    #     FROM saved_opportunities s
    #     JOIN scholarships sc ON sc.id = s.opportunity_id
    #     WHERE s.user_id = %s
    #       AND s.opportunity_type = 'scholarship'
    #     """,
    #     (user_id,)
    # )
    # scholarships = cur.fetchall()
    # cols_s = [d[0] for d in cur.description]
    # scholarships = [dict(zip(cols_s, r)) for r in scholarships]

    scholarships=[]

    cur.close()
    conn.close()

    return render_template(
        "saved.html",
        internships=internships,
        scholarships=scholarships
    )

#Unsave route
@app.route("/unsave", methods=["POST"])
@login_required
def unsave_opportunity():
    user_id = session["user_id"]
    data = request.get_json()

    opportunity_id = data["opportunity_id"]
    opportunity_type = data["opportunity_type"]

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        DELETE FROM saved_opportunities
        WHERE user_id = %s
          AND opportunity_id = %s
          AND opportunity_type = %s
        """,
        (user_id, opportunity_id, opportunity_type)
    )

    conn.commit()
    cur.close()
    conn.close()

    return {"status": "UNSAVED"}, 200

#Route for FAQS
@app.route("/faqs")
def faqs():
    return render_template("faqs.html")

#Route for About Us
@app.route("/about")
def about_us():
    return render_template("about_us.html")

#Route for Privacy page
@app.route("/privacy")
def privacy():
    return render_template("privacy.html") 

# Route for Feedback Form
@app.route("/feedback")
def feedback():
    return render_template("feedback.html")


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

    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO feedback 
            (name, email, satisfaction, relevance, used_type, time_saved,
             ease, overall_experience, improve, recommend)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            data["name"],
            data["email"],
            data["satisfaction"],
            data["relevance"],
            data["used_type"],
            data["time_saved"],
            data["ease"],
            data["overall_experience"],
            data["improve"],
            data["recommend"]
        ))

        conn.commit()
        cur.close()
        conn.close()

        flash("✅ Thank you! Your feedback has been submitted.", "feedback_success")
        return redirect(url_for("feedback"))

    except Exception as e:
        print("FEEDBACK ERROR:", e)
        return "An error occurred while saving feedback. Check console.", 500


# Route for contacts
@app.route("/contact")
def contacts():
    return render_template("contacts.html")


@app.route("/send-message", methods=["POST"])
def send_message():

    data = {
        "name": request.form.get("name"),
        "email": request.form.get("email"),
        "category": request.form.get("category"),
        "message": request.form.get("message")
    }

    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO contact_messages 
            (name, email, category, message)
            VALUES (%s, %s, %s, %s)
        """, (
            data["name"],
            data["email"],
            data["category"],
            data["message"]
        ))

        conn.commit()
        cur.close()
        conn.close()

        flash("Your message has been sent successfully!", "contact_success")
        return redirect(url_for("contacts"))

    except Exception as e:
        print("CONTACT MESSAGE ERROR:", e)
        return "An error occurred.", 500

# Documentation link
@app.route('/docs')
def download_documentation():
    # Adjust 'static/docs' to match your actual folder path
    directory = os.path.join(app.root_path, 'static', 'docs')
    return send_from_directory(directory, 'Documentation.pdf')

from flask import make_response
from datetime import datetime

@app.route('/sitemap.xml', methods=['GET'])
def sitemap():
    """Generates a dynamic XML sitemap for Google Search Console."""
    
    # IMPORTANT: Change this to your actual production domain when you deploy!
    base_url = "https://smartintern-portal.onrender.com" 
    
    # 1. Define your public static routes
    # Notice we do NOT include /dashboard, /profile, or /admin because Google shouldn't see those!
    static_urls = [
        "/", 
        "/about", 
        "/contact", 
        "/faqs", 
        "/privacy", 
        "/internships", 
        "/scholarships", 
        "/employer/info",
        "/login",
        "/signup"
    ]
    
    # 2. Start building the XML string
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    
    # 3. Loop through static routes and add them to the XML
    today = datetime.today().strftime('%Y-%m-%d')
    for url in static_urls:
        xml += '  <url>\n'
        xml += f'    <loc>{base_url}{url}</loc>\n'
        xml += f'    <lastmod>{today}</lastmod>\n'
        xml += '    <changefreq>weekly</changefreq>\n'
        xml += '    <priority>0.8</priority>\n'
        xml += '  </url>\n'
        
    xml += '</urlset>'
    
    # 4. Return as a proper XML file
    response = make_response(xml)
    response.headers["Content-Type"] = "application/xml"
    
    return response

# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# ==========================================
# GLOBAL ERROR SAFETY NET
# ==========================================

# 1. Catch ALL Standard Web Errors (404 Not Found, 403 Forbidden, 405 Bad Method, etc.)
@app.errorhandler(HTTPException)
def handle_http_exception(e):
    """Handles all standard HTTP routing and access errors dynamically."""
    return render_template(
        "error.html", 
        error_code=e.code, 
        error_message=e.name
    ), e.code

# 2. Catch ALL Unknown Python/Database Crashes (The Ultimate 500 Catch-All)
@app.errorhandler(Exception)
def handle_unknown_exception(e):
    """
    Catches ANY unhandled Python error, database crash, or logic failure.
    Prevents the app from showing raw code to the user.
    """
    # 1. Print the actual error to your terminal so YOU can fix it later
    print(f"🚨 CRITICAL UNHANDLED ERROR: {e}")
    
    # 2. Rollback the database just in case a transaction got stuck
    try:
        conn = get_db()
        conn.rollback()
        conn.close()
    except:
        pass # If the DB is completely dead, just ignore and show the error page

    # 3. Show the user a safe, generic error page
    return render_template(
        "error.html", 
        error_code=500, 
        error_message="Internal Server Error"
    ), 500
# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(debug=True)