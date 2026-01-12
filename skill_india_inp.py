# import requests
# from bs4 import BeautifulSoup
# import pandas as pd
# import os
# import time
# from datetime import datetime

# BASE_URL = "https://api-fe.skillindiadigital.gov.in/api/internship/get-programs"


# HEADERS = {
#     "User-Agent": (
#         "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
#         "AppleWebKit/537.36 (KHTML, like Gecko) "
#         "Chrome/120.0.0.0 Safari/537.36"
#     ),
#     "Accept-Language": "en-US,en;q=0.9",
#     "Accept-Encoding": "gzip, deflate, br",
#     "Connection": "keep-alive"
#     "Accept" "application/json",
#     "Content-Type": "application/json",
#     "Referer": "https://www.skillindiadigital.gov.in/internship"
# }

# OUTPUT_DIR = "data"
# OUTPUT_FILE = "skill_india_internships.csv"

# def ensure_data_dir():
#     if not os.path.exists(OUTPUT_DIR):
#         os.makedirs(OUTPUT_DIR)

# # def scrape_page(url):
# #     print(f"Scraping page: {url}")

# #     response = requests.get(url, headers=HEADERS, timeout=20)
# #     print("Status:", response.status_code, "Length:", len(response.text))

# #     if response.status_code != 200 or len(response.text) < 50000:
# #         print("⚠️ Page blocked or empty")
# #         return []

# #     soup = BeautifulSoup(response.text, "lxml")

# #     internships = soup.find_all("div", class_="app-internship-card")
# #     print("Internships found:", len(internships))

# # scrape_page(BASE_URL)

# payload = {
#     "page": 1,
#     "size": 12
# }

# r = requests.post(BASE_URL, json=payload, headers=HEADERS, timeout=20)
# print(r.status_code)
# data = r.json()

import requests

API_URL = "https://api-fe.skillindiadigital.gov.in/api/internship/get-programs"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Referer": "https://www.skillindiadigital.gov.in/internship"
}

payload = {
    "page": 0,
    "size": 20,
    "keyword": "",
    "programType": "INTERNSHIP",
    "programCategory": "ALL",
    "sectorIds": [],
    "jobRoleIds": [],
    "stateIds": [],
    "districtIds": [],
    "sortBy": "createdDate",
    "sortOrder": "DESC"
}



r = requests.post(API_URL, json=payload, headers=HEADERS, timeout=20)
r.raise_for_status()

data = r.json()

programs = data.get("Data", {}).get("Programs", [])
print("Programs count:", len(programs))


all_programs = []

for page in range(0, 10):
    payload["page"] = page
    r = requests.post(API_URL, json=payload, headers=HEADERS, timeout=20)
    data = r.json()

    programs = data.get("Data", {}).get("Programs", [])
    if not programs:
        break

    all_programs.extend(programs)

print("Total programs:", len(all_programs))
