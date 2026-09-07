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
    res = requests.get(ULTIMAS_URL, headers=HEADERS)
    # Find all article links on the page
    hrefs = re.findall(r'href="(/[^"]+)"', res.text)
    
    articles = []
    seen = set()
    
    for href in hrefs:
        # Filter for typical news article URL paths
        if any(cat in href for cat in ['/pais/', '/mundo/', '/economia/', '/desporto/', '/especiais/']):
            full_url = urllib.parse.urljoin(BASE_URL, href)
            if full_url not in seen:
                seen.add(full_url)
                # Pull a rough title from the slug or path
                title_slug = href.strip('/').split('/')[-1].replace('-', ' ').capitalize()
                articles.append({'title': title_slug, 'url': full_url})
            if len(articles) >= limit:
                break
    return articles

def extract_video_url(article_url):
    try:
        res = requests.get(article_url, headers=HEADERS, timeout=10)
        
        # 1. Search for Next.js / React build state JSON containing video metadata
        next_data_match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', res.text)
        if next_data_match:
            data = json.loads(next_data_match.group(1))
            # Extract video player source URLs from JSON payload
            json_str = json.dumps(data)
            m3u8_matches = re.findall(r'https?://[^\s"\']+\.m3u8[^\s"\']*', json_str)
            if m3u8_matches:
                return m3u8_matches[0]

        # 2. Fallback: Direct RegEx scan across full page source (scripts + variables)
        m3u8_matches = re.findall(r'https?://[^\s"\']+\.m3u8[^\s"\']*', res.text)
        for url in m3u8_matches:
            if "impresa" in url or "stream" in url or "hls" in url:
                return url

    except Exception as e:
        print(f"Error fetching {article_url}: {e}")
    return None

def generate_m3u():
    articles = get_latest_articles(50)
    print(f"Scanning {len(articles)} articles for streams...")
    
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
        
    print(f"Successfully added {count} video entries to playlist.m3u")

if __name__ == "__main__":
    generate_m3u()
