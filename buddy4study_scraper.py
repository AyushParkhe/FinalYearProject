from playwright.sync_api import sync_playwright
import pandas as pd
import time

BASE_URL = "https://www.buddy4study.com"
LIST_URL = BASE_URL + "/scholarships"

data = []

def extract_section(page, heading_text):
    try:   
        heading = page.locator(f"text={heading_text}").first
        content = heading.locator("xpath=following-sibling::*").first
        return content.inner_text().strip()
    except:
        return "N/A"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()

    # ---------- LOAD LIST PAGE ----------
    page.goto(LIST_URL, timeout=60000)
    page.wait_for_load_state("domcontentloaded")
    time.sleep(10)

    for _ in range(30):
        page.mouse.wheel(0, 12000)
        time.sleep(2)

    links = list(set(
        page.eval_on_selector_all(
            "a[href^='/scholarship/']",
            "els => els.map(e => e.getAttribute('href'))"
        )
    ))

    print(f"🔗 Found {len(links)} scholarship links")

    # ---------- VISIT EACH SCHOLARSHIP ----------
    for i, link in enumerate(links[:100], start=1):
        try:
            url = BASE_URL + link
            page.goto(url, timeout=60000)
            page.wait_for_load_state("domcontentloaded")
            time.sleep(6)

            title = page.locator("h1").inner_text()

            # Expand accordion sections
            for btn in page.locator("button").all():
                try:
                    btn.click(timeout=500)
                    time.sleep(0.2)
                except:
                    pass

            record = {
                "Scholarship Name": title,
                "Provider": extract_section(page, "Provider"),
                "Eligibility": extract_section(page, "Eligibility"),
                "Benefits": extract_section(page, "Benefits"),
                "Deadline": extract_section(page, "Deadline"),
                "How to Apply": extract_section(page, "How to Apply"),
                "Documents Required": extract_section(page, "Documents"),
                "Application Mode": extract_section(page, "Application"),
                "URL": url
            }

            data.append(record)
            print(f"✅ [{i}] Structured data saved")

        except:
            print("❌ Skipped one scholarship")
            continue

    browser.close()

# ---------- SAVE CSV ----------
df = pd.DataFrame(data)
df.to_csv("buddy4study_structured_scholarships.csv", index=False, encoding="utf-8")

print(f"\n🎉 FINAL CSV CREATED WITH {len(df)} SCHOLARSHIPS")
