import requests 
import re
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
import pandas as pd
import os
import time
import random
from datetime import datetime, timezone

# -------------------- CONFIG --------------------

BASE_URLS = [
    "https://internshala.com/internships/artificial-intelligence-ai-internship",
    "https://internshala.com/internships/artificial-intelligence-ai-internship/page-2/",
    "https://internshala.com/internships/computer-science-internship",
    "https://internshala.com/internships/computer-science-internship/page-2/",
    "https://internshala.com/internships/information-technology-internship",
    "https://internshala.com/internships/information-technology-internship/page-2/",
    "https://internshala.com/internships/web-development-internship/",
    "https://internshala.com/internships/web-development-internship/page-2/",
    "https://internshala.com/internships/backend-development-internship/",
    "https://internshala.com/internships/backend-development-internship/page-2/",
    "https://internshala.com/internships/data-science-internship/",
    "https://internshala.com/internships/data-science-internship/page-2/",
    "https://internshala.com/internships/game-development-internship/",
    "https://internshala.com/internships/game-development-internship/page-2/",
    "https://internshala.com/internships/mobile-app-development-internship/",
    "https://internshala.com/internships/mobile-app-development-internship/page-2/",
    "https://internshala.com/internships/software-development-internship/",
    "https://internshala.com/internships/software-development-internship/page-2/",
    "https://internshala.com/internships/software-testing-internship/",
    "https://internshala.com/internships/software-testing-internship/page-2/",
    "https://internshala.com/internships/full-stack-development-internship/",
    "https://internshala.com/internships/full-stack-development-internship/page-2/",
    "https://internshala.com/internships/front-end-development-internship/",
    "https://internshala.com/internships/front-end-development-internship/page-2/",
    "https://internshala.com/internships/cloud-computing-internship/",
    "https://internshala.com/internships/natural-language-processing-nlp-internship/",
    "https://internshala.com/internships/natural-language-processing-nlp-internship/page-2/",
]

HEADERS_LIST = [
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Connection": "keep-alive",
    },
    {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Accept-Language": "en-GB,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Connection": "keep-alive",
    },
    {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Connection": "keep-alive",
    },
]

OUTPUT_DIR = "data"
OUTPUT_FILE = "internshala_inp.csv"
MAX_RETRIES = 3
RETRY_BACKOFF = 2
MIN_DELAY = 8
MAX_DELAY = 15

# ------------------------------------------------


def get_session():
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=RETRY_BACKOFF,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


SESSION = get_session()


def ensure_data_dir():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)


def fetch_with_retry(url):
    for attempt in range(1, MAX_RETRIES + 1):
        headers = random.choice(HEADERS_LIST)
        try:
            print(f"  Attempt {attempt}/{MAX_RETRIES} for: {url}")
            response = SESSION.get(url, headers=headers, timeout=(10, 60))
            print(f"  Status: {response.status_code} | Length: {len(response.text)}")
            return response
        except requests.exceptions.ReadTimeout:
            print(f"  ⚠️ Read timeout on attempt {attempt}")
        except requests.exceptions.ConnectTimeout:
            print(f"  ⚠️ Connect timeout on attempt {attempt}")
        except requests.exceptions.ConnectionError as e:
            print(f"  ⚠️ Connection error on attempt {attempt}: {e}")
        except requests.exceptions.RequestException as e:
            print(f"  ⚠️ Request failed on attempt {attempt}: {e}")

        if attempt < MAX_RETRIES:
            wait = RETRY_BACKOFF ** attempt + random.uniform(1, 3)
            print(f"  Retrying in {wait:.1f}s...")
            time.sleep(wait)

    print(f"  ❌ All {MAX_RETRIES} attempts failed for: {url}")
    return None


def parse_internships(soup):
    internships = soup.find_all("div", class_="individual_internship")
    print(f"  Cards found: {len(internships)}")
    page_data = []

    for intern in internships:

        # ── TITLE ──────────────────────────────────────────────────
        # Uses fallbacks to hunt for the title in various known Internshala formats
        title_tag = (
            intern.find("h3", class_=re.compile(".*internship-name.*|.*job-title.*|.*heading.*")) or 
            intern.find("a", class_="job-title-href") or
            intern.find("h3") # Absolute fallback: the first h3 is usually the title
        )
        title = title_tag.get_text(strip=True) if title_tag else ""

        # ── COMPANY ────────────────────────────────────────────────
        company_tag = (
            intern.find("p", class_=re.compile(".*company.*")) or 
            intern.find("div", class_=re.compile(".*company.*")) or
            intern.find("a", class_=re.compile(".*link_display_like_text.*"))
        )
        # Sometime the company name has "Part time allowed" span inside it. Let's clean it up.
        company = company_tag.get_text(strip=True) if company_tag else ""

        # Skip broken/empty cards - BUT PRINT A DEBUG WARNING FIRST
        if not title or not company:
            print(f"  [DEBUG] Skipping card - Title missing: '{title}' | Company missing: '{company}'")
            # Uncomment the next line to see the raw HTML of the broken card and find the new classes:
            # print(intern.prettify()[:1000])
            continue

        # ── LOCATION ───────────────────────────────────────────────
        try:
            location_tag = intern.find("div", class_=re.compile(".*location.*"))
            location = location_tag.get_text(strip=True) if location_tag else ""
        except Exception:
            location = ""

        # ── STIPEND & DURATION ─────────────────────────────────────
        stipend = ""
        duration = ""
        try:
            # Try parsing by icons first
            for block in intern.find_all("div", class_=re.compile(".*row-1-item.*|.*item.*")):
                icon = block.find("i")
                if not icon:
                    continue
                classes = " ".join(icon.get("class", []))
                
                # Look for money/stipend icon
                if "money" in classes or "wallet" in classes:
                    stipend = block.get_text(strip=True)
                # Look for calendar/duration icon
                elif "calendar" in classes or "time" in classes:
                    duration = block.get_text(strip=True)
        except Exception:
            pass

        # ── SKILLS ─────────────────────────────────────────────────
        try:
            skills = [
                s.get_text(strip=True)
                for s in intern.find_all(class_=re.compile(".*skill.*"))
                if s.get_text(strip=True)
            ]
        except Exception:
            skills = []

        # ── APPLY LINK ─────────────────────────────────────────────
        try:
            # Look for ANY link inside the title tag, or a specific href
            link_tag = intern.find("a", class_=re.compile(".*job-title.*|.*href.*"))
            if link_tag and link_tag.has_attr("href"):
                href = link_tag["href"]
                link = href if href.startswith("http") else "https://internshala.com" + href
            else:
                link = ""
        except Exception:
            link = ""

        # ── POSTED ON ──────────────────────────────────────────────
        posted_on = ""
        try:
            status_div = intern.find("div", class_=re.compile(".*status.*"))
            if status_div:
                posted_on = status_div.get_text(strip=True)
        except Exception:
            pass

        page_data.append({
            "title": title,
            "organization": company,
            "location": location,
            "stipend": stipend,
            "skills_final": skills,
            "duration": duration,
            "posted_on": posted_on,
            "start_date": None,
            "type": "Internship",
            "source": "Internshala",
            "apply_link": link,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "content_hash": None,
            "extra_data": None,
        })

    return page_data

def scrape_page(url):
    print(f"\nScraping: {url}")
    response = fetch_with_retry(url)

    if response is None:
        print("  ⏭️  Skipping URL due to repeated failures.")
        return []

    if response.status_code != 200:
        print(f"  ⚠️ Non-200 status: {response.status_code}. Skipping.")
        return []

    if len(response.text) < 50000:
        print("  ⚠️ Response too short — likely blocked or empty. Skipping.")
        return []

    soup = BeautifulSoup(response.text, "lxml")
    return parse_internships(soup)


def main():
    print("=" * 60)
    print(f"Scraping started at: {datetime.now()}")
    print("=" * 60)

    all_data = []
    failed_urls = []

    for i, url in enumerate(BASE_URLS):
        data = scrape_page(url)

        if not data:
            failed_urls.append(url)
        else:
            all_data.extend(data)

        if i < len(BASE_URLS) - 1:
            delay = random.uniform(MIN_DELAY, MAX_DELAY)
            print(f"  💤 Sleeping {delay:.1f}s...")
            time.sleep(delay)

    print("\n" + "=" * 60)

    if not all_data:
        print("❌ No data scraped at all. Exiting safely.")
        return

    df = pd.DataFrame(all_data).drop_duplicates(subset=["apply_link"])

    ensure_data_dir()
    output_path = os.path.join(OUTPUT_DIR, OUTPUT_FILE)
    df.to_csv(output_path, index=False)

    print(f"✅ Saved {len(df)} internships to {output_path}")
    print(f"📊 Before dedupe: {len(all_data)} | After dedupe: {len(df)}")

    if failed_urls:
        print(f"\n⚠️ {len(failed_urls)} URL(s) failed completely:")
        for u in failed_urls:
            print(f"   - {u}")

    print(f"\nScraping finished at: {datetime.now()}")
    print("=" * 60)


if __name__ == "__main__":
    main()