import json
import os
import tempfile
from pathlib import Path
import pytest
from loam_iiif.cache import ManifestCache

def test_default_cache_dir():
    """Test that cache uses system temp dir by default"""
    cache = ManifestCache()
    expected_path = Path(tempfile.gettempdir()) / "loam-iiif"
    assert cache.cache_dir == expected_path

def test_get_invalid_json(tmp_path):
    """Test handling of invalid JSON in cached file"""
    cache = ManifestCache(cache_dir=tmp_path)
    test_url = "http://example.com/manifest.json"
    
    # Create an invalid JSON file in the cache
    manifest_path = cache._get_manifest_path(test_url)
    manifest_path.parent.mkdir(parents=True)
    with manifest_path.open('w') as f:
        f.write("invalid json{")
    
    # Should return None when JSON is invalid
    assert cache.get(test_url) is None

def test_get_io_error(tmp_path, monkeypatch):
    """Test handling of IOError when reading cache"""
    cache = ManifestCache(cache_dir=tmp_path)
    test_url = "http://example.com/manifest.json"
    
    # Create a test manifest file
    manifest_path = cache._get_manifest_path(test_url)
    manifest_path.parent.mkdir(parents=True)
    with manifest_path.open('w') as f:
        json.dump({"test": "data"}, f)
    
    # Mock open to raise IOError
    def mock_open(*args, **kwargs):
        raise IOError("Test IO error")
    
    monkeypatch.setattr(Path, "open", mock_open)
    assert cache.get(test_url) is None

def test_put_io_error(tmp_path, monkeypatch):
    """Test handling of IOError when writing cache"""
    cache = ManifestCache(cache_dir=tmp_path)
    test_url = "http://example.com/manifest.json"
    test_data = {"test": "data"}
    
    # Mock os.open to raise IOError
    def mock_open(*args, **kwargs):
        raise IOError("Test IO error")
    
    monkeypatch.setattr(os, "open", mock_open)
    assert cache.put(test_url, test_data) is False