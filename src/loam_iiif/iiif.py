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

    def _normalize_item_id(self, item: dict, parent_url: str) -> str:
        """
        Gets a normalized item ID from a IIIF item.

        Args:
            item (dict): The item from a collection
            parent_url (str): The URL of the parent collection

        Returns:
            str: An normalized item ID.
        """
        id = item.get("id") or item.get("@id")

        if not id:
            logger.warning(
                f"Item without ID encountered in collection {parent_url}: {item}"
            )
            return None

        return id

    def _normalize_item_type(self, item: dict) -> str:
        """
        Gets a normalized item type from a IIIF item.

        Args:
            item (dict): The item from a collection

        Returns:
            str: An normalized item type.
        """
        type = item.get("type") or item.get("@type")

        if isinstance(type, list):
            type = type[0]

        return str(type).lower().split(":")[-1] if type else ""

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
        self, collection_url: str, max_manifests: int | None = None
    ) -> Tuple[List[str], List[str]]:
        """
        Traverses a IIIF collection, extracting unique manifests and nested collections.

        Args:
            collection_url (str): The URL of the IIIF collection to traverse.
            max_manifests (int | None): The maximum number of manifests to retrieve. If None, all manifests are retrieved.

        Returns:
            Tuple[List[str], List[str]]: A tuple containing a list of unique manifest URLs and a list of nested collection URLs.
        """
        manifest_ids: Set[str] = set()
        collection_ids: Set[str] = set()

        collection_urls_queue = [collection_url]

        while collection_urls_queue:
            url = collection_urls_queue.pop(0)

            if url in collection_ids:
                logger.debug(f"Already processed collection: {url}")
                continue

            try:
                data = self.fetch_json(url)
            except (requests.RequestException, ValueError):
                logger.warning(f"Skipping collection due to fetch error: {url}")
                return

            collection_ids.add(url)
            logger.info(f"Processing collection: {url}")

            try:
                items = data.get("items") or (data.get("collections", []) + data.get("manifests", [])) # Fallback for IIIF Presentation API 2.0

                manifest_items = [item for item in items if "manifest" in self._normalize_item_type(item)]
                manifest_item_ids = [self._normalize_item_id(item, url) for item in manifest_items]
                manifest_item_ids = list(filter(None, manifest_item_ids))
                manifest_ids.update(manifest_item_ids)

                if max_manifests and len(manifest_ids) >= max_manifests:
                    logger.info(f"Reached maximum number of manifests: {max_manifests}")
                    break

                if logger.debug:
                    for manifest_id in manifest_ids:
                        logger.debug(f"Added manifest: {manifest_id}")

                nested_collection_items = [item for item in items if "collection" in self._normalize_item_type(item)]
                nested_collection_items_ids = [self._normalize_item_id(item, url) for item in nested_collection_items]
                nested_collection_items_ids = list(filter(None, nested_collection_items_ids))

                if logger.debug:
                    for collection_id in nested_collection_items_ids:
                        logger.debug(f"Found nested collection: {collection_id}")

                # An ID is also a URL
                collection_urls_queue.extend(nested_collection_items_ids)

            except Exception as e:
                logger.error(f"Error processing {url}: {e}")
                continue

        manifest_ids = list(manifest_ids)[:max_manifests]

        logger.info(f"Completed traversal of {collection_url}")
        logger.info(
            f"Found {len(manifest_ids)} unique manifests and {(len(collection_ids) - 1)} nested collections" # -1 to exclude the root collection
        )

        return manifest_ids, list(collection_ids)
