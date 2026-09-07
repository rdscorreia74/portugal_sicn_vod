import asyncio
import re
from playwright.async_api import async_playwright

BASE_URL = "https://sicnoticias.pt"
ULTIMAS_URL = "https://sicnoticias.pt/ultimas"
PLAYLIST_FILE = "playlist.m3u"

async def get_article_links(page):
    """Navigates to /ultimas and collects article URLs."""
    print(f"Navigating to latest news: {ULTIMAS_URL}")
    
    # Load page and allow dynamic content hydration
    await page.goto(ULTIMAS_URL, wait_until="domcontentloaded", timeout=60000)
    await page.wait_for_timeout(3000)

    # Extract all links matching article URL patterns
    hrefs = await page.eval_on_selector_all("a[href]", "elements => elements.map(e => e.getAttribute('href'))")
    
    article_links = []
    seen = set()
    for href in hrefs:
        if href and re.search(r"/\d{4}-\d{2}-\d{2}-", href):  # Matches date pattern in article URLs
            full_url = href if href.startswith("http") else f"{BASE_URL}{href}"
            if full_url not in seen:
                seen.add(full_url)
                article_links.append(full_url)

    print(f"Discovered {len(article_links)} article links.")
    return article_links[:10]  # Grab the 10 most recent articles


async def extract_video_stream(context, article_url):
    """Opens an article and intercepts background network requests for .m3u8 video streams."""
    print(f"Extracting video from: {article_url}")
    page = await context.new_page()
    
    m3u8_url = None
    article_title = "SIC Noticias Video"

    # Intercept network requests made during page rendering
    def handle_request(request):
        nonlocal m3u8_url
        url = request.url
        if ".m3u8" in url:
            # Filter for master/index/playlist streams, avoiding tracking fragments
            if any(k in url for k in ["index", "master", "playlist", "m3u8"]):
                if not m3u8_url:
                    m3u8_url = url

    page.on("request", handle_request)

    try:
        await page.goto(article_url, wait_until="domcontentloaded", timeout=45000)
        
        # Grab the article title for the M3U metadata
        title_element = await page.query_selector("h1")
        if title_element:
            article_title = (await title_element.inner_text()).strip()

        # Brief wait to catch delayed video initialization scripts
        await page.wait_for_timeout(4000)

        # If no stream captured yet, trigger play button explicitly
        if not m3u8_url:
            play_btn = await page.query_selector("button[class*='play'], div[class*='play'], .vjs-big-play-button")
            if play_btn:
                await play_btn.click()
                await page.wait_for_timeout(2000)

    except Exception as e:
        print(f"  [ERROR] Failed processing {article_url}: {e}")
    finally:
        await page.close()

    return {"title": article_title, "stream_url": m3u8_url, "article_url": article_url}


async def main():
    async with async_playwright() as p:
        # Launch headless browser mimicking standard user browser headers
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720},
            extra_http_headers={
                "Accept-Language": "pt-PT,pt;q=0.9,en-US;q=0.8,en;q=0.7",
                "Referer": "https://sicnoticias.pt/"
            }
        )

        page = await context.new_page()
        article_urls = await get_article_links(page)
        await page.close()

        playlist_items = []
        for url in article_urls:
            data = await extract_video_stream(context, url)
            if data["stream_url"]:
                print(f"  [FOUND STREAM]: {data['stream_url']}")
                playlist_items.append(data)
            else:
                print("  [NO STREAM]: No video stream found on page.")

        await browser.close()

        # Save to playlist.m3u
        if playlist_items:
            with open(PLAYLIST_FILE, "w", encoding="utf-8") as f:
                f.write("#EXTM3U\n")
                for item in playlist_items:
                    f.write(f'#EXTINF:-1 tvg-logo="{BASE_URL}/favicon.ico",{item["title"]}\n')
                    f.write(f'{item["stream_url"]}\n')
            print(f"\n[DONE] Saved {len(playlist_items)} streams to {PLAYLIST_FILE}")
        else:
            print("\n[WARNING] No streams collected. Playlist file was not overwritten.")

if __name__ == "__main__":
    asyncio.run(main())
