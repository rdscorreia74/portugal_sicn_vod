from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

def extract_links(html: str, base_url: str, allowed_domain: str) -> set[str]:
    """Extracts absolute internal links from HTML content."""
    soup = BeautifulSoup(html, "lxml")
    links = set()
    
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        absolute_url = urljoin(base_url, href)
        parsed = urlparse(absolute_url)
        
        # Keep only HTTP(S) links within the allowed domain
        if parsed.scheme in ("http", "https") and allowed_domain in parsed.netloc:
            # Strip fragments and trailing query parameters for deduplication
            clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")
            if clean_url:
                links.add(clean_url)
                
    return links

def parse_article(html: str, url: str) -> dict:
    """Extracts structured article data from HTML."""
    soup = BeautifulSoup(html, "lxml")
    
    title = soup.find("h1")
    title_text = title.get_text(strip=True) if title else None
    
    # Extract main text content
    paragraphs = [p.get_text(strip=True) for p in soup.find_all("p") if p.get_text(strip=True)]
    content = "\n".join(paragraphs)
    
    return {
        "url": url,
        "title": title_text,
        "content_length": len(content),
        "text": content
    }
