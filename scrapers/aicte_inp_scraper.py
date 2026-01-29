import os
import csv
import time
import json
from datetime import datetime, timezone
from playwright.sync_api import sync_playwright
from utils.insert_supabase import insert_internship_supabase
from utils.hashing import row_hash

# ---------------- CONFIG ---------------- #

URL = "https://internship.aicte-india.org/recentlyposted.php"
OUTPUT_FOLDER = "data"
OUTPUT_FILE = "aicte_inp.csv"
MAX_PAGES = 50  # safety cap

# --------------------------------------- #

def ensure_output_dir():
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

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
                        if idx is not None:
                            return loc.nth(idx).inner_text().strip()
                        return loc.inner_text().strip()
                    except:
                        return ""

                # -------- EXTRA DATA -------- #
                extra_data_raw = {
                    "work_type": text("li.wfh span"),
                    "start_date": text("li.start-date span"),
                    "openings": text("li.user span"),
                    "apply_by": text("li.apply-by span")
                }

                extra_data_json = json.dumps(extra_data_raw)

                raw_link = card.locator("div.btn-wrap a").get_attribute("href")
                if not raw_link:
                    continue

                apply_link = f"{raw_link}#page={current_page}_idx={i}"

                # -------- CSV RECORD -------- #
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
                    "type": "internship",
                    "source": "AICTE",
                    "apply_link": apply_link,
                    "scraped_at": datetime.now(timezone.utc).isoformat()
                }

                all_internships.append(record)

                # -------- DB ROW -------- #
                row = {
                    "title": record["title"],
                    "organization": record["company"],
                    "location": record["location"],
                    "duration": record["duration"],
                    "stipend": record["stipend"],
                    "skills_final": "",
                    "posted_on": record["posted_on"],
                    "type": "Internship",
                    "source": "AICTE",
                    "apply_link": apply_link,
                    "scraped_at": record["scraped_at"],
                    "extra_data": extra_data_json
                }

                row["content_hash"] = row_hash(row)
                insert_internship_supabase(row)

            # -------- PAGINATION (FIXED) -------- #
            # -------- PAGINATION (AICTE JS-BASED, FIXED) --------
# -------- PAGINATION (AICTE FINAL, STABLE) --------
            try:
                next_page = current_page + 1

                next_btn = page.locator("a.page-link[data-page='%s']" % next_page)

                if next_btn.count() == 0:
                    break

                next_btn.first.click()

                # wait for network + DOM to settle
                page.wait_for_load_state("networkidle", timeout=15000)
                time.sleep(1)

                current_page += 1

            except Exception as e:
                print("Pagination stopped:", e)
                break

if __name__ == "__main__":
    # create_tables()
    scrape_aicte()
