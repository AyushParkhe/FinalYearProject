import time
import pandas as pd
import os
from playwright.sync_api import sync_playwright

BASE_URL = "https://www.buddy4study.com"
LIST_URL = f"{BASE_URL}/scholarships"

def scrape_buddy4study():
    all_data = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        )
        page = context.new_page()

        print(f"🚀 Navigating to {LIST_URL}...")
        page.goto(LIST_URL, wait_until="domcontentloaded", timeout=60000)

        print("📄 Processing First Page...")

        page.wait_for_selector(".Listing_categoriesBox__CiGvQ", timeout=20000)

        # Scroll to trigger lazy loading
        for _ in range(12):
            page.mouse.wheel(0, 1500)
            time.sleep(0.7)

        cards = page.locator(".Listing_categoriesBox__CiGvQ")
        count = cards.count()

        print(f"🔎 Found {count} listings on first page.")

        for i in range(count):
            try:
                card = cards.nth(i)

                title = card.locator("h4.Listing_scholarshipName__VLFMj p, h4 p").first.inner_text().strip()

                award = ""
                elig = ""
                deadline = ""

                award_locator = card.locator(".Listing_awardCont__qnjQK").nth(0).locator("p span")
                if award_locator.count() > 0:
                    award = award_locator.inner_text().strip()

                elig_locator = card.locator(".Listing_awardCont__qnjQK").nth(1).locator("p span")
                if elig_locator.count() > 0:
                    elig = elig_locator.inner_text().strip()

                
                deadline = ""

                calendar_block = card.locator(".Listing_calendarDate__WCgKV")

                if calendar_block.count() > 0:
                    # Get all <p> inside the deadline block
                    p_tags = calendar_block.locator("p")
                    
                    for j in range(p_tags.count()):
                        text = p_tags.nth(j).inner_text().strip()
                        
                        # Skip the "Deadline" label and capture actual date
                        if text and text.lower() != "deadline":
                            deadline = text
                            break

                href = card.get_attribute("href")
                apply_url = BASE_URL + href if href and href.startswith("/") else href

                all_data.append({
                    "title": title,
                    "provider": "Buddy4Study Partner",
                    "source": "Buddy4Study",
                    "category": "General",
                    "eligibility_text": elig,
                    "amount": award,
                    "deadline": deadline,
                    "apply_url": apply_url
                })

            except:
                continue

        browser.close()

    # Ensure sch_data folder exists in project root
    os.makedirs("sch_data", exist_ok=True)

    file_path = os.path.join("sch_data", "buddy4study.csv")

    df = pd.DataFrame(all_data)
    df.to_csv(file_path, index=False, encoding="utf-8")

    print(f"\n🎉 SUCCESS! Total records saved: {len(df)}")
    print(f"📁 Saved to: {file_path}")

if __name__ == "__main__":
    scrape_buddy4study()