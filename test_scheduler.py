import requests
from bs4 import BeautifulSoup
import pandas as pd
import hashlib
import sqlite3
from apscheduler.schedulers.blocking import BlockingScheduler
from datetime import datetime
import time

# ===============================
# CONFIG
# ===============================
URL = "https://internshala.com/internships/artificial-intelligence-ai-internship/"
HEADERS = {"User-Agent": "Mozilla/5.0"}
DB_NAME = "internships.db"

# ===============================
# DATABASE SETUP
# ===============================
conn = sqlite3.connect(DB_NAME)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS internships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    organization TEXT,
    location TEXT,
    stipend TEXT,
    duration TEXT,
    apply_link TEXT UNIQUE,
    data_hash TEXT,
    last_updated TEXT
)
""")

conn.commit()

# ===============================
# HASH FUNCTION (CHANGE DETECTION)
# ===============================
def generate_hash(title, stipend, duration, location):
    raw = f"{title}|{stipend}|{duration}|{location}"
    return hashlib.sha256(raw.encode()).hexdigest()

# ===============================
# SCRAPER FUNCTION
# ===============================
def scrape_internshala():
    print(f"\n🔄 Scraping started at {datetime.now()}")

    response = requests.get(URL, headers=HEADERS)
    if response.status_code != 200:
        print("❌ Failed to fetch page")
        return

    soup = BeautifulSoup(response.text, "lxml")

    internships = soup.find_all(
        "div",
        class_="container-fluid individual_internship"
    )

    print(f"📌 Found {len(internships)} internships")

    for intern in internships:
        try:
            title = intern.find("h3", class_="job-internship-name").text.strip()
        except:
            title = ""

        try:
            company = intern.find("div", class_="company_name").text.strip()
        except:
            company = ""

        try:
            location = intern.find(
                "div", class_="row-1-item locations"
            ).find("a").text.strip()
        except:
            location = ""

        try:
            stipend = intern.find("span", class_="stipend").text.strip()
        except:
            stipend = ""

        try:
            duration = intern.find("span", class_="duration").text.strip()
        except:
            duration = ""

        try:
            link = "https://internshala.com" + intern.find(
                "a", class_="job-title-href"
            )["href"]
        except:
            continue  # link is mandatory

        data_hash = generate_hash(title, stipend, duration, location)

        # ===============================
        # CHANGE DETECTION
        # ===============================
        cursor.execute(
            "SELECT data_hash FROM internships WHERE apply_link = ?",
            (link,)
        )
        row = cursor.fetchone()

        if row:
            if row[0] != data_hash:
                cursor.execute("""
                UPDATE internships
                SET title=?, organization=?, location=?, stipend=?,
                    duration=?, data_hash=?, last_updated=?
                WHERE apply_link=?
                """, (
                    title, company, location, stipend,
                    duration, data_hash, datetime.now(), link
                ))
                print(f"🔁 Updated: {title}")
        else:
            cursor.execute("""
            INSERT INTO internships
            (title, organization, location, stipend, duration,
             apply_link, data_hash, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                title, company, location, stipend,
                duration, link, data_hash, datetime.now()
            ))
            print(f"🆕 Added: {title}")

        conn.commit()
        time.sleep(3)  # polite delay

    print("✅ Scraping cycle completed")

# ===============================
# SCHEDULER (EVERY 3 HOURS)
# ===============================
scheduler = BlockingScheduler()
scheduler.add_job(scrape_internshala, "interval", hours=3)

print("🚀 Scheduler started (runs every 3 hours)")
scrape_internshala()   # run once immediately
scheduler.start()

