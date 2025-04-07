"""
FastAPI server that provides a web crawler, embeddings generation, and search functionality.
This server implements endpoints for crawling URLs, generating text embeddings,
performing web searches, and calculating text similarity.
"""
import os
import logging
from typing import List, Dict, Any, Optional, Union
from urllib.parse import unquote

import uvicorn
from fastapi import FastAPI, HTTPException, Query, Path
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from crawler.browser import Crawler
from embeddings.model import HfEmbeddings
from search.google import GoogleSearch
from utils.markdown import HtmlToMarkdown

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Standalone Crawler with Embeddings",
    description="Web crawling, scraping, and content analysis using local embeddings",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize components
crawler = Crawler()
embeddings_model = HfEmbeddings()
search_engine = GoogleSearch()
markdown_converter = HtmlToMarkdown()

# API Models
class EmbeddingRequest(BaseModel):
    """Model for embedding request containing text to be embedded."""
    text: Union[str, List[str]]

class EmbeddingResponse(BaseModel):
    """Model for embedding response containing generated embeddings."""
    embeddings: List[List[float]]

class SearchResponse(BaseModel):
    """Model for search response containing search results."""
    query: str
    results: List[Dict[str, Any]]

class CrawlResponse(BaseModel):
    """Model for crawl response containing webpage content."""
    url: str
    title: str
    content: str
    content_type: str
    screenshot: Optional[str] = None

# API Routes
@app.get("/health")
async def health_check():
    """Health check endpoint to verify server is running."""
    return {"status": "ok"}

@app.get("/crawl/{url:path}", response_model=CrawlResponse)
async def crawl_url(
    url: str = Path(..., description="URL to crawl (will be URL-decoded)"),
    respond_with: str = Query("markdown", description="Response format (markdown, html, text)"),
    target_selector: Optional[str] = Query(None, description="CSS selector to target specific content"),
    remove_selector: Optional[str] = Query(None, description="CSS selector for elements to remove"),
    timeout: Optional[int] = Query(30, description="Timeout in seconds"),
    with_screenshots: Optional[bool] = Query(False, description="Include screenshots in response"),
):
    """
    Crawl a URL and return its content in the specified format.
    """
    try:
        # Decode URL
        decoded_url = unquote(url)

        # Create options dict
        options = {
            "respond_with": respond_with,
            "target_selector": target_selector,
            "remove_selector": remove_selector,
            "timeout": timeout,
            "with_screenshots": with_screenshots
        }

        # Perform crawl
        result = await crawler.crawl(decoded_url, **options)
        return result
    except Exception as e:
        logger.error("Error crawling URL: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e

@app.post("/embeddings", response_model=EmbeddingResponse)
async def generate_embeddings(request: EmbeddingRequest):
    """
    Generate embeddings for the provided text or texts.
    """
    try:
        # Process text or array of texts
        texts = request.text if isinstance(request.text, list) else [request.text]

        # Generate embeddings
        embeddings = embeddings_model.embed_batch(texts)

        return {"embeddings": embeddings}
    except Exception as e:
        logger.error("Error generating embeddings: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e

@app.get("/search", response_model=SearchResponse)
async def search(
    q: str = Query(..., description="Search query"),
    num: Optional[int] = Query(10, description="Number of results"),
    variant: Optional[str] = Query("web", description="Search type (web, images, news)"),
    page: Optional[int] = Query(1, description="Page number"),
):
    """
    Perform a search using the configured search engine.
    """
    try:
        # Perform search
        results = await search_engine.search(q, variant=variant, num=num, page=page)
        return {
            "query": q,
            "results": results
        }
    except Exception as e:
        logger.error("Error performing search: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e

# Text similarity endpoint
@app.post("/similarity")
async def compare_similarity(
    text1: str = Query(..., description="First text to compare"),
    text2: str = Query(..., description="Second text to compare"),
):
    """
    Calculate cosine similarity between two text strings.
    """
    try:
        similarity = embeddings_model.similarity(text1, text2)
        return {"similarity": similarity}
    except Exception as e:
        logger.error("Error calculating similarity: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e

# Main entry point
if __name__ == "__main__":
    port = int(os.getenv("PORT", "3000"))
    logger.info("Starting server on port %s", port)
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=True)