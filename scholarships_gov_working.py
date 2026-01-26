import requests
from bs4 import BeautifulSoup
import pandas as pd
import time

# Base URL of scholarship list (adjust for pagination)
BASE_URL = "https://www.scholarships.net.in/list-of-scholarships-in-india?page="

all_scholarships = []

# Loop through pages (adjust range if needed)
for page in range(1, 10):  # 10 pages, usually >100 entries
    url = BASE_URL + str(page)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }

    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")
    
    table = soup.find("table")
    if not table:
        continue
    
    rows = table.find_all("tr")[1:]  # Skip header
    for row in rows:
        cols = row.find_all("td")
        if len(cols) >= 3:
            name = cols[0].get_text(strip=True)
            provider = cols[1].get_text(strip=True)
            deadline = cols[2].get_text(strip=True)
            
            all_scholarships.append({
                "Name": name,
                "Provider": provider,
                "Deadline": deadline
            })
    
    print(f"Page {page} done, total scholarships: {len(all_scholarships)}")
    time.sleep(1)  # polite delay

# Save to CSV
df = pd.DataFrame(all_scholarships)
df.to_csv("scholarships_india.csv", index=False)
print(f"Total scholarships scraped: {len(all_scholarships)}")
print("Saved to scholarships_india.csv")
