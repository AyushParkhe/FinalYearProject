from playwright.sync_api import sync_playwright, TimeoutError
import pandas as pd
import time
import os
from datetime import datetime

# ---------------- CONFIG ----------------

HOME_URL = "https://nats.education.gov.in"
OUTPUT_DIR = "data"
OUTPUT_FILE = "nats_apprenticeships.csv"

# ---------------------------------------

def ensure_data_dir():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

def wait_for_manual_login(page):
    print("🔐 Please login manually:")
    print("1️⃣ Click Login on the website")
    print("2️⃣ Enter your credentials")
    print("3️⃣ Go to Apprenticeship Opportunities page")
    print("⏳ You have 5 minutes...")

    # Wait until user navigates after login
    page.wait_for_timeout(300_000)  # 5 minutes

def scrape_apprenticeships(page):
    print("📄 Scraping apprenticeship table...")

    # Wait for table to appear
    try:
        page.wait_for_selector("table tbody tr", timeout=60_000)
    except TimeoutError:
        print("❌ Table not found")
        return []

    rows = page.query_selector_all("table tbody tr")
    data = []

    for row in rows:
        cols = row.query_selector_all("td")
        if len(cols) < 6:
            continue

        data.append({
            "organization": cols[0].inner_text().strip(),
            "title": cols[1].inner_text().strip(),
            "location": cols[2].inner_text().strip(),
            "duration": cols[3].inner_text().strip(),
            "stipend": cols[4].inner_text().strip(),
            "apply_by": cols[5].inner_text().strip(),
            "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

    print(f"✅ Scraped {len(data)} records")
    return data

def main():
    ensure_data_dir()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,  # MUST be False for manual login
            args=["--start-maximized"]
        )

        context = browser.new_context(
            viewport={"width": 1920, "height": 1080}
        )

        page = context.new_page()
        page.goto(HOME_URL)

        wait_for_manual_login(page)

        internships = scrape_apprenticeships(page)

        if not internships:
            print("⚠️ No data scraped")
            browser.close()
            return

        df = pd.DataFrame(internships)
        output_path = os.path.join(OUTPUT_DIR, OUTPUT_FILE)
        df.to_csv(output_path, index=False)

        print(f"🎉 Saved {len(df)} records to {output_path}")

        browser.close()

if __name__ == "__main__":
    main()
