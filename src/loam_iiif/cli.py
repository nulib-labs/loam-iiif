# File: /src/loam_iiif/cli.py

import json
import logging
import os
import re
import sys

import click
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

from .iiif import IIIFClient

# Initialize Rich Console for logging (outputs to stderr)
console = Console(stderr=True)


def sanitize_filename(name: str) -> str:
    """
    Sanitize the filename by removing or replacing invalid characters.

    Args:
        name (str): The original filename.

    Returns:
        str: The sanitized filename.
    """
    # Remove any characters that are not alphanumeric, hyphens, underscores, or dots
    return re.sub(r"[^\w\-_\.]", "_", name)


@click.command()
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
    "--json-output-dir",
    "-j",
    type=click.Path(),
    default="manifests",
    show_default=True,
    help="Directory to save the manifest JSON files.",
)
@click.option(
    "--max-manifests",
    "-m",
    type=click.INT,
    default=None,
    help="Maximum number of manifests to retrieve. If not specified, all manifests are retrieved.",
)
def main(
    url: str,
    output: str,
    format: str,
    debug: bool,
    download_manifests: bool,
    json_output_dir: str,
    max_manifests: int,
):
    """
    Traverse a IIIF collection URL and retrieve manifests.

    URL: The IIIF collection URL to process.
    """
    # Configure Logging with RichHandler to stderr
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.WARNING,
        format="%(message)s",
        datefmt="[%Y-%m-%d %H:%M:%S]",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )
    logger = logging.getLogger("iiif")

    if debug:
        logger.debug(f"Starting traversal of IIIF collection: {url}")

    try:
        with IIIFClient() as client:
            manifests, collections = client.get_manifests_and_collections_ids(url, max_manifests)
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        sys.exit(1)

    if debug:
        logger.debug(
            f"Traversal completed. Found {len(manifests)} unique manifests and {len(collections)} collections."
        )

    # Handle downloading of manifest JSONs if enabled
    if download_manifests:
        if debug:
            logger.debug(f"Downloading JSON contents for {len(manifests)} manifests.")
        # Ensure the output directory exists
        os.makedirs(json_output_dir, exist_ok=True)
        for idx, manifest_url in enumerate(manifests, start=1):
            try:
                manifest_data = client.fetch_json(manifest_url)
                # Extract manifest ID for filename
                manifest_id = (
                    manifest_data.get("id")
                    or manifest_data.get("@id")
                    or f"manifest_{idx}"
                )
                sanitized_id = sanitize_filename(manifest_id)
                filename = f"{sanitized_id}.json"
                filepath = os.path.join(json_output_dir, filename)
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(manifest_data, f, indent=2)
                if debug:
                    logger.debug(f"Saved manifest {idx}/{len(manifests)} to {filepath}")
            except Exception as e:
                logger.error(f"Failed to download or save manifest {manifest_url}: {e}")
        if debug:
            logger.debug(
                f"All manifests have been processed and saved to {json_output_dir}"
            )

    # Prepare output based on format
    if format.lower() == "json":
        result = {
            "manifests": manifests,
            "collections": collections,  # Include collections if needed
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
            # Print JSON to stdout
            print(json_data)

    elif format.lower() == "jsonl":
        if output:
            try:
                with open(output, "w", encoding="utf-8") as f:
                    for manifest in manifests:
                        json_line = json.dumps({"manifest": manifest})
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
            # Print JSON Lines to stdout
            for manifest in manifests:
                print(json.dumps({"manifest": manifest}))
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

            for idx, manifest in enumerate(manifests, start=1):
                manifest_table.add_row(str(idx), manifest)
            console.print(manifest_table)

        if collections:
            collection_table = Table(title="Collections")
            collection_table.add_column(
                "Index", justify="right", style="cyan", no_wrap=True
            )
            collection_table.add_column("Collection URL", style="green")

            for idx, collection in enumerate(collections, start=1):
                collection_table.add_row(str(idx), collection)
            console.print(collection_table)

        if output:
            # Save tables as plain text to the specified file
            try:
                with open(output, "w", encoding="utf-8") as f:
                    if manifests:
                        f.write("Manifests\n")
                        f.write("-" * 40 + "\n")
                        for idx, manifest in enumerate(manifests, start=1):
                            f.write(f"{idx}. {manifest}\n")
                    if collections:
                        f.write("\nCollections\n")
                        f.write("-" * 40 + "\n")
                        for idx, collection in enumerate(collections, start=1):
                            f.write(f"{idx}. {collection}\n")
                if debug:
                    logger.debug(f"Results saved to {output}")
            except IOError as e:
                logger.error(f"Failed to write to file {output}: {e}")
                sys.exit(1)

    else:
        logger.error(f"Unsupported format: {format}")
        sys.exit(1)


if __name__ == "__main__":
    main()
