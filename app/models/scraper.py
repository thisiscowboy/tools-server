from fastapi import APIRouter, Body, HTTPException, Query, Path
from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field
import random


# Define models
class ScrapeSingleUrlRequest(BaseModel):
    """Request to scrape a single URL"""

    url: str = Field(..., description="URL to scrape")
    wait_for_selector: Optional[str] = Field(None, description="CSS selector to wait for")
    wait_for_timeout: Optional[int] = Field(30000, description="Maximum wait time in ms")
    extract_tables: bool = Field(True, description="Extract tables from content")
    store_as_document: bool = Field(False, description="Store result as a document")
    document_tags: Optional[List[str]] = Field(None, description="Tags for document if stored")


class UrlList(BaseModel):
    """Request to scrape multiple URLs"""

    urls: List[str] = Field(..., description="List of URLs to scrape")
    recursion_depth: int = Field(0, ge=0, le=3, description="How many links deep to follow (0-3)")
    store_as_documents: bool = Field(False, description="Save results as documents")
    document_tags: Optional[List[str]] = Field(None, description="Tags for documents if stored")


class ScrapeCrawlRequest(BaseModel):
    """Request to crawl a website"""

    start_url: str = Field(..., description="Starting URL for crawl")
    max_pages: int = Field(100, ge=1, description="Maximum number of pages to crawl")
    recursion_depth: int = Field(1, ge=1, description="How many links deep to follow")
    allowed_domains: Optional[List[str]] = Field(
        None, description="Restrict crawling to these domains"
    )
    create_documents: bool = Field(True, description="Create documents from scraped content")
    document_tags: Optional[List[str]] = Field(None, description="Tags for documents if created")
    verification_pass: bool = Field(False, description="Run verification pass after initial crawl")


class SearchAndScrapeRequest(BaseModel):
    """Request to search and scrape results"""

    query: str = Field(..., description="Search query")
    max_results: int = Field(10, ge=1, le=50, description="Maximum search results to process")
    create_documents: bool = Field(False, description="Create documents from scraped content")
    document_tags: Optional[List[str]] = Field(None, description="Tags for documents if created")


class SitemapScrapeRequest(BaseModel):
    """Request to scrape URLs from a sitemap"""

    sitemap_url: str = Field(..., description="URL of the sitemap")
    max_urls: int = Field(50, ge=1, description="Maximum number of URLs to scrape")
    create_documents: bool = Field(True, description="Create documents from scraped content")
    document_tags: Optional[List[str]] = Field(None, description="Tags for documents if created")


class TableData(BaseModel):
    headers: List[str] = Field(default_factory=list, description="Table headers")
    rows: List[List[str]] = Field(default_factory=list, description="Table rows")


class ScraperResponse(BaseModel):
    """Response from scraper"""

    url: str = Field(..., description="Scraped URL")
    title: str = Field(..., description="Page title")
    content: str = Field(..., description="Cleaned content in Markdown format")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Extracted metadata")
    scraped_at: int = Field(..., description="Timestamp when scraped")
    success: bool = Field(True, description="Whether scraping was successful")
    links: List[str] = Field(default_factory=list, description="Links extracted from content")
    document_id: Optional[str] = Field(None, description="Document ID if saved as document")
    error: Optional[str] = Field(None, description="Error message if scraping failed")


from app.core.scraper_service import ScraperService
from app.core.documents_service import DocumentsService
from app.models.documents import DocumentType

router = APIRouter()
scraper_service = ScraperService()
documents_service = DocumentsService()


@router.post(
    "/url",
    response_model=ScraperResponse,
    summary="Scrape a single URL",
    description="Extract content from a web page and convert to Markdown",
)
async def scrape_url(request: ScrapeSingleUrlRequest = Body(...)):
    """
    Scrape a single URL and return structured data.
    Extracts content, converts to Markdown, and optionally stores as a document.
    """
    try:
        result = await scraper_service.scrape_url(
            request.url, request.wait_for_selector, request.wait_for_timeout
        )
        # If requested, store as document
        if request.store_as_document and result["success"]:
            doc = documents_service.create_document(
                title=result["title"],
                content=result["content"],
                document_type=DocumentType.WEBPAGE,
                metadata=result["metadata"],
                tags=request.document_tags,
                source_url=result["url"],
            )
            result["document_id"] = doc["id"]
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scraping failed: {str(e)}")


@router.post(
    "/urls",
    response_model=List[ScraperResponse],
    summary="Scrape multiple URLs",
    description="Scrape multiple URLs in parallel",
)
async def scrape_multiple_urls(request: UrlList = Body(...)):
    """
    Scrape multiple URLs in parallel.
    Processes a list of URLs and returns the scraped content for each.
    """
    try:
        results = await scraper_service.scrape_urls(request.urls)
        # If requested, store results as documents
        if request.store_as_documents:
            for i, result in enumerate(results):
                if result["success"]:
                    try:
                        doc = documents_service.create_document(
                            title=result["title"],
                            content=result["content"],
                            document_type=DocumentType.WEBPAGE,
                            metadata=result["metadata"],
                            tags=request.document_tags,
                            source_url=result["url"],
                        )
                        results[i]["document_id"] = doc["id"]
                    except Exception as e:
                        results[i]["error"] = f"Document creation failed: {str(e)}"
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scraping failed: {str(e)}")


@router.post(
    "/crawl",
    response_model=Dict[str, Any],
    summary="Crawl website",
    description="Crawl a website starting from a URL",
)
async def crawl_website(request: ScrapeCrawlRequest = Body(...)):
    """
    Crawl a website starting from a URL.
    Follows links up to a specified depth and processes each page.
    Optional verification pass ensures content stability.
    """
    try:
        results = await scraper_service.crawl_website(
            request.start_url,
            request.max_pages,
            request.recursion_depth,
            request.allowed_domains,
            request.verification_pass,  # Pass the verification_pass parameter
        )
        response = {
            "pages_crawled": results.get("pages_crawled", 0),
            "start_url": request.start_url,
            "success_count": results.get("success_count", 0),
            "failed_count": results.get("failed_count", 0),
        }
        # Include verification results if available
        if "verification_results" in results:
            response["verification_results"] = results["verification_results"]
            response["verification_success_rate"] = results["verification_success_rate"]
        # If requested, create documents
        if request.create_documents:
            document_ids = []
            for result in results.get("results", []):
                if result.get("success", False):
                    try:
                        doc = documents_service.create_document(
                            title=result["title"],
                            content=result["content"],
                            document_type=DocumentType.WEBPAGE,
                            metadata=result["metadata"],
                            tags=request.document_tags,
                            source_url=result["url"],
                        )
                        document_ids.append(doc["id"])
                    except Exception:
                        pass
            response["documents_created"] = len(document_ids)
            response["document_ids"] = document_ids
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Crawling failed: {str(e)}")


@router.post(
    "/search",
    response_model=List[ScraperResponse],
    summary="Search and scrape",
    description="Search for content and scrape the results",
)
async def search_and_scrape(request: SearchAndScrapeRequest = Body(...)):
    """
    Search for content and scrape the results.
    Performs a web search and scrapes the top results.
    """
    try:
        results = await scraper_service.search_and_scrape(request.query, request.max_results)
        # If requested, create documents
        if request.create_documents:
            for i, result in enumerate(results):
                if result.get("success", False):
                    try:
                        doc = documents_service.create_document(
                            title=result["title"],
                            content=result["content"],
                            document_type=DocumentType.WEBPAGE,
                            metadata=result["metadata"],
                            tags=request.document_tags,
                            source_url=result["url"],
                        )
                        results[i]["document_id"] = doc["id"]
                    except Exception:
                        pass
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search and scrape failed: {str(e)}")


@router.post(
    "/sitemap",
    response_model=Dict[str, Any],
    summary="Scrape sitemap",
    description="Extract URLs from sitemap and scrape them",
)
async def scrape_sitemap(request: SitemapScrapeRequest = Body(...)):
    """
    Extract URLs from a sitemap and scrape them.
    Processes XML sitemap files and scrapes the listed URLs.
    """
    try:
        result = await scraper_service.scrape_sitemap(request.sitemap_url, request.max_urls)
        # Handle document creation if requested
        if request.create_documents and result.get("urls_scraped", []):
            document_ids = []
            for scraped_url in result["urls_scraped"]:
                if scraped_url.get("success", False):
                    try:
                        doc = documents_service.create_document(
                            title=scraped_url["title"],
                            content=scraped_url["content"],
                            document_type=DocumentType.WEBPAGE,
                            metadata=scraped_url["metadata"],
                            tags=request.document_tags,
                            source_url=scraped_url["url"],
                        )
                        document_ids.append(doc["id"])
                    except Exception:
                        pass
            result["documents_created"] = len(document_ids)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sitemap scraping failed: {str(e)}")
