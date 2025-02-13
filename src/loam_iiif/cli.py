# File: /src/loam_iiif/cli.py

import json
import logging
import os
import re
import sys
import tempfile
from pathlib import Path

import click
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

from .iiif import IIIFClient

# Initialize Rich Console for logging (outputs to stderr)
console = Console(stderr=True)

# Get system temp directory
DEFAULT_CACHE_DIR = os.path.join(tempfile.gettempdir(), "loam-iiif")

def sanitize_filename(name: str) -> str:
    """
    Sanitize the filename by removing or replacing invalid characters.
    Primary use is for manifest downloads where filenames are derived from manifest URLs.

    Args:
        name (str): The original filename.

    Returns:
        str: The sanitized filename.
    """
    # Replace any non-alphanumeric chars (except .-_) with underscore
    base, ext = os.path.splitext(name)
    base = re.sub(r'[^\w\-_.]', '_', base)
    return base + ext


@click.group()
def cli():
    """IIIF collection and manifest processing tools."""
    pass

@cli.command(name="collect")
@click.argument("url")
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    help="Output file to save the results (JSON, JSONL, or plain text format).",
)
@click.option(
    "--format",
    "-f",
    type=click.Choice(["json", "jsonl", "table"], case_sensitive=False),
    default="json",
    help="Output format: 'json', 'jsonl' for JSON Lines, or 'table'.",
)
@click.option(
    "--debug",
    is_flag=True,
    help="Enable debug mode with detailed logs.",
)
@click.option(
    "--download-manifests",
    "-d",
    is_flag=True,
    help="Download full JSON contents of each manifest.",
)
@click.option(
    "--cache-dir",
    "-c",
    type=click.Path(),
    help="Directory to cache manifest JSON files. Defaults to system temp directory.",
)
@click.option(
    "--max-manifests",
    "-m",
    type=click.INT,
    default=None,
    help="Maximum number of manifests to retrieve. If not specified, all manifests are retrieved.",
)
@click.option(
    "--skip-cache",
    is_flag=True,
    help="Skip reading from cache but still write to it.",
)
@click.option(
    "--no-cache",
    is_flag=True,
    help="Disable manifest caching completely.",
)
@click.option(
    "--images",
    "-i",
    is_flag=True,
    help="Include image URLs in the output for each manifest.",
)
@click.option(
    "--width",
    "-w",
    type=click.INT,
    default=768,
    help="Desired width of images when using --images",
)
@click.option(
    "--height",
    "-h",
    type=click.INT,
    default=2000,
    help="Desired height of images when using --images",
)
@click.option(
    "--image-format",
    type=click.Choice(["jpg", "png"], case_sensitive=False),
    default="jpg",
    help="Image format when using --images (jpg or png)",
)
@click.option(
    "--exact",
    is_flag=True,
    help="Use exact dimensions for images without preserving aspect ratio",
)
@click.option(
    "--max",
    "use_max",
    is_flag=True,
    help="Use maximum size for images instead of specific dimensions",
)
def collect(
    url: str,
    output: str,
    format: str,
    debug: bool,
    download_manifests: bool,
    cache_dir: str,
    max_manifests: int,
    skip_cache: bool,
    no_cache: bool,
    images: bool,
    width: int,
    height: int,
    image_format: str,
    exact: bool,
    use_max: bool,
):
    """
    Traverse a IIIF collection URL and retrieve manifests.

    URL: The IIIF collection URL to process.
    """
    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.WARNING,
        format="%(message)s",
        datefmt="[%Y-%m-%d %H:%M:%S]",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )
    logger = logging.getLogger("iiif")

    if debug:
        logger.debug(f"Starting traversal of IIIF collection: {url}")

    cache_directory = cache_dir if cache_dir else DEFAULT_CACHE_DIR
    if debug:
        logger.debug(f"Using cache directory: {cache_directory}")

    try:
        with IIIFClient(cache_dir=cache_directory, skip_cache=skip_cache, no_cache=no_cache) as client:
            manifests, collections = client.get_manifests_and_collections_ids(url, max_manifests)
            
            # If images flag is set, get image URLs for each manifest
            manifest_data = []
            if images:
                if debug:
                    logger.debug(f"Processing {len(manifests)} manifests for image URLs")
                for idx, manifest_url in enumerate(manifests, start=1):
                    if debug:
                        logger.debug(f"Getting images for manifest {idx}/{len(manifests)}: {manifest_url}")
                    try:
                        image_urls = client.get_manifest_images(
                            manifest_url,
                            width=width,
                            height=height,
                            format=image_format,
                            exact=exact,
                            use_max=use_max
                        )
                        manifest_entry = {
                            "id": manifest_url,
                            "images": image_urls
                        }
                        manifest_data.append(manifest_entry)
                    except Exception as e:
                        logger.error(f"Error getting images from manifest {manifest_url}: {e}")
                        manifest_data.append({
                            "id": manifest_url,
                            "images": []
                        })
            
            if debug:
                logger.debug(
                    f"Traversal completed. Found {len(manifests)} unique manifests and {len(collections)} collections."
                )

            # Handle manifest downloads if enabled
            if download_manifests and not no_cache:
                if debug:
                    logger.debug(f"Downloading JSON contents for {len(manifests)} manifests.")

                # If output is specified, treat it as a directory for manifest files
                if output:
                    output_dir = Path(output)
                    output_dir.mkdir(parents=True, exist_ok=True)
                    if debug:
                        logger.debug(f"Will save manifest files to directory: {output_dir}")

                # Manifests will be cached automatically by fetch_json()
                for idx, manifest_url in enumerate(manifests, start=1):
                    try:
                        manifest_data = client.fetch_json(manifest_url)
                        if output:
                            # Save each manifest to its own file in the output directory
                            filename = sanitize_filename(manifest_url.split("/")[-1]) + ".json"
                            manifest_path = output_dir / filename
                            with open(manifest_path, "w", encoding="utf-8") as f:
                                json.dump(manifest_data, f, indent=2)
                        if debug:
                            logger.debug(f"Processed manifest {idx}/{len(manifests)}")
                    except Exception as e:
                        logger.error(f"Failed to download manifest {manifest_url}: {e}")

                if output:
                    if debug:
                        logger.debug(f"All manifests have been saved to {output_dir}")
                    # Exit here since we've handled the output already
                    return
                elif debug:
                    logger.debug(f"All manifests have been cached to {cache_directory}")

            # Output handling
            if format.lower() == "json":
                result = {
                    "manifests": [
                        {"id": item["id"], "images": item["images"]} if images else item
                        for item in (manifest_data if images else manifests)
                    ],
                    "collections": collections,
                }
                json_data = json.dumps(result, indent=2)

                if output:
                    try:
                        with open(output, "w", encoding="utf-8") as f:
                            f.write(json_data)
                        if debug:
                            logger.debug(f"Results saved to {output}")
                    except IOError as e:
                        logger.error(f"Failed to write to file {output}: {e}")
                        sys.exit(1)
                else:
                    print(json_data)

            elif format.lower() == "jsonl":
                if output:
                    try:
                        with open(output, "w", encoding="utf-8") as f:
                            for item in (manifest_data if images else manifests):
                                if images:
                                    json_line = json.dumps({"manifest": item["id"], "images": item["images"]})
                                else:
                                    json_line = json.dumps({"manifest": item})
                                f.write(json_line + "\n")
                            for collection in collections:
                                json_line = json.dumps({"collection": collection})
                                f.write(json_line + "\n")
                        if debug:
                            logger.debug(f"JSON Lines results saved to {output}")
                    except IOError as e:
                        logger.error(f"Failed to write to file {output}: {e}")
                        sys.exit(1)
                else:
                    for item in (manifest_data if images else manifests):
                        if images:
                            print(json.dumps({"manifest": item["id"], "images": item["images"]}))
                        else:
                            print(json.dumps({"manifest": item}))
                    for collection in collections:
                        print(json.dumps({"collection": collection}))

            elif format.lower() == "table":
                # Create and display tables using Rich
                if manifests:
                    manifest_table = Table(title="Manifests")
                    manifest_table.add_column(
                        "Index", justify="right", style="cyan", no_wrap=True
                    )
                    manifest_table.add_column("Manifest URL", style="magenta")
                    if images:
                        manifest_table.add_column("Image Count", style="green")

                    if images:
                        for idx, item in enumerate(manifest_data, start=1):
                            manifest_table.add_row(str(idx), item["id"], str(len(item["images"])))
                    else:
                        for idx, manifest in enumerate(manifests, start=1):
                            manifest_table.add_row(str(idx), manifest)
                    console.print(manifest_table)

                if collections:
                    collection_table = Table(title="Collections")
                    collection_table.add_column(
                        "Index", justify="right", style="cyan", no_wrap=True
                    )
                    collection_table.add_column("Collection URL", style="magenta")

                    for idx, collection in enumerate(collections, start=1):
                        collection_table.add_row(str(idx), collection)
                    console.print(collection_table)

    except Exception as e:
        error_msg = f"An error occurred: {e}"
        logger.error(error_msg)
        click.echo(error_msg, err=True)  # Echo error to stderr
        sys.exit(1)

def main():
    """Entry point for the CLI."""
    cli()
