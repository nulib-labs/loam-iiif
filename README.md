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

- `-o, --output PATH`: Save results to a file (JSON or plain text format)
- `-f, --format [json|jsonl|table]`: Output format (default: json)
- `-d, --download-manifests`: Download full JSON contents of each manifest
- `-j, --json-output-dir PATH`: Directory to save full manifest JSONs
- `--debug`: Enable debug mode with detailed logs
- `--help`: Show help message

### Examples

1. Basic usage (outputs JSON to stdout):

```bash
loamiiif "https://api.dc.library.northwestern.edu/api/v2/collections/c69bb1ed-accb-4cfb-b60e-495b9911690f?as=iiif"
```

2. Output as a formatted table:

```bash
loamiiif "https://api.dc.library.northwestern.edu/api/v2/collections/c69bb1ed-accb-4cfb-b60e-495b9911690f?as=iiif" --format table
```

3. Save results to a JSON file:

```bash
loamiiif "https://api.dc.library.northwestern.edu/api/v2/collections/c69bb1ed-accb-4cfb-b60e-495b9911690f?as=iiif" --output manifests.json
```

4. Save Results to a JSON Lines (jsonl) File:

```bash
loamiiif "https://api.dc.library.northwestern.edu/api/v2/collections/c69bb1ed-accb-4cfb-b60e-495b9911690f?as=iiif" --format jsonl --output manifests.jsonl
```

5. Enable debug logging:

```bash
loamiiif "https://api.dc.library.northwestern.edu/api/v2/collections?as=iiif" --debug
```

6. Combine Downloading Manifests with JSON Output:

```bash
loamiiif "https://api.dc.library.northwestern.edu/api/v2/collections?as=iiif" --format json --output manifests.json --download-manifests --json-output-dir ./manifests_json
```

7. Set a maximum number of manifests to retrieve

```bash
loamiiif "https://api.dc.library.northwestern.edu/api/v2/collections?as=iiif" --max-manifests=42
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

Debug mode shows detailed information about:

- Collection traversal progress
- HTTP requests and responses
- Discovered manifests and nested collections
- Any errors or issues encountered

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
