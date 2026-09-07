import json
import re
import urllib.parse
import requests

BASE_URL = "https://sicnoticias.pt"
FEED_URL = f"{BASE_URL}/api/v1/contents?limit=50"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*"
}

def get_latest_articles(limit=50):
    """Hits SIC Notícias internal feeds and falls back to html scraping if blocked."""
    articles = []
    seen = set()

    # Strategy A: Direct API Feed Query
    try:
        res = requests.get(FEED_URL, headers=HEADERS, timeout=10)
        if res.status_code == 200:
            data = res.json()
            items = data.get("items", []) or data.get("contents", [])
            for item in items:
                url = item.get("url") or item.get("path")
                title = item.get("title") or item.get("headline")
                if url:
                    full_url = urllib.parse.urljoin(BASE_URL, url)
                    if full_url not in seen:
                        seen.add(full_url)
                        articles.append({"title": title or "SIC Notícias Video", "url": full_url})
                if len(articles) >= limit:
                    return articles
    except Exception as e:
        print(f"API endpoint attempt failed: {e}")

    # Strategy B: Direct HTML Page Extraction (regex pattern targeting all article link paths)
    if not articles:
        try:
            res = requests.get(f"{BASE_URL}/ultimas", headers=HEADERS, timeout=10)
            matches = re.findall(r'href="(/[^"]+)"', res.text)
            for path in matches:
                # Target paths that match news slug structures (e.g., /pais/2026-04-...)
                if re.search(r'/[a-z-]+/\d{4}-', path) or (path.count('/') >= 2 and not path.startswith(('/ultimas', '/tag', '/autor'))):
                    full_url = urllib.parse.urljoin(BASE_URL, path)
                    if full_url not in seen:
                        seen.add(full_url)
                        slug = path.strip('/').split('/')[-1]
                        title = re.sub(r'^\d{4}-\d{2}-\d{2}-', '', slug).replace('-', ' ').title()
                        articles.append({"title": title, "url": full_url})
                    if len(articles) >= limit:
                        break
        except Exception as e:
            print(f"HTML fallback failed: {e}")

    return articles

def extract_video_url(article_url):
    """Fetches article page source and extracts embedded m3u8 stream manifests."""
    try:
        res = requests.get(article_url, headers=HEADERS, timeout=10)
        
        # 1. Look for m3u8 manifests directly in the source code
        m3u8_matches = re.findall(r'https?://[^\s"\']+\.m3u8[^\s"\']*', res.text)
        for url in m3u8_matches:
            if any(domain in url for domain in ["impresa", "jwplayer", "akamaized", "vod"]):
                return url

        # 2. Extract Next.js page state data object
        next_data = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', res.text)
        if next_data:
            json_str = next_data.group(1)
            urls = re.findall(r'https?://[^\s"\']+\.m3u8[^\s"\']*', json_str)
            if urls:
                return urls[0]

    except Exception as e:
        print(f"Error inspecting {article_url}: {e}")
    return None

def generate_m3u():
    articles = get_latest_articles(50)
    print(f"Found {len(articles)} articles. Searching for video streams...")
    
    m3u_entries = ["#EXTM3U"]
    count = 0
    
    for article in articles:
        video_url = extract_video_url(article['url'])
        if video_url:
            count += 1
            print(f"[{count}] Added stream: {article['title']}")
            m3u_entries.append(f'#EXTINF:-1 tvg-name="{article["title"]}",{article["title"]}')
            m3u_entries.append(video_url)
            
    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_entries))
        
    print(f"\nDone! Successfully saved {count} stream URLs to playlist.m3u")

if __name__ == "__main__":
    generate_m3u()
