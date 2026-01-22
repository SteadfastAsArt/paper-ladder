# Paper-Ladder Development Guide

## Project Overview

Paper-Ladder is a Python library for searching academic paper metadata from multiple APIs and extracting content to Markdown format.

## Tech Stack

- **Python**: 3.10+
- **Package Manager**: uv
- **HTTP Client**: httpx (async)
- **CLI**: typer
- **Data Validation**: pydantic
- **PDF Extraction**: MinerU (mineru package)

## Quick Start

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest

# Run CLI
uv run paper-ladder --help
```

## Project Structure

- `src/paper_ladder/` - Main package
  - `models.py` - Data models (Paper, Author, Institution, ExtractedContent, SearchResult)
  - `config.py` - Configuration loader
  - `clients/` - API client adapters
  - `extractors/` - Content extractors (PDF, HTML)
  - `aggregator.py` - Multi-source aggregation
  - `cli.py` - CLI entry point
- `tests/` - Test suite

## Data Models

### Paper
Core paper metadata:
- `title`, `authors`, `abstract`, `doi`, `year`, `journal`
- `url`, `pdf_url`, `source`
- `citations_count`, `references_count`, `open_access`, `keywords`
- `raw_data` - Original API response

### Author
Author metadata:
- `name`, `source_id`, `source`
- `affiliations`, `orcid`, `url`
- `paper_count`, `citation_count`, `h_index`
- `raw_data`

### Institution
Institution/affiliation metadata:
- `name`, `source_id`, `source`
- `country`, `type`, `url`
- `paper_count`, `citation_count`
- `raw_data`

### ExtractedContent
Extracted paper content:
- `markdown` - Body text as markdown
- `metadata` - Extracted metadata
- `figures`, `tables` - Lists of extracted elements
- `source_url`, `source_type` ("pdf" or "html")

---

## API Clients Reference

### 1. OpenAlex

- **Documentation**: https://docs.openalex.org/
- **API Overview**: https://docs.openalex.org/how-to-use-the-api/api-overview
- **Rate Limits**: https://docs.openalex.org/how-to-use-the-api/rate-limits-and-authentication
- **Works Entity**: https://docs.openalex.org/api-entities/works
- **Authors Entity**: https://docs.openalex.org/api-entities/authors
- **Institutions Entity**: https://docs.openalex.org/api-entities/institutions
- **Search Guide**: https://docs.openalex.org/how-to-use-the-api/get-lists-of-entities/search-entities

**Key Features**:
- 100,000 requests/day (polite pool with email in User-Agent)
- No API key required
- Entities: Works, Authors, Sources, Institutions, Concepts, Publishers, Funders
- Supports filtering, sorting, grouping
- Abstract stored as inverted index (needs reconstruction)

**Base URL**: `https://api.openalex.org`

**Implemented Methods**:
- `search(query, limit, offset, **filters)` - Search papers with filters (year, open_access, type, institution, author, cited_by_count, sort)
- `get_paper(identifier)` - Get paper by DOI or OpenAlex ID
- `get_paper_citations(paper_id, limit, offset)` - Get citing papers
- `get_paper_references(paper_id, limit, offset)` - Get referenced papers
- `search_authors(query, limit, offset, **filters)` - Search authors (institution, has_orcid)
- `get_author(identifier)` - Get author by OpenAlex ID or ORCID
- `get_author_papers(author_id, limit, offset)` - Get papers by author
- `search_institutions(query, limit, offset, **filters)` - Search institutions (country, type)
- `get_institution(identifier)` - Get institution by OpenAlex ID or ROR

### 2. Semantic Scholar

- **Documentation**: https://api.semanticscholar.org/api-docs/
- **Product Page**: https://www.semanticscholar.org/product/api
- **API Tutorial**: https://www.semanticscholar.org/product/api/tutorial
- **Get API Key**: https://www.semanticscholar.org/product/api#api-key
- **Paper Search**: https://api.semanticscholar.org/api-docs/#tag/Paper-Data/operation/get_graph_paper_relevance_search
- **Author Search**: https://api.semanticscholar.org/api-docs/#tag/Author-Data/operation/get_graph_get_author_search
- **Batch Endpoints**: https://api.semanticscholar.org/api-docs/#tag/Paper-Data/operation/post_graph_get_papers
- **Recommendations**: https://api.semanticscholar.org/api-docs/#tag/Recommendations-API

**Key Features**:
- Unauthenticated: 100 requests per 5 minutes
- Authenticated: 1 request per second (need API key)
- Entities: Papers, Authors, Paper citations/references
- Fields of study classification
- Recommendation API
- Batch paper lookup

**Base URL**: `https://api.semanticscholar.org/graph/v1`

**Header for auth**: `x-api-key: YOUR_KEY`

**Implemented Methods**:
- `search(query, limit, offset, **filters)` - Search papers (year, fields_of_study, open_access)
- `get_paper(identifier)` - Get paper by Semantic Scholar ID, DOI, arXiv ID, or CorpusId
- `get_paper_citations(paper_id, limit, offset)` - Get citing papers
- `get_paper_references(paper_id, limit, offset)` - Get referenced papers
- `search_authors(query, limit, offset)` - Search authors
- `get_author(author_id)` - Get author by Semantic Scholar ID
- `get_author_papers(author_id, limit, offset)` - Get papers by author
- `get_papers_batch(paper_ids)` - Batch lookup of up to 500 papers
- `get_authors_batch(author_ids)` - Batch lookup of up to 1000 authors
- `get_recommendations(paper_id, limit, pool_from)` - Get paper recommendations from seed paper
- `get_recommendations_from_list(positive_ids, negative_ids, limit)` - Get recommendations from paper list

### 3. Elsevier (Scopus / ScienceDirect)

- **Developer Portal**: https://dev.elsevier.com/
- **API Documentation**: https://dev.elsevier.com/documentation/
- **Scopus Search API**: https://dev.elsevier.com/documentation/SCOPUSSearchAPI.wadl
- **Abstract Retrieval**: https://dev.elsevier.com/documentation/AbstractRetrievalAPI.wadl
- **Author Search API**: https://dev.elsevier.com/documentation/AuthorSearchAPI.wadl
- **Author Retrieval API**: https://dev.elsevier.com/documentation/AuthorRetrievalAPI.wadl
- **Affiliation Search API**: https://dev.elsevier.com/documentation/AffiliationSearchAPI.wadl
- **Affiliation Retrieval API**: https://dev.elsevier.com/documentation/AffiliationRetrievalAPI.wadl
- **Citation Overview API**: https://dev.elsevier.com/documentation/AbstractCitationAPI.wadl
- **Getting Started Guide**: https://dev.elsevier.com/guides/Scopus%20API%20Guide_V1_20230907.pdf

**Key Features**:
- API key required (register at dev.elsevier.com)
- Scopus Search: Search abstracts, authors, affiliations
- Abstract Retrieval: Full metadata for single document
- Author/Affiliation lookup
- Citation overview
- ScienceDirect full-text (with appropriate entitlements)

**Base URL**: `https://api.elsevier.com`

**Header for auth**: `X-ELS-APIKey: YOUR_KEY`

**Implemented Methods**:
- `search(query, limit, offset, **filters)` - Search papers (year, subject_area)
- `get_paper(identifier)` - Get paper by DOI or Scopus ID
- `get_paper_citations(scopus_id, limit, offset)` - Get citing papers
- `get_article_fulltext(doi)` - Get full text from ScienceDirect (if available)
- `search_authors(query, limit, offset, **filters)` - Search authors (affiliation, subject_area)
- `get_author(author_id)` - Get author by Scopus author ID
- `get_author_papers(author_id, limit, offset)` - Get papers by author
- `search_institutions(query, limit, offset, **filters)` - Search affiliations (country)
- `get_institution(affiliation_id)` - Get institution by Scopus affiliation ID

### 4. Google Scholar (via SerpAPI)

- **SerpAPI Documentation**: https://serpapi.com/google-scholar-api
- **Organic Results**: https://serpapi.com/google-scholar-organic-results
- **Author Profiles Search**: https://serpapi.com/google-scholar-profiles
- **Author Profile API**: https://serpapi.com/google-scholar-author-api
- **Cite API**: https://serpapi.com/google-scholar-cite-api
- **Author Citations**: https://serpapi.com/google-scholar-author-citation
- **Python Package**: https://github.com/serpapi/google-search-results-python

**Key Features**:
- Paid API (~$0.015 per search)
- Broadest coverage (scrapes Google Scholar)
- Organic results with citations
- Author profiles
- Case law search
- Related articles

**Base URL**: `https://serpapi.com`

**Param for auth**: `api_key=YOUR_KEY`

**Implemented Methods**:
- `search(query, limit, offset, **filters)` - Search papers (year_low, year_high, year)
- `get_paper(identifier)` - Get paper by DOI or title (via search)
- `get_paper_citations(cites_id, limit, offset)` - Get citing papers
- `get_cite_info(result_id)` - Get citation formats (BibTeX, APA, etc.)
- `search_authors(query, limit, **filters)` - Search author profiles (affiliation)
- `get_author(author_id)` - Get author profile by Google Scholar ID
- `get_author_papers(author_id, limit, offset, sort_by)` - Get papers by author (sort by "cited" or "pubdate")

---

## Configuration

Copy `config.example.yaml` to `config.yaml` and add your API keys:

```yaml
# API Keys
elsevier_api_key: "your-key"           # Required for Elsevier/Scopus
serpapi_api_key: "your-key"            # Required for Google Scholar
semantic_scholar_api_key: "your-key"   # Optional, for higher rate limits

# Default sources (in order of preference)
default_sources:
  - openalex
  - semantic_scholar
```

---

## PDF Extraction (MinerU)

- **Documentation**: MinerU CLI and Python API
- **Package**: `mineru` on PyPI
- **Usage**: `from mineru.cli.common import do_parse`

The PDF extractor uses MinerU's `do_parse` function with `backend="pipeline"`.

---

## Common Tasks

### Adding a new API client

1. Create new file in `src/paper_ladder/clients/`
2. Inherit from `BaseClient`
3. Implement `search()` and `get_paper()` methods
4. Add API key property if needed
5. Register in `clients/__init__.py`

### Running specific tests

```bash
uv run pytest tests/test_clients/test_openalex.py -v
```

### Testing API clients manually

```python
import asyncio
from paper_ladder.clients import OpenAlexClient

async def test():
    async with OpenAlexClient() as client:
        papers = await client.search("machine learning", limit=5)
        for p in papers:
            print(f"{p.title} ({p.year})")

asyncio.run(test())
```

---

## Code Style

- Use ruff for linting: `uv run ruff check .`
- Format with ruff: `uv run ruff format .`
- Type hints required for public APIs
