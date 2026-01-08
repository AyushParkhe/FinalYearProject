import requests
from bs4 import BeautifulSoup
import pandas as pd
import os
import time
from datetime import datetime

# -------------------- CONFIG --------------------

BASE_URLS = [
    "https://internshala.com/internships/artificial-intelligence-ai-internship",
    "https://internshala.com/internships/computer-science-internship",
    "https://internshala.com/internships/information-technology-internship"
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive"
}

OUTPUT_DIR = "data"
OUTPUT_FILE = "internships.csv"

# ------------------------------------------------


def ensure_data_dir():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)


def scrape_page(url):
    print(f"Scraping page: {url}")

    response = requests.get(url, headers=HEADERS, timeout=20)
    print("Status:", response.status_code, "Length:", len(response.text))

    if response.status_code != 200 or len(response.text) < 50000:
        print("⚠️ Page blocked or empty")
        return []

    soup = BeautifulSoup(response.text, "lxml")

    internships = soup.find_all("div", class_="individual_internship")
    print("Internships found:", len(internships))

    page_data = []

    for intern in internships:
        try:
            title = intern.find("h3", class_="job-internship-name").text.strip()
        except:
            title = ""

        try:
            company = intern.find("div", class_="company_name").text.strip()
        except:
            company = ""

        try:
            location = intern.find(
                "div", class_="row-1-item locations"
            ).find("a").text.strip()
        except:
            location = ""

        try:
            info_blocks = intern.find_all("div", class_="row-1-item")
            stipend = ""
            duration = ""

            for block in info_blocks:
                icon = block.find("i")

                if icon and "ic-16-money" in icon.get("class", []):
                    stipend = block.find("span").text.strip()

                if icon and "ic-16-calendar" in icon.get("class", []):
                    duration = block.find("span").text.strip()

        except:
                    stipend = ""
                    duration = ""

        try:
            skills = intern.find("div", class_="job-skill").text.strip()
          
        except:
            skills = ""


        try:
            link = intern.find("a", class_="job-title-href")["href"]
            link = "https://internshala.com" + link
        except:
            link = ""

        page_data.append({
            "title": title,
            "organization": company,
            "location": location,
            "stipend": stipend,
            "skills": skills,
            "duration": duration,
            "type": "Internship",
            "source": "Internshala",
            "apply_link": link,
            "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

    return page_data


def main():
    print("Scraping started at:", datetime.now())

    all_data = []

    for url in BASE_URLS:
        data = scrape_page(url)
        all_data.extend(data)
        time.sleep(5)  # polite delay

    if not all_data:
        print("❌ No data scraped. Exiting safely.")
        return

    df = pd.DataFrame(all_data).drop_duplicates(subset=["apply_link"])

    ensure_data_dir()

    output_path = os.path.join(OUTPUT_DIR, OUTPUT_FILE)
    df.to_csv(output_path, index=False)

    print(f"✅ Saved {len(df)} internships to {output_path}")
    print("Scraping finished at:", datetime.now())

    print("Before dedupe:", len(all_data))
    print("After dedupe:", len(df))



if __name__ == "__main__":
    main()
