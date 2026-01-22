# Paper-Ladder

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Python library for searching academic paper metadata from multiple APIs and extracting content to Markdown format.

> **Note**: PDF extraction requires [MinerU](https://github.com/opendatalab/MinerU) with PyTorch. For best performance, use a GPU-enabled machine.

## Features

- **Multi-source Search**: Query multiple academic APIs concurrently with automatic deduplication
- **Content Extraction**: Convert PDF and HTML papers to structured Markdown
- **Unified Data Models**: Consistent Paper, Author, and Institution models across all sources
- **Async First**: Built on httpx for high-performance async HTTP requests
- **Rate Limiting**: Automatic per-source rate limiting to respect API quotas

## Supported Sources

| Source | API Key | Rate Limit | Papers | Authors | Institutions | Citations |
|--------|---------|------------|--------|---------|--------------|-----------|
| **OpenAlex** | Not required | 100k/day | Yes | Yes | Yes | Yes |
| **Semantic Scholar** | Optional | 100/5min (1/sec with key) | Yes | Yes | - | Yes |
| **Elsevier (Scopus)** | Required | Varies | Yes | Paid | Paid | Yes |
| **Google Scholar** | Required (SerpAPI) | ~$0.015/call | Yes | Paid | - | Yes |

## Installation

```bash
# Using uv (recommended)
uv sync

# Using pip
pip install -e .
```

## Quick Start

### Configuration

Create `config.yaml` from the example:

```bash
cp config.example.yaml config.yaml
```

Edit `config.yaml` with your API keys:

```yaml
# Optional - for Elsevier/Scopus access
elsevier_api_key: "your-key"

# Optional - for Google Scholar via SerpAPI
serpapi_api_key: "your-key"

# Optional - for higher Semantic Scholar rate limits
semantic_scholar_api_key: "your-key"

# Default sources (free, no API key needed)
default_sources:
  - openalex
```

### CLI Usage

```bash
# Search papers across multiple sources
paper-ladder search "transformer attention" --sources openalex,elsevier

# Search with filters
paper-ladder search "deep learning" --sources openalex --limit 20

# Get paper info by DOI
paper-ladder info 10.1038/nature14539

# Extract content from PDF URL
paper-ladder extract https://arxiv.org/pdf/2301.00001.pdf -o output.md

# List available sources
paper-ladder sources
```

### Python API

```python
import asyncio
from paper_ladder import search, get_paper
from paper_ladder.clients import OpenAlexClient

async def main():
    # Multi-source search
    result = await search(
        "transformer attention mechanism",
        sources=["openalex", "elsevier"],
        limit=10
    )
    for paper in result.papers:
        print(f"{paper.title} ({paper.year}) - {paper.citations_count} citations")

    # Get paper by DOI
    paper = await get_paper("10.1038/nature14539")
    print(f"Title: {paper.title}")
    print(f"Authors: {paper.authors}")

asyncio.run(main())
```

### Using Individual Clients

```python
import asyncio
from paper_ladder.clients import OpenAlexClient

async def main():
    async with OpenAlexClient() as client:
        # Search papers
        papers = await client.search("deep learning", limit=5)

        # Get paper by DOI
        paper = await client.get_paper("10.1038/nature14539")

        # Get citations
        citations = await client.get_paper_citations(paper.raw_data["id"], limit=10)

        # Search authors
        authors = await client.search_authors("Yann LeCun", limit=3)

        # Get author's papers
        author_papers = await client.get_author_papers(authors[0].source_id, limit=5)

        # Search institutions
        institutions = await client.search_institutions("MIT", limit=3)

asyncio.run(main())
```

## API Reference

### OpenAlex (Free, No API Key)

The most comprehensive free academic API with excellent coverage.

```python
from paper_ladder.clients import OpenAlexClient

async with OpenAlexClient() as client:
    # Paper search with filters
    papers = await client.search(
        "machine learning",
        limit=10,
        year=2023,              # Filter by year
        open_access=True,       # Only open access
        sort="cited_by_count"   # Sort by citations
    )

    # Get paper metadata
    paper = await client.get_paper("10.1038/nature14539")

    # Citation network
    citations = await client.get_paper_citations(paper_id, limit=100)
    references = await client.get_paper_references(paper_id, limit=100)

    # Author discovery
    authors = await client.search_authors("Geoffrey Hinton")
    author = await client.get_author("A123456789")  # OpenAlex ID
    papers = await client.get_author_papers(author_id, limit=50)

    # Institution lookup
    institutions = await client.search_institutions("Stanford", country="US")
    inst = await client.get_institution("I123456789")  # OpenAlex ID
```

### Semantic Scholar (Free, Optional API Key)

Strong coverage with recommendations and batch operations.

```python
from paper_ladder.clients import SemanticScholarClient

async with SemanticScholarClient() as client:
    # Paper search
    papers = await client.search("neural networks", limit=10)

    # Get by various identifiers
    paper = await client.get_paper("DOI:10.1038/nature14539")
    paper = await client.get_paper("ARXIV:2301.00001")
    paper = await client.get_paper("CorpusId:12345")

    # Citations and references
    citations = await client.get_paper_citations(paper_id)
    references = await client.get_paper_references(paper_id)

    # Batch operations (efficient for multiple lookups)
    papers = await client.get_papers_batch(["DOI:...", "DOI:..."])
    authors = await client.get_authors_batch(["123", "456"])

    # Recommendations
    recs = await client.get_recommendations(paper_id, limit=10)
    recs = await client.get_recommendations_from_list(
        positive_paper_ids=["paper1", "paper2"],
        negative_paper_ids=["paper3"],
        limit=10
    )
```

### Elsevier/Scopus (API Key Required)

Premium academic database with extensive metadata.

```python
from paper_ladder.clients import ElsevierClient

async with ElsevierClient() as client:
    # Paper search
    papers = await client.search(
        "quantum computing",
        limit=10,
        year=2023,
        subject_area="PHYS"
    )

    # Get by DOI
    paper = await client.get_paper("10.1016/j.example.2023.001")

    # Citations
    citations = await client.get_paper_citations(scopus_id)

    # Full text (requires entitlements)
    text = await client.get_article_fulltext(doi)

    # Author search (requires institutional access)
    authors = await client.search_authors("Smith", affiliation="MIT")

    # Institution search (requires institutional access)
    institutions = await client.search_institutions("Harvard")
```

### Google Scholar via SerpAPI (API Key Required, Paid)

Broadest coverage including non-indexed sources.

```python
from paper_ladder.clients import GoogleScholarClient

async with GoogleScholarClient() as client:
    # Paper search
    papers = await client.search(
        "attention is all you need",
        limit=10,
        year_low=2017,
        year_high=2020
    )

    # Get citing papers
    citations = await client.get_paper_citations(cites_id, limit=20)

    # Get citation formats (BibTeX, APA, MLA, etc.)
    cite_info = await client.get_cite_info(result_id)

    # Author profiles (may require higher plan)
    author = await client.get_author("dkZ6M2sAAAAJ")
    papers = await client.get_author_papers(author_id, sort_by="cited")
```

## Data Models

### Paper

```python
class Paper:
    title: str                    # Paper title
    authors: list[str]            # Author names
    abstract: str | None          # Abstract text
    doi: str | None               # DOI identifier
    year: int | None              # Publication year
    journal: str | None           # Journal/venue name
    url: str | None               # Landing page URL
    pdf_url: str | None           # Direct PDF link
    source: str                   # Data source name
    citations_count: int | None   # Citation count
    references_count: int | None  # Reference count
    open_access: bool | None      # Open access status
    keywords: list[str]           # Subject keywords
    raw_data: dict                # Original API response
```

### Author

```python
class Author:
    name: str                     # Display name
    source_id: str | None         # Source-specific ID
    affiliations: list[str]       # Institution affiliations
    orcid: str | None             # ORCID identifier
    paper_count: int | None       # Publication count
    citation_count: int | None    # Total citations
    h_index: int | None           # h-index
```

### Institution

```python
class Institution:
    name: str                     # Institution name
    source_id: str | None         # Source-specific ID
    country: str | None           # Country code
    type: str | None              # Type (education, company, etc.)
    paper_count: int | None       # Publication count
```

## Content Extraction

Extract paper content from PDFs or HTML to Markdown:

```python
from paper_ladder.extractors import PDFExtractor, HTMLExtractor

# PDF extraction (uses MinerU)
extractor = PDFExtractor()
content = await extractor.extract("https://arxiv.org/pdf/2301.00001.pdf")
print(content.markdown)
print(content.figures)  # Extracted figure paths
print(content.tables)   # Extracted tables

# HTML extraction
extractor = HTMLExtractor()
content = await extractor.extract("https://example.com/paper.html")
print(content.markdown)
print(content.metadata)
```

## Documentation

- [Architecture & Data Flow](docs/ARCHITECTURE.md) - System design and data flow diagrams
- [Development Guide](CLAUDE.md) - API references and development notes

## Development

```bash
# Install with dev dependencies
uv sync --all-extras

# Run tests
uv run pytest

# Run specific test file
uv run pytest tests/test_clients/test_openalex.py -v

# Lint
uv run ruff check .

# Format
uv run ruff format .
```

## License

MIT
