import logging
from typing import List, Set, Tuple, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class IIIFClient:
    """
    A client for interacting with IIIF APIs, handling data fetching with retries.
    """

    DEFAULT_RETRY_TOTAL = 5
    DEFAULT_BACKOFF_FACTOR = 1
    DEFAULT_STATUS_FORCELIST = [429, 500, 502, 503, 504]
    DEFAULT_ALLOWED_METHODS = ["GET", "POST"]

    def __init__(
        self,
        retry_total: int = DEFAULT_RETRY_TOTAL,
        backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
        status_forcelist: Optional[List[int]] = None,
        allowed_methods: Optional[List[str]] = None,
        timeout: Optional[float] = 10.0,
    ):
        """
        Initializes the IIIFClient with a configured requests session.

        Args:
            retry_total (int): Total number of retries.
            backoff_factor (float): Backoff factor for retries.
            status_forcelist (Optional[List[int]]): HTTP status codes to retry on.
            allowed_methods (Optional[List[str]]): HTTP methods to retry.
            timeout (Optional[float]): Timeout for HTTP requests in seconds.
        """
        self.timeout = timeout
        self.session = requests.Session()
        retries = Retry(
            total=retry_total,
            backoff_factor=backoff_factor,
            status_forcelist=status_forcelist or self.DEFAULT_STATUS_FORCELIST,
            allowed_methods=allowed_methods or self.DEFAULT_ALLOWED_METHODS,
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def __enter__(self):
        """
        Enables the use of IIIFClient as a context manager.
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Closes the session when exiting the context.
        """
        self.session.close()

    def fetch_json(self, url: str) -> dict:
        """
        Fetches JSON data from a given URL with error handling.

        Args:
            url (str): The URL to fetch data from.

        Returns:
            dict: The JSON data retrieved from the URL.

        Raises:
            requests.HTTPError: If the HTTP request returned an unsuccessful status code.
            requests.RequestException: For other request-related errors.
            ValueError: If the response content is not valid JSON.
        """
        logger.debug(f"Fetching URL: {url}")
        try:
            response = self.session.get(
                url,
                timeout=self.timeout,
                headers={"Accept": "application/json, application/ld+json"},
            )
            response.raise_for_status()
            data = response.json()
            logger.debug(f"Successfully fetched data from {url}")
            return data
        except requests.HTTPError as e:
            logger.error(f"HTTP error while fetching {url}: {e}")
            raise
        except requests.RequestException as e:
            logger.error(f"Request exception while fetching {url}: {e}")
            raise
        except ValueError as e:
            logger.error(f"Invalid JSON response from {url}: {e}")
            raise

    def get_manifests_and_collections_ids(
        self, collection_url: str
    ) -> Tuple[List[str], List[str]]:
        """
        Recursively traverses a IIIF collection, extracting unique manifests and nested collections.

        Args:
            collection_url (str): The URL of the IIIF collection to traverse.

        Returns:
            Tuple[List[str], List[str]]: A tuple containing a list of unique manifest URLs and a list of nested collection URLs.
        """
        seen_manifests: Set[str] = set()
        seen_collections: Set[str] = set()
        manifests: List[str] = []
        nested_collections: List[str] = []

        def _traverse(url: str):
            if url in seen_collections:
                logger.debug(f"Already processed collection: {url}")
                return
            logger.info(f"Processing collection: {url}")
            seen_collections.add(url)
            try:
                data = self.fetch_json(url)
            except (requests.RequestException, ValueError):
                logger.warning(f"Skipping collection due to fetch error: {url}")
                return

            # Determine IIIF Presentation API version and get items accordingly
            items = data.get("items")
            if items is None:
                # Fallback for IIIF Presentation API 2.0
                items = data.get("collections", []) + data.get("manifests", [])

            for item in items:
                item_type = item.get("type") or item.get("@type")
                item_id = item.get("id") or item.get("@id")
                if not item_id:
                    logger.warning(
                        f"Item without ID encountered in collection {url}: {item}"
                    )
                    continue

                # Normalize type for comparison
                if isinstance(item_type, list):
                    item_type = item_type[0]
                item_type_normalized = (
                    item_type.lower().split(":")[-1] if item_type else ""
                )

                if item_type_normalized == "manifest":
                    if item_id not in seen_manifests:
                        seen_manifests.add(item_id)
                        manifests.append(item_id)
                        logger.debug(f"Added manifest: {item_id}")
                elif item_type_normalized == "collection":
                    if item_id not in seen_collections:
                        nested_collections.append(item_id)
                        logger.debug(f"Found nested collection: {item_id}")
                        _traverse(item_id)
                else:
                    logger.debug(f"Unknown item type '{item_type}' in collection {url}")

        _traverse(collection_url)
        logger.info(f"Completed traversal of {collection_url}")
        logger.info(
            f"Found {len(manifests)} unique manifests and {len(nested_collections)} nested collections"
        )
        return manifests, nested_collections
