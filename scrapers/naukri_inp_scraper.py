from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import csv
import time
import hashlib
import os
from datetime import datetime

# --- NEW: Import stealth ---
from playwright_stealth import stealth_sync

BASE_URL = "https://www.naukri.com/artificial-intelligence-internship-jobs"
QUERY = "?k=artificial%20intelligence%20internship&experience=0"

TARGET_COUNT = 250  # Change as needed

def generate_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def scrape_naukri():
    all_jobs = []
    seen_hashes = set()
    page_number = 1

    with sync_playwright() as p:
        # --- MODIFIED: Added extra flags to hide automation ---
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--no-sandbox",
                "--disable-setuid-sandbox"
            ]
        )

        # --- MODIFIED: Added realistic viewport and headers ---
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            permissions=["geolocation"],
            geolocation={"latitude": 19.0760, "longitude": 72.8777},
            viewport={"width": 1920, "height": 1080},
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Upgrade-Insecure-Requests": "1"
            }
        )

        page = context.new_page()
        
        # --- NEW: Apply stealth patches to the page ---
        stealth_sync(page)

        while len(all_jobs) < TARGET_COUNT:

            url = f"{BASE_URL}-{page_number}{QUERY}"
            print(f"\nScraping Page {page_number}")
            print(url)

            page.goto(url, timeout=60000)

            # --- MODIFIED: Try/Except block to capture the block screen ---
            try:
                # Wait for job cards instead of network
                page.wait_for_selector("div.cust-job-tuple", timeout=30000)
            except Exception as e:
                print("\n❌ Timeout waiting for job cards!")
                print("Taking screenshot to see what Naukri is showing...")
                page.screenshot(path="naukri_error_screenshot.png", full_page=True)
                print("Screenshot saved as 'naukri_error_screenshot.png'")
                print(f"Page Title: {page.title()}")
                raise e # Re-raise the error to stop the script

            page.wait_for_timeout(3000)

            page.evaluate("document.body.style.scrollBehavior = 'auto'")

            previous_height = 0
            for _ in range(8):
                page.evaluate("window.scrollBy(0, 1200)")
                time.sleep(2)

                new_height = page.evaluate("document.body.scrollHeight")
                if new_height == previous_height:
                    break
                previous_height = new_height

            html = page.content()
            soup = BeautifulSoup(html, "html.parser")
            jobs = soup.select("div.cust-job-tuple")

            print(f"Found {len(jobs)} job cards")

            if len(jobs) == 0:
                print("❌ No jobs found (blocked or page not loaded)")
                break

            for job in jobs:
                title_tag = job.select_one("a.title")
                title = title_tag.text.strip() if title_tag else None
                link = title_tag["href"] if title_tag else None

                company_tag = job.select_one("a.comp-name")
                company = company_tag.text.strip() if company_tag else None

                location_tag = job.select_one("span.locWdth")
                location = location_tag.text.strip() if location_tag else None

                posted_tag = job.select_one("span.job-post-day")
                posted_on = posted_tag.text.strip() if posted_tag else None

                if not title:
                    continue

                hash_input = f"{title}_{company}_{location}"
                content_hash = generate_hash(hash_input)

                if content_hash in seen_hashes:
                    continue

                seen_hashes.add(content_hash)

                job_record = [
                    title,                        # title
                    company,                      # organization
                    location,                     # location
                    None,                         # duration
                    None,                         # stipend
                    None,                         # skills_final
                    posted_on,                    # posted_on
                    None,                         # start_date
                    "Internship",                 # type
                    "naukri.com",                 # source
                    link,                         # apply_link
                    datetime.utcnow().isoformat(),# scraped_at
                    content_hash,                 # content_hash
                    None                          # extra_data
                ]

                all_jobs.append(job_record)

                if len(all_jobs) >= TARGET_COUNT:
                    break

            page_number += 1
            time.sleep(3)

        browser.close()

    # -------- SAVE CSV IN data/ FOLDER --------
    os.makedirs("data", exist_ok=True)

    file_path = os.path.join("data", "naukri_inp.csv")

    with open(file_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        writer.writerow([
            "title",
            "organization",
            "location",
            "duration",
            "stipend",
            "skills_final",
            "posted_on",
            "start_date",
            "type",
            "source",
            "apply_link",
            "scraped_at",
            "content_hash",
            "extra_data"
        ])

        writer.writerows(all_jobs)

    print("\n✅ Scraping completed")
    print(f"Total collected: {len(all_jobs)}")
    print(f"Saved to: {file_path}")

if __name__ == "__main__":
    scrape_naukri()