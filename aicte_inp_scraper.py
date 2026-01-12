import os
import csv
import time
from datetime import datetime
from playwright.sync_api import sync_playwright

# ---------------- CONFIG ---------------- #

URL = "https://internship.aicte-india.org/recentlyposted.php"
OUTPUT_FOLDER = "data"
OUTPUT_FILE = "aicte_inp.csv"
MAX_PAGES = 10     # safety cap

# --------------------------------------- #


def ensure_output_dir():
    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)


def save_to_csv(data):
    ensure_output_dir()
    file_path = os.path.join(OUTPUT_FOLDER, OUTPUT_FILE)

    fieldnames = [
        "title",
        "company",
        "work_type",
        "posted_on",
        "location",
        "duration",
        "start_date",
        "stipend",
        "openings",
        "apply_by",
        "type",
        "source",
        "apply_link",
        "scraped_at"
    ]

    with open(file_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)

    print(f"\n✅ Saved {len(data)} records to {file_path}")


def scrape_aicte():
    all_internships = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(URL, wait_until="networkidle", timeout=60000)

        current_page = 1

        while current_page <= MAX_PAGES:
            print(f"Scraping page {current_page}...")

            try:
                page.wait_for_selector("div.card.internship-item", timeout=10000)
            except:
                print("No more listings found.")
                break

            cards = page.locator("div.card.internship-item")
            count = cards.count()

            for i in range(count):
                card = cards.nth(i)

                def text(sel, idx=None):
                    try:
                        loc = card.locator(sel)
                        return loc.nth(idx).inner_text().strip() if idx is not None else loc.inner_text().strip()
                    except:
                        return ""

                record = {
                    "title": text("h3.job-title"),
                    "company": text("h5.company-name"),
                    "work_type": text("li.wfh span"),
                    "posted_on": text("li.posted-on span"),
                    "location": text("li.location span"),
                    "duration": text("li.duration span"),
                    "start_date": text("li.start-date span"),
                    "stipend": text("li.stipend span", 0),
                    "openings": text("li.user span"),
                    "apply_by": text("li.apply-by span"),
                    "type":"internship",
                    "source": "AICTE",
                    "apply_link": card.locator("div.btn-wrap a").get_attribute("href"),
                    "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }

                all_internships.append(record)

            # pagination (safe)
            next_btn = page.locator("text=Next").first
            if next_btn.is_visible():
                next_btn.click()
                time.sleep(2)
                current_page += 1
            else:
                break

        browser.close()

    if all_internships:
        save_to_csv(all_internships)
    else:
        print("❌ No data scraped.")


if __name__ == "__main__":
    scrape_aicte()
