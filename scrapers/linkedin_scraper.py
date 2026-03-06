from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import csv
from datetime import datetime
import hashlib
from utils.skills.factory import get_skill_extractor

KEYWORDS = [
    "software intern",
    "data science intern",
    "machine learning intern",
    "artificial intelligence intern",
    "python intern",
    "cybersecurity intern"
]

BASE_URL = "https://www.linkedin.com/jobs/search/?keywords={}&location=India"
MAX_JOBS_PER_KEYWORD = 100


def generate_hash(text):
    return hashlib.md5(text.encode()).hexdigest()


def scrape_keyword(page, keyword):
    print(f"\n Scraping: {keyword}")

    page.goto(BASE_URL.format(keyword.replace(" ", "%20")), timeout=60000)
    page.wait_for_selector("div.base-search-card")

    # scrolling
    for _ in range(10):
        page.mouse.wheel(0, 3000)
        page.wait_for_timeout(2000)

    soup = BeautifulSoup(page.content(), "html.parser")
    jobs = soup.select("div.base-search-card")[:MAX_JOBS_PER_KEYWORD]

    data = []

    extractor = get_skill_extractor("linkedin")

    for job in jobs:

        title = job.select_one("h3.base-search-card__title")
        company = job.select_one("h4.base-search-card__subtitle a")
        location = job.select_one("span.job-search-card__location")
        date = job.select_one("time")
        link = job.select_one("a.base-card__full-link")

        job_title = title.text.strip() if title else None
        organization = company.text.strip() if company else None
        job_location = location.text.strip() if location else None
        posted_on = date.text.strip() if date else None
        apply_link = link["href"] if link else None

        scraped_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # -------- SKILLS EXTRACTION --------
        text_blob = " ".join(filter(None, [
            job_title,
            job_title,
            organization,
            job_location
        ]))


        skills_list = extractor.extract(text_blob) if extractor else []

        skills_final = str(skills_list) if skills_list else None
        # -----------------------------------

        content_string = (job_title or "") + (organization or "") + (apply_link or "")
        content_hash = generate_hash(content_string)

        data.append([
            job_title,
            organization,
            job_location,
            None,          # duration
            None,          # stipend
            skills_final,  # skills_final
            posted_on,
            None,          # start_date
            "internship",
            "LinkedIn",
            apply_link,
            scraped_at,
            content_hash,
            None           # extra_data
        ])

    print(f" Collected {len(data)} jobs")
    return data


def remove_duplicates(data):
    seen = set()
    final = []

    for row in data:
        if row[12] not in seen:
            seen.add(row[12])
            final.append(row)

    return final


def main():

    all_jobs = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        for keyword in KEYWORDS:
            all_jobs.extend(scrape_keyword(page, keyword))

        browser.close()

    final_data = remove_duplicates(all_jobs)

    with open("data/linkedin_internships.csv", "w", newline="", encoding="utf-8") as f:
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

        writer.writerows(final_data)

    print(f"\n Final unique records: {len(final_data)}")
    print(" Saved as linkedin_internships.csv")


if __name__ == "__main__":
    main()