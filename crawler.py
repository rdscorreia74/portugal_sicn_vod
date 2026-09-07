import sys
from playwright.sync_api import sync_playwright

BASE_URL = "https://sicnoticias.pt"

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        page = context.new_page()

        print(f"Connecting to {BASE_URL}...")
        response = page.goto(BASE_URL, wait_until="domcontentloaded", timeout=60000)
        
        print(f"Response HTTP Status: {response.status if response else 'No Response'}")

        # Wait 5 seconds for dynamic scripts to load
        page.wait_for_timeout(5000)

        # Save HTML and Screenshot artifacts for inspection
        with open("page_source.html", "w", encoding="utf-8") as f:
            f.write(page.content())
        page.screenshot(path="debug_screenshot.png", full_page=True)
        print("Saved 'page_source.html' and 'debug_screenshot.png'")

        # Collect every link tag on the page regardless of class/structure
        links = page.query_selector_all("a")
        print(f"Total raw <a> tags found on page: {len(links)}")

        valid_links = []
        for link in links:
            href = link.get_attribute("href")
            text = link.inner_text().strip()
            if href and len(href) > 1:
                valid_links.append((text, href))

        print(f"\n--- First 15 Links Found ---")
        for text, href in valid_links[:15]:
            print(f"Text: '{text}' | Href: {href}")

        browser.close()

if __name__ == "__main__":
    run()
