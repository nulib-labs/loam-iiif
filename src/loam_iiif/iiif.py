import json
import logging
import re
from typing import List, Set, Tuple, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from iiif_prezi3 import Manifest
from piffle.image import IIIFImageClient
from piffle.presentation import IIIFPresentation

from .cache import ManifestCache

logger = logging.getLogger(__name__)


class TrailingCommaJSONDecoder(json.JSONDecoder):
    def decode(self, s):
        # More robust handling of trailing commas in nested structures
        def fix_commas(match):
            # Replace any comma followed by closing bracket/brace
            return match.group(1)
            
        # Fix array and object trailing commas at any nesting level
        s = re.sub(r',(\s*[\]\}])', fix_commas, s)
        return super().decode(s)


class IIIFClient:
    """
    A client for interacting with IIIF APIs, handling data fetching with retries.
    """

    DEFAULT_RETRY_TOTAL = 2
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
        cache_dir: Optional[str] = "manifests",
        skip_cache: bool = False,
        no_cache: bool = False,
    ):
        """
        Initializes the IIIFClient with a configured requests session.

        Args:
            retry_total (int): Total number of retries.
            backoff_factor (float): Backoff factor for retries.
            status_forcelist (Optional[List[int]]): HTTP status codes to retry on.
            allowed_methods (Optional[List[str]]): HTTP methods to retry.
            timeout (Optional[float]): Timeout for HTTP requests in seconds.
            cache_dir (Optional[str]): Directory for caching manifests.
            skip_cache (bool): If True, bypass cache for reads but still write.
            no_cache (bool): If True, disable caching completely.
        """
        self.timeout = timeout
        self.session = requests.Session()
        self.skip_cache = skip_cache
        self.no_cache = no_cache
        
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
        
        # Initialize cache if enabled
        self.cache = None if no_cache else ManifestCache(cache_dir)

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
        Fetches JSON data from a given URL with error handling and caching.

        Args:
            url (str): The URL to fetch data from.

        Returns:
            dict: The JSON data retrieved from the URL.

        Raises:
            requests.HTTPError: If the HTTP request returned an unsuccessful status code.
            requests.RequestException: For other request-related errors.
            ValueError: If the response content is not valid JSON.
        """
        # Try cache first if enabled and not skipping
        if self.cache and not self.skip_cache:
            cached_data = self.cache.get(url)
            if cached_data is not None:
                return cached_data
                
        logger.debug(f"Fetching URL: {url}")
        try:
            response = self.session.get(
                url,
                timeout=self.timeout,
                headers={"Accept": "application/json, application/ld+json"},
            )
            response.raise_for_status()
            data = json.loads(response.text, cls=TrailingCommaJSONDecoder)
            logger.debug(f"Successfully fetched data from {url}")
            
            # Cache the response if caching is enabled
            if self.cache and not self.no_cache:
                self.cache.put(url, data)
                
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
                continue  # Continue processing other collections instead of returning

            try:
                items = data.get("items") or (data.get("collections", []) + data.get("manifests", [])) # Fallback for IIIF Presentation API 2.0

                manifest_items = [item for item in items if "manifest" in self._normalize_item_type(item)]
                manifest_item_ids = [self._normalize_item_id(item, url) for item in manifest_items]
                manifest_item_ids = list(filter(None, manifest_item_ids))
                manifest_ids.update(manifest_item_ids)

                if max_manifests and len(manifest_ids) >= max_manifests:
                    logger.info(f"Reached maximum number of manifests: {max_manifests}")
                    break

                # Log each manifest added
                for manifest_id in manifest_ids:
                    logger.debug(f"Added manifest: {manifest_id}")

                nested_collection_items = [item for item in items if "collection" in self._normalize_item_type(item)]
                nested_collection_items_ids = [self._normalize_item_id(item, url) for item in nested_collection_items]
                nested_collection_items_ids = list(filter(None, nested_collection_items_ids))

                # Log each nested collection found
                for collection_id in nested_collection_items_ids:
                    logger.debug(f"Found nested collection: {collection_id}")

                # An ID is also a URL
                collection_urls_queue.extend(nested_collection_items_ids)
                
                # Only add collection to processed set if we successfully processed it
                collection_ids.add(url)
                logger.info(f"Processing collection: {url}")

            except Exception as e:
                logger.error(f"Error processing {url}: {e}")
                continue

        manifest_ids = list(manifest_ids)[:max_manifests]

        logger.info(f"Completed traversal of {collection_url}")
        logger.info(
            f"Found {len(manifest_ids)} unique manifests and {(len(collection_ids) - 1)} nested collections" # -1 to exclude the root collection
        )

        return manifest_ids, list(collection_ids)

    def get_manifest_images(self, manifest_url: str, width: int = 768, height: int = 2000, format: str = 'jpg', exact: bool = False, use_max: bool = False) -> List[str]:
        """
        Extract formatted image URLs from a manifest with specified dimensions.

        Args:
            manifest_url (str): The URL of the IIIF manifest
            width (int): Desired width of images
            height (int): Desired height of images
            format (str): Image format (e.g., 'jpg', 'png')
            exact (bool): If True, use exact dimensions without aspect ratio preservation
            use_max (bool): If True, use 'max' size for v3 or 'full' size for v2 instead of specific dimensions

        Returns:
            List[str]: List of formatted IIIF image URLs
        """
        try:
            data = self.fetch_json(manifest_url)
            image_ids = []

            # Check @context to determine IIIF version
            context = data.get("@context")
            is_v3 = context == "http://iiif.io/api/presentation/3/context.json"
            is_v2 = context == "http://iiif.io/api/presentation/2/context.json"

            # Parse manifest based on version
            if is_v3:
                try:
                    items = data.get("items", [])
                    for canvas in items:
                        if not isinstance(canvas, dict):
                            continue
                            
                        # Handle both items and sequences (some v3 can use sequences)
                        canvas_items = canvas.get("items", [])
                        
                        for anno_page in canvas_items:
                            if not isinstance(anno_page, dict):
                                continue
                                
                            # Get items from annotation page
                            anno_items = anno_page.get("items", [])
                            for annotation in anno_items:
                                if not isinstance(annotation, dict):
                                    continue
                                    
                                body = annotation.get("body", {})
                                if isinstance(body, dict):
                                    # Try to get image ID from different possible locations
                                    image_id = None
                                    
                                    # First try direct ID from body
                                    if "id" in body:
                                        image_id = body["id"]
                                        # If it's a full image URL, extract base URL
                                        if '/full/' in image_id:
                                            image_id = image_id.split('/full/')[0]
                                    
                                    # If no direct ID, try service
                                    if not image_id and "service" in body:
                                        service = body["service"]
                                        # Handle both list and direct object formats
                                        if isinstance(service, list) and service:
                                            service = service[0]
                                        if isinstance(service, dict):
                                            # Try both @id and id
                                            image_id = service.get("@id") or service.get("id")
                                            # Add even if None to trigger error handling
                                            image_ids.append(image_id)
                                    elif image_id:
                                        image_ids.append(image_id)
                                        
                except Exception as e:
                    logger.error(f"Error parsing IIIF 3.0 manifest: {e}")
                    return []

            elif is_v2:
                # IIIF 2.0 parsing
                if "sequences" in data:
                    for canvas in data["sequences"][0]["canvases"]:
                        if "images" in canvas:
                            for image in canvas["images"]:
                                # Check for direct resource @id first (NLS style)
                                if "@id" in image.get("resource", {}):
                                    image_id = image["resource"]["@id"]
                                    # Convert full image URL to IIIF base URL
                                    if '/full/' in image_id:
                                        parts = image_id.split('/full/')
                                        image_id = parts[0]
                                    image_ids.append(image_id)
                                # Fallback to service ID if available
                                elif "@id" in image["resource"].get("service", {}):
                                    image_id = image["resource"]["service"]["@id"]
                                    image_ids.append(image_id)
            else:
                logger.error(f"Unsupported or missing IIIF context in manifest: {context}")
                return []

            if not image_ids:
                logger.debug(f"No image IDs found in manifest {manifest_url}")
                return []

            urls = []
            for image_id in image_ids:
                try:
                    if image_id is None:
                        raise TypeError("expected string or bytes-like object")
                    # Remove any trailing /info.json
                    image_id = re.sub(r'/info\.json$', '', image_id)
                    # Format as IIIF URL with size parameter based on version and options
                    if not re.search(r'/full/(?:max|full|!\d+,\d+|\d+,\d+)/0/default\.jpg$', image_id):
                        if use_max:
                            # Use 'full' for v2 manifests and 'max' for v3
                            size_param = "full" if is_v2 else "max"
                        else:
                            size_param = f"{'!' if not exact else ''}{width},{height}"
                        image_id = f"{image_id}/full/{size_param}/0/default.{format}"
                    urls.append(image_id)
                except Exception as e:
                    logger.error(f"Error formatting image URL for ID {image_id}: {e}")
                    continue

            return urls

        except Exception as e:
            logger.error(f"Error extracting images from manifest {manifest_url}: {e}")
            raise
