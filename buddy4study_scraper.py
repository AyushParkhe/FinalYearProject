from playwright.sync_api import sync_playwright
import pandas as pd
import time

BASE_URL = "https://www.buddy4study.com"
LIST_URL = BASE_URL + "/scholarships"

records = []

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()

    # -------- LOAD LIST PAGE --------
    page.goto(LIST_URL, timeout=60000)
    page.wait_for_load_state("domcontentloaded")
    time.sleep(10)

    # Deep scroll
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

    # -------- VISIT EACH SCHOLARSHIP --------
    for idx, link in enumerate(links[:100], start=1):
        try:
            url = BASE_URL + link
            page.goto(url, timeout=60000)
            page.wait_for_load_state("domcontentloaded")
            time.sleep(6)

            title = page.locator("h1").inner_text()

            # Expand all accordion sections
            buttons = page.locator("button").all()
            for b in buttons:
                try:
                    b.click(timeout=500)
                    time.sleep(0.3)
                except:
                    pass

            # Extract all visible text sections
            sections = page.locator("section").all()
            full_text = "\n".join(
                [s.inner_text() for s in sections if s.inner_text().strip()]
            )

            records.append({
                "Scholarship Name": title,
                "Full Details": full_text,
                "URL": url
            })

            print(f"✅ [{idx}] Saved detailed data")

        except Exception as e:
            print(f"❌ Skipped one scholarship")
            continue

    browser.close()

# -------- SAVE CSV --------
df = pd.DataFrame(records)
df.to_csv("buddy4study_detailed_scholarships.csv", index=False, encoding="utf-8")

print(f"\n🎉 CSV CREATED with {len(df)} detailed scholarships")
