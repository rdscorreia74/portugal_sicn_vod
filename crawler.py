import json
import re
import urllib.parse
import requests

BASE_URL = "https://sicnoticias.pt"
ULTIMAS_URL = f"{BASE_URL}/ultimas"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def get_latest_articles(limit=50):
    """Fetches article paths using regex without needing BeautifulSoup."""
    response = requests.get(ULTIMAS_URL, headers=HEADERS)
    hrefs = re.findall(r'href="(/[^"]+)"', response.text)
    
    articles = []
    seen = set()
    
    for href in hrefs:
        # Match standard article paths on SIC Notícias
        if any(cat in href for cat in ['/pais', '/mundo', '/economia', '/desporto', '/especiais', '/ultimas']):
            full_url = urllib.parse.urljoin(BASE_URL, href)
            if full_url not in seen and full_url != ULTIMAS_URL:
                seen.add(full_url)
                # Generate a title from the URL path slug
                title_slug = href.strip('/').split('/')[-1].replace('-', ' ').title()
                articles.append({'title': title_slug, 'url': full_url})
            if len(articles) >= limit:
                break
    return articles

def extract_video_url(article_url):
    """Parses article page for m3u8 stream links embedded in scripts or JSON."""
    try:
        res = requests.get(article_url, headers=HEADERS, timeout=10)
        
        # Look for standard m3u8 stream URLs hosted on Impresa servers
        m3u8_matches = re.findall(r'https?://[^\s"\']*\.m3u8[^\s"\']*', res.text)
        for url in m3u8_matches:
            if "impresa" in url or "live" in url or "vod" in url:
                return url

        # Fallback for Next.js hydration data script objects
        next_data_match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', res.text)
        if next_data_match:
            data_str = next_data_match.group(1)
            urls = re.findall(r'https?://[^\s"\']+\.m3u8[^\s"\']*', data_str)
            if urls:
                return urls[0]

    except Exception as e:
        print(f"Error checking {article_url}: {e}")
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
            m3u_entries.append(f'#EXTINF:-1 tvg-name="{article["title"]}",{article["title"]}')
            m3u_entries.append(video_url)
            
    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_entries))
        
    print(f"Done! Extracted {count} streams into playlist.m3u")

if __name__ == "__main__":
    generate_m3u()
