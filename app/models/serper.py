from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class SerperSearchRequest(BaseModel):
    """Request to search using Serper API"""
    query: str = Field(..., description="Search query")
    search_type: str = Field("search", description="Type of search (search, news, images, places)")
    num_results: int = Field(10, description="Number of results to return")
    country: Optional[str] = Field(None, description="Country code for localized results")
    locale: Optional[str] = Field(None, description="Language code for localized results")
    auto_scrape: bool = Field(False, description="Whether to automatically scrape search results")
    max_scrape: int = Field(5, description="Maximum number of results to scrape if auto_scrape is True")
    create_documents: bool = Field(False, description="Whether to create documents from scraped content")
    document_tags: List[str] = Field(default_factory=list, description="Tags to apply to created documents")


class SerperSearchResponse(BaseModel):
    """Response from Serper search"""
    query: str = Field(..., description="Original search query")
    search_type: str = Field(..., description="Type of search that was performed")
    organic_results: List[Dict[str, Any]] = Field(default_factory=list, description="Organic search results")
    scrape_results: Optional[List[Dict[str, Any]]] = Field(None, description="Scraped content if auto_scrape was True")
    document_ids: Optional[List[str]] = Field(None, description="IDs of created documents if requested")
    error: Optional[str] = Field(None, description="Error message if the search failed")
