import json
import re
import xml.etree.ElementTree as ET
import requests

BASE_URL = "https://sicnoticias.pt"
# Primary XML feed listing recent publication articles
SITEMAP_URL = f"{BASE_URL}/sitemap-news.xml"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def get_latest_articles(limit=50):
    """Parses SIC Notícias News Sitemap XML directly to pull guaranteed article URLs and titles."""
    articles = []
    
    try:
        res = requests.get(SITEMAP_URL, headers=HEADERS, timeout=10)
        if res.status_code == 200:
            root = ET.fromstring(res.content)
            # Define standard XML namespaces used in sitemaps
            namespaces = {
                's': 'http://www.sitemaps.org/schemas/sitemap/0.9',
                'news': 'http://www.google.com/schemas/sitemap-news/0.9'
            }
            
            for url_tag in root.findall('s:url', namespaces):
                loc = url_tag.find('s:loc', namespaces)
                news_title = url_tag.find('.//news:title', namespaces)
                
                if loc is not None and loc.text:
                    article_url = loc.text.strip()
                    title = news_title.text.strip() if news_title is not None and news_title.text else "SIC Notícias"
                    
                    articles.append({'title': title, 'url': article_url})
                    if len(articles) >= limit:
                        break
    except Exception as e:
        print(f"Sitemap parsing failed: {e}")

    # Fallback to direct HTML regex if sitemap route is unreachable
    if not articles:
        try:
            res = requests.get(f"{BASE_URL}/ultimas", headers=HEADERS, timeout=10)
            urls = re.findall(r'href="(/[^"]+)"', res.text)
            seen = set()
            for path in urls:
                if len(path.split('/')) >= 3 and not path.startswith(('/ultimas', '/tag', '/autor')):
                    full_url = f"{BASE_URL}{path}"
                    if full_url not in seen:
                        seen.add(full_url)
                        slug = path.strip('/').split('/')[-1]
                        title = slug.replace('-', ' ').title()
                        articles.append({'title': title, 'url': full_url})
                    if len(articles) >= limit:
                        break
        except Exception as e:
            print(f"Fallback scraper failed: {e}")

    return articles

def extract_video_url(article_url):
    """Scans the article page and Next.js internal props for m3u8 stream manifests."""
    try:
        res = requests.get(article_url, headers=HEADERS, timeout=10)
        
        # 1. Look for m3u8 manifests directly in script bodies or player metadata
        m3u8_matches = re.findall(r'https?://[^\s"\']+\.m3u8[^\s"\']*', res.text)
        for url in m3u8_matches:
            if any(domain in url for domain in ["impresa", "jwplayer", "akamaized", "vod", "live"]):
                return url

        # 2. Parse __NEXT_DATA__ payload embedded by Next.js
        next_data = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', res.text)
        if next_data:
            json_str = next_data.group(1)
            urls = re.findall(r'https?://[^\s"\']+\.m3u8[^\s"\']*', json_str)
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
            print(f"[{count}] Stream added: {article['title']}")
            m3u_entries.append(f'#EXTINF:-1 tvg-name="{article["title"]}",{article["title"]}')
            m3u_entries.append(video_url)
            
    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_entries))
        
    print(f"\nDone! Saved {count} streams into playlist.m3u")

if __name__ == "__main__":
    generate_m3u()
