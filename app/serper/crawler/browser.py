"""
Browser-based web crawler implementation using Playwright.
Provides functionality to crawl websites, extract content, and convert to various formats.
"""
import os
import logging
import base64
from typing import Dict, Any, List
from playwright.async_api import async_playwright, Route
from bs4 import BeautifulSoup

from utils.markdown import HtmlToMarkdown

logger = logging.getLogger(__name__)

class Crawler:
    """
    Web crawler class that uses Playwright to navigate websites and extract content.
    Supports content extraction in multiple formats and handles browser automation.
    """
    def __init__(self):
        self.browser = None
        self.context = None
        self.markdown_converter = HtmlToMarkdown()
        self.chrome_path = os.getenv("CHROME_PATH")
        self.proxy_url = os.getenv("PROXY_URL")

    async def __ensure_browser(self):
        """Ensure browser is launched if not already"""
        if not self.browser:
            playwright = await async_playwright().start()
            launch_args = {
                "headless": True
            }

            if self.chrome_path:
                launch_args["executable_path"] = self.chrome_path

            self.browser = await playwright.chromium.launch(**launch_args)

    async def crawl(self, url: str, **options) -> Dict[str, Any]:
        """
        Crawl a URL and return its content
        """
        logger.info("Crawling URL: %s", url)
        await self.__ensure_browser()

        # Extract options
        respond_with = options.get("respond_with", "markdown")
        target_selector = options.get("target_selector")
        remove_selector = options.get("remove_selector")
        timeout = options.get("timeout", 30)
        with_screenshots = options.get("with_screenshots", False)

        # Create browser context with options
        context_options = {
            "viewport": {"width": 1280, "height": 800},
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

        if self.proxy_url:
            context_options["proxy"] = {"server": self.proxy_url}

        context = await self.browser.new_context(**context_options)
        page = await context.new_page()

        # Setup route handler to block unnecessary resources
        async def route_handler(route: Route):
            if route.request.resource_type in ["image", "media", "font", "stylesheet"]:
                await route.abort()
            else:
                await route.continue_()

        await page.route("**/*", route_handler)

        try:
            # Navigate to URL
            await page.goto(url, timeout=timeout * 1000, wait_until="networkidle")

            # Take screenshot if requested
            screenshot_data = None
            if with_screenshots:
                screenshot_data = await page.screenshot(type="jpeg", quality=80)
                screenshot_data = screenshot_data if screenshot_data else None

            # Get page content
            if target_selector:
                # Wait for selector
                await page.wait_for_selector(target_selector, timeout=timeout * 1000)

                # Remove elements if specified
                if remove_selector:
                    elements = await page.query_selector_all(remove_selector)
                    for element in elements:
                        await element.evaluate("el => el.remove()")

                # Get content of targeted elements
                content_html = await page.inner_html(target_selector)
            else:
                # Get full page content
                content_html = await page.content()

                # Process with BeautifulSoup to remove unwanted elements
                if remove_selector:
                    soup = BeautifulSoup(content_html, "html.parser")
                    for element in soup.select(remove_selector):
                        element.decompose()
                    content_html = str(soup)

            # Get page title
            title = await page.title()

            # Format output based on respond_with option
            if respond_with == "html":
                content = content_html
                content_type = "html"
            elif respond_with == "markdown":
                content = self.markdown_converter.convert(content_html)
                content_type = "markdown"
            elif respond_with == "text":
                content = await page.evaluate('() => document.body.innerText')
                content_type = "text"
            else:
                content = content_html
                content_type = "html"

            # Create result object
            result = {
                "url": url,
                "title": title,
                "content": content,
                "content_type": content_type
            }

            if screenshot_data:
                result["screenshot"] = base64.b64encode(screenshot_data).decode("utf-8")

            return result

        finally:
            await context.close()

    def extract_links(self, html_content: str) -> List[Dict[str, str]]:
        """
        Extract links from HTML content
        """
        soup = BeautifulSoup(html_content, "html.parser")
        links = []

        for a_tag in soup.find_all("a", href=True):
            link = {
                "url": a_tag["href"],
                "text": a_tag.text.strip()
            }
            links.append(link)

        return links