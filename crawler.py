import asyncio
from playwright.async_api import async_playwright

TARGET_URL = "https://sicnoticias.pt"

async def run_crawler():
    async with async_playwright() as p:
        # Launch Chromium with extra flags to avoid automation detection
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
            ]
        )

        # Configure browser context with real browser attributes
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="pt-PT",
            timezone_id="Europe/Lisbon",
            extra_http_headers={
                "Accept-Language": "pt-PT,pt;q=0.9,en-US;q=0.8,en;q=0.7",
                "Sec-Ch-Ua": '"Google Chrome";v="123", "Not:A-Brand";v="8", "Chromium";v="123"',
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": '"Windows"',
            }
        )

        page = await context.new_page()

        # Hide Playwright's navigator.webdriver signature
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        print(f"Navigating to {TARGET_URL}...")
        
        try:
            # Navigate to the page and wait for the network to idle
            response = await page.goto(TARGET_URL, wait_until="networkidle", timeout=60000)
            
            # Print response status
            if response:
                print(f"Response Status Code: {response.status}")

            # Short wait to handle any deferred JS execution or dynamic rendering
            await page.wait_for_timeout(3000)

            # Check if page loaded successfully
            if response and response.status == 200:
                print("Page loaded successfully. Extracting links...")
                
                # Retrieve all anchor tags and filter unique URLs
                links = await page.eval_on_selector_all(
                    "a[href]",
                    "elements => elements.map(el => el.href)"
                )
                
                unique_links = sorted(list(set(links)))
                print(f"Found {len(unique_links)} unique links:\n")
                
                for link in unique_links[:20]:  # Displaying the first 20 extracted links
                    print(f" - {link}")
                    
                if len(unique_links) > 20:
                    print(f"\n... and {len(unique_links) - 20} more.")

            else:
                print(f"Failed to fetch page. Received HTTP {response.status if response else 'No Response'}")
                
                # Save debugging artifacts if blocked
                await page.screenshot(path="debug_screenshot.png", full_page=True)
                content = await page.content()
                with open("page_source.html", "w", encoding="utf-8") as f:
                    f.write(content)
                print("Saved debug_screenshot.png and page_source.html for inspection.")

        except Exception as e:
            print(f"An error occurred during crawling: {e}")

        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(run_crawler())
