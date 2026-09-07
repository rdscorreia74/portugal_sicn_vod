import asyncio
import re
from playwright.async_api import async_playwright

BASE_URL = "https://sicnoticias.pt"
ULTIMAS_URL = f"{BASE_URL}/ultimas"

async def get_latest_articles(page, limit=50):
    """Navigates to /ultimas and collects the latest article URLs."""
    await page.goto(ULTIMAS_URL, wait_until="networkidle", timeout=30000)
    
    # Handle GDPR cookie banner if it blocks rendering
    try:
        consent_btn = page.locator('button:has-text("Aceitar"), button:has-text("Concordo"), #didomi-notice-agree-button')
        if await consent_btn.is_visible(timeout=3000):
            await consent_btn.click()
            await page.wait_for_timeout(1000)
    except Exception:
        pass

    # Extract all anchor tags
    links = await page.eval_on_selector_all(
        'a[href]', 
        'elements => elements.map(e => ({ href: e.getAttribute("href"), text: e.innerText }))'
    )
    
    articles = []
    seen = set()
    
    for item in links:
        href = item.get('href')
        text = item.get('text', '').strip()
        
        if not href:
            continue
            
        # Match valid article paths (ignore static pages, anchors, or external social links)
        if href.startswith('/') and len(href.split('/')) >= 3 and not href.startswith('/ultimas'):
            full_url = f"{BASE_URL}{href}"
            if full_url not in seen:
                seen.add(full_url)
                
                # Use visible element text if available; fall back to URL slug
                if not text or len(text) < 5:
                    slug = href.strip('/').split('/')[-1]
                    title = slug.replace('-', ' ').title()
                else:
                    title = text.replace('\n', ' ')
                    
                articles.append({'title': title, 'url': full_url})
                
            if len(articles) >= limit:
                break
                
    return articles

async def extract_video_from_article(context, article_url):
    """Visits an article page and intercepts network requests for stream URLs."""
    video_url = None
    page = await context.new_page()

    # Intercept network traffic looking for .m3u8 manifest URLs
    def handle_request(request):
        nonlocal video_url
        url = request.url
        if ".m3u8" in url and not video_url:
            if "impresa" in url or "jwplayer" in url or "akamaized" in url or "vod" in url:
                video_url = url

    page.on("request", handle_request)

    try:
        await page.goto(article_url, wait_until="domcontentloaded", timeout=15000)
        await page.wait_for_timeout(2500)
        
        # Fallback: inspect HTML DOM for video player elements
        if not video_url:
            video_url = await page.evaluate('''() => {
                const videoTag = document.querySelector('video');
                if (videoTag && videoTag.src) return videoTag.src;
                if (window.jwplayer && window.jwplayer().getPlaylist) {
                    const item = window.jwplayer().getPlaylist()[0];
                    return item ? item.file : null;
                }
                return null;
            }''')
    except Exception as e:
        print(f"Skipping {article_url}: {e}")
    finally:
        await page.close()

    return video_url

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        main_page = await context.new_page()
        articles = await get_latest_articles(main_page, limit=50)
        print(f"Found {len(articles)} articles. Extracting video streams...")

        m3u_entries = ["#EXTM3U"]
        count = 0

        for article in articles:
            stream_url = await extract_video_from_article(context, article['url'])
            if stream_url:
                count += 1
                print(f"[{count}] Found video for: {article['title']}")
                m3u_entries.append(f'#EXTINF:-1 tvg-name="{article["title"]}",{article["title"]}')
                m3u_entries.append(stream_url)

        await browser.close()

        with open("playlist.m3u", "w", encoding="utf-8") as f:
            f.write("\n".join(m3u_entries))

        print(f"\nDone! Successfully wrote {count} videos into playlist.m3u")

if __name__ == "__main__":
    asyncio.run(main())
