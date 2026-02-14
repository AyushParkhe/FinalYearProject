from playwright.sync_api import sync_playwright
import pandas as pd
from datetime import datetime
import time

# ---------------- CONFIG ---------------- #
URL = "https://remoteok.com"
TARGET_JOBS = 120
OUTPUT_FILE = "remoteok_aicte_inp.csv"

# ---------------- HELPERS ---------------- #
def auto_scroll(page, scrolls=12):
    """Scroll page to load more jobs"""
    for _ in range(scrolls):
        page.mouse.wheel(0, 6000)
        time.sleep(2)

# ---------------- MAIN ---------------- #
def main():
    print("🚀 Starting RemoteOK scraping (AICTE INP format)...")

    data = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        page.goto(URL, timeout=60_000)
        page.wait_for_selector("tr.job", timeout=60_000)

        auto_scroll(page)

        rows = page.query_selector_all("tr.job")
        print(f"🔍 Found {len(rows)} job rows")

        for row in rows:
            try:
                company_cell = row.query_selector("td.company")
                if not company_cell:
                    continue

                title_el = company_cell.query_selector("h2")
                company_el = company_cell.query_selector("h3")

                if not title_el or not company_el:
                    continue

                # Location (NULL if not fetched)
                location_el = company_cell.query_selector(".location")
                location = (
                    location_el.inner_text().strip()
                    if location_el else None
                )

                # Job URL (NULL if not fetched)
                link = row.get_attribute("data-href")
                job_url = (
                    f"https://remoteok.com{link}"
                    if link else None
                )

                data.append({
                    # ---- fetched fields ----
                    "title": title_el.inner_text().strip(),
                    "organization": company_el.inner_text().strip(),
                    "location": location,  
                    "duration": None,
                    "stipend": None,
                    "skills_final": None,
                    "posted_on": None,
                    "start_date": None,
                    "type": "Remote",
                    "source": "RemoteOK",
                    "apply_link": job_url,
                    "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "content_hash": None,
                    "extra_data": None,         
                })

            except Exception:
                continue

        browser.close()

    # ---------------- DATAFRAME CLEANUP ---------------- #
    df = pd.DataFrame(data)

    # Empty string → NULL
    df.replace("", pd.NA, inplace=True)

    # Remove duplicates safely
    df.drop_duplicates(subset=["apply_link"], inplace=True)

    # Save AICTE INP file
    df.to_csv(OUTPUT_FILE, index=False)

    print("\n✅ SUCCESS")
    print(f"📊 Total jobs saved: {len(df)}")
    print(f"📁 File created: {OUTPUT_FILE}")

# ---------------- RUN ---------------- #
if __name__ == "__main__":
    main()
