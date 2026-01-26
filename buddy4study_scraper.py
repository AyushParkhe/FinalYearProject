from playwright.sync_api import sync_playwright
import pandas as pd
import time

URL = "https://www.buddy4study.com/scholarships"

results = set()

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()

    page.goto(URL, timeout=60000)
    page.wait_for_load_state("domcontentloaded")

    print("⏳ Waiting for React content...")
    time.sleep(10)

    previous_count = 0

    for _ in range(40):  # deep scroll
        page.mouse.wheel(0, 10000)
        time.sleep(2)

        links = page.locator("a[href^='/scholarship/']").all()
        current_count = len(links)

        print(f"🔄 Loaded {current_count} links")

        if current_count == previous_count:
            print("🛑 No new scholarships loading")
            break

        previous_count = current_count

    for link in page.locator("a[href^='/scholarship/']").all():
        try:
            title = link.inner_text().split("\n")[0]
            href = link.get_attribute("href")

            if title and href:
                results.add((title, "https://www.buddy4study.com" + href))
        except:
            continue

    browser.close()

df = pd.DataFrame(results, columns=["Scholarship Name", "Link"])
df.to_csv("buddy4study_scholarships_100plus.csv", index=False)

print(f"✅ Saved {len(df)} scholarships successfully")
