import time
import pandas as pd
from playwright.sync_api import sync_playwright

BASE_URL = "https://www.buddy4study.com"
LIST_URL = f"{BASE_URL}/scholarships"

def scrape_buddy4study():
    all_data = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False) # Keep False so you can see the fix
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
        page = context.new_page()
        
        print(f"🚀 Navigating to {LIST_URL}...")
        page.goto(LIST_URL, wait_until="domcontentloaded", timeout=60000)

        for current_page_num in range(1, 6): 
            print(f"📄 Processing Page {current_page_num}...")
            
            # Wait for content and scroll slowly to trigger all lazy-loading
            page.wait_for_selector(".Listing_categoriesBox__CiGvQ", timeout=20000)
            for _ in range(10):
                page.mouse.wheel(0, 1200)
                time.sleep(0.5)

            # EXTRACTION
            cards = page.locator(".Listing_categoriesBox__CiGvQ")
            count = cards.count()
            
            valid_on_page = 0
            for i in range(count):
                try:
                    card = cards.nth(i)
                    title = card.locator("h4.Listing_scholarshipName__VLFMj p, h4 p").first.inner_text().strip()
                    
                    # Filtering Logic (This is why your count decreases)
                    if not title or "closed" in title.lower(): 
                        continue

                    award = card.locator(".Listing_awardCont__qnjQK").nth(0).locator("p span").inner_text().strip()
                    elig = card.locator(".Listing_awardCont__qnjQK").nth(1).locator("p span").inner_text().strip()
                    deadline = card.locator(".Listing_calendarDate__WCgKV p").last.inner_text().strip()
                    
                    href = card.get_attribute("href")
                    apply_url = BASE_URL + href if href.startswith("/") else href

                    all_data.append({
                        "title": title, "provider": "Buddy4Study Partner", "source": "Buddy4Study",
                        "category": "General", "eligibility_text": elig, "amount": f"Rs. {award}",
                        "deadline": deadline, "apply_url": apply_url
                    })
                    valid_on_page += 1
                except: continue

            print(f"✅ Extracted {valid_on_page} valid scholarships from Page {current_page_num}.")

            # --------- ROBUST PAGINATION FIX ----------
            try:
                # Store current URL before clicking
                current_url = page.url

                # Target Next button more reliably
                next_btn = page.get_by_role("button", name="Next").first

                if next_btn.count() > 0 and next_btn.is_enabled():
                    print("⏭️ Clicking Next Button...")

                    next_btn.scroll_into_view_if_needed()
                    next_btn.click()

                    # Wait until URL changes OR content refreshes
                    page.wait_for_function(
                        "(prevUrl) => window.location.href !== prevUrl",
                        current_url,
                        timeout=15000
                    )

                    # Wait for new cards to load
                    page.wait_for_selector(".Listing_categoriesBox__CiGvQ", timeout=20000)

                    time.sleep(2)  # small stability delay

                else:
                    print("🏁 Next button not clickable. Ending.")
                    break

            except Exception as e:
                print(f"🏁 Pagination stopped: {e}")
                break

        browser.close()

    df = pd.DataFrame(all_data)
    df.to_csv("buddy4study_precision.csv", index=False, encoding="utf-8")
    print(f"\n🎉 SUCCESS! Total unique records saved: {len(df)}")

if __name__ == "__main__":
    scrape_buddy4study()