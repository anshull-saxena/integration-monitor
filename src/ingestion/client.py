import logging
import requests
from typing import Dict, Any
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

logger = logging.getLogger(__name__)


class UpstreamClientException(Exception):
    """Raised when an upstream service returns a non-retryable 4xx client error."""
    pass


class UpstreamServerException(Exception):
    """Raised when an upstream service returns a retryable 5xx error or connection error."""
    pass


class UpstreamClient:
    """REST Client for upstream mock services with retries and backoff."""

    def __init__(self, base_url: str, timeout: float = 5.0, max_retries: int = 3, backoff_factor: float = 1.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

    def fetch_page(self, endpoint: str, page: int = 1, page_size: int = 20, scenario_id: str = "default") -> Dict[str, Any]:
        """Fetch a page with exponential backoff and retries on 5xx or connection errors."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        params = {"page": page, "page_size": page_size, "scenario_id": scenario_id}

        @retry(
            reraise=True,
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential(multiplier=self.backoff_factor, min=0.2, max=4.0),
            retry=retry_if_exception_type((UpstreamServerException, requests.exceptions.RequestException)),
            before_sleep=before_sleep_log(logger, logging.WARNING),
        )
        def _request_with_retry():
            try:
                resp = requests.get(url, params=params, timeout=self.timeout)
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                logger.warning(f"Connection issue to {url}: {e}")
                raise UpstreamServerException(f"Connection error to {url}: {e}") from e

            if resp.status_code >= 500:
                logger.warning(f"Upstream server error {resp.status_code} from {url}")
                raise UpstreamServerException(f"HTTP {resp.status_code}: {resp.text}")
            elif resp.status_code >= 400:
                raise UpstreamClientException(f"HTTP {resp.status_code}: {resp.text}")

            try:
                return resp.json()
            except Exception as e:
                raise UpstreamServerException(f"Malformed JSON from {url}: {e}") from e

        return _request_with_retry()
