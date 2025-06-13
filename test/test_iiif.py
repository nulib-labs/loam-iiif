import json
import os
import pytest
import requests
import logging
from pathlib import Path
from unittest.mock import patch, MagicMock
from loam_iiif.iiif import IIIFClient, TrailingCommaJSONDecoder

FIXTURES_DIR = Path(__file__).parent / "fixtures"

def load_fixture(filename):
    """Helper to load a JSON fixture file"""
    with open(FIXTURES_DIR / filename, 'r') as f:
        return json.load(f, cls=TrailingCommaJSONDecoder)

def test_collection_with_manifests():
    """Test traversing a collection that contains manifests"""
    client = IIIFClient(no_cache=True)
    collection_data = load_fixture('iiif_v3_collection_with_manifests.json')
    
    def mock_fetch_json(url):
        if url == "https://api.dc.library.northwestern.edu/api/v2/collections/ba35820a-525a-4cfa-8f23-4891c9f798c4?as=iiif":
            return collection_data
        return {}
        
    client.fetch_json = mock_fetch_json

    # Get manifests and collections
    manifests, collections = client.get_manifests_and_collections_ids(
        "https://api.dc.library.northwestern.edu/api/v2/collections/ba35820a-525a-4cfa-8f23-4891c9f798c4?as=iiif"
    )

    # Test expectations
    assert len(manifests) == 3, "Should find 3 manifests in the collection"
    assert len(collections) == 1, "Should find 1 collection (root collection)"

    # Verify manifest URLs
    expected_manifests = [
        "https://api.dc.library.northwestern.edu/api/v2/works/e40479c4-06cb-48be-9d6b-adf47f238852?as=iiif",
        "https://api.dc.library.northwestern.edu/api/v2/works/f4720687-61b6-4dcd-aed0-b70eff985583?as=iiif",
        "https://api.dc.library.northwestern.edu/api/v2/works/faafca34-ecf4-4848-838a-da220d864042?as=iiif"
    ]
    for manifest in expected_manifests:
        assert manifest in manifests, f"Should find manifest {manifest}"

def test_get_manifest_images_v3():
    """Test extracting image URLs from a IIIF v3 manifest, including various service formats"""
    client = IIIFClient(no_cache=True)

    # Test cases for different service object formats
    test_cases = [
        # Original test case
        load_fixture('iiif_v3.json'),
        
        # Test case with service as list
        {
            "@context": "http://iiif.io/api/presentation/3/context.json",
            "items": [{
                "items": [{
                    "items": [{
                        "body": {
                            "service": [
                                {"@id": "https://iiif.test.org/service1"}
                            ]
                        }
                    }]
                }]
            }]
        },
        
        # Test case with service as direct object with @id
        {
            "@context": "http://iiif.io/api/presentation/3/context.json",
            "items": [{
                "items": [{
                    "items": [{
                        "body": {
                            "service": {
                                "@id": "https://iiif.test.org/service2"
                            }
                        }
                    }]
                }]
            }]
        },
        
        # Test case with service as direct object with id
        {
            "@context": "http://iiif.io/api/presentation/3/context.json",
            "items": [{
                "items": [{
                    "items": [{
                        "body": {
                            "service": {
                                "id": "https://iiif.test.org/service3"
                            }
                        }
                    }]
                }]
            }]
        },
        
        # Test case with empty service list
        {
            "@context": "http://iiif.io/api/presentation/3/context.json",
            "items": [{
                "items": [{
                    "items": [{
                        "body": {
                            "service": []
                        }
                    }]
                }]
            }]
        },
        
        # Test case with invalid service (not list or dict)
        {
            "@context": "http://iiif.io/api/presentation/3/context.json",
            "items": [{
                "items": [{
                    "items": [{
                        "body": {
                            "service": "invalid"
                        }
                    }]
                }]
            }]
        }
    ]

    for i, manifest_data in enumerate(test_cases):
        def mock_fetch_json(url):
            return manifest_data
            
        client.fetch_json = mock_fetch_json

        images = client.get_manifest_images("http://example.org/manifest")
        
        if i == 0:  # Original test case
            assert len(images) == 2, "Should find 2 images in the manifest"
            for image in images:
                assert image.startswith("https://iiif.dc.library.northwestern.edu/iiif/3/")
                assert image.endswith("/full/!768,2000/0/default.jpg")
        elif i == 1:  # Service as list
            assert len(images) == 1, "Should find 1 image with service list"
            assert images[0].startswith("https://iiif.test.org/service1")
        elif i == 2:  # Service as direct object with @id
            assert len(images) == 1, "Should find 1 image with service @id"
            assert images[0].startswith("https://iiif.test.org/service2")
        elif i == 3:  # Service as direct object with id
            assert len(images) == 1, "Should find 1 image with service id"
            assert images[0].startswith("https://iiif.test.org/service3")
        elif i == 4:  # Empty service list
            assert len(images) == 0, "Should find no images with empty service list"
        elif i == 5:  # Invalid service
            assert len(images) == 0, "Should find no images with invalid service"

def test_get_manifest_images_v2():
    """Test extracting image URLs from a IIIF v2 manifest"""
    client = IIIFClient(no_cache=True)

    test_cases = [
        # Original test case
        load_fixture('iiif_v2.json'),
        
        # Test case for service @id path
        {
            "@context": "http://iiif.io/api/presentation/2/context.json",
            "sequences": [{
                "canvases": [{
                    "images": [{
                        "resource": {
                            "service": {
                                "@id": "https://iiif.service.test/image1"
                            }
                        }
                    }]
                }]
            }]
        },
        
        # Test case for missing service
        {
            "@context": "http://iiif.io/api/presentation/2/context.json",
            "sequences": [{
                "canvases": [{
                    "images": [{
                        "resource": {}
                    }]
                }]
            }]
        },
        
        # Test case for service without @id
        {
            "@context": "http://iiif.io/api/presentation/2/context.json",
            "sequences": [{
                "canvases": [{
                    "images": [{
                        "resource": {
                            "service": {}
                        }
                    }]
                }]
            }]
        }
    ]

    for i, manifest_data in enumerate(test_cases):
        def mock_fetch_json(url):
            return manifest_data
            
        client.fetch_json = mock_fetch_json

        images = client.get_manifest_images("http://example.org/manifest")
        
        if i == 0:  # Original test case
            assert len(images) == 1, "Should find 1 image in the manifest"
            assert images[0].startswith("https://iiif.bodleian.ox.ac.uk/iiif/image/")
            assert images[0].endswith("/full/!768,2000/0/default.jpg")
        elif i == 1:  # Service @id path
            assert len(images) == 1, "Should find 1 image with service @id"
            assert images[0] == "https://iiif.service.test/image1/full/!768,2000/0/default.jpg"
        elif i == 2:  # Missing service
            assert len(images) == 0, "Should find no images when service is missing"
        elif i == 3:  # Service without @id
            assert len(images) == 0, "Should find no images when service has no @id"

def test_get_manifest_images_v2_service():
    """Test extracting image URLs from a IIIF v2 manifest when ID is in service object"""
    client = IIIFClient(no_cache=True)
    manifest_data = load_fixture('iiif_v2_manifest_service_id.json')
    
    def mock_fetch_json(url):
        return manifest_data
        
    client.fetch_json = mock_fetch_json

    images = client.get_manifest_images("http://example.org/manifest")
    
    assert len(images) == 1, "Should find 1 image in the manifest"
    assert images[0].startswith("https://iiif.bodleian.ox.ac.uk/iiif/image/43847824-6ec2-4bad-ba49-8acbeba6a6f2")
    assert images[0].endswith("/full/!768,2000/0/default.jpg")

def test_get_manifest_images_nls_v2():
    """Test extracting image IDs from NLS v2 manifest format"""
    client = IIIFClient(no_cache=True)

    # Use the NLS v2 fixture
    manifest_data = load_fixture("iiif_v2_nls_manifest.json")

    def mock_fetch_json(url):
        return manifest_data
        
    client.fetch_json = mock_fetch_json
    
    images = client.get_manifest_images("http://example.org/manifest")
    
    assert len(images) > 0, "Should have found image IDs in the manifest"
    # The actual manifest has empty image arrays, but this verifies our extraction logic works
    for image_url in images:
        assert image_url.startswith('https://view.nls.uk/iiif/'), "Image URLs should be from NLS domain"
        assert image_url.endswith('/default.jpg'), "Image URLs should end with default.jpg"

def test_normalize_item_type():
    """Test the _normalize_item_type method"""
    client = IIIFClient()
    
    # Test various type formats
    assert client._normalize_item_type({"type": "Collection"}) == "collection"
    assert client._normalize_item_type({"@type": "sc:Collection"}) == "collection"
    assert client._normalize_item_type({"type": "Manifest"}) == "manifest"
    assert client._normalize_item_type({"@type": "sc:Manifest"}) == "manifest"
    assert client._normalize_item_type({"type": ["Collection"]}) == "collection"
    assert client._normalize_item_type({}) == ""

def test_normalize_item_id():
    """Test the _normalize_item_id method"""
    client = IIIFClient()
    parent_url = "http://example.org/collection"
    
    # Test various ID formats
    assert client._normalize_item_id({"id": "test"}, parent_url) == "test"
    assert client._normalize_item_id({"@id": "test"}, parent_url) == "test"
    assert client._normalize_item_id({}, parent_url) is None

def test_max_manifests_limit():
    """Test that max_manifests parameter limits the number of manifests returned"""
    client = IIIFClient(no_cache=True)
    collection_data = load_fixture('iiif_v3_collection_with_manifests.json')
    
    def mock_fetch_json(url):
        if url == "https://api.dc.library.northwestern.edu/api/v2/collections/ba35820a-525a-4cfa-8f23-4891c9f798c4?as=iiif":
            return collection_data
        return {}
        
    client.fetch_json = mock_fetch_json

    # Get manifests with limit
    manifests, collections = client.get_manifests_and_collections_ids(
        "https://api.dc.library.northwestern.edu/api/v2/collections/ba35820a-525a-4cfa-8f23-4891c9f798c4?as=iiif",
        max_manifests=2
    )

    assert len(manifests) == 2, "Should only return 2 manifests when max_manifests=2"

def test_sub_collections_traversal():
    """Test traversing a collection that contains only sub-collections"""
    client = IIIFClient(no_cache=True)
    collection_data = load_fixture('iiif_v3_collection_with_subcollections.json')
    
    # Mock the fetch_json method to return our fixture data
    def mock_fetch_json(url):
        if url == "https://api.dc.library.northwestern.edu/api/v2/collections?as=iiif":
            return collection_data
        return {}
        
    client.fetch_json = mock_fetch_json

    # Get manifests and collections
    manifests, collections = client.get_manifests_and_collections_ids(
        "https://api.dc.library.northwestern.edu/api/v2/collections?as=iiif"
    )

    # Test expectations
    assert len(manifests) == 0, "Should find no manifests in a collection with only sub-collections"
    
    # Should find all collections (10 sub-collections + 1 "Next page" collection + root collection)
    assert len(collections) == 12, "Should find all collections including sub-collections"
    
    # Verify specific collections are found
    root_collection = "https://api.dc.library.northwestern.edu/api/v2/collections?as=iiif"
    assert root_collection in collections, "Root collection should be included"

    # Test that expected sub-collections are present
    sub_collection_ids = [
        "https://api.dc.library.northwestern.edu/api/v2/collections/ba35820a-525a-4cfa-8f23-4891c9f798c4?as=iiif",
        "https://api.dc.library.northwestern.edu/api/v2/collections/267bed1b-f808-4c51-acb1-0288378819d2?as=iiif",
        "https://api.dc.library.northwestern.edu/api/v2/collections/8fdc5942-12a0-4abd-8f43-5d19b37ece75?as=iiif"
    ]
    for sub_id in sub_collection_ids:
        assert sub_id in collections, f"Sub-collection {sub_id} should be included"

    # Test that pagination collection is included
    pagination_collection = "https://api.dc.library.northwestern.edu/api/v2/collections?as=iiif&page=2"
    assert pagination_collection in collections, "Pagination collection should be included"

def test_trailing_comma_manifest():
    """Test handling of manifests with trailing commas in JSON"""
    client = IIIFClient(no_cache=True)
    collection_data = load_fixture('problem_manifest.json')
    
    # Mock the fetch_json method to return our fixture data
    def mock_fetch_json(url):
        if url == "https://view.nls.uk/collections/1009/8921/100989212.json":
            return collection_data
        return {}
        
    client.fetch_json = mock_fetch_json

    # Get manifests and collections
    manifests, collections = client.get_manifests_and_collections_ids(
        "https://view.nls.uk/collections/1009/8921/100989212.json"
    )

    # Test expectations
    assert len(manifests) == 5, "Should find 5 manifests in the collection"
    assert len(collections) == 1, "Should find 1 collection (root collection)"

    # Verify specific manifest is present
    expected_manifest = "https://view.nls.uk/manifest/1009/8921/100989217/manifest.json"
    assert expected_manifest in manifests, "Should find manifest with trailing comma"

def test_context_manager():
    """Test IIIFClient works as a context manager"""
    with patch('requests.Session') as mock_session:
        # Create a mock session instance
        session_instance = MagicMock()
        mock_session.return_value = session_instance

        # Use client as context manager
        with IIIFClient() as client:
            assert not session_instance.close.called, "Session should not be closed while in context"
            assert isinstance(client, IIIFClient), "Context manager should return IIIFClient instance"

        # Verify session was closed after context
        session_instance.close.assert_called_once(), "Session should be closed after context"

def test_context_manager_with_error():
    """Test IIIFClient closes session even when error occurs"""
    with patch('requests.Session') as mock_session:
        session_instance = MagicMock()
        mock_session.return_value = session_instance

        try:
            with IIIFClient() as client:
                raise ValueError("Test error")
        except ValueError:
            pass

        session_instance.close.assert_called_once(), "Session should be closed after error"

def test_fetch_json_with_cache(tmp_path):
    """Test fetch_json behavior with caching enabled"""
    client = IIIFClient(cache_dir=str(tmp_path))
    url = "http://example.org/manifest"
    test_data = {"test": "data"}
    
    # Mock session.get to return test data
    with patch.object(client.session, 'get') as mock_get:
        mock_response = MagicMock()
        mock_response.text = json.dumps(test_data)
        mock_get.return_value = mock_response
        
        # First call should hit the network
        result = client.fetch_json(url)
        assert result == test_data
        mock_get.assert_called_once()
        
        # Second call should use cache
        mock_get.reset_mock()
        result = client.fetch_json(url)
        assert result == test_data
        mock_get.assert_not_called()

def test_fetch_json_skip_cache(tmp_path):
    """Test fetch_json behavior with skip_cache=True"""
    client = IIIFClient(cache_dir=str(tmp_path), skip_cache=True)
    url = "http://example.org/manifest"
    test_data = {"test": "data"}
    
    # Mock session.get to return test data
    with patch.object(client.session, 'get') as mock_get:
        mock_response = MagicMock()
        mock_response.text = json.dumps(test_data)
        mock_get.return_value = mock_response
        
        # First call should hit network
        result = client.fetch_json(url)
        assert result == test_data
        mock_get.assert_called_once()
        
        # Second call should also hit network
        mock_get.reset_mock()
        result = client.fetch_json(url)
        assert result == test_data
        mock_get.assert_called_once()

def test_fetch_json_no_cache():
    """Test fetch_json behavior with no_cache=True"""
    client = IIIFClient(no_cache=True)
    url = "http://example.org/manifest"
    test_data = {"test": "data"}
    
    with patch.object(client.session, 'get') as mock_get:
        mock_response = MagicMock()
        mock_response.text = json.dumps(test_data)
        mock_get.return_value = mock_response
        
        # Both calls should hit network
        result = client.fetch_json(url)
        assert result == test_data
        mock_get.assert_called_once()
        
        mock_get.reset_mock()
        result = client.fetch_json(url)
        assert result == test_data
        mock_get.assert_called_once()

def test_fetch_json_http_error():
    """Test fetch_json behavior when an HTTP error occurs"""
    client = IIIFClient(no_cache=True)
    url = "http://example.org/manifest"
    
    with patch.object(client.session, 'get') as mock_get:
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("404 Not Found")
        mock_get.return_value = mock_response
        
        with pytest.raises(requests.HTTPError):
            client.fetch_json(url)

def test_fetch_json_request_exception():
    """Test fetch_json behavior when a network error occurs"""
    client = IIIFClient(no_cache=True)
    url = "http://example.org/manifest"
    
    with patch.object(client.session, 'get') as mock_get:
        mock_get.side_effect = requests.RequestException("Connection error")
        
        with pytest.raises(requests.RequestException):
            client.fetch_json(url)

def test_fetch_json_invalid_json():
    """Test fetch_json behavior with invalid JSON response"""
    client = IIIFClient(no_cache=True)
    url = "http://example.org/manifest"
    
    with patch.object(client.session, 'get') as mock_get:
        mock_response = MagicMock()
        mock_response.text = "invalid json"
        mock_get.return_value = mock_response
        
        with pytest.raises(ValueError):
            client.fetch_json(url)

def test_duplicate_collections_handling():
    """Test handling of duplicate collections in a IIIF collection"""
    client = IIIFClient(no_cache=True)
    collection_data = load_fixture('iiif_v3_collection_with_duplicate_subcollections.json')
    
    logged_messages = []
    
    # Create a mock logger that captures debug messages
    class MockLogger:
        def debug(self, msg):
            logged_messages.append(msg)
        def info(self, msg):
            pass
        def warning(self, msg):
            pass
        def error(self, msg):
            pass
    
    # Mock both fetch_json and the logger
    def mock_fetch_json(url):
        if url == "https://api.dc.library.northwestern.edu/api/v2/collections?as=iiif":
            return collection_data
        return {}
        
    client.fetch_json = mock_fetch_json
    
    # Replace the logger at module level
    from loam_iiif.iiif import logger as iiif_logger
    original_logger = iiif_logger
    mock_logger = MockLogger()
    
    try:
        # Replace the module logger directly
        import loam_iiif.iiif
        loam_iiif.iiif.logger = mock_logger
        
        # Get manifests and collections
        manifests, collections = client.get_manifests_and_collections_ids(
            "https://api.dc.library.northwestern.edu/api/v2/collections?as=iiif"
        )
        
        # Verify that duplicate collection was detected
        duplicate_collection_url = "https://api.dc.library.northwestern.edu/api/v2/collections/ba35820a-525a-4cfa-8f23-4891c9f798c4?as=iiif"
        assert any(f"Collection already in queue: {duplicate_collection_url}" in msg for msg in logged_messages), \
            "Should log when encountering duplicate collection"
        
        # Verify the collection was only processed once
        assert collections.count(duplicate_collection_url) == 1, \
            "Duplicate collection should only be included once"
        
        # There should be 2 collections total (root + one unique sub-collection)
        assert len(collections) == 2, \
            "Should only include root collection and one instance of duplicate collection"
            
    finally:
        # Restore the original logger
        loam_iiif.iiif.logger = original_logger

def test_get_manifests_and_collections_error_handling():
    """Test that get_manifests_and_collections_ids continues processing after a fetch error"""
    client = IIIFClient(no_cache=True)
    
    # Track which URLs were attempted
    attempted_urls = []

    def mock_fetch_json(url):
        attempted_urls.append(url)
        if url == "http://example.org/error-collection":
            raise requests.RequestException("Simulated fetch error")
        elif url == "http://example.org/root-collection":
            return {
                "items": [
                    {
                        "id": "http://example.org/error-collection",
                        "type": "Collection"
                    },
                    {
                        "id": "http://example.org/good-collection",
                        "type": "Collection"
                    }
                ]
            }
        elif url == "http://example.org/good-collection":
            return {
                "items": [
                    {
                        "id": "http://example.org/manifest1",
                        "type": "Manifest"
                    }
                ]
            }
        return {}

    client.fetch_json = mock_fetch_json

    # Capture logged warnings
    with patch('logging.Logger.warning') as mock_warning:
        manifests, collections = client.get_manifests_and_collections_ids(
            "http://example.org/root-collection"
        )

        # Verify that all collections were attempted
        assert "http://example.org/root-collection" in attempted_urls
        assert "http://example.org/error-collection" in attempted_urls
        assert "http://example.org/good-collection" in attempted_urls

        # Verify warning was logged for error collection
        mock_warning.assert_called_once_with(
            "Skipping collection due to fetch error: http://example.org/error-collection"
        )

        # Verify we still got results from good collection
        assert len(manifests) == 1
        assert manifests[0] == "http://example.org/manifest1"

        # Verify collections list includes root and good collection, but not error collection
        assert len(collections) == 2
        assert "http://example.org/root-collection" in collections
        assert "http://example.org/good-collection" in collections
        assert "http://example.org/error-collection" not in collections

def test_collection_processing_error_handling():
    """Test that get_manifests_and_collections_ids continues when processing a collection fails"""
    client = IIIFClient(no_cache=True)
    
    def mock_fetch_json(url):
        if url == "http://example.org/root-collection":
            return {
                "items": [
                    {
                        "id": "http://example.org/bad-collection",
                        "type": "Collection"
                    },
                    {
                        "id": "http://example.org/good-collection",
                        "type": "Collection"
                    }
                ]
            }
        elif url == "http://example.org/bad-collection":
            # Return something that will cause an error during items processing
            return {"items": [{"id": "http://example.org/bad-item", "type": "Manifest"}]}  # This will be handled by our mock
        elif url == "http://example.org/good-collection":
            return {
                "items": [
                    {
                        "id": "http://example.org/manifest1",
                        "type": "Manifest"
                    }
                ]
            }
        return {}

    client.fetch_json = mock_fetch_json

    # Mock _normalize_item_type to raise an exception for the bad collection
    original_normalize = client._normalize_item_type
    
    def mock_normalize_item_type(item):
        if isinstance(item, dict) and item.get("id") == "http://example.org/bad-item":
            raise AttributeError("'NoneType' object has no attribute 'get'")
        return original_normalize(item)
    
    client._normalize_item_type = mock_normalize_item_type

    # Capture logged errors
    with patch('logging.Logger.error') as mock_error:
        manifests, collections = client.get_manifests_and_collections_ids(
            "http://example.org/root-collection"
        )

        # Verify error was logged
        mock_error.assert_called_once_with(
            "Error processing http://example.org/bad-collection: 'NoneType' object has no attribute 'get'"
        )

        # Verify we still got results from good collection
        assert len(manifests) == 1
        assert manifests[0] == "http://example.org/manifest1"

        # Verify collections list includes root and good collection
        assert len(collections) == 2
        assert "http://example.org/root-collection" in collections
        assert "http://example.org/good-collection" in collections

def test_get_manifest_images_v3_malformed_data():
    """Test handling of malformed data in IIIF v3 manifest at various levels"""
    client = IIIFClient(no_cache=True)

    # Test various malformed manifest structures
    test_cases = [
        {
            "@context": "http://iiif.io/api/presentation/3/context.json",
            "items": None  # Missing items array
        },
        {
            "@context": "http://iiif.io/api/presentation/3/context.json",
            "items": [None]  # Invalid canvas
        },
        {
            "@context": "http://iiif.io/api/presentation/3/context.json",
            "items": [{"items": None}]  # Invalid items in canvas
        },
        {
            "@context": "http://iiif.io/api/presentation/3/context.json",
            "items": [{"items": [None]}]  # Invalid annotation page
        },
        {
            "@context": "http://iiif.io/api/presentation/3/context.json",
            "items": [{"items": [{"items": None}]}]  # Invalid items in annotation page
        },
        {
            "@context": "http://iiif.io/api/presentation/3/context.json",
            "items": [{"items": [{"items": [None]}]}]  # Invalid annotation
        },
        {
            "@context": "http://iiif.io/api/presentation/3/context.json",
            "items": [{"items": [{"items": [{"body": None}]}]}]  # Invalid body
        }
    ]

    for manifest_data in test_cases:
        def mock_fetch_json(url):
            return manifest_data
            
        client.fetch_json = mock_fetch_json
        
        # Should handle malformed data without raising exceptions
        try:
            images = client.get_manifest_images("http://example.org/manifest")
            assert images == [], f"Should return empty list for malformed manifest: {manifest_data}"
        except Exception as e:
            pytest.fail(f"Should not raise exception for malformed manifest: {e}")

def test_get_manifest_images_v3_parsing_error():
    """Test handling of errors during IIIF v3 manifest parsing"""
    client = IIIFClient(no_cache=True)

    # Manifest that will cause an error during parsing by having an item that raises
    # when accessing its properties
    class ErrorDict(dict):
        def get(self, key, default=None):
            raise RuntimeError("Simulated error during parsing")

    manifest_data = {
        "@context": "http://iiif.io/api/presentation/3/context.json",
        "items": [
            ErrorDict()  # This will raise when we try to process it
        ]
    }

    def mock_fetch_json(url):
        return manifest_data
        
    client.fetch_json = mock_fetch_json

    # Capture logged errors
    with patch('logging.Logger.error') as mock_error:
        # Get images from manifest - should return empty list due to error
        images = client.get_manifest_images("http://example.org/manifest")
        
        # Verify error was logged
        mock_error.assert_called_once_with(
            "Error parsing IIIF 3.0 manifest: Simulated error during parsing"
        )
        
        # Should return empty list on error
        assert images == [], "Should return empty list when parsing fails"

def test_get_manifest_images_v3_empty_structures():
    """Test handling of empty structures in IIIF v3 manifest"""
    client = IIIFClient(no_cache=True)

    # Test manifest with valid structure but empty arrays
    manifest_data = {
        "@context": "http://iiif.io/api/presentation/3/context.json",
        "items": [
            {
                "items": [
                    {
                        "items": []  # Empty annotation list
                    }
                ]
            },
            {
                "items": []  # Empty annotation page
            }
        ]
    }

    def mock_fetch_json(url):
        return manifest_data
        
    client.fetch_json = mock_fetch_json

    # Should handle empty structures without errors
    images = client.get_manifest_images("http://example.org/manifest")
    assert images == [], "Should return empty list for manifest with empty structures"

def test_unsupported_iiif_context():
    """Test handling of manifests with unsupported or missing IIIF contexts"""
    client = IIIFClient(no_cache=True)

    test_cases = [
        # Missing context
        {
            "sequences": [{
                "canvases": [{
                    "images": [{
                        "resource": {
                            "@id": "https://example.org/image1"
                        }
                    }]
                }]
            }]
        },
        
        # Unsupported context
        {
            "@context": "http://iiif.io/api/presentation/1/context.json",
            "sequences": [{
                "canvases": [{
                    "images": [{
                        "resource": {
                            "@id": "https://example.org/image1"
                        }
                    }]
                }]
            }]
        },
        
        # Invalid context type
        {
            "@context": ["http://iiif.io/api/presentation/2/context.json"],
            "sequences": [{
                "canvases": [{
                    "images": [{
                        "resource": {
                            "@id": "https://example.org/image1"
                        }
                    }]
                }]
            }]
        }
    ]

    # Capture logged errors
    with patch('logging.Logger.error') as mock_error:
        for manifest_data in test_cases:
            def mock_fetch_json(url):
                return manifest_data
                
            client.fetch_json = mock_fetch_json

            images = client.get_manifest_images("http://example.org/manifest")
            
            # Should return empty list for unsupported contexts
            assert images == [], "Should return empty list for unsupported context"
            
            # Should log appropriate error
            mock_error.assert_called_with(
                f"Unsupported or missing IIIF context in manifest: {manifest_data.get('@context')}"
            )
            mock_error.reset_mock()

def test_image_url_formatting_errors():
    """Test handling of errors during image URL formatting"""
    client = IIIFClient(no_cache=True)

    # Create a manifest with an invalid image ID that will cause formatting errors
    manifest_data = {
        "@context": "http://iiif.io/api/presentation/3/context.json",
        "items": [{
            "items": [{
                "items": [{
                    "body": {
                        "service": {
                            "@id": None  # This will cause an error during formatting
                        }
                    }
                }]
            }]
        }]
    }

    def mock_fetch_json(url):
        return manifest_data
        
    client.fetch_json = mock_fetch_json

    # Patch the correct logger
    with patch('loam_iiif.iiif.logger.error') as mock_error:
        images = client.get_manifest_images("http://example.org/manifest")
        
        # Should return empty list but continue processing
        assert images == [], "Should return empty list when image URL formatting fails"
        
        # Should log error about formatting failure
        mock_error.assert_called_with(
            "Error formatting image URL for ID None: expected string or bytes-like object"
        )

def test_image_url_formatting_edge_cases():
    """Test handling of edge cases during image URL formatting"""
    client = IIIFClient(no_cache=True)

    test_cases = [
        # Case 1: Image ID with existing IIIF parameters that shouldn't be modified
        {
            "@context": "http://iiif.io/api/presentation/3/context.json",
            "items": [{
                "items": [{
                    "items": [{
                        "body": {
                            "service": {
                                "@id": "https://example.org/iiif/123/full/!800,600/0/default.jpg"
                            }
                        }
                    }]
                }]
            }]
        },
        
        # Case 2: Image ID with info.json that should be stripped
        {
            "@context": "http://iiif.io/api/presentation/3/context.json",
            "items": [{
                "items": [{
                    "items": [{
                        "body": {
                            "service": {
                                "@id": "https://example.org/iiif/123/info.json"
                            }
                        }
                    }]
                }]
            }]
        },
        
        # Case 3: Invalid URL characters that might cause formatting errors
        {
            "@context": "http://iiif.io/api/presentation/3/context.json",
            "items": [{
                "items": [{
                    "items": [{
                        "body": {
                            "service": {
                                "@id": "https://example.org/iiif/123 456/image"
                            }
                        }
                    }]
                }]
            }]
        }
    ]

    for i, manifest_data in enumerate(test_cases):
        def mock_fetch_json(url):
            return manifest_data
            
        client.fetch_json = mock_fetch_json

        with patch('logging.Logger.error') as mock_error:
            images = client.get_manifest_images("http://example.org/manifest")
            
            if i == 0:
                # Should preserve existing IIIF parameters
                assert len(images) == 1, "Should process image with existing parameters"
                assert images[0] == "https://example.org/iiif/123/full/!800,600/0/default.jpg"
                assert not mock_error.called, "Should not log any errors"
            
            elif i == 1:
                # Should strip info.json and add parameters
                assert len(images) == 1, "Should process image with info.json"
                assert images[0] == "https://example.org/iiif/123/full/!768,2000/0/default.jpg"
                assert not mock_error.called, "Should not log any errors"
            
            elif i == 2:
                # Should attempt to handle invalid URL characters
                assert len(images) == 1, "Should attempt to process image with invalid characters"
                assert "https://example.org/iiif/123 456/image/full/!768,2000/0/default.jpg" in images[0]

def test_get_manifest_images_fatal_error():
    """Test handling of fatal errors in get_manifest_images"""
    client = IIIFClient(no_cache=True)

    # Mock fetch_json to raise an exception
    def mock_fetch_json(url):
        raise RuntimeError("Fatal error during manifest processing")
        
    client.fetch_json = mock_fetch_json

    # Patch the logger to capture error messages
    with patch('loam_iiif.iiif.logger.error') as mock_error:
        # Method should re-raise the exception
        with pytest.raises(RuntimeError) as exc_info:
            client.get_manifest_images("http://example.org/manifest")
        
        assert str(exc_info.value) == "Fatal error during manifest processing"
        
        # Verify error was logged before re-raising
        mock_error.assert_called_once_with(
            "Error extracting images from manifest http://example.org/manifest: Fatal error during manifest processing"
        )

def test_get_manifest_images_size_options():
    """Test different size parameter options for image URLs"""
    client = IIIFClient(no_cache=True)
    
    # Test manifest with a basic image service
    manifest_data = {
        "@context": "http://iiif.io/api/presentation/3/context.json",
        "items": [{
            "items": [{
                "items": [{
                    "body": {
                        "service": {
                            "@id": "https://example.org/iiif/test-image"
                        }
                    }
                }]
            }]
        }]
    }

    def mock_fetch_json(url):
        return manifest_data
        
    client.fetch_json = mock_fetch_json

    # Test default behavior (with !)
    images = client.get_manifest_images("http://example.org/manifest")
    assert images[0] == "https://example.org/iiif/test-image/full/!768,2000/0/default.jpg"

    # Test exact dimensions
    images = client.get_manifest_images("http://example.org/manifest", exact=True)
    assert images[0] == "https://example.org/iiif/test-image/full/768,2000/0/default.jpg"

    # Test max size
    images = client.get_manifest_images("http://example.org/manifest", use_max=True)
    assert images[0] == "https://example.org/iiif/test-image/full/max/0/default.jpg"

    # Test custom dimensions
    images = client.get_manifest_images("http://example.org/manifest", width=100, height=100)
    assert images[0] == "https://example.org/iiif/test-image/full/!100,100/0/default.jpg"

    # Test custom dimensions with exact
    images = client.get_manifest_images("http://example.org/manifest", width=100, height=100, exact=True)
    assert images[0] == "https://example.org/iiif/test-image/full/100,100/0/default.jpg"

    # Test that max overrides other parameters
    images = client.get_manifest_images("http://example.org/manifest", width=100, height=100, exact=True, use_max=True)
    assert images[0] == "https://example.org/iiif/test-image/full/max/0/default.jpg"

def test_version_specific_max_size():
    """Test that 'max' and 'full' size parameters are used correctly for v3 and v2 manifests"""
    client = IIIFClient(no_cache=True)

    # Test IIIF v3 manifest
    v3_manifest = {
        "@context": "http://iiif.io/api/presentation/3/context.json",
        "items": [{
            "items": [{
                "items": [{
                    "body": {
                        "service": {
                            "@id": "https://example.org/iiif/v3-image"
                        }
                    }
                }]
            }]
        }]
    }

    # Test IIIF v2 manifest
    v2_manifest = {
        "@context": "http://iiif.io/api/presentation/2/context.json",
        "sequences": [{
            "canvases": [{
                "images": [{
                    "resource": {
                        "service": {
                            "@id": "https://example.org/iiif/v2-image"
                        }
                    }
                }]
            }]
        }]
    }

    def mock_fetch_json(url):
        if "v3" in url:
            return v3_manifest
        return v2_manifest
            
    client.fetch_json = mock_fetch_json

    # Test v3 manifest with max size
    v3_images = client.get_manifest_images("http://example.org/v3-manifest", use_max=True)
    assert len(v3_images) == 1, "Should find 1 image in v3 manifest"
    assert v3_images[0] == "https://example.org/iiif/v3-image/full/max/0/default.jpg", "V3 image should use 'max' parameter"

    # Test v2 manifest with max size (should use 'full')
    v2_images = client.get_manifest_images("http://example.org/v2-manifest", use_max=True)
    assert len(v2_images) == 1, "Should find 1 image in v2 manifest"
    assert v2_images[0] == "https://example.org/iiif/v2-image/full/full/0/default.jpg", "V2 image should use 'full' parameter"

    # Test that normal size parameters work the same for both versions
    v3_sized = client.get_manifest_images("http://example.org/v3-manifest", width=100, height=100)
    v2_sized = client.get_manifest_images("http://example.org/v2-manifest", width=100, height=100)
    assert v3_sized[0] == "https://example.org/iiif/v3-image/full/!100,100/0/default.jpg", "V3 sized image should use specified dimensions"
    assert v2_sized[0] == "https://example.org/iiif/v2-image/full/!100,100/0/default.jpg", "V2 sized image should use specified dimensions"

    # Test exact size parameter works the same for both versions
    v3_exact = client.get_manifest_images("http://example.org/v3-manifest", width=100, height=100, exact=True)
    v2_exact = client.get_manifest_images("http://example.org/v2-manifest", width=100, height=100, exact=True)
    assert v3_exact[0] == "https://example.org/iiif/v3-image/full/100,100/0/default.jpg", "V3 exact sized image should not use !"
    assert v2_exact[0] == "https://example.org/iiif/v2-image/full/100,100/0/default.jpg", "V2 exact sized image should not use !"

def test_parent_collection_label_extraction_v2():
    """Test extracting parent collection labels from IIIF v2 manifests using 'within' field"""
    client = IIIFClient(no_cache=True)
    
    # Mock manifest with 'within' field pointing to a collection
    manifest_data = {
        "@context": "http://iiif.io/api/presentation/2/context.json",
        "@id": "https://digital.library.villanova.edu/Item/vudl:10950/Manifest",
        "@type": "sc:Manifest",
        "label": "Test Manifest",
        "within": "https://digital.library.villanova.edu/Collection/vudl:680115/IIIF"
    }
    
    # Mock collection data that would be fetched
    collection_data = {
        "@context": "http://iiif.io/api/presentation/2/context.json",
        "@id": "https://digital.library.villanova.edu/Collection/vudl:680115/IIIF",
        "@type": "sc:Collection",
        "label": "Naturforschenden Vereines in Brünn"
    }
    
    def mock_fetch_json(url):
        if url == "https://digital.library.villanova.edu/Item/vudl:10950/Manifest":
            return manifest_data
        elif url == "https://digital.library.villanova.edu/Collection/vudl:680115/IIIF":
            return collection_data
        return {}
        
    client.fetch_json = mock_fetch_json

    # Create chunks and verify parent collection label is extracted
    chunks = client.create_manifest_chunks([
        "https://digital.library.villanova.edu/Item/vudl:10950/Manifest"
    ])
    
    assert len(chunks) == 1, "Should create one chunk"
    chunk = chunks[0]
    
    # Verify parent collection information
    assert len(chunk["metadata"]["parent_collections"]) == 1, "Should have one parent collection"
    parent_collection = chunk["metadata"]["parent_collections"][0]
    
    assert parent_collection["id"] == "https://digital.library.villanova.edu/Collection/vudl:680115/IIIF"
    assert parent_collection["label"] == "Naturforschenden Vereines in Brünn", "Should extract correct collection label"
    
    # Verify text includes proper parent collection info
    assert "Part Of: Naturforschenden Vereines in Brünn (https://digital.library.villanova.edu/Collection/vudl:680115/IIIF)" in chunk["text"]

def test_parent_collection_label_extraction_v3():
    """Test extracting parent collection labels from IIIF v3 manifests using 'partOf' field"""
    client = IIIFClient(no_cache=True)
    
    # Mock IIIF v3 manifest with partOf field containing label
    manifest_data = {
        "@context": ["http://iiif.io/api/presentation/3/context.json"],
        "id": "https://api.dc.library.northwestern.edu/api/v2/works/test-manifest?as=iiif",
        "type": "Manifest",
        "label": {"none": ["Test Manifest"]},
        "partOf": [
            {
                "id": "https://api.dc.library.northwestern.edu/api/v2/collections/test-collection?as=iiif",
                "type": "Collection",
                "label": {"none": ["Africa Embracing Obama"]}
            }
        ]
    }
    
    def mock_fetch_json(url):
        return manifest_data
        
    client.fetch_json = mock_fetch_json

    # Create chunks and verify parent collection label is extracted
    chunks = client.create_manifest_chunks([
        "https://api.dc.library.northwestern.edu/api/v2/works/test-manifest?as=iiif"
    ])
    
    assert len(chunks) == 1, "Should create one chunk"
    chunk = chunks[0]
    
    # Verify parent collection information
    assert len(chunk["metadata"]["parent_collections"]) == 1, "Should have one parent collection"
    parent_collection = chunk["metadata"]["parent_collections"][0]
    
    assert parent_collection["id"] == "https://api.dc.library.northwestern.edu/api/v2/collections/test-collection?as=iiif"
    assert parent_collection["label"] == "Africa Embracing Obama", "Should extract correct collection label"
    
    # Verify text includes proper parent collection info
    assert "Part Of: Africa Embracing Obama (https://api.dc.library.northwestern.edu/api/v2/collections/test-collection?as=iiif)" in chunk["text"]

def test_parent_collection_fetch_failure():
    """Test handling when parent collection fetch fails"""
    client = IIIFClient(no_cache=True)
    
    # Mock manifest with 'within' field
    manifest_data = {
        "@context": "http://iiif.io/api/presentation/2/context.json",
        "@id": "https://example.org/manifest",
        "@type": "sc:Manifest",
        "label": "Test Manifest",
        "within": "https://example.org/collection"
    }
    
    def mock_fetch_json(url):
        if url == "https://example.org/manifest":
            return manifest_data
        elif url == "https://example.org/collection":
            # Simulate fetch failure
            raise requests.RequestException("Connection failed")
        return {}
        
    client.fetch_json = mock_fetch_json

    # Capture logged warnings
    with patch('logging.Logger.warning') as mock_warning:
        chunks = client.create_manifest_chunks(["https://example.org/manifest"])
        
        assert len(chunks) == 1, "Should still create chunk despite fetch failure"
        chunk = chunks[0]
        
        # Should fall back to "Label Unknown"
        parent_collection = chunk["metadata"]["parent_collections"][0]
        assert parent_collection["label"] == "Parent Collection (Label Unknown)"
        
        # Should log warning about fetch failure
        mock_warning.assert_called_with(
            "Failed to fetch parent collection data from https://example.org/collection: Connection failed"
        )

def test_parent_collection_within_list():
    """Test handling 'within' field as a list of collection URLs"""
    client = IIIFClient(no_cache=True)
    
    # Mock manifest with 'within' as list
    manifest_data = {
        "@context": "http://iiif.io/api/presentation/2/context.json",
        "@id": "https://example.org/manifest",
        "@type": "sc:Manifest",
        "label": "Test Manifest",
        "within": [
            "https://example.org/collection1",
            "https://example.org/collection2"
        ]
    }
    
    # Mock collection data
    collection1_data = {
        "@context": "http://iiif.io/api/presentation/2/context.json",
        "@id": "https://example.org/collection1",
        "@type": "sc:Collection",
        "label": "First Collection"
    }
    
    collection2_data = {
        "@context": "http://iiif.io/api/presentation/2/context.json",
        "@id": "https://example.org/collection2",
        "@type": "sc:Collection",
        "label": "Second Collection"
    }
    
    def mock_fetch_json(url):
        if url == "https://example.org/manifest":
            return manifest_data
        elif url == "https://example.org/collection1":
            return collection1_data
        elif url == "https://example.org/collection2":
            return collection2_data
        return {}
        
    client.fetch_json = mock_fetch_json

    chunks = client.create_manifest_chunks(["https://example.org/manifest"])
    
    assert len(chunks) == 1, "Should create one chunk"
    chunk = chunks[0]
    
    # Should have both parent collections
    assert len(chunk["metadata"]["parent_collections"]) == 2, "Should have two parent collections"
    
    labels = [pc["label"] for pc in chunk["metadata"]["parent_collections"]]
    assert "First Collection" in labels
    assert "Second Collection" in labels

def test_parent_collection_within_object():
    """Test handling 'within' field as an object with embedded collection info"""
    client = IIIFClient(no_cache=True)
    
    # Mock manifest with 'within' as object
    manifest_data = {
        "@context": "http://iiif.io/api/presentation/2/context.json",
        "@id": "https://example.org/manifest",
        "@type": "sc:Manifest",
        "label": "Test Manifest",
        "within": {
            "@id": "https://example.org/collection",
            "@type": "sc:Collection",
            "label": "Embedded Collection Label"
        }
    }
    
    def mock_fetch_json(url):
        return manifest_data
        
    client.fetch_json = mock_fetch_json

    chunks = client.create_manifest_chunks(["https://example.org/manifest"])
    
    assert len(chunks) == 1, "Should create one chunk"
    chunk = chunks[0]
    
    # Should extract label from embedded object without additional fetch
    assert len(chunk["metadata"]["parent_collections"]) == 1, "Should have one parent collection"
    parent_collection = chunk["metadata"]["parent_collections"][0]
    
    assert parent_collection["id"] == "https://example.org/collection"
    assert parent_collection["label"] == "Embedded Collection Label"

def test_parent_collection_complex_label_structures():
    """Test handling complex IIIF label structures in parent collections"""
    client = IIIFClient(no_cache=True)
    
    # Mock manifest with 'within' field
    manifest_data = {
        "@context": "http://iiif.io/api/presentation/2/context.json",
        "@id": "https://example.org/manifest",
        "@type": "sc:Manifest",
        "label": "Test Manifest",
        "within": "https://example.org/collection"
    }
    
    # Mock collection with complex IIIF v3 style label structure
    collection_data = {
        "@context": ["http://iiif.io/api/presentation/3/context.json"],
        "id": "https://example.org/collection",
        "type": "Collection",
        "label": {
            "en": ["English Label"],
            "none": ["Fallback Label"]
        }
    }
    
    def mock_fetch_json(url):
        if url == "https://example.org/manifest":
            return manifest_data
        elif url == "https://example.org/collection":
            return collection_data
        return {}
        
    client.fetch_json = mock_fetch_json

    chunks = client.create_manifest_chunks(["https://example.org/manifest"])
    
    assert len(chunks) == 1, "Should create one chunk"
    chunk = chunks[0]
    
    parent_collection = chunk["metadata"]["parent_collections"][0]
    # Should prefer English label over fallback
    assert parent_collection["label"] == "English Label"

def test_no_parent_collection():
    """Test handling manifests with no parent collection information"""
    client = IIIFClient(no_cache=True)
    
    # Mock manifest without parent collection fields
    manifest_data = {
        "@context": "http://iiif.io/api/presentation/2/context.json",
        "@id": "https://example.org/manifest",
        "@type": "sc:Manifest",
        "label": "Test Manifest"
    }
    
    def mock_fetch_json(url):
        return manifest_data
        
    client.fetch_json = mock_fetch_json

    chunks = client.create_manifest_chunks(["https://example.org/manifest"])
    
    assert len(chunks) == 1, "Should create one chunk"
    chunk = chunks[0]
    
    # Should have empty parent collections list
    assert chunk["metadata"]["parent_collections"] == []
    
    # Text should not include "Part Of" section
    assert "Part Of:" not in chunk["text"]

def test_homepage_extraction_from_related_field():
    """Test homepage extraction from IIIF v2 'related' field"""
    client = IIIFClient(no_cache=True)
    
    manifest_data = {
        "@context": "http://iiif.io/api/presentation/2/context.json",
        "@id": "https://digital.library.villanova.edu/Item/test/Manifest",
        "label": "Test Document",
        "related": {
            "@id": "https://digital.library.villanova.edu/Item/test",
            "format": "text/html"
        }
    }
    
    def mock_fetch_json(url):
        return manifest_data
        
    client.fetch_json = mock_fetch_json
    
    chunks = client.create_manifest_chunks(["https://digital.library.villanova.edu/Item/test/Manifest"])
    
    assert len(chunks) == 1
    metadata = chunks[0]["metadata"]
    
    # Should extract homepage from related field
    assert metadata["homepage"] == "https://digital.library.villanova.edu/Item/test"


def test_homepage_extraction_from_metadata_about_field():
    """Test homepage extraction from 'About' metadata field with Permanent Link"""
    client = IIIFClient(no_cache=True)
    
    manifest_data = {
        "@context": "http://iiif.io/api/presentation/2/context.json",
        "@id": "https://digital.library.villanova.edu/Item/test/Manifest",
        "label": "Test Document",
        "metadata": [
            {
                "label": "About",
                "value": "<span><a href=\"https://digital.library.villanova.edu/Record/test\">More Details</a><br /><a href=\"https://digital.library.villanova.edu/Item/test\">Permanent Link</a></span>"
            }
        ]
    }
    
    def mock_fetch_json(url):
        return manifest_data
        
    client.fetch_json = mock_fetch_json
    
    chunks = client.create_manifest_chunks(["https://digital.library.villanova.edu/Item/test/Manifest"])
    
    assert len(chunks) == 1
    metadata = chunks[0]["metadata"]
    
    # Should extract homepage from "Permanent Link" in About metadata
    assert metadata["homepage"] == "https://digital.library.villanova.edu/Item/test"


def test_homepage_extraction_priority():
    """Test that homepage extraction from About metadata takes priority over related field"""
    client = IIIFClient(no_cache=True)
    
    manifest_data = {
        "@context": "http://iiif.io/api/presentation/2/context.json",
        "@id": "https://digital.library.villanova.edu/Item/test/Manifest",
        "label": "Test Document",
        "related": {
            "@id": "https://digital.library.villanova.edu/Item/test-related",
            "format": "text/html"
        },
        "metadata": [
            {
                "label": "About",
                "value": "<span><a href=\"https://digital.library.villanova.edu/Item/test-permanent\">Permanent Link</a></span>"
            }
        ]
    }
    
    def mock_fetch_json(url):
        return manifest_data
        
    client.fetch_json = mock_fetch_json
    
    chunks = client.create_manifest_chunks(["https://digital.library.villanova.edu/Item/test/Manifest"])
    
    assert len(chunks) == 1
    metadata = chunks[0]["metadata"]
    
    # Should prefer Permanent Link from metadata over related field
    assert metadata["homepage"] == "https://digital.library.villanova.edu/Item/test-permanent"


def test_rights_extraction_from_attribution():
    """Test rights URL extraction from attribution HTML content"""
    client = IIIFClient(no_cache=True)
    
    manifest_data = {
        "@context": "http://iiif.io/api/presentation/2/context.json",
        "@id": "https://digital.library.villanova.edu/Item/test/Manifest",
        "label": "Test Document",
        "requiredStatement": {
            "label": "ATTRIBUTION",
            "value": "<span>Digital Library@Villanova University<br /><br /><b>Disclaimers</b>: <br /><a href=\"https://digital.library.villanova.edu/copyright.html#liability\">Disclaimer of Liability</a><br /><a href=\"https://digital.library.villanova.edu/copyright.html#endorsement\">Disclaimer of Endorsement</a><br /><br /><b>License</b>: <br /><a href=\"https://digital.library.villanova.edu/rights.html\">Rights Information</a></span>"
        }
    }
    
    def mock_fetch_json(url):
        return manifest_data
        
    client.fetch_json = mock_fetch_json
    
    chunks = client.create_manifest_chunks(["https://digital.library.villanova.edu/Item/test/Manifest"])
    
    assert len(chunks) == 1
    metadata = chunks[0]["metadata"]
    
    # Should extract rights URL from attribution HTML
    assert metadata["rights"] == "https://digital.library.villanova.edu/rights.html"


def test_enhanced_metadata_extraction_combined():
    """Test the complete enhanced metadata extraction with both homepage and rights"""
    client = IIIFClient(no_cache=True)
    
    manifest_data = {
        "@context": "http://iiif.io/api/presentation/2/context.json",
        "@id": "https://digital.library.villanova.edu/Item/test/Manifest",
        "label": "Test Document",
        "related": {
            "@id": "https://digital.library.villanova.edu/Item/test",
            "format": "text/html"
        },
        "metadata": [
            {
                "label": "About",
                "value": "<span><a href=\"https://digital.library.villanova.edu/Record/test\">More Details</a><br /><a href=\"https://digital.library.villanova.edu/Item/test-permanent\">Permanent Link</a></span>"
            }
        ],
        "requiredStatement": {
            "label": "ATTRIBUTION",
            "value": "<span>Digital Library@Villanova University<br /><br /><b>License</b>: <br /><a href=\"https://digital.library.villanova.edu/rights.html\">Rights Information</a></span>"
        }
    }
    
    def mock_fetch_json(url):
        return manifest_data
        
    client.fetch_json = mock_fetch_json
    
    chunks = client.create_manifest_chunks(["https://digital.library.villanova.edu/Item/test/Manifest"])
    
    assert len(chunks) == 1
    metadata = chunks[0]["metadata"]
    
    # Should extract homepage from "Permanent Link" (priority over related)
    assert metadata["homepage"] == "https://digital.library.villanova.edu/Item/test-permanent"
    
    # Should extract rights URL from attribution
    assert metadata["rights"] == "https://digital.library.villanova.edu/rights.html"
    
    # Should have attribution details
    assert metadata["attribution"]["label"] == "ATTRIBUTION"
    assert "Digital Library@Villanova University" in metadata["attribution"]["value"]


def test_rights_extraction_fallback_when_no_rights_field():
    """Test that rights extraction from attribution only happens when no explicit rights field exists"""
    client = IIIFClient(no_cache=True)
    
    manifest_data = {
        "@context": "http://iiif.io/api/presentation/3/context.json",
        "id": "https://example.org/manifest",
        "label": {"en": ["Test Document"]},
        "rights": "http://creativecommons.org/licenses/by/4.0/",
        "requiredStatement": {
            "label": {"en": ["Attribution"]},
            "value": {"en": ["Some institution<br /><a href=\"https://example.org/rights.html\">Rights Information</a>"]}
        }
    }
    
    def mock_fetch_json(url):
        return manifest_data
        
    client.fetch_json = mock_fetch_json
    
    chunks = client.create_manifest_chunks(["https://example.org/manifest"])
    
    assert len(chunks) == 1
    metadata = chunks[0]["metadata"]
    
    # Should use explicit rights field, not extract from attribution
    assert metadata["rights"] == "http://creativecommons.org/licenses/by/4.0/"


def test_homepage_extraction_with_related_list():
    """Test homepage extraction when related field is a list"""
    client = IIIFClient(no_cache=True)
    
    manifest_data = {
        "@context": "http://iiif.io/api/presentation/2/context.json",
        "@id": "https://digital.library.villanova.edu/Item/test/Manifest",
        "label": "Test Document",
        "related": [
            {
                "@id": "https://digital.library.villanova.edu/Item/test-first",
                "format": "text/html"
            },
            {
                "@id": "https://digital.library.villanova.edu/Item/test-second",
                "format": "application/pdf"
            }
        ]
    }
    
    def mock_fetch_json(url):
        return manifest_data
        
    client.fetch_json = mock_fetch_json
    
    chunks = client.create_manifest_chunks(["https://digital.library.villanova.edu/Item/test/Manifest"])
    
    assert len(chunks) == 1
    metadata = chunks[0]["metadata"]
    
    # Should extract homepage from first item in related list
    assert metadata["homepage"] == "https://digital.library.villanova.edu/Item/test-first"


def test_no_homepage_extraction_when_no_sources():
    """Test that homepage remains None when no extraction sources are available"""
    client = IIIFClient(no_cache=True)
    
    manifest_data = {
        "@context": "http://iiif.io/api/presentation/2/context.json",
        "@id": "https://digital.library.villanova.edu/Item/test/Manifest",
        "label": "Test Document",
        "metadata": [
            {
                "label": "Topic",
                "value": "Natural history"
            }
        ]
    }
    
    def mock_fetch_json(url):
        return manifest_data
        
    client.fetch_json = mock_fetch_json
    
    chunks = client.create_manifest_chunks(["https://digital.library.villanova.edu/Item/test/Manifest"])
    
    assert len(chunks) == 1
    metadata = chunks[0]["metadata"]
    
    # Should remain None when no homepage sources are available
    assert metadata["homepage"] is None


def test_rights_extraction_with_different_html_patterns():
    """Test rights extraction with various HTML patterns"""
    client = IIIFClient(no_cache=True)
    
    test_cases = [
        {
            "html": '<a href="https://example.org/rights.html">Rights Info</a>',
            "expected": "https://example.org/rights.html"
        },
        {
            "html": 'Text before <a href="https://institution.edu/rights.html" target="_blank">Rights Information</a> text after',
            "expected": "https://institution.edu/rights.html"
        },
        {
            "html": '<span><a href="https://library.org/copyright-rights.html">Copyright Rights</a></span>',
            "expected": "https://library.org/copyright-rights.html"
        }
    ]
    
    for i, test_case in enumerate(test_cases):
        manifest_data = {
            "@context": "http://iiif.io/api/presentation/2/context.json",
            "@id": f"https://example.org/manifest-{i}",
            "label": f"Test Document {i}",
            "requiredStatement": {
                "label": "ATTRIBUTION",
                "value": test_case["html"]
            }
        }
        
        def mock_fetch_json(url):
            return manifest_data
            
        client.fetch_json = mock_fetch_json
        
        chunks = client.create_manifest_chunks([f"https://example.org/manifest-{i}"])
        
        assert len(chunks) == 1
        metadata = chunks[0]["metadata"]
        
        # Should extract the expected rights URL
        assert metadata["rights"] == test_case["expected"], f"Failed for test case {i}: {test_case['html']}"

def test_paginated_collection_v2_1_1():
    """Test processing IIIF 2.1.1 paginated collections"""
    client = IIIFClient(no_cache=True)
    
    # Mock top-level collection with pagination
    top_collection_data = load_fixture('iiif_v2.1.1_pagination.json')
    
    # Mock first page with manifests
    first_page_data = {
        "@context": "http://iiif.io/api/presentation/2/context.json",
        "@id": "https://api.digitale-sammlungen.de/iiif/presentation/v2/collection/top?cursor=initial",
        "@type": "sc:Collection",
        "label": "First Page",
        "manifests": [
            {
                "@id": "https://api.digitale-sammlungen.de/iiif/presentation/v2/bsb12040605/manifest",
                "@type": "sc:Manifest",
                "label": "Manifest 1"
            },
            {
                "@id": "https://api.digitale-sammlungen.de/iiif/presentation/v2/bsb12040606/manifest", 
                "@type": "sc:Manifest",
                "label": "Manifest 2"
            }
        ],
        "next": "https://api.digitale-sammlungen.de/iiif/presentation/v2/collection/top?cursor=page2"
    }
    
    # Mock second page with manifests (no next page)
    second_page_data = {
        "@context": "http://iiif.io/api/presentation/2/context.json",
        "@id": "https://api.digitale-sammlungen.de/iiif/presentation/v2/collection/top?cursor=page2",
        "@type": "sc:Collection", 
        "label": "Second Page",
        "manifests": [
            {
                "@id": "https://api.digitale-sammlungen.de/iiif/presentation/v2/bsb12040607/manifest",
                "@type": "sc:Manifest",
                "label": "Manifest 3"
            }
        ]
    }
    
    def mock_fetch_json(url):
        if url == "https://api.digitale-sammlungen.de/iiif/presentation/v2/collection/top":
            return top_collection_data
        elif url == "https://api.digitale-sammlungen.de/iiif/presentation/v2/collection/top?cursor=initial":
            return first_page_data
        elif url == "https://api.digitale-sammlungen.de/iiif/presentation/v2/collection/top?cursor=page2":
            return second_page_data
        return {}
        
    client.fetch_json = mock_fetch_json

    # Get manifests and collections
    manifests, collections = client.get_manifests_and_collections_ids(
        "https://api.digitale-sammlungen.de/iiif/presentation/v2/collection/top"
    )

    # Test expectations
    assert len(manifests) == 3, "Should find 3 manifests across paginated pages"
    assert len(collections) == 1, "Should find 1 collection (root collection)"

    # Verify specific manifest URLs
    expected_manifests = [
        "https://api.digitale-sammlungen.de/iiif/presentation/v2/bsb12040605/manifest",
        "https://api.digitale-sammlungen.de/iiif/presentation/v2/bsb12040606/manifest",
        "https://api.digitale-sammlungen.de/iiif/presentation/v2/bsb12040607/manifest"
    ]
    for manifest in expected_manifests:
        assert manifest in manifests, f"Should find manifest {manifest}"

def test_paginated_collection_with_max_manifests():
    """Test paginated collection respects max_manifests limit"""
    client = IIIFClient(no_cache=True)
    
    # Mock top-level collection with pagination
    top_collection_data = load_fixture('iiif_v2.1.1_pagination.json')
    
    # Mock first page with manifests
    first_page_data = {
        "@context": "http://iiif.io/api/presentation/2/context.json",
        "@id": "https://api.digitale-sammlungen.de/iiif/presentation/v2/collection/top?cursor=initial",
        "@type": "sc:Collection",
        "manifests": [
            {
                "@id": "https://api.digitale-sammlungen.de/iiif/presentation/v2/bsb12040605/manifest",
                "@type": "sc:Manifest",
                "label": "Manifest 1"
            },
            {
                "@id": "https://api.digitale-sammlungen.de/iiif/presentation/v2/bsb12040606/manifest",
                "@type": "sc:Manifest", 
                "label": "Manifest 2"
            }
        ],
        "next": "https://api.digitale-sammlungen.de/iiif/presentation/v2/collection/top?cursor=page2"
    }
    
    def mock_fetch_json(url):
        if url == "https://api.digitale-sammlungen.de/iiif/presentation/v2/collection/top":
            return top_collection_data
        elif url == "https://api.digitale-sammlungen.de/iiif/presentation/v2/collection/top?cursor=initial":
            return first_page_data
        return {}
        
    client.fetch_json = mock_fetch_json

    # Get manifests with limit of 1
    manifests, collections = client.get_manifests_and_collections_ids(
        "https://api.digitale-sammlungen.de/iiif/presentation/v2/collection/top",
        max_manifests=1
    )

    # Should stop at max_manifests limit
    assert len(manifests) == 1, "Should only return 1 manifest when max_manifests=1"
    assert manifests[0] == "https://api.digitale-sammlungen.de/iiif/presentation/v2/bsb12040605/manifest"

def test_paginated_collection_with_collections():
    """Test paginated collection that contains other collections"""
    client = IIIFClient(no_cache=True)
    
    # Mock top-level collection with pagination
    top_collection_data = {
        "@context": "http://iiif.io/api/presentation/2/context.json",
        "@id": "https://api.digitale-sammlungen.de/iiif/presentation/v2/collection/top",
        "@type": "sc:Collection",
        "label": "Top Level Collection",
        "first": "https://api.digitale-sammlungen.de/iiif/presentation/v2/collection/top?cursor=initial",
        "total": 100
    }
    
    # Mock first page with collections and manifests
    first_page_data = {
        "@context": "http://iiif.io/api/presentation/2/context.json",
        "@id": "https://api.digitale-sammlungen.de/iiif/presentation/v2/collection/top?cursor=initial",
        "@type": "sc:Collection",
        "collections": [
            {
                "@id": "https://api.digitale-sammlungen.de/iiif/presentation/v2/collection/subcoll1",
                "@type": "sc:Collection",
                "label": "Sub Collection 1"
            }
        ],
        "manifests": [
            {
                "@id": "https://api.digitale-sammlungen.de/iiif/presentation/v2/manifest1",
                "@type": "sc:Manifest",
                "label": "Manifest 1"
            }
        ]
    }
    
    def mock_fetch_json(url):
        if url == "https://api.digitale-sammlungen.de/iiif/presentation/v2/collection/top":
            return top_collection_data
        elif url == "https://api.digitale-sammlungen.de/iiif/presentation/v2/collection/top?cursor=initial":
            return first_page_data
        return {}
        
    client.fetch_json = mock_fetch_json

    manifests, collections = client.get_manifests_and_collections_ids(
        "https://api.digitale-sammlungen.de/iiif/presentation/v2/collection/top"
    )

    # Should find both manifests and sub-collections
    assert len(manifests) == 1, "Should find 1 manifest"
    assert len(collections) == 2, "Should find root collection and sub-collection"
    assert "https://api.digitale-sammlungen.de/iiif/presentation/v2/manifest1" in manifests
    assert "https://api.digitale-sammlungen.de/iiif/presentation/v2/collection/subcoll1" in collections

def test_paginated_collection_fetch_error():
    """Test handling when a paginated collection page fetch fails"""
    client = IIIFClient(no_cache=True)
    
    # Mock top-level collection with pagination
    top_collection_data = load_fixture('iiif_v2.1.1_pagination.json')
    
    def mock_fetch_json(url):
        if url == "https://api.digitale-sammlungen.de/iiif/presentation/v2/collection/top":
            return top_collection_data
        elif url == "https://api.digitale-sammlungen.de/iiif/presentation/v2/collection/top?cursor=initial":
            raise requests.RequestException("Connection error")
        return {}
        
    client.fetch_json = mock_fetch_json

    # Should handle page fetch error gracefully
    manifests, collections = client.get_manifests_and_collections_ids(
        "https://api.digitale-sammlungen.de/iiif/presentation/v2/collection/top"
    )

    # Should still include root collection even if page fetch fails
    assert len(manifests) == 0, "Should find no manifests due to page fetch error"
    assert len(collections) == 1, "Should still find root collection"

def test_paginated_collection_no_first_property():
    """Test handling when paginated collection has no 'first' property"""
    client = IIIFClient(no_cache=True)
    
    # Mock collection that looks paginated but has no 'first' property
    collection_data = {
        "@context": "http://iiif.io/api/presentation/2/context.json",
        "@id": "https://api.digitale-sammlungen.de/iiif/presentation/v2/collection/top",
        "@type": "sc:Collection",
        "label": "Top Level Collection",
        "total": 3074231
        # No 'first' property
    }
    
    def mock_fetch_json(url):
        if url == "https://api.digitale-sammlungen.de/iiif/presentation/v2/collection/top":
            return collection_data
        return {}
        
    client.fetch_json = mock_fetch_json

    # Should handle missing 'first' property gracefully
    manifests, collections = client.get_manifests_and_collections_ids(
        "https://api.digitale-sammlungen.de/iiif/presentation/v2/collection/top"
    )

    # Should still include root collection
    assert len(manifests) == 0, "Should find no manifests"
    assert len(collections) == 1, "Should find root collection"

def test_non_paginated_collection_with_items():
    """Test that non-paginated collections with regular items still work"""
    client = IIIFClient(no_cache=True)
    collection_data = load_fixture('iiif_v3_collection_with_manifests.json')
    
    def mock_fetch_json(url):
        if url == "https://api.dc.library.northwestern.edu/api/v2/collections/ba35820a-525a-4cfa-8f23-4891c9f798c4?as=iiif":
            return collection_data
        return {}
        
    client.fetch_json = mock_fetch_json

    # Should process normally (not as paginated collection)
    manifests, collections = client.get_manifests_and_collections_ids(
        "https://api.dc.library.northwestern.edu/api/v2/collections/ba35820a-525a-4cfa-8f23-4891c9f798c4?as=iiif"
    )

    # Should work as before
    assert len(manifests) == 3, "Should find 3 manifests in non-paginated collection"
    assert len(collections) == 1, "Should find 1 collection"
