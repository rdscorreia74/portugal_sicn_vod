import asyncio
import re
from playwright.async_api import async_playwright

BASE_URL = "https://sicnoticias.pt"
ULTIMAS_URL = f"{BASE_URL}/ultimas"

# Domains to ignore (ads/pre-rolls seen in your clip)
AD_KEYWORDS = ["doubleclick", "googlesyndication", "adnami", "vpaid", "telemetry", "securepubads"]

async def dismiss_consent(page):
    """Handles Didomi cookie consent overlay shown in video."""
    try:
        consent_btn = page.locator('#didomi-notice-agree-button, button:has-text("Aceitar e fechar")')
        if await consent_btn.is_visible(timeout=5000):
            await consent_btn.click()
            await page.wait_for_timeout(1000)
    except Exception:
        pass

async def get_latest_articles(page, limit=30):
    """Navigates to /ultimas, accepts cookies, and extracts valid news links."""
    print(f"Navigating to {ULTIMAS_URL}...")
    await page.goto(ULTIMAS_URL, wait_until="networkidle", timeout=30000)
    await dismiss_consent(page)

    # Scroll down to trigger Next.js lazy loading
    await page.evaluate("window.scrollBy(0, 800)")
    await page.wait_for_timeout(2000)

    links = await page.eval_on_selector_all(
        'a[href]', 
        'elements => elements.map(e => ({ href: e.getAttribute("href"), text: e.innerText }))'
    )

    articles = []
    seen = set()

    for item in links:
        href = item.get("href", "")
        text = item.get("text", "").strip()

        # Match SIC article path pattern: /category/YYYY-MM-DD-slug-id
        if href and re.search(r'/[a-z-]+/\d{4}-\d{2}-\d{2}-', href):
            full_url = f"{BASE_URL}{href}" if href.startswith("/") else href
            if full_url not in seen:
                seen.add(full_url)
                title = text.split('\n')[0] if text else "SIC Notícias Video"
                articles.append({"title": title, "url": full_url})

        if len(articles) >= limit:
            break

    return articles

async def extract_video_stream(context, article_url):
    """Visits the article, handles pre-roll ads, and grabs the true content m3u8."""
    page = await context.new_page()
    found_stream = None

    # Network Interceptor to capture .m3u8 while filtering out VAST ads
    def handle_request(request):
        nonlocal found_stream
        url = request.url
        if ".m3u8" in url:
            if not any(ad_kw in url.lower() for ad_kw in AD_KEYWORDS):
                if "impresa" in url or "akamaized" in url or "cdn" in url:
                    found_stream = url

    page.on("request", handle_request)

    try:
        await page.goto(article_url, wait_until="domcontentloaded", timeout=20000)
        await dismiss_consent(page)
        
        # Wait for the video player container to load and play past pre-rolls
        await page.wait_for_timeout(6000)

    except Exception as e:
        print(f"Error loading {article_url}: {e}")
    finally:
        await page.close()

    return found_stream

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, Gecko) Chrome/122.0.0.0 Safari/537.36"
        )

        main_page = await context.new_page()
        articles = await get_latest_articles(main_page, limit=20)
        print(f"Found {len(articles)} articles on /ultimas. Processing videos...")

        m3u_entries = ["#EXTM3U"]
        count = 0

        for idx, article in enumerate(articles, start=1):
            print(f"Checking [{idx}/{len(articles)}]: {article['title']}")
            stream_url = await extract_video_stream(context, article['url'])

            if stream_url:
                count += 1
                print(f"  -> Stream captured: {stream_url}")
                clean_title = article['title'].replace('"', "'")
                m3u_entries.append(f'#EXTINF:-1 tvg-name="{clean_title}",{clean_title}')
                m3u_entries.append(stream_url)

        await browser.close()

        with open("playlist.m3u", "w", encoding="utf-8") as f:
            f.write("\n".join(m3u_entries))

        print(f"\nDone! Saved {count} video streams into playlist.m3u")

if __name__ == "__main__":
    asyncio.run(main())
