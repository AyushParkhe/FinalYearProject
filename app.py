from flask import Flask, render_template, request, redirect, session, flash, url_for
from psycopg2.extras import RealDictCursor
from authlib.integrations.flask_client import OAuth,OAuthError
from dotenv import load_dotenv
import os
import psycopg2
from utils.db import get_db
from utils.security import validate_password, hash_password, check_password
from utils.supabase_client import supabase
from utils.profile_utils import is_profile_complete
from utils.recommendation_utils import get_internship_recommendations


def fetch_all_internships():
    response = (
        supabase
        .table("internships")
        .select("*")
        .order("created_at", desc=True)
        .execute()
    )
    return response.data


# ---------------- LOAD ENV ----------------
load_dotenv()
app = Flask(__name__)
app.secret_key = "dev-secret"

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
            flash("Invalid credentials")
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
    # FIX: Get display_name from session (set in login/signup)
    display_name = session.get("display_name", "")
    # # print(user_id)
    # print(display_name)

    # 🔐 REAL PROFILE CHECK
    profile_complete = is_profile_complete(user_id)

    internships = []
    if profile_complete:
        internships = get_internship_recommendations(user_id)
    # print("RECOMMENDED INTERNSHIPS:", internships)

    # ---------------- UPCOMING DEADLINES (ALWAYS SHOWN) ----------------
    deadlines = [
        "Software Development Intern — 25 Jan",
        "Merit Scholarship — 28 Jan",
        "Backend Intern — 2 Feb"
    ]

    return render_template(
        "dashboard.html",
        profile_complete=profile_complete,
        internships=internships,
        deadlines=deadlines,
        display_name=display_name
    )


#View all internships
@app.route("/internships")
def internships():
    page = request.args.get("page", 1, type=int)
    PER_PAGE = 12
    start = (page - 1) * PER_PAGE
    end = start + PER_PAGE - 1

    location = request.args.get("location")
    source = request.args.get("source")

    query = supabase.table("internships").select("*")

    if location:
        query = query.ilike("location", f"%{location}%")

    if source:
        query = query.ilike("source", f"%{source}%")

    query = query.order("created_at", desc=True).range(start, end)

    internships = query.execute().data

    # fetch saved internship ids for this user
    user_id = session.get("user_id") # Use .get() to avoid error if not logged in
    saved_ids = set()
    
    if user_id:
        conn=get_db()
        cur=conn.cursor()
        cur.execute(
            """
            SELECT opportunity_id
            FROM saved_opportunities
            WHERE user_id = %s
            AND opportunity_type = 'internship'
            """,
            (user_id,)
        )
        saved_ids = set(int(row[0]) for row in cur.fetchall())
        conn.close() # Ensure connection is closed

    return render_template(
        "internships.html",
        internships=internships,
        saved_ids=saved_ids,
        page=page
    )


@app.route("/internships/<int:internship_id>")
def internship_details(internship_id):
    internship = (
        supabase
        .table("internships")
        .select("*")
        .eq("id", internship_id)
        .single()
        .execute()
        .data
    )

    return render_template(
        "internship_details.html",
        internship=internship
    )

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

# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")



# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(debug=True)