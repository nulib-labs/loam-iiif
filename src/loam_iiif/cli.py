import json
import logging
import sys
from typing import List

import click
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

from .iiif import IIIFClient

# Initialize Rich Console for logging (outputs to stderr)
console = Console(stderr=True)


@click.command()
@click.argument("url")
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    help="Output file to save the results (JSON or plain text format).",
)
@click.option(
    "--format",
    "-f",
    type=click.Choice(["json", "table"], case_sensitive=False),
    default="json",
    help="Output format: 'json' for JSON output or 'table' for a formatted table.",
)
@click.option(
    "--debug",
    is_flag=True,
    help="Enable debug mode with detailed logs.",
)
def main(url: str, output: str, format: str, debug: bool):
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
            manifests, collections = client.get_manifests_and_collections_ids(url)
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        sys.exit(1)

    if debug:
        logger.debug(
            f"Traversal completed. Found {len(manifests)} unique manifests and {len(collections)} collections."
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
