"""CLI entry point for Paper-Ladder."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Annotated

import typer

from paper_ladder.aggregator import Aggregator, search
from paper_ladder.config import get_config, load_config
from paper_ladder.extractors import get_extractor
from paper_ladder.models import Paper
from paper_ladder.utils import truncate_text

app = typer.Typer(
    name="paper-ladder",
    help="Academic paper search and content extraction tool.",
    no_args_is_help=True,
)


def format_paper(paper: Paper, verbose: bool = False) -> str:
    """Format a paper for display.

    Args:
        paper: Paper to format.
        verbose: Include more details.

    Returns:
        Formatted string.
    """
    lines = []

    # Title
    lines.append(f"📄 {paper.title}")

    # Authors
    if paper.authors:
        authors_str = ", ".join(paper.authors[:5])
        if len(paper.authors) > 5:
            authors_str += f" et al. ({len(paper.authors)} authors)"
        lines.append(f"   Authors: {authors_str}")

    # Year and Journal
    meta = []
    if paper.year:
        meta.append(str(paper.year))
    if paper.journal:
        meta.append(paper.journal)
    if meta:
        lines.append(f"   {' | '.join(meta)}")

    # DOI
    if paper.doi:
        lines.append(f"   DOI: {paper.doi}")

    # URLs
    if paper.url:
        lines.append(f"   URL: {paper.url}")
    if paper.pdf_url:
        lines.append(f"   PDF: {paper.pdf_url}")

    # Source
    lines.append(f"   Source: {paper.source}")

    # Abstract (verbose mode)
    if verbose and paper.abstract:
        abstract = truncate_text(paper.abstract, 300)
        lines.append(f"   Abstract: {abstract}")

    # Citations
    if paper.citations_count:
        lines.append(f"   Citations: {paper.citations_count}")

    return "\n".join(lines)


@app.command(name="search")
def search_cmd(
    query: Annotated[str, typer.Argument(help="Search query")],
    sources: Annotated[
        str | None,
        typer.Option(
            "--sources", "-s",
            help="Comma-separated list of sources"
        ),
    ] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results per source")] = 10,
    config_file: Annotated[
        Path | None,
        typer.Option("--config", "-c", help="Path to config file")
    ] = None,
    output_json: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Show more details")] = False,
) -> None:
    """Search for academic papers."""
    # Load config
    if config_file:
        load_config(config_file)

    # Parse sources
    source_list = None
    if sources:
        source_list = [s.strip() for s in sources.split(",")]

    async def _search() -> None:
        papers = await search(query, sources=source_list, limit=limit)

        if output_json:
            data = [p.model_dump() for p in papers]
            typer.echo(json.dumps(data, indent=2, default=str))
        else:
            typer.echo(f"\nFound {len(papers)} papers for: {query}\n")
            for i, paper in enumerate(papers, 1):
                typer.echo(f"{i}. {format_paper(paper, verbose)}\n")

    asyncio.run(_search())


@app.command()
def info(
    identifier: Annotated[str, typer.Argument(help="DOI or paper identifier")],
    sources: Annotated[
        str | None,
        typer.Option("--sources", "-s", help="Comma-separated list of sources"),
    ] = None,
    config_file: Annotated[
        Path | None,
        typer.Option("--config", "-c", help="Path to config file")
    ] = None,
    output_json: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    merge: Annotated[
        bool, typer.Option("--merge", "-m", help="Merge data from all sources")
    ] = False,
) -> None:
    """Get paper information by DOI or identifier."""
    # Load config
    if config_file:
        load_config(config_file)

    # Parse sources
    source_list = None
    if sources:
        source_list = [s.strip() for s in sources.split(",")]

    async def _info() -> None:
        async with Aggregator(sources=source_list) as agg:
            if merge:
                paper = await agg.get_paper_from_all(identifier, sources=source_list)
            else:
                paper = await agg.get_paper(identifier, sources=source_list)

        if not paper:
            typer.echo(f"Paper not found: {identifier}", err=True)
            raise typer.Exit(1)

        if output_json:
            typer.echo(json.dumps(paper.model_dump(), indent=2, default=str))
        else:
            typer.echo(format_paper(paper, verbose=True))

    asyncio.run(_info())


@app.command()
def extract(
    source: Annotated[str, typer.Argument(help="URL or file path to extract from")],
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Output file path")
    ] = None,
    config_file: Annotated[
        Path | None,
        typer.Option("--config", "-c", help="Path to config file")
    ] = None,
    output_json: Annotated[bool, typer.Option("--json", help="Output metadata as JSON")] = False,
) -> None:
    """Extract content from a paper URL or file."""
    # Load config
    if config_file:
        load_config(config_file)

    async def _extract() -> None:
        try:
            extractor = get_extractor(source)
        except ValueError as e:
            typer.echo(f"Error: {e}", err=True)
            raise typer.Exit(1) from e

        typer.echo(f"Extracting content using {extractor.name} extractor...")

        try:
            content = await extractor.extract(source)
        except Exception as e:
            typer.echo(f"Extraction failed: {e}", err=True)
            raise typer.Exit(1) from e

        if output_json:
            data = {
                "markdown_length": len(content.markdown),
                "figures_count": len(content.figures),
                "tables_count": len(content.tables),
                "metadata": content.metadata,
                "source_type": content.source_type,
            }
            typer.echo(json.dumps(data, indent=2, default=str))
        elif output:
            output.write_text(content.markdown)
            typer.echo(f"Content saved to: {output}")
            typer.echo(f"  - Markdown: {len(content.markdown)} characters")
            typer.echo(f"  - Figures: {len(content.figures)}")
            typer.echo(f"  - Tables: {len(content.tables)}")
        else:
            typer.echo(content.markdown)

    asyncio.run(_extract())


@app.command(name="config")
def config_show(
    config_file: Annotated[
        Path | None,
        typer.Option("--config", "-c", help="Path to config file")
    ] = None,
) -> None:
    """Show current configuration."""
    if config_file:
        load_config(config_file)

    cfg = get_config()

    typer.echo("Current configuration:")
    typer.echo(f"  Default sources: {', '.join(cfg.default_sources)}")
    typer.echo(f"  Request timeout: {cfg.request_timeout}s")
    typer.echo(f"  Max retries: {cfg.max_retries}")
    typer.echo(f"  Output directory: {cfg.output_dir}")
    typer.echo(f"  Elsevier API key: {'configured' if cfg.elsevier_api_key else 'not set'}")
    typer.echo(f"  SerpAPI key: {'configured' if cfg.serpapi_api_key else 'not set'}")
    if cfg.proxy:
        typer.echo(f"  Proxy HTTP: {cfg.proxy.http or 'not set'}")
        typer.echo(f"  Proxy HTTPS: {cfg.proxy.https or 'not set'}")


@app.command()
def sources() -> None:
    """List available data sources."""
    from paper_ladder.clients import CLIENTS

    typer.echo("Available data sources:\n")

    source_info = {
        "openalex": ("OpenAlex", "Free, 100k requests/day", "No"),
        "semantic_scholar": ("Semantic Scholar", "Free, 100 req/5min", "No"),
        "elsevier": ("Elsevier (Scopus)", "API key required", "Yes"),
        "google_scholar": ("Google Scholar (SerpAPI)", "~$0.015/call", "Yes"),
    }

    for name in CLIENTS:
        display_name, rate_limit, needs_key = source_info.get(
            name, (name, "Unknown", "Unknown")
        )
        typer.echo(f"  {name}")
        typer.echo(f"    Name: {display_name}")
        typer.echo(f"    Rate limit: {rate_limit}")
        typer.echo(f"    API key required: {needs_key}")
        typer.echo()


if __name__ == "__main__":
    app()
