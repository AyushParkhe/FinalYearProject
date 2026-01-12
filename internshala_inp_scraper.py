import requests
from bs4 import BeautifulSoup
import pandas as pd
import os
import time
from datetime import datetime

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
    "https://internshala.com/internships/cloud-computing-internship/page-2",
    "https://internshala.com/internships/natural-language-processing-nlp-internship/",
    "https://internshala.com/internships/natural-language-processing-nlp-internship/page-2/"


    
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
OUTPUT_FILE = "internshala_inp.csv"

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
            # Use find_all to get every skill pill, not just the first one
            skill_tags = intern.find_all("div", class_="job_skill")
            if skill_tags:
                # Create a comma-separated string (e.g., "Python, Django, SQL")
                skills = ", ".join([s.text.strip() for s in skill_tags])
            else:
                skills = ""
        except:
            skills = ""


        try:
            link = intern.find("a", class_="job-title-href")["href"]
            link = "https://internshala.com" + link
        except:
            link = ""

        try:
            posted_on = ""
            # The time is usually inside 'color-labels' -> 'status-success' or 'status-inactive'
            labels_container = intern.find("div", class_="color-labels")
            
            if labels_container:
                # Look for the specific div that holds the time (it usually has these classes)
                status_div = labels_container.find("div", class_=["status-success", "status-inactive"])
                
                if status_div:
                    # The text is typically inside a <span> tag within that div
                    time_span = status_div.find("span")
                    if time_span:
                        posted_on = time_span.text.strip()
                    else:
                        # Fallback: just get the text if no span exists
                        posted_on = status_div.text.strip()
        except:
            posted_on = ""

        page_data.append({
            "title": title,
            "organization": company,
            "location": location,
            "stipend": stipend,
            "skills": skills,
            "duration": duration,
            "posted_on": posted_on,
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
