import re
import urllib.parse
import requests

BASE_URL = "https://sicnoticias.pt"
ULTIMAS_URL = f"{BASE_URL}/ultimas"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def get_latest_articles(limit=50):
    """Fetches the latest article URLs from /ultimas."""
    response = requests.get(ULTIMAS_URL, headers=HEADERS)
    soup = BeautifulSoup(response.text, "html.parser")
    
    articles = []
    # Find article links on the page
    for link in soup.find_all("a", href=True):
        href = link['href']
        # Filter for article paths and avoid duplicate links
        if href.startswith("/") and len(href.split("/")) > 2:
            full_url = urllib.parse.urljoin(BASE_URL, href)
            title = link.get_text(strip=True) or "SIC Notícias Video"
            if full_url not in [a['url'] for a in articles]:
                articles.append({'title': title, 'url': full_url})
            if len(articles) >= limit:
                break
    return articles

def extract_video_url(article_url):
    """Inspects article HTML to extract video source (.m3u8 or .mp4)."""
    try:
        res = requests.get(article_url, headers=HEADERS, timeout=10)
        
        # Method 1: Look for HLS stream URLs embedded in Javascript variables or JSON-LD
        # Impresa videos typically host streams on videos.impresa.pt or live.impresa.pt
        m3u8_matches = re.findall(r'https?://[^\s"\']*impresa[^\s"\']*\.m3u8[^\s"\']*', res.text)
        if m3u8_matches:
            # Filter for higher resolution if variant tracks exist, or return primary HLS
            return m3u8_matches[0]

        # Method 2: Look for direct mp4 video source tags
        soup = BeautifulSoup(res.text, "html.parser")
        video_tag = soup.find("video")
        if video_tag:
            source = video_tag.find("source")
            if source and source.get("src"):
                return source["src"]
                
    except Exception as e:
        print(f"Failed to extract video from {article_url}: {e}")
    
    return None

def generate_m3u(playlist_file="playlist.m3u"):
    articles = get_latest_articles(50)
    print(f"Found {len(articles)} articles. Searching for video streams...")
    
    m3u_entries = ["#EXTM3U"]
    count = 0
    
    for article in articles:
        video_url = extract_video_url(article['url'])
        if video_url:
            count += 1
            # Clean up title for M3U output
            clean_title = article['title'].replace("\n", " ").replace(",", "-")
            m3u_entries.append(f'#EXTINF:-1 tvg-name="{clean_title}",{clean_title}')
            m3u_entries.append(video_url)
            
    with open(playlist_file, "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_entries))
        
    print(f"Done! Saved {count} video URLs to {playlist_file}")

if __name__ == "__main__":
    generate_m3u()
