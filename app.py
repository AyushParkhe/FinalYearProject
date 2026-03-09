from flask import Flask, render_template, request, redirect, session, flash, url_for, send_from_directory, abort, jsonify, make_response
from authlib.integrations.flask_client import OAuth, OAuthError
from dotenv import load_dotenv
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.exceptions import HTTPException
from datetime import datetime
from supabase import create_client, ClientOptions
import hashlib
import os

from utils.security import validate_password, hash_password, check_password
from utils.profile_utils import is_profile_complete


# ============================================================
# LOAD ENVIRONMENT VARIABLES
# ============================================================
load_dotenv()

app = Flask(__name__)

# 1. Security Key
app.secret_key = os.getenv("SECRET_KEY", "your-dev-fallback-secret")

# 2. Render Proxy Fix (Expanded for Render's specific load balancer headers)
app.wsgi_app = ProxyFix(
    app.wsgi_app, 
    x_for=1, 
    x_proto=1, 
    x_host=1, 
    x_prefix=1
)

# 3. Secure OAuth Cookie Settings
app.config["PREFERRED_URL_SCHEME"] = "https"
app.config["SESSION_COOKIE_SECURE"] = True

from flask import request

@app.after_request
def add_header(response):
    """
    Forces the browser to never cache HTML pages (prevents Back-button logout bypass).
    Leaves static files (CSS/JS/Images) alone so the app stays lightning fast!
    """
    # Only apply the no-cache rules if the response is an HTML web page
    if 'text/html' in response.headers.get('Content-Type', ''):
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '-1'
        
    return response


# ============================================================
# SUPABASE CLIENT SETUP
# Single client used throughout the app for all DB operations.
# Uses the SERVICE KEY for elevated (admin-level) access.
# ============================================================
supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY"),
    options=ClientOptions(postgrest_client_timeout=60, storage_client_timeout=60)
)


# ============================================================
# OAUTH SETUP  (Google Login)
# ============================================================
oauth = OAuth(app)

google = oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"}
)


# ============================================================
# LOGIN REQUIRED DECORATOR
# Wraps any route that needs the user to be authenticated.
# Redirects to /login if user_id is not in session.
# ============================================================
def login_required(fn):
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect("/login")
        return fn(*args, **kwargs)
    wrapper.__name__ = fn.__name__
    return wrapper


# ============================================================
# HOME
# ============================================================
@app.route("/")
def home():
    return render_template("home.html")


# ============================================================
# LOGIN  (local username + password)
# 1. Verify credentials against users table
# 2. Fetch display_name for the session
# ============================================================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].lower()
        password = request.form["password"]

        try:
            # -- Step 1: Fetch user by username (local auth only, must be active) --
            response = supabase.table("users") \
                .select("id, password_hash") \
                .eq("username", username) \
                .eq("auth_provider", "local") \
                .eq("is_active", True) \
                .execute()

            users = response.data
            user = users[0] if users else None

            if not user or not check_password(password, user["password_hash"]):
                flash("Invalid credentials", "login_error")
                return redirect("/login")

            user_id = str(user["id"])
            session["user_id"] = user_id

        except Exception as e:
            print(f"LOGIN ERROR (credentials fetch): {e}")
            flash("An error occurred. Please try again.", "login_error")
            return redirect("/login")

        try:
            # -- Step 2: Fetch display_name for the welcome message --
            name_response = supabase.table("users") \
                .select("display_name") \
                .eq("id", user_id) \
                .execute()

            name_row = name_response.data[0] if name_response.data else {}
            display_name = name_row.get("display_name", "")
            display_name = display_name.split()[0].capitalize() if display_name else ""

            session["display_name"] = display_name
            session["auth_provider"] = "local"

        except Exception as e:
            print(f"LOGIN ERROR (display name fetch): {e}")
            # Non-critical — still let them in with a blank display name
            session["display_name"] = ""
            session["auth_provider"] = "local"

        return redirect(url_for("dashboard"))

    return render_template("login.html")


# ============================================================
# SIGNUP  (local account creation)
# Validates password strength, checks for duplicate username,
# then inserts the new user into the users table.
# ============================================================
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"].lower()
        password = request.form["password"]

        # Enforce password policy (length, uppercase, lowercase, digit)
        if not validate_password(password):
            flash(
                "Password must be at least 8 characters long and include uppercase, lowercase, and a number.",
                "signup_error"
            )
            return redirect("/signup")

        try:
            # -- Check if username already exists --
            existing = supabase.table("users") \
                .select("id") \
                .eq("username", username) \
                .execute()

            if existing.data:
                flash("Username already exists.", "signup_error")
                return redirect("/signup")

            # -- Insert new user --
            insert_response = supabase.table("users").insert({
                "username": username,
                "display_name": username,
                "password_hash": hash_password(password),
                "auth_provider": "local"
            }).execute()

            new_user = insert_response.data[0] if insert_response.data else None
            if not new_user:
                raise Exception("Insert returned no data")

            user_id = str(new_user["id"])
            display_name = new_user.get("display_name", username)
            display_name = display_name.split()[0].capitalize()

            session["user_id"] = user_id
            session["display_name"] = display_name

        except Exception as e:
            print(f"SIGNUP ERROR: {e}")
            flash("An error occurred during signup. Please try again.", "signup_error")
            return redirect("/signup")

        return redirect("/dashboard")

    return render_template("signup.html")


# ============================================================
# GOOGLE OAUTH  — Step 1: Redirect to Google
# ============================================================
@app.route("/login/google")
def login_google():
    redirect_uri = url_for("google_callback", _external=True)
    return google.authorize_redirect(redirect_uri)


# ============================================================
# GOOGLE OAUTH  — Step 2: Handle callback
# Looks up or creates the user in the DB, then sets session.
# ============================================================
@app.route("/auth/google/callback")
def google_callback():
    try:
        token = google.authorize_access_token()
    except Exception as e:
        print(f"⚠️ OAuth Error: {e}")
        flash("Session expired or invalid. Please try logging in again.")
        return redirect(url_for('login'))

    user_info = token.get("userinfo")
    if not user_info:
        user_info = google.get("userinfo").json()

    email = user_info["email"]
    raw_name = user_info.get("name") or email.split("@")[0]
    display_name = raw_name.split()[0]

    try:
        # -- Check if user already exists by email --
        response = supabase.table("users") \
            .select("*") \
            .eq("email", email) \
            .execute()
        existing_users = response.data

        if existing_users:
            # Returning Google user — just log them in
            user = existing_users[0]
            user_id = user["id"]
            final_display_name = user.get("display_name") or display_name
            print(f"✅ Existing user logged in: {email}")
        else:
            # New Google user — create their account
            insert_response = supabase.table("users").insert({
                "email": email,
                "display_name": display_name,
                "auth_provider": "google"
            }).execute()

            if insert_response.data:
                user = insert_response.data[0]
                user_id = user["id"]
                final_display_name = user["display_name"]
                print(f"🎉 New user created: {email}")
            else:
                raise Exception("Failed to insert user into database")

        # -- Set session --
        session.permanent = True
        session["user_id"] = str(user_id)
        session["display_name"] = final_display_name.capitalize()
        session["email"] = email

        return redirect("/dashboard")

    except Exception as e:
        print(f"❌ Google Callback DB Error: {e}")
        flash("An error occurred during login. Please try again.")
        return redirect(url_for('login'))


# ============================================================
# EMPLOYER LANDING PAGE
# Redirects already-logged-in employers straight to dashboard.
# ============================================================
@app.route("/employer/info")
def employer_landing():
    if "employer_id" in session:
        return redirect(url_for("employer_dashboard"))
    return render_template("employer_landing.html")


# ============================================================
# EMPLOYER REGISTER
# Creates a new employer account with status = 'pending'.
# Admin must approve before the employer can post jobs.
# ============================================================
@app.route("/employer/register", methods=["GET", "POST"])
def employer_register():
    if request.method == "POST":
        company_name = request.form.get("company_name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        cin_number = request.form.get("cin_number", "").strip()

        try:
            supabase.table("employers").insert({
                "company_name": company_name,
                "email": email,
                "password_hash": hash_password(password),
                "cin_number": cin_number
            }).execute()

            flash("Registration successful! Your account is pending admin approval.", "success")
            return redirect(url_for("employer_register.html"))

        except Exception as e:
            print(f"EMPLOYER REGISTRATION ERROR: {e}")
            flash("Error: Email might already be registered.", "danger")
            return redirect(url_for("employer_register"))

    return render_template("employer_register.html")


# ============================================================
# EMPLOYER LOGIN
# Verifies email + password, sets employer session vars.
# ============================================================
@app.route("/employer/login", methods=["GET", "POST"])
def employer_login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        try:
            response = supabase.table("employers") \
                .select("id, company_name, password_hash, status") \
                .eq("email", email) \
                .execute()

            employers = response.data
            employer = employers[0] if employers else None

            if employer and check_password(password, employer["password_hash"]):
                session["employer_id"] = employer["id"]
                session["employer_name"] = employer["company_name"]
                session["employer_status"] = employer["status"]
                flash(f"Welcome back, {employer['company_name']}!", "success")
                return redirect(url_for("employer_dashboard"))
            elif employer:
                flash("Invalid email or password.", "danger")
            else:
                flash("No employer account found with that email.", "danger")

        except Exception as e:
            print(f"EMPLOYER LOGIN ERROR: {e}")
            flash("An error occurred during login. Please try again.", "danger")

    return render_template("employer_login.html")


# ============================================================
# EMPLOYER DASHBOARD
# Shows the employer's posted jobs (only if approved).
# ============================================================
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
        try:
            # Fetch all internships posted by this employer
            response = supabase.table("internships") \
                .select("id, title, location, posted_on") \
                .eq("employer_id", employer_id) \
                .order("posted_on", desc=True) \
                .execute()

            posted_jobs = response.data or []

        except Exception as e:
            print(f"EMPLOYER DASHBOARD ERROR: {e}")
            flash("Could not load your posted jobs.", "danger")

    return render_template(
        "employer_dashboard.html",
        status=employer_status,
        company_name=employer_name,
        jobs=posted_jobs
    )


# ============================================================
# POST INTERNSHIP
# Employer creates a new internship listing.
# Requires account to be approved.
# ============================================================
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

        # Ensure apply_link has a valid URL scheme
        if apply_link and not apply_link.startswith(('http://', 'https://')):
            apply_link = 'https://' + apply_link

        employer_id = session["employer_id"]
        company_name = session.get("employer_name", "Unknown Company")
        posted_on = datetime.today().strftime('%Y-%m-%d')

        # Hash title+company+location to detect duplicates
        content_hash = hashlib.sha256(
            f"{title}_{company_name}_{location}".encode('utf-8')
        ).hexdigest()

        try:
            supabase.table("internships").insert({
                "title": title,
                "organization": company_name,
                "location": location,
                "duration": duration,
                "stipend": stipend,
                "skills_final": skills,
                "posted_on": posted_on,
                "type": "Internship",
                "source": "SmartIntern Direct",
                "apply_link": apply_link,
                "content_hash": content_hash,
                "employer_id": employer_id
            }).execute()

            flash("Internship posted successfully!", "success")
            return redirect(url_for("employer_dashboard"))

        except Exception as e:
            print(f"POST INTERNSHIP ERROR: {e}")
            flash("An error occurred while posting. Please try again.", "danger")

    return render_template("post_internship.html")


# ============================================================
# EDIT INTERNSHIP
# Employer can update an existing internship they own.
# ============================================================
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

        try:
            # Update only rows owned by this employer (security check via employer_id)
            supabase.table("internships") \
                .update({
                    "title": title,
                    "location": location,
                    "duration": duration,
                    "stipend": stipend,
                    "skills_final": skills,
                    "apply_link": apply_link
                }) \
                .eq("id", job_id) \
                .eq("employer_id", employer_id) \
                .execute()

            flash("Internship updated successfully!", "success")
            return redirect(url_for("employer_dashboard"))

        except Exception as e:
            print(f"EDIT INTERNSHIP ERROR: {e}")
            flash("Error updating internship.", "danger")

    # GET: load existing internship details for the edit form
    try:
        response = supabase.table("internships") \
            .select("id, title, location, duration, stipend, skills_final, apply_link") \
            .eq("id", job_id) \
            .eq("employer_id", employer_id) \
            .execute()

        job = response.data[0] if response.data else None

        if not job:
            flash("Job not found or unauthorized.", "danger")
            return redirect(url_for("employer_dashboard"))

        return render_template("edit_internship.html", job=job)

    except Exception as e:
        print(f"FETCH EDIT ERROR: {e}")
        flash("Error loading job details.", "danger")
        return redirect(url_for("employer_dashboard"))


# ============================================================
# DELETE INTERNSHIP
# Permanently removes an internship owned by this employer.
# ============================================================
@app.route("/employer/delete-internship/<int:job_id>", methods=["POST"])
def delete_internship(job_id):
    if "employer_id" not in session:
        return redirect(url_for("employer_login"))

    try:
        supabase.table("internships") \
            .delete() \
            .eq("id", job_id) \
            .eq("employer_id", session["employer_id"]) \
            .execute()

        flash("Internship deleted permanently.", "info")

    except Exception as e:
        print(f"DELETE INTERNSHIP ERROR: {e}")
        flash("Error deleting internship.", "danger")

    return redirect(url_for("employer_dashboard"))


# ============================================================
# EMPLOYER LOGOUT
# ============================================================
@app.route("/employer/logout")
def employer_logout():
    session.pop("employer_id", None)
    return redirect(url_for("employer_login"))


# ============================================================
# ADMIN LOGIN
# Simple password-only admin gate (no user account needed).
# ============================================================
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


# ============================================================
# ADMIN DASHBOARD
# Lists all pending and approved employer accounts.
# ============================================================
@app.route("/admin/dashboard")
def admin_dashboard():
    import traceback as _tb

    if not session.get("is_admin"):
        flash("Unauthorized access. Please log in as admin.", "danger")
        return redirect(url_for("admin_login"))

    pending_employers = []
    approved_employers = []

    try:
        # -- Fetch employers awaiting approval --
        pending_response = supabase.table("employers") \
            .select("id, company_name, email, cin_number, created_at") \
            .eq("status", "pending") \
            .order("created_at", desc=False) \
            .execute()
        pending_employers = pending_response.data or []

        # -- Fetch already-approved employers --
        approved_response = supabase.table("employers") \
            .select("id, company_name, email, cin_number, created_at") \
            .eq("status", "approved") \
            .order("created_at", desc=True) \
            .execute()
        approved_employers = approved_response.data or []

    except Exception as e:
        print(f"ADMIN DASHBOARD DB ERROR: {e}")
        print(_tb.format_exc())
        flash("Could not load employer data.", "danger")

    try:
        return render_template(
            "admin_dashboard.html",
            employers=pending_employers,
            approved_employers=approved_employers
        )
    except Exception as e:
        print(f"ADMIN DASHBOARD TEMPLATE ERROR: {e}")
        print(_tb.format_exc())
        return f"<pre>Template error: {e}\n\n{_tb.format_exc()}</pre>", 500


# ============================================================
# ADMIN APPROVE EMPLOYER
# Sets employer status to 'approved' so they can post jobs.
# ============================================================
@app.route("/admin/approve/<int:employer_id>", methods=["POST"])
def admin_approve(employer_id):
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))

    try:
        supabase.table("employers") \
            .update({"status": "approved"}) \
            .eq("id", employer_id) \
            .execute()

        flash("Employer approved successfully! They can now post jobs.", "success")

    except Exception as e:
        print(f"ADMIN APPROVE ERROR: {e}")
        flash("Error approving employer.", "danger")

    return redirect(url_for("admin_dashboard"))


# ============================================================
# ADMIN REJECT EMPLOYER
# Permanently deletes a pending employer application.
# ============================================================
@app.route("/admin/reject/<int:employer_id>", methods=["POST"])
def admin_reject(employer_id):
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))

    try:
        supabase.table("employers") \
            .delete() \
            .eq("id", employer_id) \
            .execute()

        flash("Employer application rejected and permanently deleted.", "info")

    except Exception as e:
        print(f"ADMIN REJECT ERROR: {e}")
        flash("Error rejecting employer.", "danger")

    return redirect(url_for("admin_dashboard"))


# ============================================================
# ADMIN LOGOUT
# ============================================================
@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    flash("Admin logged out successfully.", "info")
    return redirect(url_for("home"))


# ============================================================
# USER DASHBOARD
# Shows personalised content; checks if profile is complete
# to decide whether to show AI recommendations.
# ============================================================
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


# ============================================================
# RECOMMENDATIONS API
# Returns AI-matched internships (if profile is complete)
# and scholarships as JSON for async dashboard loading.
# ============================================================
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


# ============================================================
# INTERNSHIPS LIST
# Paginated list with optional location and source filters.
# Also fetches which IDs the logged-in user has saved.
# ============================================================
@app.route("/internships")
@login_required

def internships():
    page = request.args.get("page", 1, type=int)
    PER_PAGE = 12
    offset = (page - 1) * PER_PAGE
    location = request.args.get("location", "").strip()
    source = request.args.get("source", "").strip()

    internship_list = []
    saved_ids = set()

    try:
        # Build the query with optional filters
        query = supabase.table("internships").select("*")

        if location:
            query = query.ilike("location", f"%{location}%")
        if source:
            query = query.ilike("source", f"%{source}%")

        # Order by newest first, then paginate
        response = query \
            .order("created_at", desc=True) \
            .order("id", desc=True) \
            .range(offset, offset + PER_PAGE - 1) \
            .execute()

        internship_list = response.data or []

        # Fetch saved opportunity IDs for the logged-in user
        user_id = session.get("user_id")
        if user_id:
            saved_response = supabase.table("saved_opportunities") \
                .select("opportunity_id") \
                .eq("user_id", user_id) \
                .eq("opportunity_type", "internship") \
                .execute()

            saved_ids = {int(row["opportunity_id"]) for row in (saved_response.data or [])}

    except Exception as e:
        print(f"INTERNSHIPS LIST ERROR: {e}")

    return render_template(
        "internships.html",
        internships=internship_list,
        saved_ids=saved_ids,
        page=page,
        current_location=location,
        current_source=source
    )


# ============================================================
# SCHOLARSHIPS LIST
# Paginated list with optional search and source filters.
# ============================================================
@app.route("/scholarships")
@login_required

def scholarships():
    page = request.args.get("page", 1, type=int)
    search_query = request.args.get("search", "").strip()
    source_filter = request.args.get("source", "all").strip()
    PER_PAGE = 12
    offset = (page - 1) * PER_PAGE

    scholarship_list = []
    total_pages = 0

    try:
        # Build filtered query for count
        count_query = supabase.table("scholarships").select("id", count="exact")

        if search_query:
            count_query = count_query.or_(
                f"title.ilike.%{search_query}%,provider.ilike.%{search_query}%"
            )
        if source_filter and source_filter != "all":
            count_query = count_query.ilike("source", f"%{source_filter}%")

        count_response = count_query.execute()
        total_scholarships = count_response.count or 0
        total_pages = (total_scholarships + PER_PAGE - 1) // PER_PAGE

        # Build filtered query for actual rows
        data_query = supabase.table("scholarships").select("*")

        if search_query:
            data_query = data_query.or_(
                f"title.ilike.%{search_query}%,provider.ilike.%{search_query}%"
            )
        if source_filter and source_filter != "all":
            data_query = data_query.ilike("source", f"%{source_filter}%")

        data_response = data_query \
            .order("created_at", desc=True) \
            .range(offset, offset + PER_PAGE - 1) \
            .execute()

        scholarship_list = data_response.data or []

    except Exception as e:
        print(f"SCHOLARSHIPS LIST ERROR: {e}")

    return render_template(
        "scholarships.html",
        scholarships=scholarship_list,
        page=page,
        total_pages=total_pages,
        current_search=search_query,
        current_source=source_filter
    )


# ============================================================
# INTERNSHIP DETAIL PAGE
# Fetches a single internship by its ID.
# ============================================================
@app.route("/internships/<int:internship_id>")
@login_required

def internship_details(internship_id):
    try:
        response = supabase.table("internships") \
            .select("*") \
            .eq("id", internship_id) \
            .execute()

        internship = response.data[0] if response.data else None

        if not internship:
            abort(404)

        return render_template("internship_details.html", internship=internship)

    except HTTPException:
        raise
    except Exception as e:
        print(f"INTERNSHIP DETAIL ERROR: {e}")
        abort(500)


# ============================================================
# SCHOLARSHIP DETAIL PAGE
# Fetches a single scholarship by its ID.
# ============================================================
@app.route("/scholarships/<int:scholarship_id>")
@login_required

def scholarship_details(scholarship_id):
    try:
        response = supabase.table("scholarships") \
            .select("*") \
            .eq("id", scholarship_id) \
            .execute()

        scholarship = response.data[0] if response.data else None

        if not scholarship:
            abort(404)

        return render_template("scholarship_details.html", scholarship=scholarship)

    except HTTPException:
        raise
    except Exception as e:
        print(f"SCHOLARSHIP DETAIL ERROR: {e}")
        abort(500)


# ============================================================
# PROFILE SETUP
# GET  – loads existing profile, skills, interests, and email
# POST – validates and saves (upsert) profile data via service
# ============================================================
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

    # GET: load existing profile data to pre-fill the form
    profile = None
    skills = []
    interests = []
    email = "Error"

    try:
        # Fetch profile row
        profile_response = supabase.table("user_profiles") \
            .select("*") \
            .eq("user_id", user_id) \
            .execute()
        profile = profile_response.data[0] if profile_response.data else None

        # Fetch skills list
        skills_response = supabase.table("user_skills") \
            .select("skill") \
            .eq("user_id", user_id) \
            .execute()
        skills = [r["skill"] for r in (skills_response.data or [])]

        # Fetch interests list
        interests_response = supabase.table("user_interests") \
            .select("interest") \
            .eq("user_id", user_id) \
            .execute()
        interests = [r["interest"] for r in (interests_response.data or [])]

        # Fetch email for display
        email_response = supabase.table("users") \
            .select("email") \
            .eq("id", user_id) \
            .execute()
        email_row = email_response.data[0] if email_response.data else {}
        email = email_row.get("email", "Error")

    except Exception as e:
        print(f"PROFILE LOAD ERROR: {e}")

    return render_template(
        "profile_setup.html",
        profile=profile,
        skills=", ".join(skills),
        interests=", ".join(interests),
        email=email
    )


# ============================================================
# SAVE OPPORTUNITY
# Inserts a record into saved_opportunities (idempotent).
# ============================================================
@app.route("/save", methods=["POST"])

@login_required
def save_opportunity():
    user_id = session["user_id"]
    data = request.get_json()
    opportunity_id = data["opportunity_id"]
    opportunity_type = data["opportunity_type"]

    try:
        # upsert=True / ON CONFLICT DO NOTHING equivalent
        supabase.table("saved_opportunities").upsert({
            "user_id": user_id,
            "opportunity_id": opportunity_id,
            "opportunity_type": opportunity_type
        }, on_conflict="user_id,opportunity_id,opportunity_type").execute()

    except Exception as e:
        print(f"SAVE OPPORTUNITY ERROR: {e}")
        return {"status": "ERROR"}, 500

    return {"status": "SAVED"}, 200


# ============================================================
# SAVED PAGE
# Shows all internships (and scholarships) the user saved.
# ============================================================
@app.route("/saved")
@login_required
def saved_page():
    user_id = session["user_id"]
    internships = []
    scholarships = []

    try:
        # Step 1: Get the saved internship IDs for this user
        saved_response = supabase.table("saved_opportunities") \
            .select("opportunity_id") \
            .eq("user_id", user_id) \
            .eq("opportunity_type", "internship") \
            .execute()

        saved_ids = [row["opportunity_id"] for row in (saved_response.data or [])]

        # Step 2: Fetch the full internship details for those IDs
        if saved_ids:
            internships_response = supabase.table("internships") \
                .select("*") \
                .in_("id", saved_ids) \
                .execute()
            internships = internships_response.data or []

    except Exception as e:
        print(f"SAVED PAGE ERROR: {e}")

    return render_template("saved.html", internships=internships, scholarships=scholarships)


# ============================================================
# UNSAVE OPPORTUNITY
# Removes a record from saved_opportunities.
# ============================================================
@app.route("/unsave", methods=["POST"])
@login_required
def unsave_opportunity():
    user_id = session["user_id"]
    data = request.get_json()
    opportunity_id = data["opportunity_id"]
    opportunity_type = data["opportunity_type"]

    try:
        supabase.table("saved_opportunities") \
            .delete() \
            .eq("user_id", user_id) \
            .eq("opportunity_id", opportunity_id) \
            .eq("opportunity_type", opportunity_type) \
            .execute()

    except Exception as e:
        print(f"UNSAVE ERROR: {e}")
        return {"status": "ERROR"}, 500

    return {"status": "UNSAVED"}, 200



# ============================================================
# STATIC PAGES
# ============================================================
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
    # Pre-fill form fields if the user is logged in
    user_name = session.get("display_name", "")
    user_email = session.get("email", "")
    return render_template(
        "feedback.html",
        prefill_name=user_name,
        prefill_email=user_email
    )


# ============================================================
# SUBMIT FEEDBACK
# Saves user-submitted feedback form data.
# ============================================================
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
        supabase.table("feedback").insert(data).execute()
        flash("✅ Thank you! Your feedback has been submitted.", "feedback_success")
        return redirect(url_for("feedback"))

    except Exception as e:
        print(f"FEEDBACK ERROR: {e}")
        return "An error occurred while saving feedback. Check console.", 500


# ============================================================
# CONTACT  —  page render + message submission
# ============================================================
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

    try:
        supabase.table("contact_messages").insert(data).execute()
        flash("Your message has been sent successfully!", "contact_success")
        return redirect(url_for("contacts"))

    except Exception as e:
        print(f"CONTACT MESSAGE ERROR: {e}")
        return "An error occurred.", 500


# ============================================================
# DOCS  —  serve the PDF documentation file
# ============================================================
@app.route('/docs')
def download_documentation():
    directory = os.path.join(app.root_path, 'static', 'docs')
    return send_from_directory(directory, 'Documentation.pdf')


# ============================================================
# SITEMAP  —  XML sitemap for SEO crawlers
# ============================================================
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


# ============================================================
# LOGOUT  —  clears the entire session
# ============================================================
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# ============================================================
# GLOBAL ERROR HANDLERS
# Renders a user-friendly error page for HTTP errors and
# any unexpected exceptions that bubble up to Flask.
# ============================================================
@app.errorhandler(HTTPException)
def handle_http_exception(e):
    return render_template("error.html", error_code=e.code, error_message=e.name), e.code


@app.errorhandler(Exception)
def handle_unknown_exception(e):
    import traceback
    print(f"🚨 CRITICAL UNHANDLED ERROR: {e}")
    print(traceback.format_exc())  # prints the full stack trace to terminal
    return render_template("error.html", error_code=500, error_message="Internal Server Error"), 500


# ============================================================
# RUN  (dev server only — use gunicorn/uwsgi in production)
# ============================================================
if __name__ == "__main__":
    app.run(debug=True)