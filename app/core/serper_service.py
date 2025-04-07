import asyncio
import logging
from typing import Dict, Any, List, Optional, TYPE_CHECKING, cast
from urllib.parse import urlparse
from app.utils.config import get_config

# For type checking to prevent "Import could not be resolved" errors
if TYPE_CHECKING:
    import httpx  # type: ignore
    import aiohttp  # type: ignore
    import requests  # type: ignore

# Initialize module variables
httpx = None
aiohttp = None
requests = None
HTTPX_AVAILABLE = False
AIOHTTP_AVAILABLE = False
REQUESTS_AVAILABLE = False

# Group all imports together to fix "ungrouped imports" warnings
# We need to disable pylint warnings for the import grouping
# pylint: disable=ungrouped-imports,wrong-import-position
try:
    # Use a type ignore comment to silence the Pylance warning
    import httpx as httpx_module  # type: ignore
    httpx = httpx_module
    HTTPX_AVAILABLE = True
except ImportError:
    pass

try:
    import aiohttp as aiohttp_module
    aiohttp = aiohttp_module
    AIOHTTP_AVAILABLE = True
except ImportError:
    pass

try:
    import requests as requests_module
    requests = requests_module
    REQUESTS_AVAILABLE = True
except ImportError:
    pass
# pylint: enable=ungrouped-imports,wrong-import-position

if not (HTTPX_AVAILABLE or AIOHTTP_AVAILABLE or REQUESTS_AVAILABLE):
    # If all HTTP libraries are unavailable, log a more serious warning
    logging.warning("No HTTP client libraries available. API calls will fail.")

logger = logging.getLogger(__name__)

if not HTTPX_AVAILABLE:
    logger.warning(
        "httpx package not installed. This is recommended for optimal performance. "
        "Install with: pip install httpx"
    )
    if not AIOHTTP_AVAILABLE:
        logger.warning(
            "Neither httpx nor aiohttp is available. Using synchronous requests library as fallback. "
            "This may affect performance. Install httpx with: pip install httpx"
        )

class SerperService:
    """Service for interacting with Serper.dev API for web search and content discovery"""
    
    def __init__(self):
        config = get_config()
        self.api_key = config.search_api_key  # Use the unified search_api_key
        self.base_url = "https://google.serper.dev"
        self.default_country = config.search_default_country
        self.default_locale = config.search_default_locale
        self.timeout = config.search_timeout
        self.max_retries = config.search_max_retries
        self.retry_delay = config.search_retry_delay
        
        if not self.api_key:
            logger.warning("Search API key not configured - search functionality will be limited")
    
    async def search(self, 
                     query: str, 
                     search_type: str = "search", 
                     num_results: int = 10,
                     country: Optional[str] = None,
                     locale: Optional[str] = None) -> Dict[str, Any]:
        """
        Perform a search using the Serper API
        
        Args:
            query: The search query
            search_type: Type of search (search, news, images, places)
            num_results: Number of results to return
            country: Country code for localized results
            locale: Language code for localized results
            
        Returns:
            Dict containing search results
        """
        if not self.api_key:
            return {"error": "Serper API key not configured", "results": []}
        
        headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json"
        }
        
        payload = {
            "q": query,
            "num": num_results,
            "gl": country or self.default_country,
            "hl": locale or self.default_locale
        }
        
        endpoint = f"/{search_type}"
        
        # Define the requests handler outside the loop to avoid 'cell-var-from-loop' warning
        # This function is used when only the requests library is available
        def make_requests_call():
            if not REQUESTS_AVAILABLE or requests is None:
                return None
            
            requests_lib = cast(Any, requests)
            response = requests_lib.post(
                f"{self.base_url}{endpoint}",
                headers=headers,
                json=payload,
                timeout=self.timeout
            )
            return response
        
        for attempt in range(self.max_retries):
            try:
                if HTTPX_AVAILABLE and httpx is not None:
                    # Use httpx if available - with explicit type check
                    client_cls = cast(Any, httpx).AsyncClient  # Use cast for type safety
                    async with client_cls(timeout=self.timeout) as client:
                        response = await client.post(
                            f"{self.base_url}{endpoint}", 
                            headers=headers,
                            json=payload
                        )
                        
                        if response.status_code == 200:
                            return response.json()
                        else:
                            logger.error(f"Serper API error: {response.status_code} - {response.text}")
                            return {
                                "error": f"API error: {response.status_code}", 
                                "message": response.text,
                                "results": []
                            }
                elif AIOHTTP_AVAILABLE and aiohttp is not None:
                    # Use aiohttp as a fallback - with explicit type check
                    session_cls = cast(Any, aiohttp).ClientSession  # Use cast for type safety
                    async with session_cls() as session:
                        async with session.post(
                            f"{self.base_url}{endpoint}",
                            headers=headers,
                            json=payload,
                            timeout=self.timeout
                        ) as response:
                            if response.status == 200:
                                return await response.json()
                            else:
                                error_text = await response.text()
                                logger.error(f"Serper API error: {response.status} - {error_text}")
                                return {
                                    "error": f"API error: {response.status}",
                                    "message": error_text,
                                    "results": []
                                }
                elif REQUESTS_AVAILABLE and requests is not None:
                    # Use requests as a last resort (synchronous)
                    loop = asyncio.get_running_loop()
                    response = await loop.run_in_executor(None, make_requests_call)
                    
                    if response and response.status_code == 200:
                        return response.json()
                    elif response:
                        logger.error(f"Serper API error: {response.status_code} - {response.text}")
                        return {
                            "error": f"API error: {response.status_code}",
                            "message": response.text,
                            "results": []
                        }
                    else:
                        return {"error": "Failed to make request", "results": []}
                else:
                    return {"error": "No HTTP client libraries available", "results": []}
            
            except Exception as e:
                logger.error(f"Serper API request failed (attempt {attempt+1}/{self.max_retries}): {str(e)}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                else:
                    return {"error": str(e), "results": []}
        
        # Add an explicit return to satisfy the return type requirement
        return {"error": "Maximum retries exceeded", "results": []}
    
    async def search_and_extract_urls(self, 
                                      query: str, 
                                      num_results: int = 10,
                                      search_type: str = "search") -> List[str]:
        """
        Search and extract URLs from results
        
        Args:
            query: The search query
            num_results: Number of results to return
            search_type: Type of search
            
        Returns:
            List of URLs from the search results
        """
        search_results = await self.search(query, search_type, num_results)
        
        if "error" in search_results:
            logger.error(f"Error in search: {search_results['error']}")
            return []
        
        urls = []
        
        # Extract organic search results
        organic_results = search_results.get("organic", [])
        for result in organic_results:
            if "link" in result:
                urls.append(result["link"])
        
        # Extract other result types as needed
        if "news" in search_results:
            for result in search_results["news"]:
                if "link" in result:
                    urls.append(result["link"])
                    
        if "knowledgeGraph" in search_results and "website" in search_results["knowledgeGraph"]:
            urls.append(search_results["knowledgeGraph"]["website"])
        
        return urls
    
    def extract_domain(self, url: str) -> str:
        """Extract the domain from a URL"""
        parsed_url = urlparse(url)
        domain = parsed_url.netloc
        return domain
    
    def normalize_url(self, url: str) -> str:
        """Normalize a URL by adding https:// if needed"""
        if not url.startswith(('http://', 'https://')):
            return f"https://{url}"
        return url
