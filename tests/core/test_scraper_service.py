import pytest
import os
import shutil
import json
import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

from app.core.scraper_service import ScraperService
from bs4 import BeautifulSoup


@pytest.fixture
def temp_dir():
    # Create a temporary directory for testing
    temp_dir = Path("./test_scraper_data")
    temp_dir.mkdir(exist_ok=True)
    yield temp_dir
    # Cleanup
    shutil.rmtree(temp_dir)


@pytest.fixture
def scraper_service(temp_dir):
    with patch("app.core.scraper_service.get_config") as mock_config:
        mock_config.return_value.scraper_min_delay = 0.1
        mock_config.return_value.scraper_max_delay = 0.2
        mock_config.return_value.scraper_data_path = str(temp_dir)

        service = ScraperService()
        yield service


class TestScraperService:
    @pytest.mark.asyncio
    @patch("app.core.scraper_service.aiohttp.ClientSession")
    async def test_scrape_url(self, mock_session, scraper_service):
        # Mock the aiohttp session
        mock_session_instance = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_session_instance

        # Mock response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(
            return_value="""
        <html>
            <head>
                <title>Test Page</title>
                <meta name="description" content="Test description">
            </head>
            <body>
                <h1>Test Heading</h1>
                <p>Test paragraph content.</p>
            </body>
        </html>
        """
        )
        mock_session_instance.get.return_value.__aenter__.return_value = mock_response

        # Test scraping a URL
        result = await scraper_service.scrape_url("https://example.com")

        # Verify successful scrape
        assert result["success"] is True
        assert result["url"] == "https://example.com"
        assert result["title"] == "Test Page"
        assert "Test Heading" in result["content"]
        assert "Test paragraph" in result["content"]
        assert result["metadata"]["description"] == "Test description"

    @pytest.mark.asyncio
    @patch("app.core.scraper_service.aiohttp.ClientSession")
    async def test_scrape_url_error(self, mock_session, scraper_service):
        # Mock a failed response
        mock_session_instance = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_session_instance

        # Connection error
        mock_session_instance.get.side_effect = Exception("Connection error")

        # Test scraping with error
        result = await scraper_service.scrape_url("https://nonexistent.example.com")

        # Verify failed scrape
        assert result["success"] is False
        assert "error" in result
        assert "Connection error" in result["error"]

    @pytest.mark.asyncio
    async def test_extract_metadata(self, scraper_service):
        # Create sample HTML
        html = """
        <html>
            <head>
                <title>Metadata Test</title>
                <meta name="description" content="Meta description">
                <meta name="keywords" content="test, metadata, extraction">
                <meta property="og:title" content="OG Title">
                <meta property="og:description" content="OG Description">
                <script type="application/ld+json">
                    {"@context": "https://schema.org", "@type": "Article", "name": "Test Article"}
                </script>
            </head>
            <body>
                <h1>Test Content</h1>
            </body>
        </html>
        """

        # Extract metadata
        soup = BeautifulSoup(html, "html.parser")
        metadata = scraper_service._extract_metadata(html, "https://example.com/metadata")

        # Verify metadata extraction
        assert metadata["title"] == "Metadata Test"
        assert metadata["description"] == "Meta description"
        assert "og:title" in metadata
        assert metadata["og:title"] == "OG Title"
        assert len(metadata["structured_data"]) == 1
        assert metadata["structured_data"][0]["@type"] == "Article"

    @pytest.mark.asyncio
    @patch("app.core.scraper_service.aiohttp.ClientSession")
    async def test_scrape_with_pagination(self, mock_session, scraper_service):
        # Mock session
        mock_session_instance = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_session_instance

        # First page with next link
        first_page = """
        <html>
            <head><title>Page 1</title></head>
            <body>
                <h1>First Page</h1>
                <p>Content on first page</p>
                <a href="https://example.com/page/2" rel="next">Next Page</a>
            </body>
        </html>
        """

        # Second page with no next link
        second_page = """
        <html>
            <head><title>Page 2</title></head>
            <body>
                <h1>Second Page</h1>
                <p>Content on second page</p>
            </body>
        </html>
        """

        # Set up mock responses for pagination
        mock_responses = [
            # First page response
            AsyncMock(status=200, text=AsyncMock(return_value=first_page)),
            # Second page response
            AsyncMock(status=200, text=AsyncMock(return_value=second_page)),
        ]

        mock_session_instance.get.return_value.__aenter__.side_effect = mock_responses

        # Test paginated scraping
        result = await scraper_service.scrape_with_pagination("https://example.com")

        # Verify results
        assert result["success"] is True
        assert result["pages_scraped"] == 2
        assert "First Page" in result["content"]
        assert "Second Page" in result["content"]

    @pytest.mark.asyncio
    @patch("playwright.async_api.async_playwright")
    async def test_capture_screenshot(self, mock_playwright, scraper_service, temp_dir):
        # Mock Playwright
        mock_playwright_instance = AsyncMock()
        mock_playwright.return_value.__aenter__.return_value = mock_playwright_instance

        # Mock browser, context, and page
        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_page = AsyncMock()

        mock_playwright_instance.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_context.new_page = AsyncMock(return_value=mock_page)

        # Mock screenshot
        mock_page.screenshot = AsyncMock(return_value=b"fake screenshot data")

        # Test capturing screenshot
        result = await scraper_service.capture_screenshot("https://example.com")

        # Verify screenshot capture
        assert result["success"] is True
        assert "screenshot_path" in result
        assert mock_page.goto.called
        assert mock_page.screenshot.called

    @pytest.mark.asyncio
    @patch("app.core.scraper_service.aiohttp.ClientSession")
    async def test_scrape_sitemap(self, mock_session, scraper_service):
        # Mock session
        mock_session_instance = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_session_instance

        # Mock sitemap response
        sitemap_xml = """
        <?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            <url>
                <loc>https://example.com/page1</loc>
                <lastmod>2023-01-01</lastmod>
            </url>
            <url>
                <loc>https://example.com/page2</loc>
                <lastmod>2023-01-02</lastmod>
            </url>
        </urlset>
        """

        # Mock page responses
        page_html = """
        <html>
            <head><title>Test Page</title></head>
            <body><p>Test content</p></body>
        </html>
        """

        # Set up mock responses
        sitemap_response = AsyncMock(status=200, text=AsyncMock(return_value=sitemap_xml))
        page_response = AsyncMock(status=200, text=AsyncMock(return_value=page_html))

        # Return different responses for different URLs
        def get_side_effect(url, **kwargs):
            if url.endswith(".xml"):
                return sitemap_response
            else:
                return page_response

        mock_session_instance.get.side_effect = get_side_effect

        # Test sitemap scraping
        result = await scraper_service.scrape_sitemap("https://example.com/sitemap.xml", max_urls=2)

        # Verify results
        assert result["success"] is True
        assert len(result["results"]) == 2
        assert result["results"][0]["url"] == "https://example.com/page1"
        assert result["results"][1]["url"] == "https://example.com/page2"
