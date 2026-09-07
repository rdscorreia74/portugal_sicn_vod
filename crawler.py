import asyncio
import re
from playwright.async_api import async_playwright

BASE_URL = "https://sicnoticias.pt"
ULTIMAS_URL = f"{BASE_URL}/ultimas"

async def get_latest_articles(page, limit=50):
    """Navigates to /ultimas and collects the latest article URLs."""
    await page.goto(ULTIMAS_URL, wait_until="domcontentloaded")
    
    # Extract article links
    hrefs = await page.eval_on_selector_all(
        'a[href]', 
        'elements => elements.map(e => e.getAttribute("href"))'
    )
    
    articles = []
    seen = set()
    
    for href in hrefs:
        if not href:
            continue
        # Check for standard news category paths
        if any(cat in href for cat in ['/pais', '/mundo', '/economia', '/desporto', '/especiais']):
            full_url = href if href.startswith('http') else f"{BASE_URL}{href}"
            if full_url not in seen and full_url != ULTIMAS_URL:
                seen.add(full_url)
                # Format a title from the URL slug
                slug = href.strip('/').split('/')[-1]
                title = slug.replace('-', ' ').title()
                articles.append({'title': title, 'url': full_url})
            if len(articles) >= limit:
                break
                
    return articles

async def extract_video_from_article(context, article_url):
    """Visits an article page, intercepts network requests, handles consent, and fetches stream URLs."""
    video_url = None
    page = await context.new_page()

    # Intercept network requests looking for .m3u8 video manifests or player CDN links
    def handle_request(request):
        nonlocal video_url
        url = request.url
        if (".m3u8" in url or "cdn.jwplayer.com/manifests" in url) and not video_url:
            if "impresa" in url or "jwplayer" in url or "akamaized" in url:
                video_url = url

    page.on("request", handle_request)

    try:
        await page.goto(article_url, wait_until="domcontentloaded", timeout=15000)
        
        # Click consent button if GDPR popup appears
        try:
            consent_btn = page.locator('button:has-text("Aceitar"), button:has-text("Concordo"), #didomi-notice-agree-button')
            if await consent_btn.is_visible(timeout=2000):
                await consent_btn.click()
        except Exception:
            pass

        await page.wait_for_timeout(2500)
        
        # Fallback: Check if the player exposed a JWPlayer instance or HTML video tag
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

        for idx, article in enumerate(articles, start=1):
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
