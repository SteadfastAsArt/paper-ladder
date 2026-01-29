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

| Source | API Key | Rate Limit | Papers | Authors | Institutions | Citations | Unique Features |
|--------|---------|------------|--------|---------|--------------|-----------|-----------------|
| **OpenAlex** | Optional | 100k/day | ✓ | ✓ | ✓ | ✓ | Free, comprehensive |
| **Semantic Scholar** | Optional | 100/5min | ✓ | ✓ | - | ✓ | Recommendations, arXiv |
| **Crossref** | Not required | ~50/sec | ✓ | - | - | - | Journals, Funders, 150M+ DOIs |
| **PubMed** | Optional | 3-10/sec | ✓ | ✓ | - | ✓ | Biomedical, MeSH terms |
| **Web of Science** | Required | ~2/sec | ✓ | ✓ | - | ✓ | Citation analysis, impact metrics |
| **Elsevier (Scopus)** | Required | ~2/sec | ✓ | ✓ | ✓ | ✓ | Full-text access |
| **Google Scholar** | Required (SerpAPI) | $0.015/call | ✓ | ✓ | - | ✓ | Broadest coverage |
| **arXiv** | Not required | 1/3 sec | ✓ | - | - | - | Physics/Math/CS preprints, direct PDF |
| **bioRxiv** | Not required | ~10/sec | ✓ | - | - | - | Biology preprints, date-based search |
| **medRxiv** | Not required | ~10/sec | ✓ | - | - | - | Health sciences preprints |
| **GS Scraper** | Not required | 1/5 sec | ✓ | ✓ | - | - | Free Google Scholar, may trigger CAPTCHA |

### Comparison

| Metric | OpenAlex | Semantic Scholar | Crossref | PubMed | Web of Science | Elsevier | Google Scholar | arXiv | bioRxiv | medRxiv | GS Scraper |
|--------|----------|------------------|----------|--------|----------------|----------|----------------|-------|---------|---------|------------|
| **Max per request** | 200 | 100 | 1,000 | 10,000 | 100 | 25 | 20 | 2,000 | 100 | 100 | 10 |
| **Max offset** | 10,000 | 1,000 | cursor | 10,000 | 100,000 | 5,000 | ~100 | ∞ | cursor | cursor | ~100 |
| **Free** | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ | ✓ | ✓ | ✓ | ✓ |

**Citation counts for the same paper** (Deep Learning, LeCun 2015):
- Semantic Scholar: ~162,000 (includes preprints)
- OpenAlex: ~77,000
- Crossref: ~68,500

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
# API Keys
openalex_api_key: "your-key"           # Recommended for 100k credits/day (free at openalex.org)
semantic_scholar_api_key: "your-key"   # Optional, for higher rate limits (1 req/s)
pubmed_api_key: "your-key"             # Optional, for higher rate limits (10 req/s vs 3 req/s)
wos_api_key: "your-key"                # Required for Web of Science (institutional subscription)
elsevier_api_key: "your-key"           # Required for Elsevier/Scopus access
serpapi_api_key: "your-key"            # Required for Google Scholar via SerpAPI

# Default sources (free, no API key needed)
default_sources:
  - openalex
  - crossref
  - semantic_scholar
  - pubmed
  - arxiv              # Preprint server
  - biorxiv            # Biology preprints
  - medrxiv            # Health sciences preprints

# Rate limits (requests per second)
rate_limits:
  openalex: 10
  semantic_scholar: 10  # Use 0.3 without API key
  crossref: 50
  pubmed: 10            # 3 without API key, 10 with API key
  wos: 2
  elsevier: 5
  google_scholar: 1
  arxiv: 0.33           # 1 request per 3 seconds
  biorxiv: 10
  medrxiv: 10
  google_scholar_scraper: 0.2  # 1 request per 5 seconds (CAPTCHA risk)
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

### Crossref (Free, No API Key)

DOI registration agency with 150M+ metadata records. Unique journal and funder search capabilities.

```python
from paper_ladder.clients import CrossrefClient

async with CrossrefClient() as client:
    # Paper search with filters
    papers = await client.search(
        "CRISPR gene editing",
        limit=100,
        year=2024,
        has_abstract=True,
        type="journal-article",
        sort="is-referenced-by-count"
    )

    # Get by DOI
    paper = await client.get_paper("10.1038/nature14539")

    # Get references (not citations - Crossref doesn't support citation lookup)
    refs = await client.get_paper_references(doi, limit=50)

    # Journal metadata (unique to Crossref)
    journal = await client.get_journal("0028-0836")  # Nature ISSN
    print(f"{journal['title']}: {journal['counts']['total-dois']} articles")

    # Search within a journal
    papers = await client.get_journal_works("0028-0836", query="AI", limit=20)

    # Funder metadata (unique to Crossref)
    funder = await client.get_funder("501100001809")  # NSFC
    print(f"{funder['name']}: {funder['work-count']} funded papers")

    # Search funded papers
    papers = await client.get_funder_works("501100001809", query="deep learning")
```

### PubMed (Free, Optional API Key)

Premier biomedical literature database with MeSH indexing.

```python
from paper_ladder.clients import PubMedClient

async with PubMedClient() as client:
    # Paper search with filters
    papers = await client.search(
        "CRISPR gene therapy",
        limit=20,
        year=2024,                    # Filter by year
        sort="relevance"              # or "pub_date"
    )

    # Get by PMID or DOI
    paper = await client.get_paper("26017442")  # PMID
    paper = await client.get_paper("10.1038/nature14539")  # DOI

    # Citations and references
    citations = await client.get_paper_citations(pmid, limit=50)
    references = await client.get_paper_references(pmid, limit=50)

    # Related papers (using PubMed's similarity algorithm)
    related = await client.get_related_papers(pmid, limit=20)

    # Author search
    authors = await client.search_authors("Doudna JA")
    papers = await client.get_author_papers("Doudna JA", limit=20)
```

**Note**: API key is optional but recommended for higher rate limits (10 req/s vs 3 req/s). Get from NCBI account settings.

### Web of Science (API Key Required)

Premier citation index with comprehensive impact metrics.

```python
from paper_ladder.clients import WebOfScienceClient

async with WebOfScienceClient() as client:
    # Paper search with filters
    papers = await client.search(
        "machine learning healthcare",
        limit=20,
        year=2024,                    # Filter by year
        document_type="Article"       # Article, Review, etc.
    )

    # Get by DOI or WoS UID
    paper = await client.get_paper("10.1038/nature14539")
    paper = await client.get_paper("WOS:000123456789")

    # Citations and references
    citations = await client.get_paper_citations(uid, limit=50)
    references = await client.get_paper_references(uid, limit=50)

    # Related papers
    related = await client.get_related_papers(uid, limit=20)

    # Author search
    authors = await client.search_authors("Hinton G")
    papers = await client.get_author_papers("Hinton G", limit=20)
```

**Note**: Requires institutional subscription. Get API key from developer.clarivate.com.

### arXiv (Free, No API Key)

Open access preprints in physics, mathematics, computer science, and more.

```python
from paper_ladder.clients import ArxivClient

async with ArxivClient() as client:
    # Search papers
    papers = await client.search("transformer attention", limit=20)

    # Search by category
    papers = await client.search_by_category("cs.AI", query="attention", limit=10)

    # Search by author
    papers = await client.search_by_author("Hinton", limit=10)

    # Get paper by arXiv ID
    paper = await client.get_paper("2301.07041")

    # Cursor-based pagination for large results
    async for paper in client.search_with_cursor("machine learning", max_results=5000):
        print(paper.title)
```

**Note**: Rate limit is 1 request per 3 seconds. Direct PDF access available.

### bioRxiv / medRxiv (Free, No API Key)

Open access preprints in biology and health sciences.

```python
from paper_ladder.clients import BiorxivClient, MedrxivClient

async with BiorxivClient() as client:
    # Search papers (client-side filtering)
    papers = await client.search("CRISPR", limit=20, days=30)

    # Search by date range
    papers = await client.search_by_date("2024-01-01", "2024-01-31", limit=100)

    # Get recent papers
    papers = await client.get_recent_papers(days=7, limit=50)

    # Search by category
    papers = await client.search_by_category("genomics", limit=20)

    # Get paper by DOI
    paper = await client.get_paper("10.1101/2024.01.01.123456")

# medRxiv has the same API
async with MedrxivClient() as client:
    papers = await client.search("COVID-19", limit=20)
```

**Note**: API uses date-based retrieval; full-text search is done client-side.

### Google Scholar Scraper (Free, No API Key)

Free alternative to SerpAPI for Google Scholar searches.

```python
from paper_ladder.clients import GoogleScholarScraperClient

async with GoogleScholarScraperClient() as client:
    # Search papers
    papers = await client.search("machine learning", limit=20)

    # Search by author
    papers = await client.search_author("Geoffrey Hinton", limit=10)

    # Get author profile by Google Scholar ID
    author = await client.get_author_profile("dkZ6M2sAAAAJ")

    # Search with year filter
    papers = await client.search("deep learning", limit=10, year_low=2020, year_high=2024)
```

**Warning**: Web scraping may violate Google's Terms of Service. Use responsibly for educational and research purposes. May trigger CAPTCHA with heavy use. Consider SerpAPI for production.

**Common Funder IDs**:
| Funder | ID | Papers |
|--------|-----|--------|
| NSFC (China) | 501100001809 | 3.1M |
| NIH (US) | 100000002 | 443K |
| NSF (US) | 100000001 | 428K |
| JSPS (Japan) | 501100001691 | 246K |
| DOE (US) | 100000015 | 139K |

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

## PDF Download

Download PDFs from various academic sources with automatic URL resolution and open access fallback.

```python
from paper_ladder.downloader import PDFDownloader, download_pdf, download_papers

# Simple download
path = await download_pdf("https://arxiv.org/pdf/2301.07041.pdf", output_dir="papers/")

# Download with custom filename
path = await download_pdf(
    "https://arxiv.org/abs/2301.07041",
    output_dir="papers/",
    filename="attention_paper"
)

# Create downloader with Unpaywall for open access lookup
downloader = PDFDownloader(
    output_dir="papers/",
    unpaywall_email="your@email.com"  # Register at unpaywall.org
)

# Download from a Paper object
path = await downloader.download_paper(paper)

# Download by DOI (automatically tries Unpaywall for paywalled papers)
path = await downloader.download_from_doi("10.1038/nature14539")

# Download from specific sources
path = await downloader.download_from_arxiv("2301.07041")
path = await downloader.download_from_biorxiv_medrxiv("10.1101/2024.01.01.123456")
path = await downloader.download_from_pmc("PMC1234567")

# Download directly via Unpaywall
path = await downloader.download_from_unpaywall("10.1038/nature14539")

# Batch download multiple papers
results = await download_papers(
    papers,
    output_dir="papers/",
    unpaywall_email="your@email.com"
)
for title, path in results.items():
    print(f"{title}: {path or 'Failed'}")
```

### Supported Sources

- **arXiv** - ID or URL (`arxiv.org/abs/...` or `arxiv.org/pdf/...`)
- **bioRxiv / medRxiv** - DOI-based downloads
- **PubMed Central** - PMC ID downloads
- **Unpaywall** - Finds legal open access versions of paywalled papers
- **DOI resolution** - Follows DOI redirects to find PDFs

### Unpaywall Integration

[Unpaywall](https://unpaywall.org) is a free service that finds legal open access versions of papers. To use it:

1. Register your email at https://unpaywall.org/products/api
2. Pass your email to the downloader:

```python
downloader = PDFDownloader(output_dir="papers/", unpaywall_email="your@email.com")

# Now download_from_doi automatically tries Unpaywall for paywalled papers
path = await downloader.download_from_doi("10.1038/nature14539")
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
