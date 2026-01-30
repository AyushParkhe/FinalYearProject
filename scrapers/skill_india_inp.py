from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
import pandas as pd
import time
import json
from datetime import datetime, timezone
import os

# Configuration
URL = "https://www.skillindiadigital.gov.in/internship"
OUTPUT_FOLDER = "data"
OUTPUT_FILE = "skill-india_inp.csv"

def ensure_output_dir():
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

def run_complex_scraper():
    with sync_playwright() as p:
        # 1. Advanced Browser Launch
        browser = p.chromium.launch(headless=True)

        # 2. Context with Geolocation (kept as-is)
        context = browser.new_context(
            geolocation={"latitude": 28.6139, "longitude": 77.2090},
            permissions=["geolocation"],
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )

        # 3. Block Images (kept)
        page = context.new_page()
        page.route(
            "**/*",
            lambda route: route.abort()
            if route.request.resource_type in ["image", "media", "font"]
            else route.continue_(),
        )

        print(f"🔄 Connecting to {URL}...")

        try:
            page.goto(URL, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_selector("ul.pagination", state="visible", timeout=30000)
        except Exception as e:
            print(f"❌ Fatal Error loading site: {e}")
            browser.close()
            return

        all_data = []
        current_page_num = 1

        while True:
            print(f"\n--- ⚡ Processing Page {current_page_num} ---")

            try:
                page.wait_for_selector("app-internship-card", state="attached", timeout=10000)
            except PlaywrightTimeout:
                print("⚠️ Warning: No cards detected.")

            cards = page.locator("app-internship-card").all()
            print(f"   Found {len(cards)} internships.")

            for card in cards:
                try:
                    title = card.locator("h3").inner_text().strip()

                    company_el = card.locator(".time-technology span")
                    organization = (
                        company_el.inner_text().strip()
                        if company_el.count() > 0
                        else None
                    )

                    dept_el = card.locator(".internship-dep")
                    sector = (
                        dept_el.inner_text().strip()
                        if dept_el.count() > 0
                        else None
                    )

                    duration_el = card.locator(".duration-list-value")
                    duration = (
                        duration_el.inner_text()
                        .replace("Duration:", "")
                        .strip()
                        if duration_el.count() > 0
                        else None
                    )

                    # ---------------- EXTRA DATA ---------------- #
                    extra_data = {
                        "sector": sector
                    }

                    # ✅ NEW: Canonical CSV record (schema-aligned)
                    record = {
                        "title": title,
                        "organization": organization,
                        "location": None,
                        "duration": duration,
                        "stipend": None,
                        "skills_final": None,
                        "posted_on": None,
                        "start_date": None,
                        "type": "Internship",
                        "source": "Skill India",
                        "apply_link": URL,
                        "scraped_at": datetime.now(timezone.utc).isoformat(),
                        "content_hash": None,  # kept for schema compatibility
                        "extra_data": json.dumps(extra_data),
                    }

                    all_data.append(record)

                    # ❌ OLD STRUCTURE (kept commented)
                    # all_data.append({
                    #     "Title": title,
                    #     "Company": company,
                    #     "Sector": department,
                    #     "Duration": duration
                    # })

                except:
                    continue

            # ---------------- PAGINATION (UNCHANGED) ---------------- #
            next_btn = page.locator("li[title='Next page']")
            class_attr = next_btn.get_attribute("class")
            is_disabled = class_attr and "disabled" in class_attr

            if not next_btn.is_visible() or is_disabled:
                print("🏁 Reached end of pagination.")
                break

            print(f"   Clicking Next -> Page {current_page_num + 1}")
            target_page_str = str(current_page_num + 1)

            try:
                next_btn.click()
                page.wait_for_selector(
                    f"li.page-item.active >> text='{target_page_str}'",
                    timeout=20000,
                    state="visible",
                )
                current_page_num += 1
            except PlaywrightTimeout:
                print("❌ Pagination timeout.")
                break

        browser.close()

        # ---------------- CSV SAVE (NEW, FINAL STEP) ---------------- #
        if all_data:
            ensure_output_dir()
            file_path = os.path.join(OUTPUT_FOLDER, OUTPUT_FILE)
            df = pd.DataFrame(all_data)
            df.to_csv(file_path, index=False)
            print(f"\n✅ SUCCESS: Saved {len(all_data)} rows to {file_path}")
        else:
            print("❌ Failure: No data collected.")

if __name__ == "__main__":
    run_complex_scraper()
