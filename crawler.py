import sys
import time
import re
from playwright.sync_api import sync_playwright

TARGET_URL = "https://sicnoticias.pt/ultimas"
OUTPUT_FILE = "playlist.m3u"

def run():
    print(f"Starting crawler targeting: {TARGET_URL}")
    streams_found = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        # Intercept network requests to record m3u8 stream links
        def handle_request(request):
            url = request.url
            if ".m3u8" in url and url not in streams_found:
                print(f"[FOUND STREAM] {url}")
                streams_found.append(url)

        page.on("request", handle_request)

        try:
            print("Navigating to main target page...")
            page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=60000)
            time.sleep(4)

            # Dismiss cookie consent banners if present
            try:
                page.click("button:has-text('Aceitar')", timeout=3000)
                print("Dismissed cookie banner.")
            except Exception:
                pass

            # Extract all href attributes on the page
            all_hrefs = page.locator("a").evaluate_all(
                "elements => elements.map(e => e.href)"
            )

            # Filter links matching article paths (e.g., date formats or section categories)
            article_links = set()
            for href in all_hrefs:
                if href and ("sicnoticias.pt" in href) and re.search(r'/(ultimas|pais|mundo|economia|especiais|/202\d-)', href):
                    article_links.add(href)

            article_links = list(article_links)
            print(f"Discovered {len(article_links)} article links.")

            # Visit the first batch of links to trigger streaming requests
            for idx, link in enumerate(article_links[:5]):
                print(f"Visiting article ({idx + 1}/{min(5, len(article_links))}): {link}")
                try:
                    page.goto(link, wait_until="domcontentloaded", timeout=30000)
                    time.sleep(3)
                except Exception as e:
                    print(f"Skipped {link}: {e}")

        except Exception as e:
            print(f"Execution error: {e}")
        finally:
            browser.close()

    # Write output file
    if streams_found:
        print(f"Writing {len(streams_found)} stream(s) to {OUTPUT_FILE}")
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            for idx, stream_url in enumerate(streams_found, 1):
                f.write(f"#EXTINF:-1 tvg-id=\"sicnoticias.pt\" tvg-name=\"SIC Noticias {idx}\", SIC Noticias {idx}\n")
                f.write(f"{stream_url}\n")
        print("Playlist generated successfully.")
    else:
        print("[WARNING] No streams collected. Playlist file was not overwritten.")

if __name__ == "__main__":
    run()
