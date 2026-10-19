# ThesisLens

**AI Investment Research & Financial RAG Platform**

ThesisLens is a full-stack AI investment research platform that transforms public-company financial disclosures into structured, traceable, and source-grounded research.

Instead of relying on a language model's internal knowledge, ThesisLens builds a financial research knowledge base from SEC filings, XBRL financial data, institutional disclosures, market data, and normalized company evidence.

The platform combines deterministic financial analysis, hybrid retrieval, and a local LLM to help users understand:

- what a company does
- how its financial performance is changing
- what risks management has disclosed
- what recent company-specific developments matter
- what supports or weakens an investment thesis
- what investors should monitor next

The core design principle is simple:

> **The LLM synthesizes research evidence; it does not manufacture research data.**

---

## Key Features

### Company Research

Generate a structured, evidence-linked company research view containing:

- Investment Story
- Business Overview
- Financial Snapshot
- Bull Case
- Key Risks
- What Investors Should Watch
- Recent company-specific disclosures
- Institutional ownership
- Detailed SEC evidence
- Source coverage and provenance

Company Research is designed around a consistent SEC-backed baseline so that supported issuers can be analyzed using the same research structure rather than depending on inconsistent third-party data availability.

---

### AI Research / Ask

Users can ask financial-research questions such as:

- What are the biggest risks of investing in this company?
- How has revenue changed over time?
- What does management say about competition?
- What risks could weaken the investment thesis?
- Compare two companies based on their filings.
- What should investors monitor next?

ThesisLens retrieves relevant evidence before generating the answer.

Responses can combine:

- SEC filing evidence
- financial facts
- risk disclosures
- business descriptions
- company-specific developments
- institutional disclosures

This allows answers to remain grounded in the underlying research evidence.

---

### Financial Research Knowledge Base

ThesisLens maintains a domain-specific financial research knowledge base built from public-company evidence.

The knowledge base is not a single database.

It is a logical evidence layer composed of structured financial facts, normalized research records, document chunks, lexical indexes, vector indexes, cached research snapshots, and source provenance.

Core knowledge sources include:

- SEC annual filings
- SEC quarterly filings
- SEC current reports
- SEC XBRL / CompanyFacts
- institutional ownership disclosures
- normalized business evidence
- normalized risk evidence
- company-specific updates
- optional verified public-company sources

---

## System Architecture

```text
                    Public Financial Sources
                             │
          ┌──────────────────┼──────────────────┐
          │                  │                  │
          ▼                  ▼                  ▼
     SEC Filings         SEC XBRL /        Institutional
   10-K / 10-Q /        CompanyFacts        Disclosures
    8-K / 20-F
          │                  │                  │
          └──────────────────┼──────────────────┘
                             ▼
                  Ingestion & Normalization
                             │
                  ┌──────────┴──────────┐
                  │                     │
                  ▼                     ▼
          Document Processing      Structured Facts
          Parsing / Chunking       Financial Metrics
          Section Detection        Ownership Data
          Evidence Metadata
                  │                     │
                  └──────────┬──────────┘
                             ▼
              Financial Research Knowledge Base
                             │
          ┌──────────────────┼──────────────────┐
          │                  │                  │
          ▼                  ▼                  ▼
       BM25 Index       Qdrant Vector      Normalized
                         Search Index       Evidence
          │                  │                  │
          └──────────────────┼──────────────────┘
                             ▼
                  Hybrid Retrieval Layer
                             │
                             ▼
                Research Context / Routing
                             │
               ┌─────────────┴─────────────┐
               │                           │
               ▼                           ▼
      Deterministic Python            Local LLM
          Analysis                  Qwen3:4B / Ollama
               │                           │
               └─────────────┬─────────────┘
                             ▼
                    Research Synthesis
                             │
          ┌──────────────────┼──────────────────┐
          │                  │                  │
          ▼                  ▼                  ▼
     Company Research       Ask           Risk Analysis
          │
          ▼
    Investment Insights
```

---

## Architecture Layers

ThesisLens is organized conceptually into five layers.

### 1. Data Sources

Raw financial and company information enters ThesisLens from public sources.

Examples include:

- SEC EDGAR filings
- SEC XBRL / CompanyFacts
- institutional 13F disclosures
- market data
- official company-specific disclosures
- optional verified issuer feeds

Raw source data is not treated as final research.

It must first be parsed, normalized, validated, and connected to provenance.

---

### 2. Knowledge Ingestion & Normalization

The ingestion layer converts raw documents and structured data into usable research evidence.

It includes:

- SEC filing discovery
- filing retrieval
- form-aware document parsing
- SEC item-boundary detection
- table-of-contents avoidance
- Business section extraction
- Risk Factors extraction
- exact evidence-span tracking
- financial fact normalization
- evidence chunking
- metadata generation
- accession tracking
- source URL preservation
- parser-versioned caching
- background annual-evidence hydration

Annual business and risk evidence are handled separately from current-period financial analysis.

For example:

```text
Latest annual filing
        │
        ├── Business Overview
        └── Annual Risk Factors

Latest relevant filing / XBRL
        │
        └── Current Financial Analysis
```

This avoids treating the latest quarterly filing as a replacement for longer-term annual business context.

---

### 3. Financial Research Knowledge Base

Processed evidence becomes part of the ThesisLens Financial Research Knowledge Base.

```text
Financial Research Knowledge Base
│
├── Filing evidence chunks
├── Business overview evidence
├── Risk-factor evidence
├── Financial facts
├── Current-report evidence
├── Institutional disclosures
├── Company-specific updates
├── Research snapshots
├── BM25 lexical index
└── Qdrant vector index
```

Qdrant is one retrieval index within the knowledge base.

It is not the knowledge base itself.

Likewise, BM25 is used as a lexical retrieval mechanism alongside semantic vector search.

---

### 4. Retrieval & Research Orchestration

When a user asks a research question, ThesisLens determines which evidence is relevant.

The retrieval layer combines:

- BM25 lexical retrieval
- semantic embeddings
- Qdrant vector similarity search
- structured financial lookup
- deterministic company-context selection
- research intent routing

This hybrid approach allows ThesisLens to retrieve both:

- exact terminology such as financial metrics, filing phrases, and company-specific terms
- semantically related evidence even when the wording differs

Conceptually:

```text
User Question
      │
      ▼
Intent / Research Context
      │
      ▼
Hybrid Retrieval
      │
      ├── BM25
      ├── Vector Search
      ├── Financial Facts
      └── Structured Evidence
      │
      ▼
Evidence Bundle
```

---

### 5. Analysis & Product Layer

The final layer converts evidence into user-facing research.

Deterministic Python logic is responsible for reliable calculations and evidence selection.

The local LLM is primarily responsible for synthesis and explanation.

The model is used to:

- explain financial evidence
- summarize relevant filing evidence
- compare companies
- explain investment risks
- synthesize research context
- answer source-grounded questions

The model is not treated as a financial fact provider.

---

## Company Research Model

The Company Research experience follows a consistent SEC-first research baseline.

### Investment Story

The top-level research narrative focuses on:

- Why It Matters
- Bull Case
- Key Risks
- What Investors Should Watch
- Evidence Gaps

The Investment Story contains concise synthesis rather than duplicating complete filing excerpts.

---

### Business Overview

Business context is primarily derived from validated annual filing sections such as:

- 10-K Item 1
- relevant 20-F business sections

The objective is to explain what the company says it does using authoritative company disclosures.

---

### Financial Snapshot

Core financial research focuses on consistently available and decision-useful metrics such as:

- revenue
- revenue growth
- gross margin
- operating performance
- free cash flow
- cash
- debt

Structured calculations are handled deterministically in Python.

---

### Key Risks

Risk evidence is derived from validated annual risk disclosures.

Examples include:

- 10-K Item 1A
- relevant 20-F risk sections

Each displayed risk can retain:

- evidence ID
- filing identity
- filing date
- accession
- parent section
- exact supporting evidence span
- original source URL

Risk titles are evidence-derived when the underlying filing supports the classification.

When specificity is not defensible, ThesisLens falls back to a conservative generic risk label rather than inventing a stronger conclusion.

---

### Recent Company Developments

Recent company-specific developments primarily rely on verified public disclosures such as:

- 8-K
- 6-K
- recent quarterly filings
- supported official company updates

ThesisLens does not substitute unrelated market-wide headlines for company-specific developments.

---

### What Investors Should Watch

The research narrative uses human-readable investment themes such as:

- whether revenue growth remains durable
- whether margins remain resilient
- whether free cash flow remains strong
- whether capital requirements increase
- whether regulatory pressure becomes more material

Separate trackable research ideas may retain explicit numeric thresholds.

This separates human-readable research interpretation from machine-trackable monitoring rules.

---

## Evidence Coverage States

Company Research distinguishes between different levels of evidence availability.

### Complete Baseline

A company has sufficient core evidence such as:

- verified company identity
- annual business evidence
- annual risk evidence
- usable core financial evidence

A full investment-research narrative can be produced.

---

### Preliminary Baseline

Useful financial evidence exists, but part of the broader business or risk context is still incomplete.

The research remains conservative and avoids describing the company as clearly positive or negative.

---

### Insufficient Baseline

Too little reliable evidence is currently available to form a meaningful company-level investment assessment.

ThesisLens explicitly communicates this rather than fabricating missing analysis.

---

## Automatic Annual Evidence Hydration

Company Research should not depend on whether a user previously opened a company.

When annual research evidence is missing but SEC annual filing metadata is available, ThesisLens can use its background refresh pipeline to retrieve and prepare the missing research evidence.

Conceptually:

```text
Company Opened
      │
      ▼
Check Annual Research Evidence
      │
      ├── Available ───────────────► Continue
      │
      └── Missing
             │
             ▼
       Locate Annual Filing
             │
             ▼
         Fetch Filing
             │
             ▼
       Parse Business/Risks
             │
             ▼
       Generate Evidence
             │
             ▼
          Cache Result
             │
             ▼
       Research Available
```

This keeps company coverage consistent without requiring destructive cache resets.

---

## Hybrid RAG Pipeline

ThesisLens uses hybrid retrieval rather than relying exclusively on semantic vector search.

```text
Question
   │
   ├── BM25 lexical retrieval
   │
   ├── Vector similarity retrieval
   │
   ├── Structured financial lookup
   │
   └── Company evidence selection
   │
   ▼
Ranked Evidence Context
   │
   ▼
Local LLM
   │
   ▼
Source-Grounded Answer
```

BM25 helps retrieve exact financial terminology and filing language.

Vector search helps retrieve semantically related evidence.

Combining both improves retrieval robustness across financial research questions.

---

## Local LLM

ThesisLens can run a local language model through Ollama.

Current development uses:

```text
Qwen3:4B
```

The local model is used for research synthesis and question answering while the supporting facts remain grounded in retrieved evidence.

This allows the platform to operate without requiring every research request to be sent to an external hosted LLM API.

---

## Deterministic Analysis

Not every task should be delegated to an LLM.

ThesisLens uses deterministic Python logic for areas where reproducibility is more important than generative flexibility.

Examples include:

- financial calculations
- period comparisons
- growth calculations
- evidence selection
- filing selection
- research-state classification
- source provenance
- fallback behavior
- cache handling

This provides predictable behavior and prevents the language model from becoming the source of numerical financial facts.

---

## Evidence Provenance

Traceability is a core design requirement.

Detailed research evidence may include metadata such as:

```text
Company
Form
Filing Date
Fiscal Period
Accession
Section
Parent Section Span
Exact Evidence Span
Original SEC URL
Evidence ID
```

This allows users to move from a synthesized research conclusion back to the underlying company disclosure.

---

## Source Reliability Philosophy

ThesisLens prioritizes:

1. consistency
2. traceability
3. conservative interpretation
4. authoritative public evidence

over maximizing the number of external data providers.

The core Company Research experience does not require:

- paid analyst APIs
- analyst price targets
- consensus estimates
- general financial news APIs
- third-party sentiment providers

These may be added as optional enrichment in the future but are not required for the SEC-backed research baseline.

---

## Institutional Ownership

ThesisLens also analyzes selected public institutional disclosures.

The system can surface reported position changes such as:

- increased
- reduced
- new
- exited
- unchanged

Institutional filings are treated as delayed disclosure context.

They are not treated as real-time trading activity or direct evidence of investor intent.

---

## Market Pulse

Market Pulse provides a broader view of market-level developments.

It is kept separate from company-specific Company Research so that:

- company research focuses on company evidence
- market-wide developments remain in the market intelligence workflow

This separation prevents unrelated market headlines from being presented as company-specific research evidence.

---

## Portfolio Network

Portfolio Network explores relationships between companies and tracked institutional managers using public ownership disclosures.

It provides another research perspective without treating disclosed institutional holdings as investment recommendations.

---

## Frontend

The frontend is built with:

- Next.js
- React
- TypeScript

The interface provides:

- company research
- AI research
- market intelligence
- institutional ownership views
- research tracking
- source provenance
- responsive desktop/mobile layouts

---

## Backend

The backend is built with:

- Python
- FastAPI

Responsibilities include:

- SEC ingestion
- filing parsing
- XBRL processing
- evidence normalization
- research context construction
- hybrid retrieval
- vector search
- deterministic financial analysis
- cache management
- research synthesis
- API delivery

---

## Core Technology Stack

### Backend

- Python
- FastAPI
- SQLite

### Frontend

- Next.js
- React
- TypeScript

### Retrieval

- BM25 / BM25S
- semantic embeddings
- Qdrant vector database
- hybrid retrieval

### AI

- Ollama
- Qwen3:4B
- retrieval-augmented generation

### Financial Data

- SEC EDGAR
- SEC XBRL / CompanyFacts
- public institutional disclosures
- supported market-data sources
- optional issuer-verified sources

---

## Example Research Flow

A question such as:

```text
What are the biggest risks of investing in RKLB?
```

can follow a workflow conceptually similar to:

```text
User Question
      │
      ▼
Identify Company + Research Intent
      │
      ▼
Retrieve Financial Evidence
      │
      ├── Business Context
      ├── Financial Performance
      ├── Annual Risk Factors
      ├── Recent Company Disclosures
      └── Institutional Context
      │
      ▼
Rank Relevant Evidence
      │
      ▼
Research Synthesis
      │
      ├── Bull Case
      ├── Key Risks
      ├── What To Watch
      └── Evidence Gaps
      │
      ▼
Source-Grounded Answer
```

The objective is not merely to summarize documents.

The objective is to connect evidence into a useful investment-research view.

---

## Why Not Let the LLM Do Everything?

Financial research contains information that should remain deterministic and verifiable.

For example:

- reported revenue should come from financial data
- filing dates should come from filing metadata
- risk evidence should come from disclosed risk language
- institutional positions should come from reported filings

The language model is therefore used primarily to interpret and communicate retrieved research evidence.

This reduces unsupported financial claims and improves reproducibility.

---

## Design Principles

### Evidence First

Important research conclusions should originate from traceable evidence.

### Deterministic Where Possible

Financial calculations and evidence selection should not depend on generative randomness.

### Conservative When Evidence Is Missing

Missing evidence is not treated as positive or negative evidence.

### Source-Grounded AI

The model receives relevant research context before generating company-specific answers.

### Consistency Over Maximum Breadth

A dependable research baseline across companies is preferred over a highly detailed experience for only a small subset of issuers.

---

## Current Limitations

ThesisLens is an active research project and has several intentional limitations.

- General company-news coverage is not guaranteed.
- Verified analyst ratings and price targets are not required for the core research workflow.
- Some unusual or malformed filings may not support reliable section extraction.
- Some foreign issuer filings use different disclosure structures.
- Public institutional disclosures are delayed and should not be interpreted as real-time holdings.
- Missing evidence is intentionally not replaced with model-generated facts.
- Market-data sources may occasionally return delayed or cached values.
- ThesisLens is currently designed primarily as a local research application rather than a production multi-tenant financial platform.

---

## Future Direction

Potential future improvements include:

### Research Tool Calling

Expose existing research capabilities as explicit tools such as:

```text
get_company_profile()
get_financial_evidence()
get_business_evidence()
get_risk_evidence()
get_recent_company_events()
search_company_filings()
retrieve_company_evidence()
```

A research planner could dynamically choose the required tools based on the user's question.

---

### Agentic Research

A future research agent could perform multi-step research such as:

```text
Question
   ↓
Plan Required Evidence
   ↓
Call Research Tools
   ↓
Identify Missing Evidence
   ↓
Retrieve Additional Evidence
   ↓
Cross-Analyze Sources
   ↓
Generate Research Conclusion
```

The existing financial research knowledge base can support this architecture without replacing the deterministic Company Research baseline.

---

### Cross-Source Research

Future versions may compare:

- financial performance
- filed risks
- recent company developments
- institutional disclosures
- optional verified third-party research

to identify:

- supporting evidence
- contradictions
- catalysts
- weakening assumptions
- unresolved investment questions

---

## Validation

The project includes automated validation across the backend and frontend.

Current validation workflows include:

- Ruff
- Python tests
- TypeScript validation
- Vitest
- Next.js production build
- Playwright desktop/mobile tests
- Git diff validation
- credential and sensitive-file checks

Research-quality regression fixtures are used to test representative filing structures and evidence behavior without introducing ticker-specific production logic.

---

## Local Development

Clone the repository:

```bash
git clone https://github.com/SsONg6993/financial-report-rag.git
cd financial-report-rag
```

On Windows, the project can be started using:

```powershell
.\start-thesislens.ps1
```

Then open:

```text
http://localhost:3000
```

Configuration is handled through the project's environment settings.

Do not commit local `.env`, database, cache, or runtime files containing machine-specific state.

---

## Project Status

ThesisLens currently includes:

- full-stack Company Research
- SEC filing ingestion
- XBRL financial analysis
- annual business and risk extraction
- evidence provenance
- financial research knowledge base
- BM25 + vector hybrid retrieval
- Qdrant
- local Ollama/Qwen research synthesis
- institutional ownership analysis
- Market Pulse
- Portfolio Network
- AI research / Ask
- deterministic fallback behavior
- background evidence refresh
- desktop and mobile regression testing

Development continues to focus on improving research consistency, evidence coverage, retrieval quality, and source-grounded investment synthesis.

---

## Disclaimer

ThesisLens is an educational and research project.

It does not provide financial, investment, legal, or tax advice.

Information may be incomplete, delayed, or subject to interpretation.

Users should review original company filings and perform their own research before making investment decisions.
