# CURATOR — AI-Powered Medical Curriculum Explorer

**An RAG-based knowledge exploration platform for Koç University School of Medicine — now including the MİMAR research prototype (TÜBİTAK 1001): expert-supervised curriculum mapping with locked, pre-registered evaluation.**

> Proposal: KU-PSRF 2025 | Team: Dr Gonenli, Prof Mutlu, Prof Gursoy, Prof Demir, Ruken Esmer

---

## Architecture

```
curator/
├── backend/           # FastAPI + LangGraph RAG pipeline
│   ├── app/
│   │   ├── api/       # REST endpoints
│   │   ├── core/      # Config, logging, security
│   │   ├── rag/       # LangGraph agents (Router → Retrieval → Generation)
│   │   ├── graph/     # Neo4j knowledge graph client
│   │   ├── models/    # Pydantic schemas
│   │   ├── services/  # Business logic
│   │   └── utils/     # Helpers (embeddings, text processing)
│   └── data/          # Curriculum corpus & embeddings
├── frontend/          # React + Vite
│   └── src/
│       ├── components/
│       ├── hooks/
│       ├── services/
│       └── store/
├── scripts/           # Ingestion, seeding, eval scripts
└── docker-compose.yml
```

## Stack

| Layer | Technology |
|---|---|
| Backend API | FastAPI (Python 3.11) |
| RAG Orchestration | LangGraph |
| LLM | Anthropic Claude / OpenAI GPT-4 |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) |
| Vector Store | FAISS (local) / Pinecone (production) |
| Knowledge Graph | Neo4j (AuraDB) |
| PDF Parsing | PyMuPDF |
| NLP | spaCy |
| Frontend | React 18 + Vite + TypeScript |
| Graph Viz | react-force-graph-2d |
| Containerisation | Docker Compose |

## Quick Start

### 1. Prerequisites
- Python 3.11+
- Node.js 18+
- Docker & Docker Compose
- Neo4j AuraDB account (or local Neo4j)

### 2. Environment Setup

```bash
cp .env.example .env
# Fill in your API keys and Neo4j credentials
```

### 3. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Seed the Curriculum Knowledge Graph

```bash
# Ingest curriculum data into Neo4j + build FAISS index
python scripts/ingest_curriculum.py
```

### 5. Run (Development)

```bash
# Start all services with Docker Compose
docker-compose up

# OR run individually:
cd backend && uvicorn app.main:app --reload --port 8000
cd frontend && npm install && npm run dev
```

### 6. Access

| Service | URL |
|---|---|
| API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |
| Frontend | http://localhost:5173 |
| Neo4j Browser | http://localhost:7474 |

## RAG Pipeline

```
User Query
    │
    ▼
┌─────────────┐
│ Router Agent │  ← Classifies: factual / relational / pathway / advisory
└──────┬──────┘
       │
   ┌───┴────────────────────────┐
   ▼            ▼               ▼
Graph        Vector          Keyword
Retriever    Retriever       Retriever
(Cypher)     (FAISS)         (BM25)
   │            │               │
   └───────┬────┘               │
           │◄───────────────────┘
           ▼
   ┌────────────────┐
   │ Fusion & Rank  │  ← RRF (Reciprocal Rank Fusion)
   └───────┬────────┘
           ▼
   ┌────────────────┐
   │ Generation     │  ← Claude / GPT-4 + curriculum context
   │ Agent          │
   └───────┬────────┘
           ▼
   ┌────────────────┐
   │ Validation     │  ← Hallucination check, citation verify
   └───────┬────────┘
           ▼
     Structured Response
     (answer + citations + pathway)
```

## MİMAR research prototype (v1.1)

MİMAR lives in `backend/app/mimar/` and is exposed under `/api/v1/mimar` and the
**“MİMAR research”** tab of the frontend (`http://localhost:5173/#mimar`).
It never makes curriculum decisions; it produces sourced candidates for expert review.

| Stage | What the software does |
|---|---|
| Data | CSV/XLSX/JSON import, QC with exclusion reasons, frozen versions with SHA-256 content hash |
| AS1 | BM25 + embedding/FAISS + concept graph rankers on LO texts only, RRF (k = 60), content-family 70/30 split with lock hash, pre-registered plan, stratified sampling with inclusion probabilities, blinded double review + adjudication, weighted sensitivity/PPV, Cohen κ & Gwet AC1, family-clustered bootstrap, H1 rule, 5-run stability check |
| AS2 | MİMAR–Core / Expert–Core / MİMAR–Extended (KuLearn as a separate 4th channel) reports, UÇEP correspondence map, matching, blinded standardised pool with sealed sources, 3-criterion validation, ΔMU with linked-family bootstrap (H2a, −10/−5/−15 pp), H2b new-verified share, blinding check, person-hour log, Monte Carlo power |
| AS5 | Stratified whole-curriculum candidate sample (≤ 300), coordinator evaluation, completion-weight adjustment, extreme-case bounds, coordinator-clustered CI (H5) |
| AS6 | T0/T1 version diff, change-impact alerts with sources, expected effects registered & locked beforehand (hidden from the technical team), ≥ 24 controlled scenarios (H6) |
| Cross-cutting | Role-based access with independence rules, hash-chained audit log, content-addressed artifacts, local SQLite store (no cloud) |

```bash
cd backend
pip install -r requirements.txt            # optional extras: requirements-optional.txt
uvicorn app.main:app --reload              # admin token in development: dev-admin-token
python -m pytest -q                        # 44 tests
python ../scripts/run_mimar_demo.py        # full synthetic run of AS1 → AS6 (~20 s)
```

In the UI, log in with the admin token and press **“Sentetik demoyu kur”** to create
synthetic data, demo users for every role and a complete run; then switch roles
(reviewer, validator, coordinator, …) to see each person’s view.
**All demo data are synthetic and all human decisions are simulated.**

See `docs/mimar-notes.md` for the architecture, the API and the mapping to the application.

## Real KUSOM 2025–2026 data (v1.6)

CURATOR now runs on the faculty's own timetables and learning-objective
documents instead of the demonstration curriculum.

```bash
# put the shared Drive folders (Dönem 2, Dönem 3, Dönem 4 ve 5, Ders programları) in
# backend/data/kusom_raw/ (git-ignored), then:
cd backend && python -m app.data.kusom.parse_timetables data/kusom_raw
# → app/data/kusom/kusom_2025_2026.json (blocks, topics, objectives, sessions, quality report)
```

* **Importer** (`app/data/kusom/parse_timetables.py`) reads year overview workbooks,
  per-block and per-group clerkship programmes, LO `.docx` files and the RPHM
  PDF.  Sheets listing students are never opened.  It cleans session titles,
  classifies sessions (lecture, lab, case discussion, PBL, skills, exam, study
  time, admin…), fixes block-code typos, detects copied sheets and
  cross-listed sessions, and writes a quality report.
* **Source switch:** `CURRICULUM_SOURCE=kusom` (default) or `placeholder`.
  Pathways, chat retrieval, the sidebar, block details and expert review all
  follow it; expert reviews are stored separately per source.
* **Pathways on real data:** phases are year 2 (normal body) → year 3
  (disease) → years 4–5 (clinic); prerequisites are derived from shared
  content; objectives (where written) refine Bloom level and retrieval.
* **MİMAR input screen:** “KUSOM 2025–2026 programından yükle” loads chosen
  blocks; objectives written on one template for different entities (Na⁺/K⁺,
  male/female) and lecture + lab restatements are reported separately, not as
  redundancy.
* Block names in the data are codes only; the Turkish/English names in
  `app/data/kusom/curriculum.py` are descriptive and should be replaced with the
  official names.

## Languages

Supports **English** and **Turkish**. Query language is auto-detected.

## Roadmap

- [x] v1: KU SOM curriculum, RAG pipeline, bilingual support
- [x] v1.1: MİMAR research prototype (AS1–AS6 workflow, locked evaluation, blinded review), offline mode, build fixes
- [ ] v2: All Turkish medical schools
- [ ] v3: Global expansion, cross-institutional comparison
