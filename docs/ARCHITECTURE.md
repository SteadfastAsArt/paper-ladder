# Paper-Ladder Architecture

## System Overview

Paper-Ladder is a Python library for academic paper search and content extraction. It provides a unified interface to multiple academic APIs with automatic rate limiting, deduplication, and result aggregation.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              User Application                                │
│                         (CLI / Python API / Scripts)                         │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                               Aggregator                                     │
│                    (Multi-source search & deduplication)                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
          ┌───────────────────────────┼───────────────────────────┐
          ▼                           ▼                           ▼
┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
│   OpenAlex      │         │ Semantic Scholar │         │    Crossref     │
│   Client        │         │    Client        │         │    Client       │
└─────────────────┘         └─────────────────┘         └─────────────────┘
          │                           │                           │
          ▼                           ▼                           ▼
┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
│   Elsevier      │         │ Google Scholar   │         │   (Future       │
│   Client        │         │   Client         │         │    Clients)     │
└─────────────────┘         └─────────────────┘         └─────────────────┘
          │                           │                           │
          └───────────────────────────┼───────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                             Base Client                                      │
│              (HTTP client, rate limiting, error handling)                    │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          External APIs                                       │
│     OpenAlex │ Semantic Scholar │ Crossref │ Elsevier │ SerpAPI            │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Project Structure

```
paper-ladder/
├── src/paper_ladder/
│   ├── __init__.py           # Package exports
│   ├── models.py             # Pydantic data models
│   ├── config.py             # Configuration loader
│   ├── aggregator.py         # Multi-source aggregation
│   ├── utils.py              # Utility functions
│   ├── cli.py                # Typer CLI application
│   ├── clients/
│   │   ├── __init__.py       # Client registry
│   │   ├── base.py           # Abstract base client
│   │   ├── openalex.py       # OpenAlex API client
│   │   ├── semantic_scholar.py
│   │   ├── crossref.py       # Crossref API client
│   │   ├── elsevier.py       # Scopus/ScienceDirect client
│   │   └── google_scholar.py # SerpAPI client
│   └── extractors/
│       ├── __init__.py
│       ├── pdf.py            # MinerU PDF extraction
│       ├── html.py           # HTML extraction
│       └── structured.py     # Structured content parsing
├── tests/
├── docs/
├── config.example.yaml
├── pyproject.toml
├── CLAUDE.md                 # Development guide
└── README.md                 # User documentation
```

## Data Flow

### Search Flow

```
User Query: "machine learning"
            │
            ▼
┌───────────────────────────────────────────────────────────────┐
│                        Aggregator.search()                     │
│  sources=["openalex", "crossref", "semantic_scholar"]          │
└───────────────────────────────────────────────────────────────┘
            │
            │  Parallel async requests
            ▼
┌───────────┬───────────┬───────────┐
│ OpenAlex  │ Crossref  │ Semantic  │
│  search() │  search() │ Scholar   │
│           │           │  search() │
└─────┬─────┴─────┬─────┴─────┬─────┘
      │           │           │
      ▼           ▼           ▼
┌───────────────────────────────────┐
│        Rate Limiter               │
│  (Per-client, configurable)       │
│  OpenAlex: 10/s                   │
│  Crossref: 50/s                   │
│  Semantic Scholar: 0.33/s         │
└───────────────────────────────────┘
      │           │           │
      ▼           ▼           ▼
┌───────────────────────────────────┐
│      External API Responses       │
│  (JSON → Paper objects)           │
└───────────────────────────────────┘
      │           │           │
      └─────┬─────┴─────┬─────┘
            │           │
            ▼           ▼
┌───────────────────────────────────┐
│         Result Merging            │
│  - Round-robin interleaving       │
│  - DOI-based deduplication        │
│  - Title-based fallback dedup     │
└───────────────────────────────────┘
            │
            ▼
┌───────────────────────────────────┐
│         SearchResult              │
│  - papers: list[Paper]            │
│  - total_results: int             │
│  - sources_queried: list[str]     │
│  - errors: dict[str, str]         │
└───────────────────────────────────┘
```

### Paper Retrieval Flow

```
DOI: "10.1038/nature14539"
            │
            ▼
┌───────────────────────────────────────────────────────────────┐
│                      Aggregator.get_paper()                    │
│                 or Client.get_paper(doi)                       │
└───────────────────────────────────────────────────────────────┘
            │
            ▼
┌───────────────────────────────────────────────────────────────┐
│                     DOI Normalization                          │
│  "https://doi.org/10.1038/nature14539"                         │
│  "doi:10.1038/nature14539"          →  "10.1038/nature14539"   │
│  "10.1038/nature14539"                                         │
└───────────────────────────────────────────────────────────────┘
            │
            ▼
┌───────────────────────────────────────────────────────────────┐
│                      API Request                               │
│  OpenAlex:  GET /works/https://doi.org/10.1038/nature14539     │
│  Crossref:  GET /works/10.1038/nature14539                     │
│  Semantic:  GET /paper/DOI:10.1038/nature14539                 │
└───────────────────────────────────────────────────────────────┘
            │
            ▼
┌───────────────────────────────────────────────────────────────┐
│                   Response Parsing                             │
│  API-specific JSON → Unified Paper model                       │
│  - Extract title, authors, abstract                            │
│  - Normalize DOI, year, journal                                │
│  - Parse citations_count, references_count                     │
│  - Store raw_data for advanced use                             │
└───────────────────────────────────────────────────────────────┘
            │
            ▼
┌───────────────────────────────────────────────────────────────┐
│                        Paper                                   │
│  title: "Deep learning"                                        │
│  authors: ["Yann LeCun", "Yoshua Bengio", "Geoffrey Hinton"]   │
│  doi: "10.1038/nature14539"                                    │
│  year: 2015                                                    │
│  citations_count: 68506                                        │
│  source: "crossref"                                            │
└───────────────────────────────────────────────────────────────┘
```

## Component Details

### BaseClient

Abstract base class providing common functionality for all API clients.

```python
class BaseClient(ABC):
    name: str           # Client identifier (e.g., "openalex")
    base_url: str       # API base URL

    # Lazy-initialized
    _client: httpx.AsyncClient
    _rate_limiter: RateLimiter

    # Abstract methods (must implement)
    async def search(query, limit, offset, **kwargs) -> list[Paper]
    async def get_paper(identifier) -> Paper | None

    # Provided methods
    async def _get(url, **kwargs) -> Response   # Rate-limited GET
    async def _post(url, **kwargs) -> Response  # Rate-limited POST
```

### Client Registry

```python
# clients/__init__.py
CLIENTS = {
    "openalex": OpenAlexClient,
    "semantic_scholar": SemanticScholarClient,
    "crossref": CrossrefClient,
    "elsevier": ElsevierClient,
    "google_scholar": GoogleScholarClient,
}

def get_client(name: str) -> type[BaseClient]:
    return CLIENTS[name]
```

### Data Models

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              Paper                                       │
├─────────────────────────────────────────────────────────────────────────┤
│ title: str                    # Paper title                              │
│ authors: list[str]            # Author names                             │
│ abstract: str | None          # Abstract text                            │
│ doi: str | None               # DOI identifier                           │
│ year: int | None              # Publication year                         │
│ journal: str | None           # Journal/venue name                       │
│ url: str | None               # Landing page URL                         │
│ pdf_url: str | None           # Direct PDF link                          │
│ source: str                   # Data source (e.g., "openalex")           │
│ citations_count: int | None   # Number of citations                      │
│ references_count: int | None  # Number of references                     │
│ open_access: bool | None      # Open access status                       │
│ keywords: list[str]           # Subject keywords                         │
│ raw_data: dict                # Original API response                    │
├─────────────────────────────────────────────────────────────────────────┤
│ __hash__() → int              # Hash by DOI or title (for dedup)         │
│ __eq__(other) → bool          # Equal by DOI or title                    │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                              Author                                      │
├─────────────────────────────────────────────────────────────────────────┤
│ name: str                     # Display name                             │
│ source_id: str | None         # Source-specific ID                       │
│ source: str | None            # Data source                              │
│ affiliations: list[str]       # Institution affiliations                 │
│ orcid: str | None             # ORCID identifier                         │
│ url: str | None               # Profile URL                              │
│ paper_count: int | None       # Number of publications                   │
│ citation_count: int | None    # Total citations                          │
│ h_index: int | None           # h-index                                  │
│ raw_data: dict                # Original API response                    │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                           Institution                                    │
├─────────────────────────────────────────────────────────────────────────┤
│ name: str                     # Institution name                         │
│ source_id: str | None         # Source-specific ID                       │
│ source: str | None            # Data source                              │
│ country: str | None           # Country code                             │
│ type: str | None              # Type (education, company, etc.)          │
│ url: str | None               # Homepage URL                             │
│ paper_count: int | None       # Number of publications                   │
│ citation_count: int | None    # Total citations                          │
│ raw_data: dict                # Original API response                    │
└─────────────────────────────────────────────────────────────────────────┘
```

## API Client Capabilities

```
┌────────────────────┬──────────┬──────────┬──────────┬──────────┬──────────┐
│ Capability         │ OpenAlex │ Semantic │ Crossref │ Elsevier │ Google   │
│                    │          │ Scholar  │          │          │ Scholar  │
├────────────────────┼──────────┼──────────┼──────────┼──────────┼──────────┤
│ search()           │    ✓     │    ✓     │    ✓     │    ✓     │    ✓     │
│ get_paper()        │    ✓     │    ✓     │    ✓     │    ✓     │    ✓     │
│ get_citations()    │    ✓     │    ✓     │    ✗     │    ✓     │    ✓     │
│ get_references()   │    ✓     │    ✓     │    ✓     │    ✗     │    ✗     │
│ search_authors()   │    ✓     │    ✓     │    ✗     │    ✓     │    ✓     │
│ get_author()       │    ✓     │    ✓     │    ✗     │    ✓     │    ✓     │
│ author_papers()    │    ✓     │    ✓     │    ✗     │    ✓     │    ✓     │
│ institutions()     │    ✓     │    ✗     │    ✗     │    ✓     │    ✗     │
│ get_journal()      │    ✗     │    ✗     │    ✓     │    ✗     │    ✗     │
│ journal_works()    │    ✗     │    ✗     │    ✓     │    ✗     │    ✗     │
│ get_funder()       │    ✗     │    ✗     │    ✓     │    ✗     │    ✗     │
│ funder_works()     │    ✗     │    ✗     │    ✓     │    ✗     │    ✗     │
│ recommendations()  │    ✗     │    ✓     │    ✗     │    ✗     │    ✗     │
│ batch_lookup()     │    ✗     │    ✓     │    ✗     │    ✗     │    ✗     │
├────────────────────┼──────────┼──────────┼──────────┼──────────┼──────────┤
│ Requires API Key   │    ✗     │ Optional │    ✗     │    ✓     │    ✓     │
│ Free               │    ✓     │    ✓     │    ✓     │    ✗     │    ✗     │
│ Max per request    │   200    │   100    │  1,000   │    25    │    20    │
│ Rate limit (req/s) │   ~10    │  ~0.33*  │   ~50    │   ~2     │   ~1     │
└────────────────────┴──────────┴──────────┴──────────┴──────────┴──────────┘
* Semantic Scholar: 1/s with API key
```

## Rate Limiting

Each client has an independent rate limiter based on the configuration.

```python
class RateLimiter:
    def __init__(self, requests_per_second: float):
        self.min_interval = 1.0 / requests_per_second

    async def acquire(self):
        # Wait if needed to respect rate limit
        elapsed = now - self.last_request_time
        if elapsed < self.min_interval:
            await asyncio.sleep(self.min_interval - elapsed)
```

Default rate limits (config.py):
```python
class RateLimits:
    openalex: float = 10          # 10 req/s
    semantic_scholar: float = 10  # 10 req/s (with API key)
    crossref: float = 50          # 50 req/s (polite pool)
    elsevier: float = 5           # 5 req/s
    google_scholar: float = 1     # 1 req/s
```

## Configuration

```yaml
# config.yaml

# API Keys
elsevier_api_key: "xxx"           # Required for Elsevier
serpapi_api_key: "xxx"            # Required for Google Scholar
semantic_scholar_api_key: "xxx"   # Optional, higher rate limits

# Default sources for aggregated search
default_sources:
  - openalex
  - crossref
  - semantic_scholar

# Rate limits (requests per second)
rate_limits:
  openalex: 10
  semantic_scholar: 10
  crossref: 50
  elsevier: 5
  google_scholar: 1

# Request settings
request_timeout: 30
max_retries: 3

# Output directory for extractions
output_dir: "./output"

# Proxy settings (optional)
proxy:
  http: "http://proxy:8080"
  https: "http://proxy:8080"
```

## Error Handling

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Error Handling Flow                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  API Request                                                             │
│      │                                                                   │
│      ▼                                                                   │
│  ┌─────────────┐     Success      ┌──────────────┐                      │
│  │ Rate Limit  │ ───────────────► │ Parse JSON   │                      │
│  │   Check     │                  │   Response   │                      │
│  └─────────────┘                  └──────────────┘                      │
│      │                                   │                               │
│      │ 429 Too Many Requests             │ Parse Error                   │
│      ▼                                   ▼                               │
│  ┌─────────────┐                  ┌──────────────┐                      │
│  │   Wait &    │                  │ Return None  │                      │
│  │   Retry     │                  │  or Empty    │                      │
│  └─────────────┘                  └──────────────┘                      │
│                                                                          │
│  Aggregator handles errors gracefully:                                   │
│  - Failed sources are recorded in SearchResult.errors                    │
│  - Other sources still return results                                    │
│  - No exception thrown to caller                                         │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Crossref Unique Features

### Journal Metadata

Crossref provides unique access to journal-level metadata:

```python
async with CrossrefClient() as client:
    # Get journal info by ISSN
    journal = await client.get_journal("0028-0836")  # Nature
    
    # Returns:
    # {
    #   "title": "Nature",
    #   "publisher": "Springer Science and Business Media LLC",
    #   "ISSN": ["0028-0836", "1476-4687"],
    #   "counts": {
    #     "total-dois": 444301,
    #     "current-dois": 9179,
    #     "backfile-dois": 435122
    #   },
    #   "coverage": {
    #     "abstracts-current": 0.119,
    #     "references-current": 0.634,
    #     "orcids-current": 0.395
    #   }
    # }
    
    # Search papers within a specific journal
    papers = await client.get_journal_works("0028-0836", query="AI", limit=20)
```

### Funder Metadata

Search by funding agency:

```python
async with CrossrefClient() as client:
    # Get funder info
    funder = await client.get_funder("501100001809")  # NSFC
    
    # Returns:
    # {
    #   "name": "National Natural Science Foundation of China",
    #   "location": "China",
    #   "work-count": 3104226,
    #   "alt-names": ["NSFC", "国家自然科学基金委员会", ...]
    # }
    
    # Search papers funded by this agency
    papers = await client.get_funder_works("501100001809", query="deep learning")
```

**Common Funder IDs**:

| Funder | ID | Country | Papers |
|--------|-----|---------|--------|
| NSFC | 501100001809 | China | 3.1M |
| NIH | 100000002 | US | 443K |
| NSF | 100000001 | US | 428K |
| JSPS | 501100001691 | Japan | 246K |
| DOE | 100000015 | US | 139K |
| EPSRC | 501100000266 | UK | 112K |
| DARPA | 100000185 | US | 19K |

## Extending the Library

### Adding a New Client

1. Create `src/paper_ladder/clients/new_source.py`:

```python
from paper_ladder.clients.base import BaseClient
from paper_ladder.models import Paper

class NewSourceClient(BaseClient):
    name = "new_source"
    base_url = "https://api.newsource.com"

    async def search(self, query, limit=10, offset=0, **kwargs):
        params = {"q": query, "limit": limit, "offset": offset}
        response = await self._get("/search", params=params)
        return [self._parse_paper(item) for item in response.json()["results"]]

    async def get_paper(self, identifier):
        try:
            response = await self._get(f"/papers/{identifier}")
            return self._parse_paper(response.json())
        except Exception:
            return None

    def _parse_paper(self, data):
        return Paper(
            title=data["title"],
            authors=data.get("authors", []),
            doi=data.get("doi"),
            year=data.get("year"),
            source=self.name,
            raw_data=data,
        )
```

2. Register in `src/paper_ladder/clients/__init__.py`:

```python
from paper_ladder.clients.new_source import NewSourceClient

CLIENTS["new_source"] = NewSourceClient
__all__.append("NewSourceClient")
```

3. Add rate limit in `src/paper_ladder/config.py`:

```python
class RateLimits:
    # ...existing...
    new_source: float = 10
```
