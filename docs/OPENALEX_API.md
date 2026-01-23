# OpenAlex API Integration

This document describes the OpenAlex API integration in paper-ladder.

## Overview

OpenAlex is a free, open catalog of the world's scholarly works. It provides access to over 250 million works and is particularly strong for scientific literature including geochemistry papers.

**API Documentation:** https://docs.openalex.org/

## Authentication

### API Key

OpenAlex requires an API key for production usage:

| Tier | Daily Credits | Rate Limit |
|------|---------------|------------|
| Without key | 100 | 100 req/s |
| Free API key | 100,000 | 100 req/s |
| Premium | Custom | 100 req/s |

**Get your free API key at:** https://openalex.org/settings/api

### Configuration

Add your API key to `config.yaml`:

```yaml
# API Keys
openalex_api_key: "your-api-key-here"  # Free key for 100k credits/day
```

### Implementation

The `OpenAlexClient` class automatically appends the API key to all requests:

```python
# paper_ladder/clients/openalex.py

class OpenAlexClient(BaseClient):
    """Client for the OpenAlex API."""

    name = "openalex"
    base_url = "https://api.openalex.org"

    async def _get(self, url: str, **kwargs: object) -> httpx.Response:
        """Make a rate-limited GET request with API key."""
        if self.config.openalex_api_key:
            params = kwargs.get("params", {})
            if isinstance(params, dict):
                params["api_key"] = self.config.openalex_api_key
                kwargs["params"] = params
        return await self._request("GET", url, **kwargs)
```

## Credit Costs

Different request types consume different amounts of credits:

| Request Type | Credits | Example |
|--------------|---------|---------|
| Singleton (get one work) | 1 | `/works/W123456789` |
| List/Search | 10 | `/works?search=basalt` |
| Text Classification | 1,000 | Topic classification endpoints |

### Daily Budget Planning

With 100k free credits:
- ~100,000 single paper lookups, OR
- ~10,000 search queries, OR
- ~100 text classifications

For typical usage (search + fetch details):
- Each search query: 10 credits
- Each paper detail fetch: 1 credit
- Budget for ~8,000 search queries with detail fetches

## Usage Examples

### Search for Papers

```python
from paper_ladder.clients.openalex import OpenAlexClient
from paper_ladder.config import load_config

config = load_config("config.yaml")
client = OpenAlexClient(config=config)

# Search for papers
papers = await client.search("Hawaii basalt", limit=50)

for paper in papers[:5]:
    print(f"{paper.title} ({paper.year})")

await client.close()
```

### Get Paper by DOI

```python
paper = await client.get_paper("10.1038/nature12345")
if paper:
    print(f"Title: {paper.title}")
    print(f"Authors: {', '.join(paper.authors)}")
    print(f"Abstract: {paper.abstract[:200]}...")
```

### Get Citations

```python
# Get papers that cite a given paper
citations = await client.get_paper_citations("W2741809807", limit=100)
print(f"Found {len(citations)} citing papers")
```

### Get References

```python
# Get papers referenced by a given paper
references = await client.get_paper_references("W2741809807", limit=100)
print(f"Found {len(references)} referenced papers")
```

## Search Filters

The search method supports various filters:

```python
papers = await client.search(
    "climate change",
    limit=50,
    year="2020-2024",           # Publication year range
    open_access=True,            # Only open access papers
    type="article",              # Work type (article, book, etc.)
    cited_by_count=10,           # Minimum citations
    sort="cited_by_count:desc",  # Sort by citations
)
```

### Available Filters

| Filter | Type | Description |
|--------|------|-------------|
| `year` | str/int | Publication year or range (e.g., "2020-2024") |
| `open_access` | bool | Filter for open access papers |
| `type` | str | Work type: article, book, dataset, etc. |
| `institution` | str | OpenAlex institution ID |
| `author` | str | OpenAlex author ID |
| `cited_by_count` | int | Minimum citation count |
| `sort` | str | Sort field: cited_by_count, publication_date, relevance_score |

## Error Handling

### Rate Limiting (429)

If you exceed rate limits, implement exponential backoff:

```python
import asyncio

async def search_with_retry(client, query, max_retries=5):
    for attempt in range(max_retries):
        try:
            return await client.search(query)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                wait_time = 2 ** attempt  # 1, 2, 4, 8, 16 seconds
                await asyncio.sleep(wait_time)
            else:
                raise
    raise Exception("Max retries exceeded")
```

### Common Errors

| Error Code | Cause | Solution |
|------------|-------|----------|
| 429 | Rate limit exceeded | Wait and retry with backoff |
| 403 | Invalid/missing API key | Check config.yaml |
| 404 | Work not found | Verify DOI/ID format |

## Best Practices

1. **Always use an API key** for production workloads
2. **Batch requests** when possible to reduce credit usage
3. **Cache results** to avoid redundant API calls
4. **Implement retry logic** for transient failures
5. **Monitor credit usage** to avoid hitting daily limits

## Data Model

OpenAlex returns rich metadata for each paper:

```python
@dataclass
class Paper:
    title: str
    authors: list[str]
    abstract: str | None
    doi: str | None
    year: int | None
    journal: str | None
    url: str | None
    pdf_url: str | None
    source: str  # "openalex"
    citations_count: int | None
    references_count: int | None
    open_access: bool | None
    keywords: list[str]
    raw_data: dict  # Full OpenAlex response
```

## Comparison with Other Sources

| Feature | OpenAlex | Semantic Scholar | Elsevier |
|---------|----------|------------------|----------|
| Coverage | 250M+ works | 200M+ works | 80M+ works |
| Free tier | 100k credits/day | 5k req/day | Limited |
| Open access | Yes | Yes | Partial |
| Full text | Links only | Links only | Some |
| Best for | Broad coverage | CS/Bio | Curated quality |

For geochemistry research, **OpenAlex provides the best coverage** and should be the primary source.
