import json
import logging
import re
import html # Import the html module
from typing import List, Set, Tuple, Optional, Dict, Any, Union

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Assuming cache is in the same directory or installed package
try:
    from .cache import ManifestCache
except ImportError:
    # Fallback if running as a script and cache.py is in the same dir
    from cache import ManifestCache


logger = logging.getLogger(__name__)


class TrailingCommaJSONDecoder(json.JSONDecoder):
    def decode(self, s):
        # More robust handling of trailing commas in nested structures
        def fix_commas(match):
            # Replace any comma followed by closing bracket/brace
            return match.group(1)

        # Fix array and object trailing commas at any nesting level
        s = re.sub(r',(\s*[\]\}])', fix_commas, s)
        try:
            return super().decode(s)
        except json.JSONDecodeError as e:
            logger.error(f"JSON Decode Error: {e}. Original string snippet: {s[:500]}...")
            # Optionally re-raise or return a default value like None or {}
            raise # Re-raise by default


class IIIFClient:
    """
    A client for interacting with IIIF APIs, handling data fetching with retries,
    caching, and generating text chunks for embeddings.
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

    def _normalize_item_id(self, item: dict, parent_url: str) -> Optional[str]:
        """
        Gets a normalized item ID from a IIIF item (handles 'id' and '@id').

        Args:
            item (dict): The item from a collection
            parent_url (str): The URL of the parent collection (for logging)

        Returns:
            Optional[str]: A normalized item ID or None if not found.
        """
        id_val = item.get("id") or item.get("@id")

        if not id_val:
            logger.warning(
                f"Item without ID encountered in resource {parent_url}: {item}"
            )
            return None

        return str(id_val) # Ensure it's a string

    def _normalize_item_type(self, item: dict) -> str:
        """
        Gets a normalized item type from a IIIF item (handles 'type' and '@type').

        Args:
            item (dict): The item from a collection

        Returns:
            str: An normalized item type (lowercase).
        """
        type_val = item.get("type") or item.get("@type")

        if isinstance(type_val, list):
            # Take the first type if it's a list
            type_val = type_val[0] if type_val else None

        # Normalize common variations like sc:Collection to collection
        return str(type_val).lower().split(':')[-1] if type_val else ""

    def _extract_iiif_text(
        self,
        data: Optional[Union[Dict[str, List[str]], List[str], str]],
        strip_tags: bool = True
    ) -> Optional[str]:
        """
        Extracts text content from IIIF language maps or simple string/list fields,
        decodes HTML entities, and optionally strips HTML tags.

        Handles structures like:
        - {"none": ["<span>value1</span>", "value2"]}
        - {"en": ["value"]}
        - ["value1", "value2"]
        - "value"
        - {"@value": "value", "@language": "en"} (IIIF P2 language literal)

        Args:
            data: The IIIF field value.
            strip_tags (bool): If True (default), remove HTML tags from the text.

        Returns:
            Optional[str]: The cleaned, extracted text, joined if multiple values, or None.
        """
        if not data:
            return None

        raw_text_values = []

        if isinstance(data, str):
            raw_text_values.append(data)
        elif isinstance(data, list):
            # Handle lists of strings or lists of P2 language objects
            for item in data:
                if isinstance(item, str):
                    raw_text_values.append(item)
                elif isinstance(item, dict) and "@value" in item:
                    raw_text_values.append(item["@value"])
        elif isinstance(data, dict):
            # Handle P3 language map
            if any(lang in data for lang in ["en", "none"] + list(data.keys())): # Check if keys look like lang codes
                lang_keys = list(data.keys())
                key_to_use = None
                if "en" in lang_keys:
                    key_to_use = "en"
                elif "none" in lang_keys:
                    key_to_use = "none"
                elif lang_keys:
                    key_to_use = lang_keys[0] # Fallback to first key

                if key_to_use and isinstance(data.get(key_to_use), list):
                    for item in data[key_to_use]:
                        if isinstance(item, str):
                            raw_text_values.append(item)
            # Handle P2 language literal object
            elif "@value" in data:
                 raw_text_values.append(data["@value"])


        if not raw_text_values:
            return None

        # --- Clean the extracted text ---
        cleaned_text_values = []
        for text in raw_text_values:
            if not isinstance(text, str): # Skip if somehow a non-string got in
                continue
            # 1. Decode HTML entities (e.g., ' -> ') - Always do this
            text = html.unescape(text)

            # 2. Optionally strip HTML tags
            if strip_tags:
                # Basic regex for stripping tags. Consider BeautifulSoup for complex HTML.
                text = re.sub(r'<[^>]+>', '', text)

            # 3. Strip leading/trailing whitespace that might remain
            cleaned_text = text.strip()
            if cleaned_text: # Only add if there's content left after cleaning
                 cleaned_text_values.append(cleaned_text)

        return ", ".join(cleaned_text_values) if cleaned_text_values else None


    def fetch_json(self, url: str) -> Optional[dict]:
        """
        Fetches JSON data from a given URL with error handling and caching.

        Args:
            url (str): The URL to fetch data from.

        Returns:
            Optional[dict]: The JSON data retrieved, or None if fetching/parsing fails.

        Raises:
            requests.HTTPError: If the HTTP request returned an unsuccessful status code
                                and retries failed.
            requests.RequestException: For other request-related errors if retries fail.
        """
        # Try cache first if enabled and not skipping
        if self.cache and not self.skip_cache:
            cached_data = self.cache.get(url)
            if cached_data is not None:
                logger.debug(f"Cache hit for URL: {url}")
                return cached_data
            else:
                 logger.debug(f"Cache miss for URL: {url}")

        logger.debug(f"Fetching URL: {url}")
        try:
            response = self.session.get(
                url,
                timeout=self.timeout,
                headers={"Accept": "application/json, application/ld+json"},
            )
            response.raise_for_status() # Will raise HTTPError for bad status codes (4xx, 5xx) after retries

            # Use custom decoder that handles trailing commas
            data = json.loads(response.text, cls=TrailingCommaJSONDecoder)
            logger.debug(f"Successfully fetched and parsed data from {url}")

            # Cache the response if caching is enabled
            if self.cache and not self.no_cache:
                self.cache.put(url, data)

            return data
        except requests.HTTPError as e:
            # Log error after retries have failed
            if e.response is not None:
                logger.error(f"HTTP error after retries while fetching {url}: {e.response.status_code} {e.response.reason}")
            else:
                logger.error(f"HTTP error after retries while fetching {url}: {e}")
            raise # Re-raise HTTPError as expected by tests
        except requests.RequestException as e:
            logger.error(f"Request exception after retries while fetching {url}: {e}")
            raise # Re-raise RequestException as expected by tests
        except json.JSONDecodeError as e: # Catches JSONDecodeError from our custom decoder
            logger.error(f"Invalid JSON response from {url}: {e}")
            raise # Re-raise JSONDecodeError as expected by tests
        except Exception as e:
            logger.error(f"An unexpected error occurred while fetching {url}: {e}")
            return None


    def get_manifests_and_collections_ids(
        self, collection_url: str, max_manifests: int | None = None
    ) -> Tuple[List[str], List[str]]:
        """
        Traverses a IIIF collection, extracting unique manifests and nested collections.
        Handles both Presentation API 2.0 and 3.0 structures, including 2.1.1 pagination.

        Args:
            collection_url (str): The URL of the IIIF collection to traverse.
            max_manifests (int | None): The maximum number of manifests to retrieve. If None, all manifests are retrieved.

        Returns:
            Tuple[List[str], List[str]]: A tuple containing a list of unique manifest URLs and a list of nested collection URLs.
        """
        manifest_ids: Set[str] = set()
        processed_collection_ids: Set[str] = set() # Track processed collections to avoid loops/redundancy
        successfully_processed_collections: Set[str] = set() # Track only successfully processed collections
        collection_urls_queue = [collection_url]

        while collection_urls_queue:
            # Check manifest limit before fetching next collection
            if max_manifests is not None and len(manifest_ids) >= max_manifests:
                logger.info(f"Reached maximum number of manifests ({max_manifests}). Stopping traversal.")
                break

            url = collection_urls_queue.pop(0)

            if url in processed_collection_ids:
                logger.debug(f"Already processed collection: {url}")
                continue

            try:
                data = self.fetch_json(url)
            except (requests.RequestException, json.JSONDecodeError) as e:
                logger.warning(f"Skipping collection due to fetch error: {url}")
                processed_collection_ids.add(url) # Mark as processed even if failed
                continue # Continue processing other collections
            
            if data is None:
                logger.warning(f"Skipping collection due to fetch/parse error: {url}")
                processed_collection_ids.add(url) # Mark as processed even if failed
                continue # Continue processing other collections

            processed_collection_ids.add(url)
            successfully_processed_collections.add(url)  # Only add to successful list if we got data
            logger.info(f"Processing collection: {url}")

            try:
                # Check for IIIF 2.1.1 pagination first
                if "first" in data and ("collections" not in data and "manifests" not in data and "items" not in data):
                    logger.info(f"Detected IIIF 2.1.1 paginated collection: {url}")
                    manifest_count, collection_count = self._process_paginated_collection(
                        data, manifest_ids, collection_urls_queue, processed_collection_ids, max_manifests
                    )
                    logger.debug(f"Found {manifest_count} new manifests and {collection_count} new collections via pagination in {url}")
                else:
                    # Handle P3 'items', P2 'collections'/'manifests' (non-paginated)
                    items = data.get("items") # P3
                    if items is None: # Try P2 structure
                        # Combine P2 collections and manifests into a single list to iterate
                        items = data.get("collections", []) + data.get("manifests", [])

                    if not isinstance(items, list):
                        logger.warning(f"Expected 'items' or 'collections'/'manifests' to be a list in {url}, found {type(items)}. Skipping items.")
                        items = []

                    current_manifest_count = 0
                    current_collection_count = 0

                    for item in items:
                        if not isinstance(item, dict):
                            logger.warning(f"Skipping non-dictionary item in collection {url}: {item}")
                            continue

                        item_type = self._normalize_item_type(item)
                        item_id = self._normalize_item_id(item, url)

                        if not item_id:
                            continue # Skip items without an ID

                        if "manifest" in item_type:
                            if max_manifests is None or len(manifest_ids) < max_manifests:
                                if item_id not in manifest_ids:
                                    manifest_ids.add(item_id)
                                    current_manifest_count += 1
                                    logger.debug(f"Added manifest: {item_id}")
                                    # Check limit again after adding
                                    if max_manifests is not None and len(manifest_ids) >= max_manifests:
                                        break # Break inner loop if limit reached
                            else:
                                 # Break inner loop if limit reached before processing this item
                                break

                        elif "collection" in item_type:
                            if item_id not in processed_collection_ids and item_id not in collection_urls_queue:
                                collection_urls_queue.append(item_id)
                                current_collection_count += 1
                                logger.debug(f"Found nested collection: {item_id}")
                            elif item_id in processed_collection_ids:
                                logger.debug(f"Already processed collection: {item_id}")
                            elif item_id in collection_urls_queue:
                                logger.debug(f"Collection already in queue: {item_id}")

                    logger.debug(f"Found {current_manifest_count} new manifests and {current_collection_count} new collections in {url}")

            except Exception as e:
                logger.error(f"Error processing {url}: {e}")
                # Remove from successfully processed collections if it was added
                successfully_processed_collections.discard(url)
                continue # Continue with the next collection URL

        # Ensure we don't exceed max_manifests if the limit was hit exactly
        final_manifest_ids = list(manifest_ids)
        if max_manifests is not None:
            final_manifest_ids = final_manifest_ids[:max_manifests]

        logger.info(f"Completed traversal starting from {collection_url}")
        logger.info(
            f"Found {len(final_manifest_ids)} unique manifests and {len(successfully_processed_collections)} collections processed"
        )

        return final_manifest_ids, list(successfully_processed_collections)

    # --- Methods for Chunking ---

    def create_manifest_chunks(
        self,
        manifest_urls: List[str],
        strip_tags: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Fetches IIIF Manifests and converts them into structured chunks
        suitable for vector embeddings. Handles both Presentation API v2 and v3 fields
        for parent collections ('within', 'partOf'). Rights and attribution are
        placed in metadata.

        Args:
            manifest_urls (List[str]): A list of IIIF Manifest URLs.
            strip_tags (bool): If True (default), remove HTML tags from extracted text fields.

        Returns:
            List[Dict[str, Any]]: A list of chunk dictionaries, each with
                                  'text' and 'metadata'.
        """
        chunks = []
        total_manifests = len(manifest_urls)
        logger.info(f"Starting chunk creation for {total_manifests} manifests. Stripping tags: {strip_tags}")

        for i, url in enumerate(manifest_urls):
            logger.info(f"Processing manifest {i+1}/{total_manifests}: {url}")
            manifest_data = self.fetch_json(url)

            if manifest_data is None:
                logger.warning(f"Skipping chunk creation for failed manifest: {url}")
                continue

            try:
                manifest_id = self._normalize_item_id(manifest_data, url) # Use helper
                if not manifest_id:
                    logger.warning(f"Manifest lacks an ID: {url}. Skipping.")
                    continue

                # --- Extract Core Information (passing strip_tags) ---
                title = self._extract_iiif_text(manifest_data.get("label"), strip_tags=strip_tags)
                summary = self._extract_iiif_text(manifest_data.get("summary") or manifest_data.get("description"), strip_tags=strip_tags) # Check P2 'description' too
                rights = manifest_data.get("rights") or manifest_data.get("license") # Check P2 'license' too

                # Required Statement (Attribution) - Handles P3 and P2 structures
                req_statement = manifest_data.get("requiredStatement") # P3
                attribution_label = None
                attribution_value = None
                if isinstance(req_statement, dict): # P3 structure
                    attribution_label = self._extract_iiif_text(req_statement.get("label"), strip_tags=strip_tags)
                    attribution_value = self._extract_iiif_text(req_statement.get("value"), strip_tags=strip_tags)
                elif "attribution" in manifest_data: # P2 structure
                    attribution_label = "Attribution" # Default label for P2
                    attribution_value = self._extract_iiif_text(manifest_data.get("attribution"), strip_tags=strip_tags)
                # Special case for Villanova's requiredStatement structure
                elif isinstance(manifest_data.get("requiredStatement"), dict) and "label" in manifest_data["requiredStatement"] and "value" in manifest_data["requiredStatement"]:
                     req_stmt_vu = manifest_data["requiredStatement"]
                     attribution_label = self._extract_iiif_text(req_stmt_vu.get("label"), strip_tags=strip_tags) or "Attribution"
                     attribution_value = self._extract_iiif_text(req_stmt_vu.get("value"), strip_tags=strip_tags)


                # Homepage - Handles P3 list and P2 string/object
                homepage_url = None
                homepage_label = None
                homepage_data = manifest_data.get("homepage")
                if isinstance(homepage_data, list) and homepage_data: # P3 list
                    homepage_entry = homepage_data[0]
                    if isinstance(homepage_entry, dict):
                        homepage_url = homepage_entry.get("id")
                        homepage_label = self._extract_iiif_text(homepage_entry.get("label"), strip_tags=strip_tags)
                elif isinstance(homepage_data, dict): # P3 single object or P2 object
                    homepage_url = homepage_data.get("id") or homepage_data.get("@id")
                    homepage_label = self._extract_iiif_text(homepage_data.get("label"), strip_tags=strip_tags)
                elif isinstance(homepage_data, str): # P2 simple string URL
                    homepage_url = homepage_data
                    # homepage_label = "Homepage" # Default label - let's leave it None if not specified
                
                # Store related field URL as fallback
                related_homepage_url = None
                if not homepage_url:
                    related_data = manifest_data.get("related")
                    if isinstance(related_data, dict) and related_data.get("@id"):
                        related_homepage_url = related_data.get("@id")
                    elif isinstance(related_data, list) and related_data:
                        for related_item in related_data:
                            if isinstance(related_item, dict) and related_item.get("@id"):
                                related_homepage_url = related_item.get("@id")
                                break

                # --- Extract Metadata Key-Value Pairs (passing strip_tags) ---
                metadata_list = manifest_data.get("metadata", [])
                metadata_dict = {}
                if isinstance(metadata_list, list):
                    for item in metadata_list:
                        if isinstance(item, dict):
                            # Handles P3 {label: {en:[]}, value: {none:[]}} and P2 {label:"", value:""}
                            label = self._extract_iiif_text(item.get("label"), strip_tags=strip_tags)
                            value = self._extract_iiif_text(item.get("value"), strip_tags=strip_tags)
                            if label and value:
                                # Handle potential duplicate labels if necessary, e.g., append
                                if label in metadata_dict:
                                     metadata_dict[label] += f"; {value}"
                                else:
                                     metadata_dict[label] = value
                                     
                                # Extract homepage from "About" metadata (priority over related field)
                                if not homepage_url and label.lower() == "about":
                                    # Look for "Permanent Link" in the raw value (before HTML stripping)
                                    import re
                                    raw_value = item.get("value")
                                    # Handle different value formats
                                    if isinstance(raw_value, dict):
                                        # Check for language map like {"none": ["<html>"], "en": ["<html>"]}
                                        for lang_values in raw_value.values():
                                            if isinstance(lang_values, list):
                                                for val in lang_values:
                                                    link_match = re.search(r'<a href="([^"]+)"[^>]*>Permanent Link</a>', str(val))
                                                    if link_match:
                                                        homepage_url = link_match.group(1)
                                                        break
                                            elif isinstance(lang_values, str):
                                                link_match = re.search(r'<a href="([^"]+)"[^>]*>Permanent Link</a>', lang_values)
                                                if link_match:
                                                    homepage_url = link_match.group(1)
                                                    break
                                            if homepage_url:
                                                break
                                    elif isinstance(raw_value, str):
                                        # Simple string value
                                        link_match = re.search(r'<a href="([^"]+)"[^>]*>Permanent Link</a>', raw_value)
                                        if link_match:
                                            homepage_url = link_match.group(1)
                
                # Use related field URL if no other homepage found
                if not homepage_url and related_homepage_url:
                    homepage_url = related_homepage_url
                
                # Extract rights information from attribution if not already found
                if not rights and attribution_value:
                    import re
                    # Look for rights.html or rights information URLs in the raw value first
                    raw_attribution = None
                    if isinstance(req_statement, dict) and "value" in req_statement:
                        raw_attribution = req_statement.get("value")
                    elif "attribution" in manifest_data:
                        raw_attribution = manifest_data.get("attribution")
                    
                    if raw_attribution:
                        rights_match = re.search(r'<a href="([^"]*rights[^"]*\.html)"', raw_attribution)
                        if rights_match:
                            rights = rights_match.group(1)

                # --- Extract Parent Collection Info (Handles P3 'partOf' and P2 'within') ---
                parent_collections = []
                part_of_list = manifest_data.get("partOf", []) # P3 field
                if isinstance(part_of_list, list):
                    for item in part_of_list:
                        if isinstance(item, dict):
                            coll_id = self._normalize_item_id(item, url)
                            coll_label = self._extract_iiif_text(item.get("label"), strip_tags=strip_tags)
                            coll_type = self._normalize_item_type(item)
                            # Only include if it's identified as a collection
                            if coll_id and "collection" in coll_type:
                                parent_collections.append({
                                    "id": coll_id,
                                    "label": coll_label or "Parent Collection (Label Unknown)"
                                })

                # If partOf didn't yield results, check P2 'within'
                if not parent_collections:
                    within_data = manifest_data.get("within")
                    if isinstance(within_data, str): # Simple URI string
                        # Fetch the collection to get its label
                        try:
                            collection_data = self.fetch_json(within_data)
                            if collection_data:
                                coll_label = self._extract_iiif_text(collection_data.get("label"), strip_tags=strip_tags)
                                parent_collections.append({
                                    "id": within_data,
                                    "label": coll_label or "Parent Collection (Label Unknown)"
                                })
                            else:
                                parent_collections.append({
                                    "id": within_data,
                                    "label": "Parent Collection (Label Unknown)"
                                })
                        except Exception as e:
                            logger.warning(f"Failed to fetch parent collection data from {within_data}: {e}")
                            parent_collections.append({
                                "id": within_data,
                                "label": "Parent Collection (Label Unknown)"
                            })
                    elif isinstance(within_data, dict): # Object reference
                         coll_id = self._normalize_item_id(within_data, url)
                         coll_label = self._extract_iiif_text(within_data.get("label"), strip_tags=strip_tags)
                         coll_type = self._normalize_item_type(within_data)
                         if coll_id and "collection" in coll_type:
                              parent_collections.append({
                                    "id": coll_id,
                                    "label": coll_label or "Parent Collection (Label Unknown)"
                              })
                    elif isinstance(within_data, list): # List of references (less common for within)
                         for item in within_data:
                             if isinstance(item, str):
                                 # Fetch the collection to get its label
                                 try:
                                     collection_data = self.fetch_json(item)
                                     if collection_data:
                                         coll_label = self._extract_iiif_text(collection_data.get("label"), strip_tags=strip_tags)
                                         parent_collections.append({
                                             "id": item,
                                             "label": coll_label or "Parent Collection (Label Unknown)"
                                         })
                                     else:
                                         parent_collections.append({
                                             "id": item,
                                             "label": "Parent Collection (Label Unknown)"
                                         })
                                 except Exception as e:
                                     logger.warning(f"Failed to fetch parent collection data from {item}: {e}")
                                     parent_collections.append({
                                         "id": item,
                                         "label": "Parent Collection (Label Unknown)"
                                     })
                             elif isinstance(item, dict):
                                 coll_id = self._normalize_item_id(item, url)
                                 coll_label = self._extract_iiif_text(item.get("label"), strip_tags=strip_tags)
                                 coll_type = self._normalize_item_type(item)
                                 if coll_id and "collection" in coll_type:
                                      parent_collections.append({
                                            "id": coll_id,
                                            "label": coll_label or "Parent Collection (Label Unknown)"
                                      })


                # --- Construct Text Chunk ---
                text_parts = []
                text_parts.append(f"Manifest ID: {manifest_id}")
                if title:
                    text_parts.append(f"Title: {title}")

                # Add parent collection info
                if parent_collections:
                     # Use label if available, otherwise just ID
                     part_of_strs = [f"{p.get('label', p['id'])} ({p['id']})" for p in parent_collections]
                     text_parts.append(f"Part Of: {'; '.join(part_of_strs)}")

                if summary:
                    text_parts.append(f"Summary: {summary}")

                # Add metadata fields from the 'metadata' block
                for label, value in metadata_dict.items():
                    # Use title() for consistency, check if label exists first
                    label_display = label.title() if label else "Metadata"
                    text_parts.append(f"{label_display}: {value}")

                # --- Construct Metadata ---
                chunk_metadata = {
                    "id": manifest_id,
                    "title": title, # Store the potentially cleaned title here too
                    "type": "Manifest", # Analogous to EAD level
                    "parent_collections": parent_collections, # Now populated by partOf or within
                    "homepage": homepage_url,
                    "thumbnail": None, # Placeholder, extract if needed
                    "rights": rights, # Moved from text
                    "attribution": None # Placeholder for attribution object/string
                }
                # Add attribution details if found
                if attribution_value:
                    chunk_metadata["attribution"] = {
                        "label": attribution_label,
                        "value": attribution_value
                    }
                elif attribution_label: # Handle case where only label might exist (unlikely but possible)
                     chunk_metadata["attribution"] = {"label": attribution_label, "value": None}


                # Extract thumbnail URL if present (handles P3 list and P2 object/string)
                thumbnail_data = manifest_data.get("thumbnail")
                if isinstance(thumbnail_data, list) and thumbnail_data: # P3 list
                    thumb_entry = thumbnail_data[0]
                    if isinstance(thumb_entry, dict):
                         chunk_metadata["thumbnail"] = thumb_entry.get("id")
                elif isinstance(thumbnail_data, dict): # P2 object
                     chunk_metadata["thumbnail"] = thumbnail_data.get("@id") or thumbnail_data.get("id")
                elif isinstance(thumbnail_data, str): # P2 string URL
                     chunk_metadata["thumbnail"] = thumbnail_data


                # --- Create Chunk ---
                chunks.append({
                    "text": "\n".join(text_parts),
                    "metadata": chunk_metadata
                })

            except Exception as e:
                logger.error(f"Error processing manifest data for {url}: {e}", exc_info=True)
                continue # Skip this manifest on error

        logger.info(f"Finished chunk creation. Generated {len(chunks)} chunks.")
        return chunks

    def save_chunks_to_json(self, chunks: List[Dict[str, Any]], output_file: str):
        """
        Save generated chunks to a JSON file.

        Args:
            chunks (List[Dict[str, Any]]): List of chunks to save.
            output_file (str): Path to the output JSON file.
        """
        logger.info(f"Saving {len(chunks)} chunks to {output_file}")
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(chunks, f, indent=2, ensure_ascii=False)
            logger.info(f"Successfully saved chunks to {output_file}")
        except IOError as e:
            logger.error(f"Failed to write chunks to {output_file}: {e}")
        except Exception as e:
            logger.error(f"An unexpected error occurred during saving: {e}")

    def create_and_save_manifest_chunks(
        self,
        collection_url: str,
        output_file: str,
        max_manifests: Optional[int] = None,
        strip_tags: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Traverses a IIIF Collection, creates manifest chunks, and saves them to a JSON file.

        Args:
            collection_url (str): The starting URL of the IIIF Collection.
            output_file (str): Path to the output JSON file for the chunks.
            max_manifests (Optional[int]): Maximum number of manifests to process.
            strip_tags (bool): If True (default), remove HTML tags from extracted text fields
                               during chunk creation.

        Returns:
            List[Dict[str, Any]]: The list of generated chunks.
        """
        logger.info(f"Starting process for collection: {collection_url}")
        manifest_urls, _ = self.get_manifests_and_collections_ids(
            collection_url, max_manifests=max_manifests
        )

        if not manifest_urls:
            logger.warning(f"No manifest URLs found for collection: {collection_url}. No chunks generated.")
            return []

        # Pass strip_tags argument down
        chunks = self.create_manifest_chunks(manifest_urls, strip_tags=strip_tags)

        if chunks:
            self.save_chunks_to_json(chunks, output_file)
        else:
            logger.warning(f"No chunks were generated from the found manifests for collection: {collection_url}")

        return chunks
    
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

    def _process_paginated_collection(
        self, 
        collection_data: dict, 
        manifest_ids: Set[str], 
        collection_urls_queue: List[str], 
        processed_collection_ids: Set[str],
        max_manifests: Optional[int] = None
    ) -> Tuple[int, int]:
        """
        Process a paginated IIIF 2.1.1 collection by following the pagination links.
        
        Args:
            collection_data (dict): The top-level collection data containing pagination properties
            manifest_ids (Set[str]): Set to add found manifest IDs to
            collection_urls_queue (List[str]): Queue to add found collection URLs to 
            processed_collection_ids (Set[str]): Set of already processed collection IDs
            max_manifests (Optional[int]): Maximum number of manifests to retrieve
            
        Returns:
            Tuple[int, int]: Number of manifests and collections found
        """
        manifest_count = 0
        collection_count = 0
        
        # Start with the first page
        first_page_url = collection_data.get("first")
        if not first_page_url:
            logger.warning("Paginated collection has no 'first' property")
            return manifest_count, collection_count
            
        current_page_url = first_page_url
        page_number = 1
        
        # Get total for logging (optional)
        total_items = collection_data.get("total")
        if total_items:
            logger.info(f"Processing paginated collection with {total_items} total items")
        
        while current_page_url:
            # Check manifest limit before fetching next page
            if max_manifests is not None and len(manifest_ids) >= max_manifests:
                logger.info(f"Reached maximum number of manifests ({max_manifests}). Stopping pagination.")
                break
                
            logger.debug(f"Processing page {page_number}: {current_page_url}")
            
            try:
                page_data = self.fetch_json(current_page_url)
            except (requests.RequestException, json.JSONDecodeError) as e:
                logger.warning(f"Skipping page due to fetch error: {current_page_url}")
                break
                
            if page_data is None:
                logger.warning(f"Skipping page due to fetch/parse error: {current_page_url}")
                break
            
            # Process items in this page
            # Handle P3 'items', P2 'collections'/'manifests'
            items = page_data.get("items") # P3
            if items is None: # Try P2 structure
                # Combine P2 collections and manifests into a single list to iterate
                items = page_data.get("collections", []) + page_data.get("manifests", [])
            
            if not isinstance(items, list):
                logger.warning(f"Expected 'items' or 'collections'/'manifests' to be a list in page {current_page_url}, found {type(items)}. Skipping page.")
                items = []
                
            page_manifest_count = 0
            page_collection_count = 0
            
            for item in items:
                if not isinstance(item, dict):
                    logger.warning(f"Skipping non-dictionary item in page {current_page_url}: {item}")
                    continue

                item_type = self._normalize_item_type(item)
                item_id = self._normalize_item_id(item, current_page_url)

                if not item_id:
                    continue # Skip items without an ID

                if "manifest" in item_type:
                    if max_manifests is None or len(manifest_ids) < max_manifests:
                        if item_id not in manifest_ids:
                            manifest_ids.add(item_id)
                            manifest_count += 1
                            page_manifest_count += 1
                            logger.debug(f"Added manifest: {item_id}")
                            # Check limit again after adding
                            if max_manifests is not None and len(manifest_ids) >= max_manifests:
                                break # Break inner loop if limit reached
                    else:
                         # Break inner loop if limit reached before processing this item
                        break

                elif "collection" in item_type:
                    if item_id not in processed_collection_ids and item_id not in collection_urls_queue:
                        collection_urls_queue.append(item_id)
                        collection_count += 1
                        page_collection_count += 1
                        logger.debug(f"Found nested collection: {item_id}")
                    elif item_id in processed_collection_ids:
                        logger.debug(f"Already processed collection: {item_id}")
                    elif item_id in collection_urls_queue:
                        logger.debug(f"Collection already in queue: {item_id}")
                        
            logger.debug(f"Page {page_number}: found {page_manifest_count} manifests and {page_collection_count} collections")
            
            # Check if we should stop due to manifest limit
            if max_manifests is not None and len(manifest_ids) >= max_manifests:
                logger.info(f"Reached maximum number of manifests ({max_manifests}). Stopping pagination.")
                break
            
            # Get next page URL
            next_page_url = page_data.get("next")
            if next_page_url:
                current_page_url = next_page_url
                page_number += 1
            else:
                # No more pages
                logger.debug(f"No more pages. Processed {page_number} pages total.")
                break
                
        logger.info(f"Pagination complete. Found {manifest_count} manifests and {collection_count} collections across {page_number} pages.")
        return manifest_count, collection_count