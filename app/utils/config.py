import os
from typing import Optional, List
from dotenv import load_dotenv

class Config:
    # Server settings
    server_host: str = "0.0.0.0"
    server_port: int = 8000
    dev_mode: bool = False
    
    # Filesystem settings
    allowed_directories: List[str] = ["./data"]
    memory_file_path: str = "./data/memory.json"
    file_cache_enabled: bool = True
    file_cache_max_age: int = 3600  # 1 hour in seconds
    
    # Git settings
    default_git_username: str = "OtherTales"
    default_git_email: str = "system@othertales.com"
    
    # S3 storage settings
    s3_access_key: Optional[str] = None
    s3_secret_key: Optional[str] = None
    s3_region: str = "us-east-1"
    s3_endpoint_url: Optional[str] = None
    
    # Search API settings (using Serper)
    search_api_key: Optional[str] = None  # Serper API key
    search_provider: str = "serper"  # Provider name (for future extensibility)
    search_default_country: str = "us"
    search_default_locale: str = "en"
    search_timeout: int = 30
    search_max_retries: int = 3
    search_retry_delay: int = 2
    
    # Memory settings
    use_graph_db: bool = False

config = Config()

def load_dotenv_config():
    """Load configuration from environment variables"""
    load_dotenv()

    # Server settings
    config.server_host = os.getenv("SERVER_HOST", "0.0.0.0")
    config.server_port = int(os.getenv("SERVER_PORT", "8000"))
    config.dev_mode = os.getenv("DEV_MODE", "False").lower() in ("true", "1", "yes")
    
    # Filesystem settings
    allowed_dirs_str = os.getenv("ALLOWED_DIRS", "./data")
    config.allowed_directories = [d.strip() for d in allowed_dirs_str.split(",")]
    config.memory_file_path = os.getenv("MEMORY_FILE_PATH", "./data/memory.json")
    config.file_cache_enabled = os.getenv("FILE_CACHE_ENABLED", "True").lower() in ("true", "1", "yes")
    config.file_cache_max_age = int(os.getenv("FILE_CACHE_MAX_AGE", "3600"))
    
    # Git settings
    config.default_git_username = os.getenv("DEFAULT_COMMIT_USERNAME", "OtherTales")
    config.default_git_email = os.getenv("DEFAULT_COMMIT_EMAIL", "system@othertales.com")
    
    # S3 settings
    config.s3_access_key = os.getenv("S3_ACCESS_KEY")
    config.s3_secret_key = os.getenv("S3_SECRET_KEY")
    config.s3_region = os.getenv("S3_REGION", "us-east-1")
    config.s3_endpoint_url = os.getenv("S3_ENDPOINT_URL")
    
    # Load search settings (both old and new keys for backward compatibility)
    config.search_api_key = os.getenv("SEARCH_API_KEY") or os.getenv("SERPER_API_KEY")
    config.search_provider = os.getenv("SEARCH_PROVIDER", "serper")
    config.search_default_country = os.getenv("SEARCH_DEFAULT_COUNTRY", "us")
    config.search_default_locale = os.getenv("SEARCH_DEFAULT_LOCALE", "en")
    config.search_timeout = int(os.getenv("SEARCH_TIMEOUT", "30"))
    config.search_max_retries = int(os.getenv("SEARCH_MAX_RETRIES", "3"))
    config.search_retry_delay = int(os.getenv("SEARCH_RETRY_DELAY", "2"))
    
    # Memory settings
    config.use_graph_db = os.getenv("USE_GRAPH_DB", "False").lower() in ("true", "1", "yes")

def get_config() -> Config:
    """Return the singleton config instance"""
    return config

# Load config at import time
load_dotenv_config()
