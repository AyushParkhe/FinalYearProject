from playwright.sync_api import sync_playwright
import pandas as pd
from datetime import datetime
import time
from utils.skills.factory import get_skill_extractor

# ---------------- CONFIG ---------------- #
URL = "https://remoteok.com"
TARGET_JOBS = 120
OUTPUT_FILE = "data/remoteok_inp.csv"

# ---------------- HELPERS ---------------- #
def auto_scroll(page, scrolls=12):
    """Scroll page to load more jobs"""
    for _ in range(scrolls):
        page.mouse.wheel(0, 6000)
        time.sleep(2)

# ---------------- MAIN ---------------- #
def main():
    print("🚀 Starting RemoteOK scraping ...")

    data = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        page.goto(URL, timeout=60000)
        page.wait_for_selector("tr.job", timeout=60000)

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

                title = title_el.inner_text().strip()
                organization = company_el.inner_text().strip()

                # Location
                location_el = company_cell.query_selector(".location")
                location = (
                    location_el.inner_text().strip()
                    if location_el else None
                )

                # Job URL
                link = row.get_attribute("data-href")
                job_url = f"https://remoteok.com{link}" if link else None

                # ---------- SKILLS EXTRACTION (FIXED) ----------

                # RemoteOK provides skill tags
                tag_elements = row.query_selector_all(".tag")

                tag_skills = []
                for tag in tag_elements:
                    try:
                        tag_skills.append(tag.inner_text().strip())
                    except:
                        pass

                # fallback unified extractor
                extractor = get_skill_extractor("remoteok")

                text_blob = " ".join(filter(None, [
                    title,
                    organization,
                    location,
                    " ".join(tag_skills)
                ]))

                extracted_skills = extractor.extract(text_blob)

                # combine both sources
                skills = list(set(tag_skills + extracted_skills))

                skills_final = str(skills) if skills else None

                # -----------------------------------------------

                data.append({
                    "title": title,
                    "organization": organization,
                    "location": location,
                    "duration": None,
                    "stipend": None,
                    "skills_final": skills_final,
                    "posted_on": None,
                    "start_date": None,
                    "type": "Remote",
                    "source": "RemoteOK",
                    "apply_link": job_url,
                    "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "content_hash": None,
                    "extra_data": None,
                })

                if len(data) >= TARGET_JOBS:
                    break

            except Exception:
                continue

        browser.close()

    # ---------------- DATAFRAME CLEANUP ---------------- #
    df = pd.DataFrame(data)

    df.replace("", pd.NA, inplace=True)

    df.drop_duplicates(subset=["apply_link"], inplace=True)

    df.to_csv(OUTPUT_FILE, index=False)

    print("\n✅ SUCCESS")
    print(f"📊 Total jobs saved: {len(df)}")
    print(f"📁 File created: {OUTPUT_FILE}")

# ---------------- RUN ---------------- #
if __name__ == "__main__":
    main()