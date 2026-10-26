"""Configuration and constants for Hermes modules."""

import os
from typing import Literal
from pathlib import Path

# Load environment variables from .env file if it exists
try:
    from dotenv import load_dotenv
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        load_dotenv(env_file)
except ImportError:
    pass


class Config:
    """Configuration class for Hermes modules."""

    # Web Search Configuration
    WEB_SEARCH_PROVIDER: Literal["serpapi", "tavily"] = os.getenv(
        "HERMES_SEARCH_PROVIDER", "serpapi"
    ).lower()
    SERPAPI_API_KEY: str = os.getenv("SERPAPI_API_KEY", "")
    TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")

    # Search defaults
    SEARCH_TIMEOUT: int = 10  # seconds
    SEARCH_MAX_RESULTS: int = 10
    SEARCH_LANGUAGE: str = "en"
    SEARCH_SAFE_MODE: bool = True

    # System Monitor Configuration
    MONITOR_CHECK_INTERVAL: int = 5  # seconds between checks
    MONITOR_CPU_THRESHOLD: float = 80.0  # percentage
    MONITOR_MEMORY_THRESHOLD: float = 85.0  # percentage
    MONITOR_ENABLE_LOGGING: bool = True

    # Logging Configuration
    LOG_LEVEL: str = os.getenv("HERMES_LOG_LEVEL", "INFO")
    LOG_FILE: str = os.getenv("HERMES_LOG_FILE", "hermes.log")

    @classmethod
    def validate(cls) -> bool:
        """Validate that required API keys are configured."""
        if cls.WEB_SEARCH_PROVIDER == "serpapi" and not cls.SERPAPI_API_KEY:
            raise ValueError(
                "SERPAPI_API_KEY environment variable is not set. "
                "Set it in .env or export it in your shell."
            )
        if cls.WEB_SEARCH_PROVIDER == "tavily" and not cls.TAVILY_API_KEY:
            raise ValueError(
                "TAVILY_API_KEY environment variable is not set. "
                "Set it in .env or export it in your shell."
            )
        return True

    @classmethod
    def get_api_key(cls) -> str:
        """Get the API key for the configured search provider."""
        if cls.WEB_SEARCH_PROVIDER == "serpapi":
            return cls.SERPAPI_API_KEY
        elif cls.WEB_SEARCH_PROVIDER == "tavily":
            return cls.TAVILY_API_KEY
        raise ValueError(f"Unknown search provider: {cls.WEB_SEARCH_PROVIDER}")
