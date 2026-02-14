from playwright.sync_api import sync_playwright
import pandas as pd
from datetime import datetime
import time

URL = "https://remoteok.com"
TARGET_JOBS = 120   # you can increase this

def auto_scroll(page, scrolls=10):
    """Scroll page to load more jobs"""
    for i in range(scrolls):
        page.mouse.wheel(0, 5000)
        time.sleep(2)

def main():
    print("🚀 Starting RemoteOK scraping with Playwright...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        page.goto(URL, timeout=60_000)
        page.wait_for_selector("tr.job", timeout=60_000)

        # 🔽 IMPORTANT FIX: Scroll to load more jobs
        auto_scroll(page, scrolls=12)

        rows = page.query_selector_all("tr.job")
        print(f"🔍 Found {len(rows)} job rows")

        data = []

        for row in rows:
            try:
                company_cell = row.query_selector("td.company")
                if not company_cell:
                    continue

                title_el = company_cell.query_selector("h2")
                company_el = company_cell.query_selector("h3")

                if not title_el or not company_el:
                    continue

                location_el = company_cell.query_selector(".location")
                location = location_el.inner_text().strip() if location_el else "Remote"

                tags = [
                    tag.inner_text().strip()
                    for tag in company_cell.query_selector_all(".tag")
                ]

                link = row.get_attribute("data-href")
                job_url = f"https://remoteok.com{link}" if link else ""

                data.append({
                    "title": title_el.inner_text().strip(),
                    "company": company_el.inner_text().strip(),
                    "location": location,
                    "tags": ", ".join(tags),
                    "job_url": job_url,
                    "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })

            except:
                continue

        browser.close()

    df = pd.DataFrame(data).drop_duplicates(subset=["job_url"])
    df.to_csv("remoteok_jobs_playwright.csv", index=False)

    print("\n✅ SUCCESS")
    print(f"📊 Total jobs scraped: {len(df)}")
    print("📁 Saved: remoteok_jobs_playwright.csv")


if __name__ == "__main__":
    main()