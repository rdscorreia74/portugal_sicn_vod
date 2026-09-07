import asyncio
import json
from pathlib import Path
from curl_cffi.requests import AsyncSession

import config
from parser import extract_links, parse_article

class SicCrawler:
    def __init__(self):
        self.visited: set[str] = set()
        self.queue: asyncio.Queue = asyncio.Queue()
        self.semaphore = asyncio.Semaphore(config.MAX_CONCURRENT_REQUESTS)

    async def fetch(self, session: AsyncSession, url: str) -> str | None:
        """Fetches page content impersonating Chrome TLS signature."""
        async with self.semaphore:
            try:
                response = await session.get(
                    url,
                    impersonate="chrome",
                    timeout=config.TIMEOUT,
                    headers={
                        "Accept-Language": "pt-PT,pt;q=0.9,en-US;q=0.8,en;q=0.7",
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    }
                )
                if response.status_code == 200:
                    return response.text
                print(f"[HTTP {response.status_code}] Failed: {url}")
            except Exception as e:
                print(f"[Error] {url}: {e}")
            return None

    async def process_url(self, session: AsyncSession, url: str, depth: int):
        if url in self.visited or depth > config.MAX_DEPTH:
            return
        self.visited.add(url)

        print(f"[Crawling] Depth {depth}: {url}")
        html = await self.fetch(session, url)
        if not html:
            return

        # Parse article content and save
        article_data = parse_article(html, url)
        if article_data["title"]:
            file_hash = abs(hash(url))
            output_path = Path(config.OUTPUT_DIR) / f"article_{file_hash}.json"
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(article_data, f, ensure_ascii=False, indent=2)

        # Discover new links if depth limit allows
        if depth < config.MAX_DEPTH:
            new_links = extract_links(html, config.BASE_URL, config.ALLOWED_DOMAIN)
            for link in new_links:
                if link not in self.visited:
                    await self.queue.put((link, depth + 1))

    async def run(self):
        await self.queue.put((config.BASE_URL, 0))
        
        async with AsyncSession() as session:
            while not self.queue.empty():
                tasks = []
                # Batch process available queue items up to max concurrency
                for _ in range(min(self.queue.qsize(), config.MAX_CONCURRENT_REQUESTS)):
                    url, depth = await self.queue.get()
                    tasks.append(self.process_url(session, url, depth))
                    self.queue.task_done()
                
                if tasks:
                    await asyncio.gather(*tasks)

if __name__ == "__main__":
    crawler = SicCrawler()
    asyncio.run(crawler.run())
