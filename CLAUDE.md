# Paper-Ladder Development Guide

## Overview
Python library for searching academic paper metadata from multiple APIs and extracting content to Markdown.

**Tech Stack**: Python 3.10+, uv, httpx (async), typer, pydantic, MinerU

**Commands**: `uv sync` | `uv run pytest` | `uv run paper-ladder --help`

## Project Structure
```
src/paper_ladder/
├── models.py      # Paper, Author, Institution, ExtractedContent, SortBy, PaginationInfo
├── config.py      # Configuration loader
├── clients/       # API client adapters (11 sources)
├── extractors/    # PDF, HTML, Structured extractors
├── downloader.py  # PDF download with Unpaywall
├── aggregator.py  # Multi-source aggregation
└── cli.py
```

## Data Models

| Model | Key Fields |
|-------|------------|
| **Paper** | title, authors, abstract, doi, year, journal, url, pdf_url, source, citations_count, references_count, open_access, keywords, raw_data |
| **Author** | name, source_id, source, affiliations, orcid, url, paper_count, citation_count, h_index |
| **Institution** | name, source_id, source, country, type, url, paper_count, citation_count |
| **ExtractedContent** | markdown, metadata, figures, tables, source_url, source_type |
| **PaperStructure** | abstract, introduction, methods, results, discussion, conclusion, sections, all_blocks |
| **BookStructure** | chapters (ChapterNode tree), get_chapter(pattern), get_all_chapters_flat() |
| **SortBy** | RELEVANCE, CITATIONS, DATE, DATE_ASC |

## API Clients

### Quick Reference

| Client | Free | Key Required | Best For |
|--------|:----:|:------------:|----------|
| OpenAlex | ✓ | No | Comprehensive, institutions/authors |
| Semantic Scholar | ✓ | Optional | AI/CS, recommendations, arXiv |
| Crossref | ✓ | No | DOI authority, journals, funders |
| Elsevier/Scopus | ✗ | Yes | Commercial, full-text |
| Google Scholar | ✗ | Yes (SerpAPI) | Broadest coverage |
| PubMed | ✓ | Optional | Biomedical, MeSH |
| Web of Science | ✗ | Yes | Citation analysis |
| arXiv | ✓ | No | Preprints (physics, CS, math) |
| bioRxiv | ✓ | No | Biology preprints |
| medRxiv | ✓ | No | Health sciences preprints |
| GS Scraper | ✓ | No | Free GS (CAPTCHA risk) |

### Critical Pagination Limits

| Client | Per Request | Max Offset | Cursor Support |
|--------|-------------|------------|----------------|
| OpenAlex | 200 | 10,000 | ✓ (unlimited) |
| **Semantic Scholar** | 100 | **1,000** | Bulk only |
| Crossref | 1,000 | No limit | ✓ (5min expiry) |
| Elsevier | 200 | 5,000 | ✓ (20k/week) |
| PubMed | 10,000 | 10,000 | ✗ |
| arXiv | 2,000 | No limit | ✗ |

**⚠️ Semantic Scholar**: `offset + limit ≤ 1,000` (reduced Oct 2024 from 10,000)

### Common Client Methods
All clients implement: `search(query, limit, offset, **filters)`, `get_paper(identifier)`

Additional methods vary by client:
- `get_paper_citations()` / `get_paper_references()` - OpenAlex, S2, Elsevier, PubMed, WoS
- `search_authors()` / `get_author()` - OpenAlex, S2, Elsevier, GS, PubMed, WoS
- `search_institutions()` / `get_institution()` - OpenAlex, Elsevier only
- `search_with_cursor()` - OpenAlex, Crossref, Elsevier (bypasses offset limits)
- `search_all(max_results)` - All clients (auto-pagination)
- `get_recommendations()` - Semantic Scholar only

### Client-Specific Features

**Crossref**: `get_journal(issn)`, `get_journal_works()`, `get_funder(id)`, `get_funder_works()`
**Semantic Scholar**: `get_papers_batch(ids)`, `get_recommendations(paper_id)`
**bioRxiv/medRxiv**: `get_recent_papers(days)`, `search_by_category()`

## Usage

```python
import asyncio
from paper_ladder.clients import OpenAlexClient
from paper_ladder.models import SortBy

async def main():
    async with OpenAlexClient() as client:
        # Basic search with sort
        papers = await client.search("transformer", limit=10, sort=SortBy.CITATIONS)

        # Get paper by DOI
        paper = await client.get_paper("10.1038/nature14539")

        # Cursor pagination (>10k results)
        async for paper in client.search_with_cursor("ML", max_results=50000):
            print(paper.title)

asyncio.run(main())
```

```python
# Multi-source aggregation
from paper_ladder.aggregator import Aggregator

async with Aggregator(sources=["openalex", "crossref"]) as agg:
    result = await agg.search("quantum computing", limit=10)
```

## PDF Download

```python
from paper_ladder.downloader import PDFDownloader

downloader = PDFDownloader(output_dir="papers/", unpaywall_email="you@email.com")
path = await downloader.download_from_doi("10.1038/nature14539")  # Tries Unpaywall
path = await downloader.download_paper(paper)  # From Paper object
```

Supports: arXiv, bioRxiv/medRxiv, PMC, Unpaywall (OA lookup), DOI resolution

## PDF Extraction

```python
from paper_ladder.extractors import PDFExtractor, StructuredExtractor

# Basic markdown
extractor = PDFExtractor()
content = await extractor.extract("paper.pdf")
print(content.markdown)

# Structured (for LLM processing)
extractor = StructuredExtractor()
paper = await extractor.extract("paper.pdf", document_type="paper")  # or "book"
print(paper.introduction, paper.methods, paper.results)
```

## Configuration

`config.yaml`:
```yaml
elsevier_api_key: "key"      # Required for Scopus
serpapi_api_key: "key"       # Required for Google Scholar
semantic_scholar_api_key: "" # Optional (higher rate limits)
pubmed_api_key: ""           # Optional (10 vs 3 req/s)
wos_api_key: "key"           # Required for Web of Science

default_sources: [openalex, semantic_scholar, crossref]

rate_limits:
  openalex: 10
  semantic_scholar: 10  # 0.3 without key
  crossref: 50
  elsevier: 5
  pubmed: 3
```

## Adding a New Client

1. Create `src/paper_ladder/clients/new_client.py`
2. Inherit from `BaseClient`
3. Implement `search()` and `get_paper()`
4. Register in `clients/__init__.py`

## Code Style

```bash
uv run ruff check .   # Lint
uv run ruff format .  # Format
```

Type hints required for public APIs.
