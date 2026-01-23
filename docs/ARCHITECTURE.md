# Paper-Ladder Architecture

## System Overview

Paper-Ladder is a Python library for academic paper search and content extraction. It provides a unified interface to multiple academic APIs with automatic rate limiting, deduplication, and result aggregation.

## System Architecture Diagram

```mermaid
graph TB
    subgraph "User Interface"
        CLI[CLI<br/>typer]
        API[Python API<br/>paper_ladder]
    end

    subgraph "Core Layer"
        AGG[Aggregator<br/>Multi-source coordination]
        CFG[Config<br/>YAML configuration]
    end

    subgraph "Client Layer"
        BC[BaseClient<br/>Abstract interface]

        subgraph "Free APIs"
            OA[OpenAlex<br/>100K/day]
            CR[Crossref<br/>50 req/s]
            PM[PubMed<br/>3-10 req/s]
        end

        subgraph "Auth Required"
            SS[Semantic Scholar<br/>Optional key]
            EL[Elsevier/Scopus<br/>API key]
            GS[Google Scholar<br/>SerpAPI]
            WOS[Web of Science<br/>Institutional]
        end
    end

    subgraph "Extraction Layer"
        BE[BaseExtractor]
        PDF[PDFExtractor<br/>MinerU]
        HTML[HTMLExtractor<br/>BeautifulSoup]
        STR[StructuredExtractor<br/>Section parsing]
    end

    subgraph "Data Models"
        P[Paper]
        A[Author]
        I[Institution]
        EC[ExtractedContent]
        PS[PaperStructure]
        BS[BookStructure]
    end

    subgraph "External Services"
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
        Q[User Query<br/>"machine learning"]
    end

    subgraph "Aggregator Layer"
        AGG[Aggregator.search]
        SRC[Source Selection<br/>openalex, crossref, semantic_scholar, pubmed, wos]
    end

    subgraph "Parallel Execution"
        direction LR
        T1[Task 1<br/>OpenAlex]
        T2[Task 2<br/>Crossref]
        T3[Task 3<br/>Semantic Scholar]
        T4[Task 4<br/>PubMed]
        T5[Task 5<br/>Web of Science]
    end

    subgraph "Rate Limiting"
        RL1[RateLimiter<br/>10 req/s]
        RL2[RateLimiter<br/>50 req/s]
        RL3[RateLimiter<br/>10 req/s]
        RL4[RateLimiter<br/>10 req/s]
        RL5[RateLimiter<br/>2 req/s]
    end

    subgraph "External APIs"
        API1[api.openalex.org]
        API2[api.crossref.org]
        API3[api.semanticscholar.org]
        API4[eutils.ncbi.nlm.nih.gov]
        API5[api.clarivate.com]
    end

    subgraph "Response Processing"
        P1[Parse JSON<br/>→ Paper objects]
        P2[Parse JSON<br/>→ Paper objects]
        P3[Parse JSON<br/>→ Paper objects]
        P4[Parse XML<br/>→ Paper objects]
        P5[Parse JSON<br/>→ Paper objects]
    end

    subgraph "Result Aggregation"
        MERGE[Round-Robin<br/>Interleaving]
        DEDUP[Deduplication<br/>by DOI & Title]
    end

    subgraph Output
        SR[SearchResult<br/>papers, total, sources, errors]
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
        DOI["DOI: 10.1038/nature14539"]
    end

    subgraph "Normalization"
        NORM[normalize_doi<br/>Remove URL prefixes<br/>Lowercase]
    end

    subgraph "Client Selection"
        SEL{Try sources<br/>sequentially}
    end

    subgraph "API Requests"
        R1["OpenAlex<br/>GET /works/https://doi.org/..."]
        R2["Crossref<br/>GET /works/10.1038/..."]
        R3["Semantic Scholar<br/>GET /paper/DOI:..."]
        R4["PubMed<br/>ESearch + EFetch"]
        R5["Web of Science<br/>GET /query?usrQuery=DO=..."]
    end

    subgraph "Response Parsing"
        PARSE[Parse API Response<br/>Extract: title, authors, abstract<br/>Normalize: DOI, year, journal<br/>Store: raw_data]
    end

    subgraph Output
        PAPER["Paper Object<br/>title, authors, doi, year<br/>citations_count, source"]
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
        DOI["DOI: 10.1038/nature14539<br/>--merge flag"]
    end

    subgraph "Parallel Queries"
        Q1[OpenAlex.get_paper]
        Q2[Crossref.get_paper]
        Q3[SemanticScholar.get_paper]
        Q4[PubMed.get_paper]
    end

    subgraph "Collected Papers"
        P1["Paper from OpenAlex<br/>citations: 77,000"]
        P2["Paper from Crossref<br/>references: 72"]
        P3["Paper from S2<br/>citations: 162,000"]
        P4["Paper from PubMed<br/>MeSH terms"]
    end

    subgraph "Merge Logic"
        M1[Best abstract<br/>longest]
        M2[Best authors<br/>most complete]
        M3[Best citations<br/>highest count]
        M4[Best PDF URL<br/>first available]
        M5[Merged keywords<br/>union of all]
    end

    subgraph Output
        MERGED["Merged Paper<br/>Best data from all sources"]
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
        PDF[PDF File<br/>paper.pdf]
        URL[PDF URL<br/>https://...]
    end

    subgraph "Download"
        DL[Download to<br/>temp file]
    end

    subgraph "MinerU Processing"
        MINERU[MinerU do_parse<br/>backend=pipeline]
        MD[markdown output]
        MJ[middle.json<br/>layout info]
        CL[content_list.json<br/>content blocks]
        IMG[images/<br/>figures as PNG/JPG]
    end

    subgraph "Content Parsing"
        CB[Parse ContentBlocks<br/>type, content, level]
        FIG[Extract Figures]
        TBL[Extract Tables]
    end

    subgraph "Type Detection"
        DET{Detect Type}
        PAPER_CHECK["Has Abstract, Introduction<br/>Methods, Results, Discussion?"]
        BOOK_CHECK["Has 'Chapter X' headers?<br/>Numbered sections 1.1, 2.3?<br/>> 50 pages?"]
    end

    subgraph "Structure Building"
        PS_BUILD[Build PaperStructure<br/>Match sections to patterns]
        BS_BUILD[Build BookStructure<br/>Create chapter hierarchy]
    end

    subgraph Output
        EC[ExtractedContent<br/>markdown, metadata<br/>figures, tables]
        PS[PaperStructure<br/>abstract, intro, methods<br/>results, discussion]
        BS[BookStructure<br/>chapters hierarchy<br/>table of contents]
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
    subgraph "Content Blocks"
        B1["Title: Abstract"]
        B2["Text: In this paper..."]
        B3["Title: 1. Introduction"]
        B4["Text: Machine learning..."]
        B5["Title: 2. Methods"]
        B6["Title: 3. Results"]
        B7["Title: 4. Discussion"]
        B8["Title: 5. Conclusion"]
        B9["Title: References"]
    end

    subgraph "Pattern Matching"
        PM["PAPER_SECTION_PATTERNS<br/>abstract: r'^abstract'<br/>introduction: r'^1?\\.?\\s*introduction'<br/>methods: r'^2?\\.?\\s*(methods|methodology)'<br/>results: r'^3?\\.?\\s*results'<br/>discussion: r'^4?\\.?\\s*discussion'<br/>conclusion: r'^5?\\.?\\s*conclusion'<br/>references: r'^references'"]
    end

    subgraph "PaperStructure"
        PS_ABS[".abstract"]
        PS_INT[".introduction"]
        PS_MET[".methods"]
        PS_RES[".results"]
        PS_DIS[".discussion"]
        PS_CON[".conclusion"]
        PS_REF[".references_text"]
    end

    B1 & B2 --> PM
    B3 & B4 --> PM
    B5 --> PM
    B6 --> PM
    B7 --> PM
    B8 --> PM
    B9 --> PM

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
        OA->>OA: GET /works?search=...
        OA-->>AGG: [Paper, Paper, ...]
    and
        AGG->>CR: search(query)
        CR->>RL: acquire()
        RL-->>CR: OK
        CR->>CR: GET /works?query=...
        CR-->>AGG: [Paper, Paper, ...]
    and
        AGG->>SS: search(query)
        SS->>RL: acquire()
        RL-->>SS: OK
        SS->>SS: GET /paper/search?query=...
        SS-->>AGG: [Paper, Paper, ...]
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
    PE->>SE: extract(path, "auto")

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
    RL->>RL: elapsed = now - last_request
    alt elapsed >= min_interval
        RL->>RL: last_request = now
        RL-->>C: OK (immediate)
    else elapsed < min_interval
        RL->>RL: sleep(min_interval - elapsed)
        RL->>RL: last_request = now
        RL-->>C: OK (after wait)
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
        +list~str~ authors
        +str|None abstract
        +str|None doi
        +int|None year
        +str|None journal
        +str|None url
        +str|None pdf_url
        +str source
        +int|None citations_count
        +int|None references_count
        +bool|None open_access
        +list~str~ keywords
        +dict raw_data
        +__hash__() int
        +__eq__(other) bool
    }

    class Author {
        +str name
        +str|None source_id
        +str|None source
        +list~str~ affiliations
        +str|None orcid
        +str|None url
        +int|None paper_count
        +int|None citation_count
        +int|None h_index
        +dict raw_data
    }

    class Institution {
        +str name
        +str|None source_id
        +str|None source
        +str|None country
        +str|None type
        +str|None url
        +int|None paper_count
        +int|None citation_count
        +dict raw_data
    }

    class SearchResult {
        +str query
        +list~Paper~ papers
        +int total_results
        +list~str~ sources_queried
        +dict~str,str~ errors
    }

    class ExtractedContent {
        +str markdown
        +dict metadata
        +list~str~ figures
        +list~str~ tables
        +str|None source_url
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
        +int|None page_idx
        +list|None bbox
        +dict raw_data
    }

    class Section {
        +str title
        +int level
        +list~ContentBlock~ blocks
        +list~Section~ subsections
        +get_text() str
        +get_all_text() str
    }

    class DocumentStructure {
        +str|None title
        +list~Section~ sections
        +list~ContentBlock~ all_blocks
        +list~str~ figures
        +list~str~ tables
        +dict metadata
        +str|None source_path
        +str document_type
        +get_section(pattern) Section
        +get_all_sections_flat() list
    }

    class PaperStructure {
        +str|None abstract
        +str|None introduction
        +str|None methods
        +str|None results
        +str|None discussion
        +str|None conclusion
        +str|None references_text
        +str|None acknowledgments
        +list~str~ detected_authors
        +list~str~ detected_affiliations
    }

    class ChapterNode {
        +str title
        +int level
        +int|None page_start
        +str|None content
        +list~ContentBlock~ blocks
        +list~ChapterNode~ children
        +get_all_text() str
    }

    class BookStructure {
        +list~ChapterNode~ chapters
        +str|None toc
        +get_chapter(pattern) ChapterNode
        +get_all_chapters_flat() list
    }

    DocumentStructure <|-- PaperStructure
    DocumentStructure <|-- BookStructure
    Section "1" --> "*" ContentBlock
    Section "1" --> "*" Section : subsections
    DocumentStructure "1" --> "*" Section
    DocumentStructure "1" --> "*" ContentBlock
    BookStructure "1" --> "*" ChapterNode
    ChapterNode "1" --> "*" ChapterNode : children
    ChapterNode "1" --> "*" ContentBlock
```

---

## API Client Capabilities

```mermaid
graph LR
    subgraph "Free APIs"
        OA[OpenAlex<br/>✓ Full features<br/>✓ Institutions<br/>100K/day]
        CR[Crossref<br/>✓ Journal/Funder<br/>✗ Citations<br/>50 req/s]
        PM[PubMed<br/>✓ MeSH terms<br/>✓ Related papers<br/>3-10 req/s]
    end

    subgraph "Auth Required"
        SS[Semantic Scholar<br/>✓ Recommendations<br/>✓ Batch lookup<br/>Optional key]
        EL[Elsevier<br/>✓ Full-text<br/>✓ Institutions<br/>API key]
        GS[Google Scholar<br/>✓ Broadest coverage<br/>✓ Patents/Books<br/>Paid]
        WOS[Web of Science<br/>✓ Citation analysis<br/>✓ Impact metrics<br/>Institutional]
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
    subgraph "Configuration"
        CFG["config.yaml<br/>rate_limits:<br/>  openalex: 10<br/>  crossref: 50<br/>  pubmed: 10<br/>  wos: 2"]
    end

    subgraph "Client Initialization"
        BC[BaseClient.__init__]
        RL_CREATE["Create RateLimiter<br/>min_interval = 1/rate"]
    end

    subgraph "Request Flow"
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
    subgraph "Request"
        REQ[API Request]
    end

    subgraph "Error Detection"
        CHK{Response Status}
    end

    subgraph "Error Types"
        E200[200 OK]
        E429[429 Too Many Requests]
        E401[401 Unauthorized]
        E404[404 Not Found]
        E500[5xx Server Error]
        ENET[Network Error]
    end

    subgraph "Handling"
        PARSE[Parse Response]
        RETRY[Wait & Retry]
        LOG_ERR[Log to errors dict]
        RETURN_NONE[Return None]
    end

    subgraph "Aggregator Result"
        SR["SearchResult<br/>papers: [...valid results...]<br/>errors: {source: error_msg}"]
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
    subgraph "Step 1: Create Client"
        F1["clients/new_source.py<br/>class NewSourceClient(BaseClient)"]
    end

    subgraph "Step 2: Implement Methods"
        F2["search(query, limit, offset)<br/>get_paper(identifier)<br/>_parse_paper(data)"]
    end

    subgraph "Step 3: Register"
        F3["clients/__init__.py<br/>CLIENTS['new_source'] = NewSourceClient"]
    end

    subgraph "Step 4: Configure"
        F4["config.py<br/>new_source: float = 10"]
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
