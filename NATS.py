from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

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

def get_driver():
    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)

def wait_for_manual_login(driver):
    print("🔐 Please login manually:")
    print("1️⃣ Click Login on the website")
    print("2️⃣ Enter your credentials")
    print("3️⃣ Wait after dashboard loads")

    WebDriverWait(driver, 300).until(
        EC.presence_of_element_located((By.TAG_NAME, "body"))
    )

    print("✅ Login completed (page loaded)")

def scrape_apprenticeships(driver):
    print("📄 Navigate to Apprenticeship Opportunities page manually if required")
    time.sleep(20)  # allow manual navigation if needed

    rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
    data = []

    for row in rows:
        cols = row.find_elements(By.TAG_NAME, "td")
        if len(cols) < 6:
            continue

        data.append({
            "organization": cols[0].text.strip(),
            "title": cols[1].text.strip(),
            "location": cols[2].text.strip(),
            "duration": cols[3].text.strip(),
            "stipend": cols[4].text.strip(),
            "apply_by": cols[5].text.strip(),
            "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

        time.sleep(2.5)

    return data

def main():
    ensure_data_dir()
    driver = get_driver()

    try:
        driver.get(HOME_URL)
        wait_for_manual_login(driver)

        print("⏳ Waiting before scraping...")
        time.sleep(20)

        internships = scrape_apprenticeships(driver)

        if not internships:
            print("⚠️ No table found yet. Make sure you are on the Opportunities page.")
            return

        df = pd.DataFrame(internships)
        output_path = os.path.join(OUTPUT_DIR, OUTPUT_FILE)
        df.to_csv(output_path, index=False)

        print(f"🎉 Saved {len(df)} records to {output_path}")

    finally:
        time.sleep(10)
        driver.quit()

if __name__ == "__main__":
    main()
