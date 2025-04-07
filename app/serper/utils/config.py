import os
from typing import List, Optional

# Third-party imports
import dotenv
from pydantic import Field as PydanticField

# Use pydantic_settings if available, otherwise fallback
try:
    from pydantic_settings import BaseSettings
except ImportError:
    from pydantic import BaseSettings  # Fallback for older pydantic versions

# Load environment variables
dotenv.load_dotenv()


class Config(BaseSettings):
    server_host: str = PydanticField(default=os.getenv("SERVER_HOST", "0.0.0.0"))
    server_port: int = PydanticField(default=int(os.getenv("SERVER_PORT", "8000")))
    dev_mode: bool = PydanticField(default=os.getenv("DEV_MODE", "False").lower() == "true")

    allowed_directories: List[str] = PydanticField(
        default_factory=lambda: os.getenv("ALLOWED_DIRS", "./data").split(",")
    )
    file_cache_enabled: bool = PydanticField(
        default=os.getenv("FILE_CACHE_ENABLED", "False").lower() == "true"
    )

    memory_file_path: str = PydanticField(
        default=os.getenv("MEMORY_FILE_PATH", "./data/memory.json")
    )
    use_graph_db: bool = PydanticField(
        default=os.getenv("USE_GRAPH_DB", "False").lower() == "true"
    )

    default_git_username: str = PydanticField(
        default=os.getenv("DEFAULT_COMMIT_USERNAME", "UnifiedTools")
    )
    default_git_email: str = PydanticField(
        default=os.getenv("DEFAULT_COMMIT_EMAIL", "tools@example.com")
    )

    s3_access_key: Optional[str] = PydanticField(default=os.getenv("S3_ACCESS_KEY"))
    s3_secret_key: Optional[str] = PydanticField(default=os.getenv("S3_SECRET_KEY"))
    s3_region: Optional[str] = PydanticField(default=os.getenv("S3_REGION"))
    s3_bucket: Optional[str] = PydanticField(default=os.getenv("S3_BUCKET"))

    scraper_min_delay: float = PydanticField(
        default=float(os.getenv("SCRAPER_MIN_DELAY", "3"))
    )
    scraper_max_delay: float = PydanticField(
        default=float(os.getenv("SCRAPER_MAX_DELAY", "7"))
    )
    user_agent: str = PydanticField(
        default=os.getenv("USER_AGENT", "Mozilla/5.0 (compatible; UnifiedToolsServer/1.0)")
    )
    scraper_data_path: str = PydanticField(
        default=os.getenv("SCRAPER_DATA_PATH", "./data/scraped")
    )

    # Special configuration for pydantic
    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
    }


# Singleton instance using function attribute pattern
def get_config() -> Config:
    """
    Get the singleton configuration instance.
    
    Returns:
        Config: The configuration object with settings from environment variables
    """
    if not hasattr(get_config, "_config_instance"):
        get_config._config_instance = Config()
    return get_config._config_instance
