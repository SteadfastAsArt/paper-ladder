# Paper-Ladder Architecture

This document describes the data models, data flow, and overall architecture of Paper-Ladder.

## Overview

Paper-Ladder is designed around three core concepts:

1. **Search & Discovery** - Query multiple academic APIs to find papers
2. **Aggregation** - Merge and deduplicate results from multiple sources
3. **Extraction** - Convert paper content (PDF/HTML) to structured Markdown

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              User Interface                                  │
│                         (CLI / Python API)                                   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Aggregator                                      │
│                    (Multi-source search & deduplication)                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              ▼                     ▼                     ▼
┌───────────────────┐   ┌───────────────────┐   ┌───────────────────┐
│   OpenAlex        │   │ Semantic Scholar  │   │    Elsevier       │
│   Client          │   │ Client            │   │    Client         │
└───────────────────┘   └───────────────────┘   └───────────────────┘
              │                     │                     │
              └─────────────────────┼─────────────────────┘
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Unified Data Models                                │
│              (Paper, Author, Institution, SearchResult)                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Extractors                                      │
│                    (PDF via MinerU, HTML via BeautifulSoup)                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          ExtractedContent                                    │
│                    (Markdown + Figures + Tables)                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Data Models

All models are defined in `src/paper_ladder/models.py` using Pydantic for validation.

### Paper

The core model representing an academic paper's metadata.

```python
class Paper(BaseModel):
    # Required
    title: str                              # Paper title
    source: str                             # Data source (e.g., "openalex", "semantic_scholar")

    # Identifiers
    doi: str | None                         # Digital Object Identifier

    # Metadata
    authors: list[str]                      # List of author names
    abstract: str | None                    # Paper abstract
    year: int | None                        # Publication year
    journal: str | None                     # Journal/venue name

    # URLs
    url: str | None                         # Landing page URL
    pdf_url: str | None                     # Direct PDF link

    # Metrics
    citations_count: int | None             # Number of citations
    references_count: int | None            # Number of references
    open_access: bool | None                # Open access status
    keywords: list[str]                     # Subject keywords/concepts

    # Raw data
    raw_data: dict[str, Any]                # Original API response
```

**Key behaviors:**
- Equality is based on DOI (if present) or title (case-insensitive)
- Hash is computed from DOI or title for set operations
- This enables automatic deduplication when aggregating from multiple sources

### Author

Represents an author with their metadata and metrics.

```python
class Author(BaseModel):
    # Required
    name: str                               # Author's display name

    # Identifiers
    source_id: str | None                   # Source-specific ID
    source: str | None                      # Data source
    orcid: str | None                       # ORCID identifier

    # Affiliation
    affiliations: list[str]                 # List of institution names

    # URLs
    url: str | None                         # Profile URL

    # Metrics
    paper_count: int | None                 # Number of publications
    citation_count: int | None              # Total citations
    h_index: int | None                     # h-index

    # Raw data
    raw_data: dict[str, Any]                # Original API response
```

### Institution

Represents an academic institution or affiliation.

```python
class Institution(BaseModel):
    # Required
    name: str                               # Institution name

    # Identifiers
    source_id: str | None                   # Source-specific ID
    source: str | None                      # Data source

    # Metadata
    country: str | None                     # Country code (e.g., "US", "GB")
    type: str | None                        # Type: "education", "company", "healthcare", etc.

    # URLs
    url: str | None                         # Homepage URL

    # Metrics
    paper_count: int | None                 # Number of publications
    citation_count: int | None              # Total citations

    # Raw data
    raw_data: dict[str, Any]                # Original API response
```

### ExtractedContent

Represents content extracted from a paper (PDF or HTML).

```python
class ExtractedContent(BaseModel):
    markdown: str                           # Body text as Markdown
    metadata: dict[str, Any]                # Extracted metadata
    figures: list[str]                      # Paths to extracted figures
    tables: list[str]                       # Extracted tables (HTML format)
    source_url: str | None                  # Original URL
    source_type: str | None                 # "pdf" or "html"
```

### SearchResult

Container for search results from multiple sources.

```python
class SearchResult(BaseModel):
    query: str                              # Original search query
    papers: list[Paper]                     # List of found papers
    total_results: int | None               # Total available (if known)
    sources_queried: list[str]              # Sources that were queried
    errors: dict[str, str]                  # Errors by source (if any)
```

---

## Data Flow

### 1. Search Flow

```
User Query
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ Aggregator.search(query, sources=["openalex", "semantic_scholar"])
│                                                                 │
│  1. Validate sources                                            │
│  2. Create client instances                                     │
│  3. Execute searches concurrently (asyncio.gather)              │
│  4. Collect results and errors                                  │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ For each source (concurrent):                                   │
│                                                                 │
│  OpenAlexClient.search(query)                                   │
│    │                                                            │
│    ├─► Rate limiter.acquire()                                   │
│    ├─► HTTP GET /works?search={query}                           │
│    ├─► Parse JSON response                                      │
│    └─► _parse_work() → Paper objects                            │
│                                                                 │
│  SemanticScholarClient.search(query)                            │
│    │                                                            │
│    ├─► Rate limiter.acquire()                                   │
│    ├─► HTTP GET /paper/search?query={query}                     │
│    ├─► Parse JSON response                                      │
│    └─► _parse_paper() → Paper objects                           │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ Aggregator._merge_results(all_papers)                           │
│                                                                 │
│  1. Flatten all paper lists                                     │
│  2. Group by DOI (if present) or title                          │
│  3. Merge metadata from multiple sources                        │
│  4. Prefer: DOI > abstract > year > etc.                        │
│  5. Return deduplicated list                                    │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
SearchResult(
    query="machine learning",
    papers=[Paper(...), Paper(...), ...],
    sources_queried=["openalex", "semantic_scholar"],
    errors={}
)
```

### 2. Paper Lookup Flow

```
DOI or Identifier
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ Client.get_paper(identifier)                                    │
│                                                                 │
│  1. Normalize identifier (DOI format, etc.)                     │
│  2. Rate limiter.acquire()                                      │
│  3. HTTP GET to source-specific endpoint                        │
│  4. Parse response into Paper                                   │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
Paper(title="...", doi="10.1234/...", ...)
```

### 3. Content Extraction Flow

```
Paper URL or File Path
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ Determine content type                                          │
│                                                                 │
│  - .pdf extension → PDFExtractor                                │
│  - .html/.htm extension → HTMLExtractor                         │
│  - URL → Fetch and detect content type                          │
└─────────────────────────────────────────────────────────────────┘
    │
    ├─────────────────────────┬───────────────────────────────────┐
    ▼                         ▼
┌──────────────────┐   ┌──────────────────┐
│  PDFExtractor    │   │  HTMLExtractor   │
│                  │   │                  │
│  1. Download PDF │   │  1. Fetch HTML   │
│  2. MinerU parse │   │  2. Parse DOM    │
│  3. Extract text │   │  3. Extract      │
│  4. Extract figs │   │     metadata     │
│  5. Convert to   │   │  4. Convert to   │
│     Markdown     │   │     Markdown     │
└──────────────────┘   └──────────────────┘
    │                         │
    └─────────────────────────┘
                │
                ▼
ExtractedContent(
    markdown="# Title\n\n## Abstract\n...",
    metadata={"title": "...", "authors": [...]},
    figures=["fig1.png", "fig2.png"],
    tables=["<table>...</table>"]
)
```

### 4. Author/Institution Lookup Flow

```
Author Name or ID
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ Client.search_authors(query) or Client.get_author(id)           │
│                                                                 │
│  OpenAlex:                                                      │
│    GET /authors?search={query}                                  │
│    → _parse_author() → Author objects                           │
│                                                                 │
│  Semantic Scholar:                                              │
│    GET /author/search?query={query}                             │
│    → _parse_author() → Author objects                           │
│                                                                 │
│  Elsevier:                                                      │
│    GET /content/search/author?query=AUTHLAST({query})           │
│    → _parse_author_entry() → Author objects                     │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
[Author(name="John Doe", h_index=45, ...), ...]
```

---

## Client Architecture

### BaseClient

All API clients inherit from `BaseClient` which provides:

```python
class BaseClient(ABC):
    name: str                    # Client identifier
    base_url: str                # API base URL

    # Shared functionality
    @property
    def client(self) -> httpx.AsyncClient     # HTTP client with proxy support
    @property
    def rate_limiter(self) -> RateLimiter     # Per-source rate limiting

    async def _get(url, **kwargs)             # Rate-limited GET
    async def _post(url, **kwargs)            # Rate-limited POST

    # Abstract methods (must implement)
    async def search(query, limit, offset, **kwargs) -> list[Paper]
    async def get_paper(identifier) -> Paper | None
```

### Client Hierarchy

```
BaseClient (abstract)
    │
    ├── OpenAlexClient
    │     - No auth required
    │     - Works, Authors, Institutions, Sources
    │     - Abstract as inverted index
    │
    ├── SemanticScholarClient
    │     - Optional API key (x-api-key header)
    │     - Papers, Authors
    │     - Batch operations, Recommendations
    │
    ├── ElsevierClient
    │     - Required API key (X-ELS-APIKey header)
    │     - Scopus search, Abstract retrieval
    │     - Authors, Affiliations
    │
    └── GoogleScholarClient
          - Required SerpAPI key (api_key param)
          - Scrapes Google Scholar
          - Author profiles, Citations
```

---

## Configuration Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ config.yaml                                                     │
│                                                                 │
│   elsevier_api_key: "..."                                       │
│   serpapi_api_key: "..."                                        │
│   semantic_scholar_api_key: "..."  # Optional                   │
│   proxy:                                                        │
│     http: "http://127.0.0.1:7890"                               │
│   default_sources: ["openalex", "semantic_scholar"]             │
│   rate_limits:                                                  │
│     openalex: 10                                                │
│     semantic_scholar: 10                                        │
└─────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────┐
│ Config (Pydantic model)                                         │
│                                                                 │
│   load_config(path) → Config                                    │
│   get_config() → Config (singleton)                             │
│                                                                 │
│   Properties:                                                   │
│     .elsevier_api_key                                           │
│     .serpapi_api_key                                            │
│     .semantic_scholar_api_key                                   │
│     .get_proxy_url() → str | None                               │
│     .rate_limits.openalex → float                               │
└─────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────┐
│ Clients use config for:                                         │
│   - API keys (headers/params)                                   │
│   - Proxy settings (httpx client)                               │
│   - Rate limits (RateLimiter)                                   │
│   - Timeouts                                                    │
└─────────────────────────────────────────────────────────────────┘
```

---

## Rate Limiting

Each client has its own rate limiter based on configured limits:

```
┌─────────────────────────────────────────────────────────────────┐
│ RateLimiter(requests_per_second)                                │
│                                                                 │
│   async def acquire():                                          │
│     1. Calculate time since last request                        │
│     2. If too soon, sleep for remaining interval                │
│     3. Update last request timestamp                            │
│     4. Return (request may proceed)                             │
│                                                                 │
│   Example (10 req/sec = 100ms between requests):                │
│     Request 1: immediate                                        │
│     Request 2: wait ~100ms                                      │
│     Request 3: wait ~100ms                                      │
└─────────────────────────────────────────────────────────────────┘
```

---

## Error Handling

```
┌─────────────────────────────────────────────────────────────────┐
│ Aggregator handles errors gracefully:                           │
│                                                                 │
│   try:                                                          │
│     papers = await client.search(query)                         │
│   except Exception as e:                                        │
│     errors[source] = str(e)                                     │
│     papers = []                                                 │
│                                                                 │
│ Result includes partial results + error info:                   │
│   SearchResult(                                                 │
│     papers=[...from working sources...],                        │
│     errors={"semantic_scholar": "429 Too Many Requests"}        │
│   )                                                             │
└─────────────────────────────────────────────────────────────────┘
```

---

## CLI Data Flow

```
$ paper-ladder search "transformer architecture" --sources openalex

┌─────────────────────────────────────────────────────────────────┐
│ CLI (typer)                                                     │
│                                                                 │
│   @app.command()                                                │
│   def search(query, sources, limit, output):                    │
│     result = asyncio.run(aggregator.search(...))                │
│     if output:                                                  │
│       write_json(output, result)                                │
│     else:                                                       │
│       print_table(result.papers)                                │
└─────────────────────────────────────────────────────────────────┘
```

---

## File Structure Summary

```
paper_ladder/
├── models.py          # Paper, Author, Institution, ExtractedContent, SearchResult
├── config.py          # Config loading and validation
├── utils.py           # DOI normalization, rate limiting, text cleaning
├── aggregator.py      # Multi-source search orchestration
├── cli.py             # Command-line interface
│
├── clients/
│   ├── base.py        # BaseClient abstract class
│   ├── openalex.py    # OpenAlex API client
│   ├── semantic_scholar.py  # Semantic Scholar API client
│   ├── elsevier.py    # Elsevier/Scopus API client
│   └── google_scholar.py    # Google Scholar via SerpAPI
│
└── extractors/
    ├── base.py        # BaseExtractor abstract class
    ├── pdf_extractor.py   # MinerU-based PDF extraction
    └── html_extractor.py  # BeautifulSoup HTML extraction
```
