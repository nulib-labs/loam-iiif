# loam-iiif

A command-line tool for traversing IIIF collections and extracting manifest URLs. This tool helps you explore and collect IIIF manifest URLs from collections, with support for nested collections and paginated results.

## Features

- **Recursively Traverses IIIF Collections:** Finds all manifest URLs within a collection, including those in nested collections.
- **Supports Multiple IIIF Presentation API Versions:** Compatible with both IIIF Presentation API 2.0 and 3.0.
- **Multiple Output Formats:** Choose between `json`, `jsonl` (JSON Lines), and formatted tables.
- **Download Full Manifest JSONs:** Save the complete JSON content of each manifest, named by their IDs.
- **Save Results to File or Display in Terminal:** Flexible output options to suit your workflow.
- **Debug Mode for Detailed Logging:** Provides comprehensive logs for troubleshooting and monitoring.
- **Robust Error Handling with Automatic Retries:** Ensures reliable data fetching even in the face of transient network issues.
- **Support for Paginated Collections:** Handles collections that span multiple pages seamlessly.

## Installation

Requires Python 3.10 or higher.

```bash
pip install loam-iiif
```

## Usage

The basic command structure is:

```bash
loamiiif [OPTIONS] URL
```

### Options

- `-o, --output PATH`: If used with `--download-manifests`, specifies directory to save manifest JSON files. Otherwise saves manifest URLs list to a file (JSON or plain text format)
- `-f, --format [json|jsonl|table]`: Output format (default: json)
- `-d, --download-manifests`: Download full JSON contents of each manifest
- `--cache-dir, -c PATH`: Directory to cache manifest JSON files (defaults to system temp directory)
- `--skip-cache`: Skip reading from cache but still write to it
- `--no-cache`: Disable manifest caching completely
- `--debug`: Enable debug mode with detailed logs
- `--help`: Show help message
- `--max-manifests, -m INTEGER`: Maximum number of manifests to retrieve

### Examples

#### Basic Usage
```bash
loamiiif "https://api.dc.library.northwestern.edu/api/v2/collections/c69bb1ed-accb-4cfb-b60e-495b9911690f?as=iiif"
```

#### Output Options

Output as a formatted table:
```bash
loamiiif "https://api.dc.library.northwestern.edu/api/v2/collections?as=iiif" --format table
```

Save manifest URLs to different formats:
```bash
# JSON output
loamiiif "https://api.dc.library.northwestern.edu/api/v2/collections?as=iiif" --output manifests.json

# JSON Lines (jsonl) output
loamiiif "https://api.dc.library.northwestern.edu/api/v2/collections?as=iiif" --format jsonl --output manifests.jsonl
```

Download manifest contents to a directory:
```bash
# Downloads full manifest JSON files to ./manifest_downloads/ directory
loamiiif "https://api.dc.library.northwestern.edu/api/v2/collections?as=iiif" --download-manifests --output ./manifest_downloads
```

#### Advanced Features

Download manifests and save JSON output:
```bash
loamiiif "https://api.dc.library.northwestern.edu/api/v2/collections?as=iiif" --format json --output manifests.json --download-manifests
```

Limit the number of manifests:
```bash
loamiiif "https://api.dc.library.northwestern.edu/api/v2/collections?as=iiif" --max-manifests=42
```

Enable debug logging:
```bash
loamiiif "https://api.dc.library.northwestern.edu/api/v2/collections?as=iiif" --debug
```

#### Cache Control

Use a custom cache directory:
```bash
loamiiif "https://api.dc.library.northwestern.edu/api/v2/collections?as=iiif" --cache-dir ./my-cache-dir
```

Skip reading from cache but still write to it:
```bash
loamiiif "https://api.dc.library.northwestern.edu/api/v2/collections?as=iiif" --skip-cache
```

Disable caching completely:
```bash
loamiiif "https://api.dc.library.northwestern.edu/api/v2/collections?as=iiif" --no-cache
```

Example debug output (truncated):

```
[2025-01-17 14:14:48] DEBUG    Starting traversal of IIIF collection: https://api.dc.library.northwestern.edu/api/v2/collections?as=iiif
                      INFO     Processing collection: https://api.dc.library.northwestern.edu/api/v2/collections?as=iiif
                      DEBUG    Fetching URL: https://api.dc.library.northwestern.edu/api/v2/collections?as=iiif
                      DEBUG    Successfully fetched data from https://api.dc.library.northwestern.edu/api/v2/collections?as=iiif
                      DEBUG    Found nested collection: https://api.dc.library.northwestern.edu/api/v2/collections/ba35820a-525a-4cfa-8f23-4891c9f798c4?as=iiif
                      INFO     Processing collection: https://api.dc.library.northwestern.edu/api/v2/collections/ba35820a-525a-4cfa-8f23-4891c9f798c4?as=iiif
                      DEBUG    Added manifest: https://api.dc.library.northwestern.edu/api/v2/works/e40479c4-06cb-48be-9d6b-adf47f238852?as=iiif
                      DEBUG    Added manifest: https://api.dc.library.northwestern.edu/api/v2/works/f4720687-61b6-4dcd-aed0-b70eff985583?as=iiif
                      # ... more manifests and collections ...
```

## Caching Behavior

The tool implements manifest caching to improve performance and reduce load on IIIF servers:

- By default, manifests are cached in your system's temporary directory (`/tmp` on Unix-like systems)
- Use `--cache-dir` to specify a custom cache location
- `--skip-cache` will ignore existing cache but still write new cache entries (useful for refreshing stale data)
- `--no-cache` completely disables caching (not recommended for large collections)

Cached manifests are stored as JSON files named using a sanitized version of their URLs. The cache is particularly useful when:

- Working with large collections that you'll need to process multiple times
- Using the `--download-manifests` option to save full manifest contents
- Running the tool repeatedly during development or testing

## Output Formats

### JSON

The JSON output includes both manifests and collections:

```json
{
  "manifests": [
    "https://api.dc.library.northwestern.edu/api/v2/works/9d87853e-3955-4912-906f-6ddf0e2e3825?as=iiif",
    "..."
  ],
  "collections": []
}
```

### JSON Lines (jsonl)

Each line contains a single manifest or collection URL:

```jsonl
{"manifest": "https://api.dc.library.northwestern.edu/api/v2/works/9d87853e-3955-4912-906f-6ddf0e2e3825?as=iiif"}
{"manifest": "..."}
{"collection": "https://api.dc.library.northwestern.edu/api/v2/collections/ba35820a-525a-4cfa-8f23-4891c9f798c4?as=iiif"}
```

### Table

The table format provides a readable view of manifests and collections with indexed entries.

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
uv venv --python 3.10
source .venv/bin/activate  # On Windows use: .venv\Scripts\activate
```

3. Install dependencies:

```bash
uv sync
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Project Links

- [GitHub Repository](https://github.com/nulib-labs/loam-iiif)
- [Issue Tracker](https://github.com/nulib-labs/loam-iiif/issues)
