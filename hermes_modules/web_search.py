"""Web Search Module - Query public search APIs for real-time information."""

import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict
import requests
from requests.exceptions import RequestException, Timeout

from .config import Config

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Structured search result with title, snippet, and URL."""

    title: str
    snippet: str
    url: str
    position: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return asdict(self)


class WebSearchClient:
    """Client for querying public web search APIs (SerpApi or Tavily)."""

    def __init__(
        self,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: int = 10,
    ):
        """
        Initialize WebSearchClient.

        Args:
            provider: Search provider ('serpapi' or 'tavily'). Uses config if not specified.
            api_key: API key for the provider. Uses config if not specified.
            timeout: Request timeout in seconds.
        """
        self.provider = (provider or Config.WEB_SEARCH_PROVIDER).lower()
        self.api_key = api_key or Config.get_api_key()
        self.timeout = timeout

        if not self.api_key:
            raise ValueError(
                f"No API key provided for {self.provider}. "
                "Set SERPAPI_API_KEY or TAVILY_API_KEY in environment."
            )

        if self.provider not in ("serpapi", "tavily"):
            raise ValueError(f"Unsupported provider: {self.provider}")

        logger.info(f"Initialized WebSearchClient with provider: {self.provider}")

    def search(
        self,
        query: str,
        max_results: Optional[int] = None,
        language: str = "en",
        safe_mode: bool = True,
    ) -> List[SearchResult]:
        """
        Execute a web search query.

        Args:
            query: Search query string.
            max_results: Maximum number of results to return. Uses config default if not specified.
            language: Language code (e.g., 'en', 'es', 'fr').
            safe_mode: Enable safe search filtering.

        Returns:
            List of SearchResult objects containing title, snippet, and URL.

        Raises:
            ValueError: If query is empty or invalid.
            RequestException: If API request fails.
        """
        if not query or not query.strip():
            raise ValueError("Search query cannot be empty")

        max_results = max_results or Config.SEARCH_MAX_RESULTS
        logger.info(f"Searching for: '{query}' (provider: {self.provider})")

        try:
            if self.provider == "serpapi":
                return self._search_serpapi(query, max_results, language, safe_mode)
            else:
                return self._search_tavily(query, max_results, safe_mode)
        except Timeout:
            logger.error(f"Search request timed out after {self.timeout}s")
            raise
        except RequestException as e:
            logger.error(f"Search request failed: {e}")
            raise

    def _search_serpapi(
        self,
        query: str,
        max_results: int,
        language: str,
        safe_mode: bool,
    ) -> List[SearchResult]:
        """Query SerpApi search engine."""
        url = "https://serpapi.com/search"
        params = {
            "q": query,
            "api_key": self.api_key,
            "num": max_results,
            "gl": language,
            "safe": "active" if safe_mode else "off",
        }

        logger.debug(f"SerpApi request params: {self._sanitize_params(params)}")

        response = requests.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()

        if "error" in data:
            logger.error(f"SerpApi error: {data['error']}")
            raise RequestException(f"SerpApi error: {data['error']}")

        results = []
        for idx, result in enumerate(data.get("organic_results", [])[:max_results]):
            try:
                search_result = SearchResult(
                    title=result.get("title", ""),
                    snippet=result.get("snippet", ""),
                    url=result.get("link", ""),
                    position=idx + 1,
                )
                results.append(search_result)
            except (KeyError, TypeError) as e:
                logger.warning(f"Failed to parse result: {e}")
                continue

        logger.info(f"Retrieved {len(results)} results from SerpApi")
        return results

    def _search_tavily(
        self,
        query: str,
        max_results: int,
        safe_mode: bool,
    ) -> List[SearchResult]:
        """Query Tavily search API."""
        url = "https://api.tavily.com/search"
        payload = {
            "api_key": self.api_key,
            "query": query,
            "max_results": max_results,
            "include_answer": False,
            "safe_search": safe_mode,
        }

        logger.debug(f"Tavily request payload (sanitized)")

        response = requests.post(url, json=payload, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()

        if data.get("query") is None:
            logger.error("Invalid Tavily response")
            raise RequestException("Invalid response from Tavily API")

        results = []
        for idx, result in enumerate(data.get("results", [])[:max_results]):
            try:
                search_result = SearchResult(
                    title=result.get("title", ""),
                    snippet=result.get("content", ""),
                    url=result.get("url", ""),
                    position=idx + 1,
                )
                results.append(search_result)
            except (KeyError, TypeError) as e:
                logger.warning(f"Failed to parse result: {e}")
                continue

        logger.info(f"Retrieved {len(results)} results from Tavily")
        return results

    @staticmethod
    def _sanitize_params(params: Dict[str, Any]) -> Dict[str, Any]:
        """Remove sensitive information from params for logging."""
        sanitized = params.copy()
        if "api_key" in sanitized:
            sanitized["api_key"] = "***REDACTED***"
        return sanitized

    def search_as_json(
        self,
        query: str,
        max_results: Optional[int] = None,
        language: str = "en",
        safe_mode: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Execute a web search and return results as JSON-serializable dicts.

        Args:
            query: Search query string.
            max_results: Maximum number of results.
            language: Language code.
            safe_mode: Enable safe search.

        Returns:
            List of dictionaries containing search results.
        """
        results = self.search(query, max_results, language, safe_mode)
        return [result.to_dict() for result in results]
