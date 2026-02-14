from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
import pandas as pd
import time

# Configuration
URL = "https://www.skillindiadigital.gov.in/internship"

def run_complex_scraper():
    with sync_playwright() as p:
        # 1. Advanced Browser Launch
        browser = p.chromium.launch(headless=True)
        
        # 2. Context with Geolocation
        context = browser.new_context(
            geolocation={"latitude": 28.6139, "longitude": 77.2090}, # Delhi
            permissions=["geolocation"],
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )
        
        # 3. Block Images to speed up loading
        page = context.new_page()
        page.route("**/*", lambda route: route.abort() if route.request.resource_type in ["image", "media", "font"] else route.continue_())

        print(f"🔄 Connecting to {URL}...")
        
        try:
            page.goto(URL, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_selector("ul.pagination", state="visible", timeout=30000)
        except Exception as e:
            print(f"❌ Fatal Error loading site: {e}")
            browser.close()
            return

        all_data = []
        current_page_num = 1
        
        while True:
            print(f"\n--- ⚡ Processing Page {current_page_num} ---")
            
            # --- PHASE 1: WAIT FOR CARDS ---
            try:
                page.wait_for_selector("app-internship-card", state="attached", timeout=10000)
            except PlaywrightTimeout:
                print("⚠️ Warning: No cards detected. Page might be empty.")

            # --- PHASE 2: SCRAPING ---
            cards = page.locator("app-internship-card").all()
            print(f"   Found {len(cards)} internships.")
            
            for card in cards:
                try:
                    title = card.locator("h3").inner_text().strip()
                    
                    company_el = card.locator(".time-technology span")
                    company = company_el.inner_text().strip() if company_el.count() > 0 else "N/A"

                    dept_el = card.locator(".internship-dep")
                    department = dept_el.inner_text().strip() if dept_el.count() > 0 else "N/A"
                    
                    duration_el = card.locator(".duration-list-value")
                    duration = duration_el.inner_text().replace("Duration:", "").strip() if duration_el.count() > 0 else "N/A"
                    
                    all_data.append({
                        "Title": title,
                        "Company": company,
                        "Sector": department,    
                        "Duration": duration

                        
                    })
                except:
                    continue

            # --- PHASE 3: STATE-BASED NAVIGATION ---
            next_btn = page.locator("li[title='Next page']")
            
            # 🟢 FIXED LOGIC HERE 🟢
            # Get attribute first (returns None or String)
            class_attr = next_btn.get_attribute("class")
            
            # Check 1: Button must be visible
            # Check 2: 'disabled' must NOT be in the class string (if class string exists)
            is_disabled = class_attr and "disabled" in class_attr
            
            if not next_btn.is_visible() or is_disabled:
                print("🏁 Reached end of pagination.")
                break
            
            print(f"   Clicking Next -> Waiting for Page {current_page_num + 1}...")
            
            target_page_str = str(current_page_num + 1)
            
            try:
                next_btn.click()
                
                # Wait for the NEW page number to get the class 'active'
                page.wait_for_selector(
                    f"li.page-item.active >> text='{target_page_str}'", 
                    timeout=20000,
                    state="visible"
                )
                current_page_num += 1
                
            except PlaywrightTimeout:
                print(f"❌ TIMEOUT: Clicked next, but Page {target_page_str} didn't load.")
                break

        browser.close()
        
        if all_data:
            filename = f"data/skill-india_inp.csv"
            df = pd.DataFrame(all_data)
            df.to_csv(filename, index=False)
            print(f"\n✅ SUCCESS: Scraped {len(all_data)} rows.")
        else:
            print("❌ Failure: No data collected.")

if __name__ == "__main__":
    run_complex_scraper()
    