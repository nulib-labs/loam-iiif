# loam-iiif

A command-line tool for traversing IIIF collections and extracting manifest URLs and image information. This tool helps you explore and collect IIIF manifest URLs from collections, with support for nested collections and image extraction.

## Features

- **Recursively Traverses IIIF Collections:** Finds all manifest URLs within a collection, including those in nested collections
- **Supports Multiple IIIF Presentation API Versions:** Compatible with both IIIF Presentation API 2.0 and 3.0, including full support for paginated collections in both IIIF 2.1.1 and 3.0 formats
- **Automatic Pagination Handling:** Seamlessly processes paginated IIIF collections using both `first`/`next` links (2.1.1) and "Next page" items (3.0)
- **Multiple Output Formats:** Choose between `json`, `jsonl` (JSON Lines), and formatted tables
- **Image URL Extraction:** Get IIIF image URLs from manifests with customizable dimensions
- **Download Full Manifest JSONs:** Save the complete JSON content of each manifest, named by their IDs
- **Save Results to File or Display in Terminal:** Flexible output options to suit your workflow
- **Debug Mode for Detailed Logging:** Provides comprehensive logs for troubleshooting and monitoring
- **Robust Error Handling with Automatic Retries:** Ensures reliable data fetching even in the face of transient network issues
- **Support for Paginated Collections:** Handles collections that span multiple pages seamlessly
- **Efficient Caching:** Built-in caching system with configurable options

## Installation

Requires Python 3.10 or higher.

```bash
pip install loam-iiif
```

## Usage

The basic command structure is:

```bash
loamiiif collect [OPTIONS] URL
```

### Options

- `-f, --format [json|jsonl|table]`: Output format (default: json)
- `-o, --output PATH`: Save output to a file. For manifests, specifies directory
- `-i, --images`: Include IIIF image URLs from each manifest
- `-w, --width INTEGER`: Desired width of images (default: 768)
- `-h, --height INTEGER`: Desired height of images (default: 2000)
- `--image-format [jpg|png]`: Image format (default: jpg)
- `--exact`: Use exact dimensions without preserving aspect ratio (default: false)
- `--max`: Use maximum size instead of specific dimensions. Uses 'full' for IIIF v2 manifests and 'max' for v3 manifests. When enabled, overrides --width, --height, and --exact options
- `-d, --download-manifests`: Download full JSON contents of each manifest
- `-c, --cache-dir PATH`: Directory to cache manifest JSON files
- `--skip-cache`: Skip reading from cache but still write to it
- `--no-cache`: Disable manifest caching completely
- `-m, --max-manifests INTEGER`: Maximum number of manifests to retrieve
- `--debug`: Enable debug mode with detailed logs

### Examples

#### Basic Usage - Get Manifests as JSON

```bash
loamiiif collect "https://api.dc.library.northwestern.edu/api/v2/collections/ba35820a-525a-4cfa-8f23-4891c9f798c4?as=iiif" --format json
```

Output:
```json
{
  "manifests": [
    "https://api.dc.library.northwestern.edu/api/v2/works/faafca34-ecf4-4848-838a-da220d864042?as=iiif",
    "https://api.dc.library.northwestern.edu/api/v2/works/e40479c4-06cb-48be-9d6b-adf47f238852?as=iiif",
    "https://api.dc.library.northwestern.edu/api/v2/works/f4720687-61b6-4dcd-aed0-b70eff985583?as=iiif"
  ],
  "collections": [
    "https://api.dc.library.northwestern.edu/api/v2/collections/ba35820a-525a-4cfa-8f23-4891c9f798c4?as=iiif"
  ]
}
```

#### Get Manifests with Image URLs in Table Format

```bash
loamiiif collect -i "https://api.dc.library.northwestern.edu/api/v2/collections?as=iiif" --max-manifests 3 --format table
```

This displays a formatted table showing manifest URLs and their image counts:

```
                                               Manifests                                                
┏━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┓
┃ Index ┃ Manifest URL                                                                   ┃ Image Count ┃
┡━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━┩
│     1 │ https://api.dc.library.northwestern.edu/api/v2/works/faafca34-ecf4-4848-838a-… │ 92          │
│     2 │ https://api.dc.library.northwestern.edu/api/v2/works/e40479c4-06cb-48be-9d6b-… │ 135         │
│     3 │ https://api.dc.library.northwestern.edu/api/v2/works/f4720687-61b6-4dcd-aed0-… │ 168         │
└───────┴────────────────────────────────────────────────────────────────────────────────┴─────────────┘
```

#### Get Manifest Image URLs with Custom Dimensions

```bash
loamiiif collect -i --width 1024 --height 1024 "https://api.dc.library.northwestern.edu/api/v2/collections?as=iiif" --format json
```

Output includes manifests with their image URLs, formatted to the specified dimensions (preserving aspect ratio by default):

```json
{
  "manifests": [
    {
      "id": "https://api.dc.library.northwestern.edu/api/v2/works/faafca34-ecf4-4848-838a-da220d864042?as=iiif",
      "images": [
        "https://iiif.dc.library.northwestern.edu/iiif/3/1e13bf6c-3be6-4971-8439-cbb5b75f9106/full/!1024,1024/0/default.jpg",
        ...
      ]
    }
  ],
  "collections": [...]
}
```

For exact dimensions without aspect ratio preservation:
```bash
loamiiif collect -i --width 1024 --height 1024 --exact "https://api.dc.library.northwestern.edu/api/v2/collections?as=iiif"
```

This will output image URLs using the exact dimensions specified:
```json
{
  "manifests": [
    {
      "id": "https://api.dc.library.northwestern.edu/api/v2/works/faafca34-ecf4-4848-838a-da220d864042?as=iiif",
      "images": [
        "https://iiif.dc.library.northwestern.edu/iiif/3/1e13bf6c-3be6-4971-8439-cbb5b75f9106/full/1024,1024/0/default.jpg",
        ...
      ]
    }
  ]
}
```

To get maximum size images regardless of any dimension settings:
```bash
loamiiif collect -i --max "https://api.dc.library.northwestern.edu/api/v2/collections?as=iiif"
```

This will output image URLs using 'max' for IIIF v3 manifests and 'full' for v2 manifests:
```json
{
  "manifests": [
    {
      "id": "https://api.dc.library.northwestern.edu/api/v2/works/faafca34-ecf4-4848-838a-da220d864042?as=iiif",
      "images": [
        "https://iiif.dc.library.northwestern.edu/iiif/3/1e13bf6c-3be6-4971-8439-cbb5b75f9106/full/max/0/default.jpg",  // v3 manifest
        "https://view.nls.uk/iiif/1161/2928/116129282.5/full/full/0/default.jpg"  // v2 manifest
      ]
    }
  ]
}
```

#### Save Results to Files

Save manifest list to JSON file:
```bash
loamiiif collect "https://api.dc.library.northwestern.edu/api/v2/collections?as=iiif" -o manifests.json
```

Download manifest contents to a directory:
```bash
loamiiif collect "https://api.dc.library.northwestern.edu/api/v2/collections?as=iiif" --download-manifests -o ./manifest_downloads
```

Save as JSON Lines format:
```bash
loamiiif collect "https://api.dc.library.northwestern.edu/api/v2/collections?as=iiif" -f jsonl -o manifests.jsonl
```

#### Cache Control

Use a custom cache directory:
```bash
loamiiif collect "https://api.dc.library.northwestern.edu/api/v2/collections?as=iiif" --cache-dir ./my-cache-dir
```

Skip reading from cache but still write to it:
```bash
loamiiif collect "https://api.dc.library.northwestern.edu/api/v2/collections?as=iiif" --skip-cache
```

Disable caching completely:
```bash
loamiiif collect "https://api.dc.library.northwestern.edu/api/v2/collections?as=iiif" --no-cache
```

## IIIF Pagination Support

loam-iiif provides comprehensive support for paginated IIIF collections across multiple API versions. Many large institutions use pagination to break down extensive collections into manageable chunks.

### Supported Pagination Patterns

loam-iiif automatically handles multiple pagination patterns:

#### IIIF Presentation API 2.1.1 Pagination
Uses `first` and `next` properties to link between pages:
```json
{
  "@context": "http://iiif.io/api/presentation/2/context.json",
  "@id": "https://example.org/collection/main",
  "@type": "sc:Collection",
  "label": "Large Collection",
  "first": {
    "@id": "https://example.org/collection/main/page/1",
    "@type": "sc:Collection"
  }
}
```

#### IIIF Presentation API 3.0 Pagination  
Uses collection items with "Next page" labels and pagination URLs:
```json
{
  "@context": "http://iiif.io/api/presentation/3/context.json",
  "id": "https://api.dc.library.northwestern.edu/api/v2/collections?as=iiif",
  "type": "Collection",
  "items": [
    {
      "id": "https://api.dc.library.northwestern.edu/api/v2/collections?as=iiif&page=2",
      "type": "Collection",
      "label": {
        "none": ["Next page"]
      }
    }
  ]
}
```

### How Pagination Works

When loam-iiif encounters a paginated collection, it:

1. **Automatically detects** pagination patterns in both IIIF 2.1.1 and 3.0 formats
2. **Follows pagination links** by traversing `first`/`next` properties or "Next page" items
3. **Collects manifests and collections** from all pages seamlessly
4. **Respects limits** set by `--max-manifests` or `max_manifests` parameter
5. **Handles errors gracefully** by stopping pagination on fetch failures

### Examples of Paginated Collections

```bash
# Process IIIF 2.1.1 paginated collection (Bavarian State Library)
loamiiif collect "https://api.digitale-sammlungen.de/iiif/presentation/v2/collection/top" --max-manifests 100

# Process IIIF 3.0 paginated collection (Northwestern University)
loamiiif collect "https://api.dc.library.northwestern.edu/api/v2/collections?as=iiif" --max-manifests 50

# Pagination is handled automatically - no special flags needed
```

Common institutions using paginated collections:
- **Northwestern University** (`api.dc.library.northwestern.edu`) - IIIF 3.0 page-based pagination
- **Bavarian State Library** (`digitale-sammlungen.de`) - IIIF 2.1.1 first/next pagination  
- **Internet Archive** - Extensive digital library collections
- **HathiTrust** - Academic and research library materials

### Non-Paginated vs Paginated Collections

**Non-paginated collections** contain all manifests and sub-collections directly in the main JSON response.

**Paginated collections** split content across multiple pages using different patterns depending on the IIIF version:

```json
{
  "@context": "http://iiif.io/api/presentation/2/context.json",
  "@id": "https://example.org/collection/main",
  "@type": "sc:Collection",
  "label": "Large Collection",
  "first": {
    "@id": "https://example.org/collection/main/page/1",
    "@type": "sc:Collection"
  }
}
```

loam-iiif seamlessly handles both types without requiring different commands or options.

## Python API Usage

In addition to the command-line interface, loam-iiif can be used directly in Python code.

### Handling Paginated Collections

loam-iiif automatically detects and processes paginated collections in both IIIF 2.1.1 and 3.0 formats. Whether a collection uses `first`/`next` links (2.1.1) or "Next page" items (3.0), the library will traverse all pages to collect manifests and nested collections.

```python
from loam_iiif.iiif import IIIFClient

# Initialize client
client = IIIFClient()

# Process IIIF 2.1.1 paginated collection (first/next links)
manifests, collections = client.get_manifests_and_collections_ids(
    "https://api.digitale-sammlungen.de/iiif/presentation/v2/collection/top",
    max_manifests=50  # Optional limit to control processing
)

# Process IIIF 3.0 paginated collection (page items)
manifests, collections = client.get_manifests_and_collections_ids(
    "https://api.dc.library.northwestern.edu/api/v2/collections?as=iiif",
    max_manifests=50  # Optional limit to control processing
)

print(f"Found {len(manifests)} manifests across all pages")
print(f"Found {len(collections)} collections")
```

### Processing Multiple Collections with Chunked Output

Here's a comprehensive example showing how to process multiple IIIF collections and save chunked output:

```python
from loam_iiif import IIIFClient
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Collection configurations
collections = [
    {
        "url": "https://digital.library.villanova.edu/Collection/vudl:7028/IIIF",
        "output_file": "loam_villanova_collection_chunks.json"
    },
    {
        "url": "https://api.dc.library.northwestern.edu/api/v2/collections/ecacd539-fe38-40ec-bbc0-590acee3d4f2?as=iiif",
        "output_file": "loam_northwestern_collection_chunks.json"
    },
    {
        "url": "https://iiif.durham.ac.uk/manifests/trifle/collection/32150/t2c7s75dc36q",
        "output_file": "loam_durham_manifest_chunks.json"
    },
    {
        "url": "https://api.digitale-sammlungen.de/iiif/presentation/v2/collection/top",
        "output_file": "loam_digitale_sammlungen_manifest_chunks.json"
    }
]

# Initialize client
client = IIIFClient()

# Process each collection
for i, collection in enumerate(collections):
    print(f"\n{'='*60}")
    print(f"Processing collection {i+1}/{len(collections)}: {collection['url']}")
    print(f"{'='*60}")
    
    logging.info(f"Processing collection: {collection['url']}")
    
    try:
        # Create and save manifest chunks (pagination handled automatically)
        chunks = client.create_and_save_manifest_chunks(
            collection["url"], 
            collection["output_file"], 
            max_manifests=10  # Limit for example purposes
        )
        
        if chunks:
            logging.info(f"Manifest chunks created and saved to {collection['output_file']}.")
            print(f"\nSample chunk from {collection['output_file']}:")
            print(json.dumps(chunks[0], indent=2))
        else:
            logging.error(f"Failed to create manifest chunks for {collection['url']}.")
            print(f"No chunks were created for {collection['url']}.")
            
    except Exception as e:
        logging.error(f"Error processing {collection['url']}: {e}")
        print(f"Error processing {collection['url']}: {e}")

print("\nProcessing complete!")
```

This example demonstrates:
- Processing multiple IIIF collections including paginated ones
- Automatic handling of IIIF 2.1.1 pagination (like digitale-sammlungen.de)
- Creating and saving manifest chunks to JSON files
- Displaying sample chunk output
- Error handling and progress logging
- Setting limits on manifest processing

### Basic Usage

```python
from loam_iiif.iiif import IIIFClient

# Initialize client with options
client = IIIFClient(
    skip_cache=True  # Skip reading from cache but still write to it
)

# Get manifest and collection URLs from a collection
manifests, collections = client.get_manifests_and_collections_ids(
    "https://api.dc.library.northwestern.edu/api/v2/collections/ba35820a-525a-4cfa-8f23-4891c9f798c4?as=iiif"
)
```

The above code returns a tuple of two lists: manifest URLs and collection URLs that were found:
```python
# manifests will contain:
[
    'https://api.dc.library.northwestern.edu/api/v2/works/f4720687-61b6-4dcd-aed0-b70eff985583?as=iiif',
    'https://api.dc.library.northwestern.edu/api/v2/works/faafca34-ecf4-4848-838a-da220d864042?as=iiif',
    'https://api.dc.library.northwestern.edu/api/v2/works/e40479c4-06cb-48be-9d6b-adf47f238852?as=iiif'
]

# collections will contain:
[
    'https://api.dc.library.northwestern.edu/api/v2/collections/ba35820a-525a-4cfa-8f23-4891c9f798c4?as=iiif'
]
```

### Getting Image URLs

```python
from loam_iiif.iiif import IIIFClient

client = IIIFClient()

# Get image URLs from a manifest with custom dimensions
image_urls = client.get_manifest_images(
    "https://api.dc.library.northwestern.edu/api/v2/works/f4720687-61b6-4dcd-aed0-b70eff985583?as=iiif",
    width=1024,
    height=1024,
    format='jpg',  # 'jpg' or 'png'
    exact=False,   # Whether to preserve aspect ratio
    use_max=False  # Whether to use maximum size
)
```

### Client Options

The `IIIFClient` constructor accepts several options:

```python
client = IIIFClient(
    retry_total=2,           # Total number of retries for failed requests
    backoff_factor=1,        # Backoff factor between retries
    timeout=10.0,           # Request timeout in seconds
    cache_dir="manifests",  # Directory for caching manifests
    skip_cache=False,       # Skip reading from cache but still write
    no_cache=False         # Disable caching completely
)
```

## Debug Output Example

When running with `--debug`, you'll see detailed progress information:

```
[2025-01-17 14:14:48] DEBUG    Starting traversal of IIIF collection: https://api.dc.library.northwestern.edu/api/v2/collections?as=iiif
                      INFO     Processing collection: https://api.dc.library.northwestern.edu/api/v2/collections?as=iiif
                      DEBUG    Fetching URL: https://api.dc.library.northwestern.edu/api/v2/collections?as=iiif
                      DEBUG    Successfully fetched data from https://api.dc.library.northwestern.edu/api/v2/collections?as=iiif
                      DEBUG    Found nested collection: https://api.dc.library.northwestern.edu/api/v2/collections/ba35820a-525a-4cfa-8f23-4891c9f798c4?as=iiif
                      DEBUG    Added manifest: https://api.dc.library.northwestern.edu/api/v2/works/e40479c4-06cb-48be-9d6b-adf47f238852?as=iiif
```

## Development

### Requirements

- Python 3.10+
- click>=8.1.8
- requests>=2.32.3
- rich>=13.9.4

### Development Installation

1. Clone the repository:
```bash
git clone https://github.com/nulib-labs/loam-iiif.git
cd loam-iiif
```

2. Create and activate a virtual environment with `uv`:
```bash
uv venv
source .venv/bin/activate  # On Windows use: .venv\Scripts\activate
```

3. Install development dependencies:
```bash
uv pip install -e ".[dev]"
```

### Running Tests

Run the test suite with pytest:
```bash
pytest
```

Generate an HTML coverage report:
```bash
pytest --cov=loam_iiif test/ --cov-report=html
```

This will create a coverage report in the `htmlcov` directory that you can view in your browser.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Project Links

- [GitHub Repository](https://github.com/nulib-labs/loam-iiif)
- [Issue Tracker](https://github.com/nulib-labs/loam-iiif/issues)
