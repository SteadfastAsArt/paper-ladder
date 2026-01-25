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
  - `models.py` - Data models (Paper, Author, Institution, ExtractedContent, SearchResult, PaperStructure, BookStructure, PaginationInfo, PaginatedSearchResult)
  - `config.py` - Configuration loader (includes PaginationLimits)
  - `clients/` - API client adapters
  - `extractors/` - Content extractors (PDF, HTML, Structured)
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

### ContentBlock
A single content block from PDF extraction:
- `type` - Block type ("text", "title", "table", "image", "equation", "list")
- `content` - Text content or image path
- `text_level` - Heading level (0=body, 1=h1, 2=h2, etc.)
- `page_idx`, `bbox` - Position information

### Section
A document section with hierarchy:
- `title`, `level` - Section heading info
- `blocks` - List of ContentBlock
- `subsections` - Nested Section list
- `get_text()` - Get section text content
- `get_all_text()` - Get text including subsections

### PaperStructure
Structured academic paper (extends DocumentStructure):
- Standard section fields: `abstract`, `introduction`, `methods`, `results`, `discussion`, `conclusion`, `references_text`, `acknowledgments`
- `sections` - All sections as Section list
- `all_blocks` - Raw ContentBlock list
- `get_section(pattern)` - Find section by title pattern

### BookStructure
Structured textbook with chapter hierarchy:
- `chapters` - List of ChapterNode (tree structure)
- `get_chapter(pattern)` - Find chapter by title
- `get_all_chapters_flat()` - Flatten chapter tree

### ChapterNode
A chapter/section in book structure:
- `title`, `level`, `page_start`
- `content`, `blocks` - Chapter content
- `children` - Nested ChapterNode list
- `get_all_text()` - Get all text including children

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

**Pagination**:
- `per_page`: 1-200 (default 25)
- Offset pagination: max 10,000 results
- Cursor pagination: unlimited (use `cursor=*`)

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
- Unauthenticated: 5,000 requests per 5 minutes (shared pool)
- Authenticated: 1 req/s (search/batch), 10 req/s (other endpoints)
- Entities: Papers, Authors, Paper citations/references
- Fields of study classification
- Recommendation API
- Batch paper lookup

**Pagination** (⚠️ Updated Oct 2024):
- Relevance Search: `offset + limit ≤ 1,000` (reduced from 10,000)
- Bulk Search: up to 10M results (token-based pagination)
- Default limit: 100 per request

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

**Pagination**:
- `count`: max 200 per request
- Offset pagination (`start`): max 5,000 results
- Cursor pagination: unlimited (forward only)
- Weekly limits: 20,000 queries, 20,000 record downloads

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

**Pagination**:
- `num`: 1-20 results per request (default 10)
- `start`: offset parameter, no documented upper limit

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

### 5. Crossref

- **Documentation**: https://www.crossref.org/documentation/retrieve-metadata/rest-api/
- **API Tips**: https://www.crossref.org/documentation/retrieve-metadata/rest-api/tips-for-using-the-crossref-rest-api/
- **Swagger UI**: https://api.crossref.org/swagger-ui/index.html
- **Works Endpoint**: https://api.crossref.org/works
- **Journals Endpoint**: https://api.crossref.org/journals
- **Funders Endpoint**: https://api.crossref.org/funders

**Key Features**:
- No API key required
- Polite pool: Add `mailto` parameter for better rate limits and stability
- 150+ million metadata records
- DOI registration agency
- Supports filtering, sorting, cursor-based pagination
- Includes funding information, licenses, ORCID/ROR identifiers

**Pagination**:
- `rows`: max 1,000 per request (default 20)
- Offset pagination: supported, no hard limit
- Cursor pagination: use `cursor=*` (cursor expires after 5 minutes)
- For large datasets: split by date range or use data snapshots

**Base URL**: `https://api.crossref.org`

**Polite Pool**: Add `mailto=your@email.com` parameter to all requests

**Filters Available**:
- `from-pub-date`, `until-pub-date` - Publication date range
- `type` - Work type (journal-article, book-chapter, etc.)
- `has-abstract`, `has-references`, `has-orcid` - Content filters
- `issn` - Filter by journal ISSN
- `funder` - Filter by funder ID

**Implemented Methods**:
- `search(query, limit, offset, **filters)` - Search papers (year, from_year, until_year, type, has_abstract, has_references, has_orcid, issn, funder, open_access, sort, order)
- `get_paper(identifier)` - Get paper by DOI
- `get_paper_references(doi, limit, offset)` - Get referenced papers from a paper's reference list
- `get_journal(issn)` - Get journal metadata by ISSN
- `get_journal_works(issn, query, limit, offset)` - Get works from a journal
- `get_funder(funder_id)` - Get funder metadata
- `get_funder_works(funder_id, query, limit, offset)` - Get works funded by a funder

**Note**: Crossref does not support citation lookup (finding papers that cite a given DOI). Use OpenAlex or Semantic Scholar for citation data.

### 6. PubMed

- **Documentation**: https://www.ncbi.nlm.nih.gov/books/NBK25497/
- **E-utilities Overview**: https://www.ncbi.nlm.nih.gov/books/NBK25500/
- **ESearch**: https://www.ncbi.nlm.nih.gov/books/NBK25499/#chapter4.ESearch
- **EFetch**: https://www.ncbi.nlm.nih.gov/books/NBK25499/#chapter4.EFetch
- **ELink**: https://www.ncbi.nlm.nih.gov/books/NBK25499/#chapter4.ELink
- **Get API Key**: https://www.ncbi.nlm.nih.gov/account/settings/

**Key Features**:
- Free access to 36M+ biomedical citations
- API key optional (for higher rate limits)
- MeSH (Medical Subject Headings) indexing
- PMC full-text links for open access articles
- Related articles algorithm

**Pagination**:
- `retmax`: max 10,000 per request (default 20)
- `retstart`: offset parameter
- PubMed database: ESearch limited to first 10,000 results
- Other NCBI databases: can retrieve more via multiple requests

**Base URL**: `https://eutils.ncbi.nlm.nih.gov/entrez/eutils`

**Param for auth**: `api_key=YOUR_KEY` (optional)

**Implemented Methods**:
- `search(query, limit, offset, **filters)` - Search papers (year, from_year, until_year, author, journal, mesh, article_type, sort)
- `get_paper(identifier)` - Get paper by PMID or DOI
- `get_paper_citations(pmid, limit, offset)` - Get citing papers (via PMC)
- `get_paper_references(pmid, limit, offset)` - Get referenced papers
- `get_related_papers(pmid, limit)` - Get related papers using PubMed's algorithm
- `search_authors(query, limit, offset, **filters)` - Search authors (affiliation)
- `get_author_papers(author_name, limit, offset)` - Get papers by author

### 7. Web of Science

- **Developer Portal**: https://developer.clarivate.com/apis
- **API Expanded**: https://developer.clarivate.com/apis/wos
- **API Starter**: https://developer.clarivate.com/apis/wos-starter (free, limited)
- **Swagger UI**: https://api.clarivate.com/swagger-ui/

**Key Features**:
- Comprehensive citation index (science, social science, arts, humanities)
- API key required (institutional subscription)
- Times Cited counts
- Related records feature
- Multiple database editions (SCI, SSCI, AHCI, etc.)

**Pagination**:
- Max 100 records per request
- Starter API: max 100,000 total results (increased from 50,000 in 2024)
- `firstRecord`: 1-based offset parameter

**Base URL**: `https://api.clarivate.com/api/wos`

**Header for auth**: `X-ApiKey: YOUR_KEY`

**Implemented Methods**:
- `search(query, limit, offset, **filters)` - Search papers (year, from_year, until_year, database, edition, doc_type, sort)
- `get_paper(identifier)` - Get paper by DOI or WoS UID
- `get_paper_citations(paper_id, limit, offset)` - Get citing papers
- `get_paper_references(paper_id, limit, offset)` - Get referenced papers
- `get_related_papers(paper_id, limit)` - Get related papers
- `search_authors(query, limit, offset, **filters)` - Search authors (organization)
- `get_author_papers(author_name, limit, offset)` - Get papers by author

**Note**: WoS Expanded API requires institutional subscription. The free Starter API has limited features (no citation counts, 50 req/day).

---

## Configuration

Copy `config.example.yaml` to `config.yaml` and add your API keys:

```yaml
# API Keys
elsevier_api_key: "your-key"           # Required for Elsevier/Scopus
serpapi_api_key: "your-key"            # Required for Google Scholar
semantic_scholar_api_key: "your-key"   # Optional, for higher rate limits
pubmed_api_key: "your-key"             # Optional, for higher rate limits (10 req/s vs 3 req/s)
wos_api_key: "your-key"                # Required for Web of Science (institutional subscription)

# Default sources (in order of preference)
default_sources:
  - openalex
  - semantic_scholar
  - crossref

# Rate limits (requests per second)
rate_limits:
  openalex: 10
  semantic_scholar: 10      # Set to 0.3 if no API key
  crossref: 50
  elsevier: 5
  google_scholar: 1
  pubmed: 3                 # 3 without key, 10 with key
  wos: 2
```

---

## PDF Extraction (MinerU)

- **Documentation**: MinerU CLI and Python API
- **Package**: `mineru` on PyPI
- **Usage**: `from mineru.cli.common import do_parse`

The PDF extractor uses MinerU's `do_parse` function with `backend="pipeline"`.

### Basic Extraction (Markdown)

```python
from paper_ladder.extractors import PDFExtractor

async def extract():
    extractor = PDFExtractor()
    content = await extractor.extract("paper.pdf")
    print(content.markdown)
```

### Structured Extraction (JSON-based)

For LLM processing, use `StructuredExtractor` to get semantically parsed content:

```python
from paper_ladder.extractors import StructuredExtractor

async def extract_paper():
    extractor = StructuredExtractor()
    paper = await extractor.extract("paper.pdf", document_type="paper")

    # Direct access to standard sections
    print(paper.abstract)
    print(paper.introduction)
    print(paper.methods)
    print(paper.results)
    print(paper.discussion)
    print(paper.conclusion)

    # Or iterate all sections
    for section in paper.sections:
        print(f"{section.title}: {section.get_text()[:100]}...")

async def extract_book():
    extractor = StructuredExtractor()
    book = await extractor.extract("textbook.pdf", document_type="book")

    # Hierarchical chapter access
    for chapter in book.chapters:
        print(f"# {chapter.title}")
        for section in chapter.children:
            print(f"  ## {section.title}")

    # Search by title
    ch = book.get_chapter("linear algebra")
    if ch:
        print(ch.get_all_text())
```

**Document Types**:
- `"paper"` - Academic papers with standard sections (Abstract, Introduction, Methods, etc.)
- `"book"` - Textbooks with chapter hierarchy
- `"auto"` - Auto-detect based on content patterns

**Output Formats**:
- `middle.json` - Full structured JSON with layout info
- `content_list.json` - Simplified flat content list
- Both are parsed into `PaperStructure` or `BookStructure` models

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

## API Clients Comparison

### Feature Comparison

| Feature                 | OpenAlex | Semantic Scholar | Crossref | Elsevier | Google Scholar | PubMed | Web of Science |
|-------------------------|:--------:|:----------------:|:--------:|:--------:|:--------------:|:------:|:--------------:|
| search()                |    ✓     |        ✓         |    ✓     |    ✓     |       ✓        |   ✓    |       ✓        |
| search_with_cursor()    |    ✓     |        ✗         |    ✓     |    ✓     |       ✗        |   ✗    |       ✗        |
| search_all()            |    ✓     |        ✓         |    ✓     |    ✓     |       ✓        |   ✓    |       ✓        |
| get_paper()             |    ✓     |        ✓         |    ✓     |    ✓     |       ✓        |   ✓    |       ✓        |
| get_paper_citations()   |    ✓     |        ✓         |    ✗     |    ✓     |       ✓        |   ✓    |       ✓        |
| get_paper_references()  |    ✓     |        ✓         |    ✓     |    ✗     |       ✗        |   ✓    |       ✓        |
| search_authors()        |    ✓     |        ✓         |    ✗     |    ✓     |       ✓        |   ✓    |       ✓        |
| get_author()            |    ✓     |        ✓         |    ✗     |    ✓     |       ✓        |   ✗    |       ✗        |
| get_author_papers()     |    ✓     |        ✓         |    ✗     |    ✓     |       ✓        |   ✓    |       ✓        |
| search_institutions()   |    ✓     |        ✗         |    ✗     |    ✓     |       ✗        |   ✗    |       ✗        |
| get_institution()       |    ✓     |        ✗         |    ✗     |    ✓     |       ✗        |   ✗    |       ✗        |
| get_journal()           |    ✗     |        ✗         |    ✓     |    ✗     |       ✗        |   ✗    |       ✗        |
| get_journal_works()     |    ✗     |        ✗         |    ✓     |    ✗     |       ✗        |   ✗    |       ✗        |
| get_funder()            |    ✗     |        ✗         |    ✓     |    ✗     |       ✗        |   ✗    |       ✗        |
| get_funder_works()      |    ✗     |        ✗         |    ✓     |    ✗     |       ✗        |   ✗    |       ✗        |
| get_recommendations()   |    ✗     |        ✓         |    ✗     |    ✗     |       ✗        |   ✓    |       ✓        |
| batch operations        |    ✗     |        ✓         |    ✗     |    ✗     |       ✗        |   ✗    |       ✗        |
| **Requires API Key**    |    ✗     |      Optional    |    ✗     |    ✓     |       ✓        | Optional |       ✓        |
| **Free**                |    ✓     |        ✓         |    ✓     |    ✗     |       ✗        |   ✓    |       ✗        |

### Rate Limits

| Engine           | Without Key               | With Key                      | Default Setting |
|------------------|---------------------------|-------------------------------|-----------------|
| OpenAlex         | 100,000/day (~10/s)       | N/A (no key needed)           | 10 req/s        |
| Semantic Scholar | 5,000/5min (shared pool)  | 1 req/s (search), 10 req/s (other) | 10 req/s   |
| Crossref         | No hard limit             | N/A (no key needed)           | 50 req/s        |
| Elsevier/Scopus  | Key required              | 20,000 queries/week           | 5 req/s         |
| Google Scholar   | Key required              | ~$0.015/search                | 1 req/s         |
| PubMed           | 3 req/s                   | 10 req/s                      | 3 req/s         |
| Web of Science   | Key required              | Varies by subscription        | 2 req/s         |

### Single Request Return Limits

| Engine           | Method                    | Code Limit        | API Max  |
|------------------|---------------------------|-------------------|----------|
| OpenAlex         | search()                  | min(limit, 200)   | 200      |
| Semantic Scholar | search()                  | min(limit, 100)   | 100      |
| Semantic Scholar | get_paper_citations()     | min(limit, 1000)  | 1000     |
| Semantic Scholar | get_papers_batch()        | Fixed 500         | 500      |
| Crossref         | search()                  | min(limit, 1000)  | 1000     |
| Elsevier/Scopus  | search()                  | min(limit, 25)    | 200*     |
| Google Scholar   | search()                  | min(limit, 20)    | 20       |
| PubMed           | search()                  | min(limit, 10000) | 10000    |
| Web of Science   | search()                  | min(limit, 100)   | 100      |

*Elsevier API supports up to 200, but code limits to 25 for safety.

### Pagination Limits (Official Documentation)

| Engine           | Per Request | Total Results (Offset) | Total Results (Cursor) | Pagination Type |
|------------------|-------------|------------------------|------------------------|-----------------|
| OpenAlex         | 200         | 10,000                 | Unlimited              | offset + cursor |
| Semantic Scholar | 100         | **1,000**              | 10M (Bulk Search)      | offset / token  |
| Crossref         | 1,000       | No hard limit          | Unlimited              | offset + cursor |
| Elsevier/Scopus  | 200         | 5,000                  | Unlimited              | offset + cursor |
| Google Scholar   | 20          | No documented limit    | N/A                    | offset only     |
| PubMed           | 10,000      | 10,000 (PubMed DB)     | N/A                    | offset only     |
| Web of Science   | 100         | 100,000 (Starter)      | N/A                    | offset only     |

**⚠️ Important Notes**:

1. **Semantic Scholar** (Updated Oct 2024): Relevance Search limit reduced from 10,000 to **1,000** (`offset + limit ≤ 1,000`). Use Bulk Search API for larger datasets.

2. **OpenAlex**: Basic paging limited to 10,000 results. Use `cursor=*` for unlimited pagination.

3. **Crossref**: Cursor expires after 5 minutes. For large datasets, split by date range or use data snapshots.

4. **Elsevier/Scopus**: Offset pagination limited to 5,000 records. Use cursor pagination (`cursor` parameter) for more. Weekly limits: 20,000 queries, 20,000 record downloads.

5. **PubMed**: ESearch can only retrieve first 10,000 records for PubMed database. Other NCBI databases allow more via multiple requests.

**Documentation Sources**:
- OpenAlex: https://docs.openalex.org/how-to-use-the-api/get-lists-of-entities/paging
- Semantic Scholar: https://github.com/allenai/s2-folks/blob/main/API_RELEASE_NOTES.md
- Crossref: https://www.crossref.org/documentation/retrieve-metadata/rest-api/tips-for-using-the-crossref-rest-api/
- Elsevier: https://dev.elsevier.com/guides/Scopus%20API%20Guide_V1_20230907.pdf
- PubMed: https://www.ncbi.nlm.nih.gov/books/NBK25499/
- Web of Science: https://clarivate.com/academia-government/release-notes/wos-apis/

### Citation Count Comparison

Same paper "Deep Learning" (LeCun et al. 2015, DOI: 10.1038/nature14539):

| Source           | Citation Count | Notes                          |
|------------------|----------------|--------------------------------|
| Semantic Scholar | ~162,000       | Includes preprint citations    |
| OpenAlex         | ~77,000        | Peer-reviewed only             |
| Crossref         | ~68,500        | DOI-registered citations only  |

### Platform Strengths

| Platform         | Best For                                              |
|------------------|-------------------------------------------------------|
| OpenAlex         | Free, comprehensive, institution/author data          |
| Semantic Scholar | AI/CS papers, recommendations, arXiv support          |
| Crossref         | DOI authority, journal/funder metadata, 150M+ records |
| Elsevier         | Commercial database, full-text access (subscription)  |
| Google Scholar   | Broadest coverage (books, patents, conferences)       |
| PubMed           | Biomedical/life sciences, MeSH indexing, free access  |
| Web of Science   | Citation analysis, impact metrics, multi-disciplinary |

---

## Crossref Unique Features

### Journal Metadata

Query journal information by ISSN:

```python
from paper_ladder.clients import CrossrefClient

async with CrossrefClient() as client:
    journal = await client.get_journal("0028-0836")  # Nature
    print(journal["title"])                # Nature
    print(journal["publisher"])            # Springer Science and Business Media LLC
    print(journal["counts"]["total-dois"]) # 444,301
```

**Sample Journal Data**:

| Journal              | ISSN       | Publisher                  | Total Articles | Current Year |
|----------------------|------------|----------------------------|----------------|--------------|
| Nature               | 0028-0836  | Springer                   | 444,301        | 9,179        |
| Science              | 0036-8075  | AAAS                       | 382,631        | 4,221        |
| Cell                 | 0092-8674  | Elsevier                   | 26,358         | 1,119        |
| The Lancet           | 0140-6736  | Elsevier                   | 473,508        | 3,351        |
| Nature Communications| 2041-1723  | Springer                   | 83,332         | 24,256       |

### Funder Metadata

Query funding agency information:

```python
async with CrossrefClient() as client:
    funder = await client.get_funder("501100001809")  # NSFC
    print(funder["name"])       # National Natural Science Foundation of China
    print(funder["location"])   # China
    print(funder["work-count"]) # 3,104,226

    # Search papers funded by this agency
    papers = await client.get_funder_works("501100001809", query="deep learning", limit=10)
```

**Common Funder IDs**:

| Funder                                      | ID           | Location      | Funded Papers |
|---------------------------------------------|--------------|---------------|---------------|
| National Natural Science Foundation (NSFC)  | 501100001809 | China         | 3,104,226     |
| National Institutes of Health (NIH)         | 100000002    | United States | 443,055       |
| National Science Foundation (NSF)           | 100000001    | United States | 427,837       |
| Japan Society for Promotion of Science      | 501100001691 | Japan         | 245,879       |
| U.S. Department of Energy (DOE)             | 100000015    | United States | 139,325       |
| EPSRC                                       | 501100000266 | UK            | 112,092       |
| Wellcome Trust                              | 100004440    | UK            | 22,975        |
| DARPA                                       | 100000185    | United States | 18,667        |

---

## Usage Examples

### Basic Search

```python
import asyncio
from paper_ladder.clients import OpenAlexClient, CrossrefClient

async def search_example():
    # OpenAlex search with filters
    async with OpenAlexClient() as client:
        papers = await client.search(
            "transformer attention",
            limit=10,
            year=2023,
            open_access=True,
            sort="cited_by_count"
        )
        for p in papers:
            print(f"[{p.citations_count}] {p.title} ({p.year})")

    # Crossref search with filters
    async with CrossrefClient() as client:
        papers = await client.search(
            "CRISPR gene editing",
            limit=10,
            year=2024,
            has_abstract=True,
            type="journal-article"
        )

asyncio.run(search_example())
```

### Get Paper by DOI

```python
async def get_paper_example():
    async with CrossrefClient() as client:
        paper = await client.get_paper("10.1038/nature14539")
        print(f"Title: {paper.title}")
        print(f"Authors: {', '.join(paper.authors)}")
        print(f"Citations: {paper.citations_count}")
        print(f"References: {paper.references_count}")

asyncio.run(get_paper_example())
```

### Journal-Specific Search

```python
async def journal_search():
    async with CrossrefClient() as client:
        # Get journal metadata
        journal = await client.get_journal("0028-0836")
        print(f"Journal: {journal['title']}")
        print(f"Total articles: {journal['counts']['total-dois']}")

        # Search within journal
        papers = await client.get_journal_works(
            "0028-0836",
            query="artificial intelligence",
            limit=10
        )

asyncio.run(journal_search())
```

### Funder-Specific Search

```python
async def funder_search():
    async with CrossrefClient() as client:
        # Get funder info
        funder = await client.get_funder("100000001")  # NSF
        print(f"Funder: {funder['name']}")
        print(f"Funded papers: {funder['work-count']}")

        # Search funded papers
        papers = await client.get_funder_works(
            "100000001",
            query="machine learning",
            limit=10
        )

asyncio.run(funder_search())
```

### Multi-Source Aggregation

```python
from paper_ladder.aggregator import Aggregator

async def aggregated_search():
    async with Aggregator(sources=["openalex", "crossref", "semantic_scholar"]) as agg:
        result = await agg.search("quantum computing", limit=10)
        print(f"Total papers: {len(result.papers)}")
        print(f"Sources queried: {result.sources_queried}")
        if result.errors:
            print(f"Errors: {result.errors}")

asyncio.run(aggregated_search())
```

### Pagination for Large Results

```python
async def paginated_search():
    async with CrossrefClient() as client:
        all_papers = []
        # Crossref allows up to 1000 per request
        for offset in range(0, 3000, 1000):
            papers = await client.search("climate change", limit=1000, offset=offset)
            all_papers.extend(papers)
            if len(papers) < 1000:
                break
        print(f"Total retrieved: {len(all_papers)}")

asyncio.run(paginated_search())
```

---

## Advanced Pagination

### Cursor Pagination

For sources that support cursor pagination (OpenAlex, Crossref, Elsevier), use `search_with_cursor()` to bypass offset limits and retrieve unlimited results:

```python
from paper_ladder.clients import OpenAlexClient

async def cursor_pagination_example():
    async with OpenAlexClient() as client:
        # Retrieve more than 10,000 results using cursor pagination
        count = 0
        async for paper in client.search_with_cursor("machine learning", max_results=50000):
            print(f"{paper.title} ({paper.year})")
            count += 1
        print(f"Total: {count}")

asyncio.run(cursor_pagination_example())
```

**Supported Sources**:

| Source   | Method                  | Bypasses Limit |
|----------|-------------------------|----------------|
| OpenAlex | `search_with_cursor()`  | 10,000 → ∞     |
| Crossref | `search_with_cursor()`  | N/A → ∞        |
| Elsevier | `search_with_cursor()`  | 5,000 → ∞      |

**Note**: Crossref cursors expire after 5 minutes. Elsevier has a weekly limit of 20,000 downloads.

### Auto Pagination (search_all)

Use `search_all()` for automatic pagination with configurable limits:

```python
from paper_ladder.clients import OpenAlexClient, SemanticScholarClient

async def auto_pagination_example():
    # Automatically uses cursor pagination when needed
    async with OpenAlexClient() as client:
        papers = await client.search_all("transformer", max_results=15000)
        print(f"Got {len(papers)} papers")

    # Warns when hitting API limits
    async with SemanticScholarClient() as client:
        papers = await client.search_all("attention mechanism", max_results=5000)
        # WARNING: [semantic_scholar] Requested 5000 results, but limited to 1000.
        # API limit: offset + limit ≤ 1,000 (reduced from 10,000)

asyncio.run(auto_pagination_example())
```

### Pagination Configuration

Configure per-source limits in `config.yaml`:

```yaml
# Auto-pagination limits (max results per source for search_all())
pagination_limits:
  openalex: 10000       # Cursor pagination allows unlimited
  semantic_scholar: 1000 # API hard limit (offset + limit ≤ 1,000)
  crossref: 10000       # Cursor pagination allows unlimited
  elsevier: 5000        # Cursor pagination bypasses 5,000 offset limit
  google_scholar: 100   # Paid API, limit to control costs
  pubmed: 10000         # ESearch hard limit
  wos: 10000            # Based on subscription tier

# Enable auto-pagination
auto_pagination: true
```

### Pagination Models

Two new models for pagination tracking:

```python
from paper_ladder.models import PaginationInfo, PaginatedSearchResult

# PaginationInfo - tracks pagination state
info = PaginationInfo(
    total_results=50000,
    returned_count=1000,
    has_more=True,
    next_cursor="abc123",
    source_limit="API limit: 10,000 offset max"
)

# PaginatedSearchResult - search result with pagination info
result = PaginatedSearchResult(
    papers=[...],
    pagination=info,
    source="openalex"
)
```

---

## Code Style

- Use ruff for linting: `uv run ruff check .`
- Format with ruff: `uv run ruff format .`
- Type hints required for public APIs
