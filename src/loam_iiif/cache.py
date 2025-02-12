import hashlib
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

class ManifestCache:
    """Manages cached IIIF manifest files using a pairtree directory structure."""

    def __init__(self, cache_dir: str | Path = None):
        """
        Initialize the manifest cache.
        
        Args:
            cache_dir: Base directory for cached manifests. If None, uses system temp directory.
        """
        if cache_dir is None:
            cache_dir = os.path.join(tempfile.gettempdir(), "loam-iiif")
        self.cache_dir = Path(cache_dir)
        
    def _get_pairtree_path(self, manifest_url: str) -> Path:
        """Generate a pairtree path for a manifest URL."""
        # Create a hash of the URL to use as the basis for the pairtree
        hash_str = hashlib.sha256(manifest_url.encode()).hexdigest()
        
        # Use pairs of characters from the hash to create directory levels
        # e.g., 'abcdef' -> 'ab/cd/ef'
        pairs = [hash_str[i:i+2] for i in range(0, 6, 2)]
        return self.cache_dir.joinpath(*pairs)
    
    def _get_manifest_path(self, manifest_url: str) -> Path:
        """Get the full path for a manifest file."""
        pairtree_dir = self._get_pairtree_path(manifest_url)
        # Use the last 8 chars of hash as filename
        hash_str = hashlib.sha256(manifest_url.encode()).hexdigest()
        return pairtree_dir / f"{hash_str[-8:]}.json"
    
    def get(self, manifest_url: str) -> Optional[dict]:
        """
        Retrieve a manifest from the cache.
        
        Args:
            manifest_url: URL of the manifest to retrieve
            
        Returns:
            The manifest data if found, None otherwise
        """
        manifest_path = self._get_manifest_path(manifest_url)
        
        if not manifest_path.exists():
            return None
            
        try:
            with manifest_path.open('r', encoding='utf-8') as f:
                data = json.load(f)
                logger.debug(f"Cache hit for manifest: {manifest_url}")
                return data
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to read cached manifest {manifest_url}: {e}")
            return None
    
    def put(self, manifest_url: str, data: dict) -> bool:
        """
        Store a manifest in the cache.
        
        Args:
            manifest_url: URL of the manifest
            data: Manifest data to cache
            
        Returns:
            True if successful, False otherwise
        """
        manifest_path = self._get_manifest_path(manifest_url)
        
        try:
            # Ensure directory exists with proper permissions
            manifest_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            
            # Write file with restrictive permissions using os.open directly
            fd = os.open(str(manifest_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
                logger.debug(f"Cached manifest: {manifest_url}")
                return True
        except IOError as e:
            logger.warning(f"Failed to cache manifest {manifest_url}: {e}")
            return False