import os
import logging
import aiohttp
import asyncio
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from urllib.parse import quote
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

class GoogleSearch:
    def __init__(self):
        self.google_domain = os.getenv("GOOGLE_DOMAIN", "www.google.com")
        self.proxy_url = os.getenv("PROXY_URL")
        logger.info("Initializing Google search")

    async def search(self, query: str, variant: str = "web", num: int = 10, page: int = 1) -> List[Dict[str, Any]]:
        """
        Perform Google search
        """
        logger.info(f"Searching for: {query} (variant: {variant})")

        # Calculate start parameter based on page
        start = (page - 1) * num

        # Build search URL
        url = f"https://{self.google_domain}/search?"
        params = {
            "q": query,
            "num": str(num),
        }

        if start > 0:
            params["start"] = str(start)

        if variant == "images":
            params["tbm"] = "isch"
        elif variant == "news":
            params["tbm"] = "nws"

        # Prepare URL
        for key, value in params.items():
            url += f"{key}={quote(value)}&"
        url = url[:-1]  # Remove trailing &

        # Setup HTTP client
        async with aiohttp.ClientSession() as session:
            # Setup proxy if specified
            proxy = self.proxy_url if self.proxy_url else None

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            }

            try:
                async with session.get(url, headers=headers, proxy=proxy) as response:
                    if response.status != 200:
                        logger.error(f"Error fetching search results: {response.status}")
                        return []

                    html = await response.text()

                    # Extract results based on variant
                    if variant == "images":
                        return self._parse_image_results(html)
                    elif variant == "news":
                        return self._parse_news_results(html)
                    else:
                        return self._parse_web_results(html)
            except Exception as e:
                logger.error(f"Error during search: {str(e)}")
                return []

    def _parse_web_results(self, html: str) -> List[Dict[str, Any]]:
        """
        Parse web search results
        """
        soup = BeautifulSoup(html, "html.parser")
        results = []

        # Extract search results
        for result in soup.select("div.g"):
            try:
                link_element = result.select_one("a")
                if not link_element or not link_element.get("href"):
                    continue

                link = link_element["href"]
                if not link.startswith("http"):
                    continue

                title_element = result.select_one("h3")
                title = title_element.text if title_element else "No title"

                snippet_element = result.select_one("div.VwiC3b")
                snippet = snippet_element.text if snippet_element else "No description"

                results.append({
                    "title": title,
                    "link": link,
                    "snippet": snippet,
                })
            except Exception as e:
                logger.error(f"Error parsing result: {str(e)}")
                continue

        return results

    def _parse_image_results(self, html: str) -> List[Dict[str, Any]]:
        """
        Parse image search results
        """
        soup = BeautifulSoup(html, "html.parser")
        results = []

        for img in soup.select("img.rg_i"):
            try:
                src = img.get("src") or img.get("data-src")
                if not src:
                    continue

                alt = img.get("alt", "No description")

                results.append({
                    "title": alt,
                    "thumbnail": src,
                    "source": img.parent.get("href", "#") if img.parent else "#",
                })
            except Exception as e:
                logger.error(f"Error parsing image result: {str(e)}")
                continue

        return results

    def _parse_news_results(self, html: str) -> List[Dict[str, Any]]:
        """
        Parse news search results
        """
        soup = BeautifulSoup(html, "html.parser")
        results = []

        for article in soup.select("div.SoaBEf"):
            try:
                link_element = article.select_one("a")
                if not link_element or not link_element.get("href"):
                    continue

                link = link_element["href"]
                if not link.startswith("http"):
                    continue

                title_element = article.select_one("div.n0jPhd")
                title = title_element.text if title_element else "No title"

                source_element = article.select_one("div.CEMjEf")
                source = source_element.text if source_element else "Unknown source"

                snippet_element = article.select_one("div.GI74Re")
                snippet = snippet_element.text if snippet_element else "No description"

                results.append({
                    "title": title,
                    "link": link,
                    "source": source,
                    "snippet": snippet,
                })
            except Exception as e:
                logger.error(f"Error parsing news result: {str(e)}")
                continue

        return results
