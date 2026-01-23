# Paper-Ladder Architecture

## System Overview

Paper-Ladder is a Python library for academic paper search and content extraction. It provides a unified interface to multiple academic APIs with automatic rate limiting, deduplication, and result aggregation.

## System Architecture Diagram

```mermaid
graph TB
    subgraph UI[User Interface]
        CLI[CLI - typer]
        API[Python API]
    end

    subgraph Core[Core Layer]
        AGG[Aggregator]
        CFG[Config]
    end

    subgraph Clients[Client Layer]
        BC[BaseClient]

        subgraph Free[Free APIs]
            OA[OpenAlex]
            CR[Crossref]
            PM[PubMed]
        end

        subgraph Auth[Auth Required]
            SS[Semantic Scholar]
            EL[Elsevier]
            GS[Google Scholar]
            WOS[Web of Science]
        end
    end

    subgraph Extract[Extraction Layer]
        BE[BaseExtractor]
        PDF[PDFExtractor]
        HTML[HTMLExtractor]
        STR[StructuredExtractor]
    end

    subgraph Models[Data Models]
        P[Paper]
        A[Author]
        I[Institution]
        EC[ExtractedContent]
        PS[PaperStructure]
        BS[BookStructure]
    end

    subgraph External[External Services]
        API_OA[api.openalex.org]
        API_CR[api.crossref.org]
        API_SS[api.semanticscholar.org]
        API_EL[api.elsevier.com]
        API_GS[serpapi.com]
        API_PM[eutils.ncbi.nlm.nih.gov]
        API_WOS[api.clarivate.com]
    end

    CLI --> AGG
    API --> AGG
    AGG --> CFG
    AGG --> BC

    BC --> OA
    BC --> CR
    BC --> SS
    BC --> EL
    BC --> GS
    BC --> PM
    BC --> WOS

    OA --> API_OA
    CR --> API_CR
    SS --> API_SS
    EL --> API_EL
    GS --> API_GS
    PM --> API_PM
    WOS --> API_WOS

    CLI --> BE
    BE --> PDF
    BE --> HTML
    PDF --> STR

    OA --> P
    CR --> P
    SS --> P
    EL --> P
    GS --> P
    PM --> P
    WOS --> P

    PDF --> EC
    HTML --> EC
    STR --> PS
    STR --> BS
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
│   │   ├── google_scholar.py # SerpAPI client
│   │   ├── pubmed.py         # PubMed E-utilities client
│   │   └── wos.py            # Web of Science client
│   └── extractors/
│       ├── __init__.py
│       ├── base.py           # Base extractor
│       ├── pdf_extractor.py  # MinerU PDF extraction
│       ├── html_extractor.py # HTML extraction
│       └── structured_extractor.py  # Structured content parsing
├── tests/
├── docs/
├── config.example.yaml
├── pyproject.toml
├── CLAUDE.md                 # Development guide
└── README.md                 # User documentation
```

---

## Data Flow Diagrams

### Search Flow

```mermaid
flowchart TB
    subgraph Input
        Q[User Query]
    end

    subgraph Aggregator[Aggregator Layer]
        AGG[Aggregator.search]
        SRC[Source Selection]
    end

    subgraph Parallel[Parallel Execution]
        T1[OpenAlex]
        T2[Crossref]
        T3[Semantic Scholar]
        T4[PubMed]
        T5[Web of Science]
    end

    subgraph RateLimit[Rate Limiting]
        RL1[10 req/s]
        RL2[50 req/s]
        RL3[10 req/s]
        RL4[10 req/s]
        RL5[2 req/s]
    end

    subgraph APIs[External APIs]
        API1[api.openalex.org]
        API2[api.crossref.org]
        API3[api.semanticscholar.org]
        API4[eutils.ncbi.nlm.nih.gov]
        API5[api.clarivate.com]
    end

    subgraph Process[Response Processing]
        P1[Parse to Paper]
        P2[Parse to Paper]
        P3[Parse to Paper]
        P4[Parse XML to Paper]
        P5[Parse to Paper]
    end

    subgraph Merge[Result Aggregation]
        MERGE[Round-Robin Interleave]
        DEDUP[Deduplicate by DOI/Title]
    end

    subgraph Output
        SR[SearchResult]
    end

    Q --> AGG
    AGG --> SRC
    SRC --> T1 & T2 & T3 & T4 & T5

    T1 --> RL1 --> API1 --> P1
    T2 --> RL2 --> API2 --> P2
    T3 --> RL3 --> API3 --> P3
    T4 --> RL4 --> API4 --> P4
    T5 --> RL5 --> API5 --> P5

    P1 & P2 & P3 & P4 & P5 --> MERGE
    MERGE --> DEDUP
    DEDUP --> SR
```

### Paper Retrieval Flow

```mermaid
flowchart TB
    subgraph Input
        DOI[DOI Input]
    end

    subgraph Normalize[Normalization]
        NORM[normalize_doi]
    end

    subgraph Select[Client Selection]
        SEL{Try sources sequentially}
    end

    subgraph Requests[API Requests]
        R1[OpenAlex API]
        R2[Crossref API]
        R3[Semantic Scholar API]
        R4[PubMed ESearch + EFetch]
        R5[Web of Science API]
    end

    subgraph Parse[Response Parsing]
        PARSE[Extract & Normalize Fields]
    end

    subgraph Output
        PAPER[Paper Object]
    end

    DOI --> NORM
    NORM --> SEL
    SEL -->|OpenAlex| R1
    SEL -->|Crossref| R2
    SEL -->|Semantic Scholar| R3
    SEL -->|PubMed| R4
    SEL -->|WoS| R5
    R1 & R2 & R3 & R4 & R5 --> PARSE
    PARSE --> PAPER
```

### Paper Data Merge Flow

```mermaid
flowchart TB
    subgraph Input
        DOI[DOI with --merge flag]
    end

    subgraph Queries[Parallel Queries]
        Q1[OpenAlex.get_paper]
        Q2[Crossref.get_paper]
        Q3[SemanticScholar.get_paper]
        Q4[PubMed.get_paper]
    end

    subgraph Collected[Collected Papers]
        P1[OpenAlex: citations 77K]
        P2[Crossref: references 72]
        P3[S2: citations 162K]
        P4[PubMed: MeSH terms]
    end

    subgraph MergeLogic[Merge Logic]
        M1[Best abstract - longest]
        M2[Best authors - most complete]
        M3[Best citations - highest]
        M4[Best PDF URL - first available]
        M5[Keywords - union of all]
    end

    subgraph Output
        MERGED[Merged Paper]
    end

    DOI --> Q1 & Q2 & Q3 & Q4
    Q1 --> P1
    Q2 --> P2
    Q3 --> P3
    Q4 --> P4
    P1 & P2 & P3 & P4 --> M1 & M2 & M3 & M4 & M5
    M1 & M2 & M3 & M4 & M5 --> MERGED
```

---

## Extraction Pipeline

### PDF Extraction Flow

```mermaid
flowchart TB
    subgraph Input
        PDF[PDF File]
        URL[PDF URL]
    end

    subgraph Download
        DL[Download to temp file]
    end

    subgraph MinerU[MinerU Processing]
        MINERU[do_parse with pipeline backend]
        MD[markdown output]
        MJ[middle.json]
        CL[content_list.json]
        IMG[images folder]
    end

    subgraph Parse[Content Parsing]
        CB[Parse ContentBlocks]
        FIG[Extract Figures]
        TBL[Extract Tables]
    end

    subgraph Detect[Type Detection]
        DET{Detect Document Type}
        PAPER_CHECK[Has standard paper sections?]
        BOOK_CHECK[Has chapter headers?]
    end

    subgraph Build[Structure Building]
        PS_BUILD[Build PaperStructure]
        BS_BUILD[Build BookStructure]
    end

    subgraph Output
        EC[ExtractedContent]
        PS[PaperStructure]
        BS[BookStructure]
    end

    PDF --> MINERU
    URL --> DL --> MINERU
    MINERU --> MD & MJ & CL & IMG
    CL --> CB
    IMG --> FIG
    CL --> TBL
    CB --> DET
    DET -->|Paper| PAPER_CHECK --> PS_BUILD
    DET -->|Book| BOOK_CHECK --> BS_BUILD
    MD --> EC
    PS_BUILD --> PS
    BS_BUILD --> BS
```

### Paper Section Matching

```mermaid
flowchart LR
    subgraph Blocks[Content Blocks]
        B1[Title: Abstract]
        B2[Title: Introduction]
        B3[Title: Methods]
        B4[Title: Results]
        B5[Title: Discussion]
        B6[Title: Conclusion]
        B7[Title: References]
    end

    subgraph Patterns[Pattern Matching]
        PM[PAPER_SECTION_PATTERNS]
    end

    subgraph Structure[PaperStructure]
        PS_ABS[.abstract]
        PS_INT[.introduction]
        PS_MET[.methods]
        PS_RES[.results]
        PS_DIS[.discussion]
        PS_CON[.conclusion]
        PS_REF[.references_text]
    end

    B1 & B2 & B3 & B4 & B5 & B6 & B7 --> PM
    PM --> PS_ABS & PS_INT & PS_MET & PS_RES & PS_DIS & PS_CON & PS_REF
```

---

## Sequence Diagrams

### Multi-Source Search Sequence

```mermaid
sequenceDiagram
    participant U as User
    participant CLI as CLI
    participant AGG as Aggregator
    participant OA as OpenAlexClient
    participant CR as CrossrefClient
    participant SS as SemanticScholarClient
    participant RL as RateLimiter

    U->>CLI: search "machine learning"
    CLI->>AGG: search(query, sources, limit)

    par Parallel API Calls
        AGG->>OA: search(query)
        OA->>RL: acquire()
        RL-->>OA: OK
        OA->>OA: GET /works
        OA-->>AGG: List of Papers
    and
        AGG->>CR: search(query)
        CR->>RL: acquire()
        RL-->>CR: OK
        CR->>CR: GET /works
        CR-->>AGG: List of Papers
    and
        AGG->>SS: search(query)
        SS->>RL: acquire()
        RL-->>SS: OK
        SS->>SS: GET /paper/search
        SS-->>AGG: List of Papers
    end

    AGG->>AGG: Round-robin interleave
    AGG->>AGG: Deduplicate by DOI/title
    AGG-->>CLI: SearchResult
    CLI-->>U: Formatted results
```

### PDF Extraction Sequence

```mermaid
sequenceDiagram
    participant U as User
    participant CLI as CLI
    participant PE as PDFExtractor
    participant SE as StructuredExtractor
    participant MU as MinerU
    participant FS as FileSystem

    U->>CLI: extract paper.pdf
    CLI->>PE: extract_structured(path)
    PE->>SE: extract(path, auto)

    SE->>MU: do_parse(pdf_path)
    MU->>FS: Write middle.json
    MU->>FS: Write content_list.json
    MU->>FS: Write markdown
    MU->>FS: Write images/
    MU-->>SE: Output directory

    SE->>FS: Read content_list.json
    SE->>SE: Parse ContentBlocks
    SE->>SE: Detect document type

    alt Paper detected
        SE->>SE: Match sections to patterns
        SE->>SE: Build PaperStructure
        SE-->>PE: PaperStructure
    else Book detected
        SE->>SE: Build chapter hierarchy
        SE->>SE: Build BookStructure
        SE-->>PE: BookStructure
    end

    PE-->>CLI: Structure object
    CLI-->>U: Display sections
```

### Rate Limiting Sequence

```mermaid
sequenceDiagram
    participant C as Client
    participant RL as RateLimiter
    participant API as External API

    Note over RL: min_interval = 0.1s (10 req/s)
    Note over RL: last_request = 0

    C->>RL: acquire()
    RL->>RL: Calculate elapsed time
    alt elapsed >= min_interval
        RL->>RL: Update last_request
        RL-->>C: OK immediate
    else elapsed < min_interval
        RL->>RL: sleep(remaining)
        RL->>RL: Update last_request
        RL-->>C: OK after wait
    end
    C->>API: HTTP Request
    API-->>C: Response

    Note over C,API: Next request...

    C->>RL: acquire()
    RL->>RL: elapsed = 0.05s
    RL->>RL: sleep(0.05s)
    RL-->>C: OK
    C->>API: HTTP Request
```

---

## Data Models

### Core Models Relationship

```mermaid
classDiagram
    class Paper {
        +str title
        +list authors
        +str abstract
        +str doi
        +int year
        +str journal
        +str url
        +str pdf_url
        +str source
        +int citations_count
        +int references_count
        +bool open_access
        +list keywords
        +dict raw_data
    }

    class Author {
        +str name
        +str source_id
        +str source
        +list affiliations
        +str orcid
        +str url
        +int paper_count
        +int citation_count
        +int h_index
        +dict raw_data
    }

    class Institution {
        +str name
        +str source_id
        +str source
        +str country
        +str type
        +str url
        +int paper_count
        +int citation_count
        +dict raw_data
    }

    class SearchResult {
        +str query
        +list papers
        +int total_results
        +list sources_queried
        +dict errors
    }

    class ExtractedContent {
        +str markdown
        +dict metadata
        +list figures
        +list tables
        +str source_url
        +str source_type
    }

    SearchResult "1" --> "*" Paper : contains
    Paper "*" --> "*" Author : written by
    Author "*" --> "*" Institution : affiliated with
```

### Structured Content Models

```mermaid
classDiagram
    class ContentBlock {
        +str type
        +str content
        +int text_level
        +int page_idx
        +list bbox
        +dict raw_data
    }

    class Section {
        +str title
        +int level
        +list blocks
        +list subsections
        +get_text() str
        +get_all_text() str
    }

    class DocumentStructure {
        +str title
        +list sections
        +list all_blocks
        +list figures
        +list tables
        +dict metadata
        +str source_path
        +str document_type
        +get_section(pattern)
        +get_all_sections_flat()
    }

    class PaperStructure {
        +str abstract
        +str introduction
        +str methods
        +str results
        +str discussion
        +str conclusion
        +str references_text
        +str acknowledgments
        +list detected_authors
        +list detected_affiliations
    }

    class ChapterNode {
        +str title
        +int level
        +int page_start
        +str content
        +list blocks
        +list children
        +get_all_text() str
    }

    class BookStructure {
        +list chapters
        +str toc
        +get_chapter(pattern)
        +get_all_chapters_flat()
    }

    DocumentStructure <|-- PaperStructure
    DocumentStructure <|-- BookStructure
    Section "1" --> "*" ContentBlock
    Section "1" --> "*" Section : subsections
    DocumentStructure "1" --> "*" Section
    BookStructure "1" --> "*" ChapterNode
    ChapterNode "1" --> "*" ChapterNode : children
    ChapterNode "1" --> "*" ContentBlock
```

---

## API Client Capabilities

```mermaid
graph LR
    subgraph Free[Free APIs]
        OA[OpenAlex - Full features, Institutions]
        CR[Crossref - Journal/Funder metadata]
        PM[PubMed - MeSH terms, Related papers]
    end

    subgraph Auth[Auth Required]
        SS[Semantic Scholar - Recommendations, Batch]
        EL[Elsevier - Full-text, Institutions]
        GS[Google Scholar - Broadest coverage]
        WOS[Web of Science - Citation analysis]
    end
```

### Feature Matrix

| Feature | OpenAlex | Semantic Scholar | Crossref | Elsevier | Google Scholar | PubMed | Web of Science |
|---------|:--------:|:----------------:|:--------:|:--------:|:--------------:|:------:|:--------------:|
| search() | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| get_paper() | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| get_citations() | ✓ | ✓ | ✗ | ✓ | ✓ | ✓ | ✓ |
| get_references() | ✓ | ✓ | ✓ | ✗ | ✗ | ✓ | ✓ |
| search_authors() | ✓ | ✓ | ✗ | ✓ | ✓ | ✓ | ✓ |
| get_author() | ✓ | ✓ | ✗ | ✓ | ✓ | ✗ | ✗ |
| author_papers() | ✓ | ✓ | ✗ | ✓ | ✓ | ✓ | ✓ |
| institutions() | ✓ | ✗ | ✗ | ✓ | ✗ | ✗ | ✗ |
| get_journal() | ✗ | ✗ | ✓ | ✗ | ✗ | ✗ | ✗ |
| get_funder() | ✗ | ✗ | ✓ | ✗ | ✗ | ✗ | ✗ |
| recommendations() | ✗ | ✓ | ✗ | ✗ | ✗ | ✓ | ✓ |
| batch_lookup() | ✗ | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ |
| **Requires API Key** | ✗ | Optional | ✗ | ✓ | ✓ | Optional | ✓ |
| **Free** | ✓ | ✓ | ✓ | ✗ | ✗ | ✓ | ✗ |
| **Max per request** | 200 | 100 | 1000 | 25 | 20 | 10000 | 100 |
| **Rate limit** | ~10/s | ~0.33/s* | ~50/s | ~2/s | ~1/s | 3-10/s | 2/s |

*Semantic Scholar: 1/s with API key

---

## Rate Limiting Architecture

```mermaid
flowchart TB
    subgraph Config[Configuration]
        CFG[config.yaml rate_limits]
    end

    subgraph Init[Client Initialization]
        BC[BaseClient.__init__]
        RL_CREATE[Create RateLimiter]
    end

    subgraph Request[Request Flow]
        REQ[client._get or _post]
        ACQ[rate_limiter.acquire]
        LOCK[asyncio.Lock]
        WAIT{elapsed < min_interval?}
        SLEEP[asyncio.sleep]
        HTTP[httpx request]
    end

    CFG --> BC
    BC --> RL_CREATE
    REQ --> ACQ
    ACQ --> LOCK
    LOCK --> WAIT
    WAIT -->|Yes| SLEEP --> HTTP
    WAIT -->|No| HTTP
```

---

## Error Handling Flow

```mermaid
flowchart TB
    subgraph Request
        REQ[API Request]
    end

    subgraph Check[Error Detection]
        CHK{Response Status}
    end

    subgraph Errors[Error Types]
        E200[200 OK]
        E429[429 Too Many Requests]
        E401[401 Unauthorized]
        E404[404 Not Found]
        E500[5xx Server Error]
        ENET[Network Error]
    end

    subgraph Handle[Handling]
        PARSE[Parse Response]
        RETRY[Wait and Retry]
        LOG_ERR[Log to errors dict]
        RETURN_NONE[Return None]
    end

    subgraph Result[Aggregator Result]
        SR[SearchResult with errors]
    end

    REQ --> CHK
    CHK -->|200| E200 --> PARSE
    CHK -->|429| E429 --> RETRY --> REQ
    CHK -->|401| E401 --> LOG_ERR
    CHK -->|404| E404 --> RETURN_NONE
    CHK -->|5xx| E500 --> LOG_ERR
    CHK -->|Network| ENET --> LOG_ERR

    PARSE --> SR
    LOG_ERR --> SR
    RETURN_NONE --> SR
```

---

## Configuration

```yaml
# config.yaml

# API Keys
elsevier_api_key: "xxx"           # Required for Elsevier
serpapi_api_key: "xxx"            # Required for Google Scholar
semantic_scholar_api_key: "xxx"   # Optional, higher rate limits
pubmed_api_key: "xxx"             # Optional, 10 req/s vs 3 req/s
wos_api_key: "xxx"                # Required for Web of Science

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
  pubmed: 10
  wos: 2

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

---

## Extending the Library

### Adding a New Client

```mermaid
flowchart LR
    subgraph Step1[Step 1: Create Client]
        F1[clients/new_source.py]
    end

    subgraph Step2[Step 2: Implement Methods]
        F2[search, get_paper, _parse_paper]
    end

    subgraph Step3[Step 3: Register]
        F3[clients/__init__.py]
    end

    subgraph Step4[Step 4: Configure]
        F4[config.py rate_limits]
    end

    F1 --> F2 --> F3 --> F4
```

Example implementation:

```python
# src/paper_ladder/clients/new_source.py
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

---

## Platform Strengths

| Platform | Best For |
|----------|----------|
| OpenAlex | Free, comprehensive, institution/author data |
| Semantic Scholar | AI/CS papers, recommendations, arXiv support |
| Crossref | DOI authority, journal/funder metadata, 150M+ records |
| Elsevier | Commercial database, full-text access |
| Google Scholar | Broadest coverage (books, patents, conferences) |
| PubMed | Biomedical/life sciences, MeSH indexing, free |
| Web of Science | Citation analysis, impact metrics, multi-disciplinary |
