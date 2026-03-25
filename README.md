# Libra: Prolog-GraphRAG Educational Assistant

Libra is an advanced GraphRAG system that combines Neo4j Knowledge Graphs with Prolog-based logical reasoning (s(CASP)) to provide verifiable, evidence-based answers to educational queries.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│ Frontend (React + TypeScript)                       │
│  App.tsx → streamChat() → SSE events                │
└────────────────────┬────────────────────────────────┘
                     │ POST /api/chat (SSE)
┌────────────────────▼────────────────────────────────┐
│ Backend (Flask)  app.py                             │
│  ├─ /api/chat → run_pipeline()                      │
│  └─ /api/ingest/* → PDF ingestion (background)      │
│                                                     │
│ prolog_graphrag_pipeline/                            │
│  ├─ main_driver.py      ← orchestration entry point │
│  ├─ llm.py              ← routing + answer gen      │
│  ├─ config.py           ← system prompts            │
│  ├─ semantic_entropy.py ← hallucination detection    │
│  │                                                   │
│  ├─ graphrag/                                        │
│  │  ├─ graphrag_driver.py ← KG builder + search     │
│  │  ├─ retriever.py       ← hybrid retriever         │
│  │  ├─ kbpedia_retriever.py ← KBPedia concept search│
│  │  ├─ encoder.py         ← PDF→KG ingestion        │
│  │  └─ wikidata_retriever.py ← Wikidata fallback    │
│  │                                                   │
│  └─ prolog/                                          │
│     ├─ prolog_driver.py   ← s(CASP) interface       │
│     ├─ prolog_generator.py← LLM→Prolog codegen      │
│     └─ prolog_config.py   ← Prolog prompts          │
└──────────────────────┬──────────────────────────────┘
                       │
        ┌──────────────┼──────────────────┐
        ▼              ▼                  ▼
   Neo4j (KG)    Together AI (LLM)   SWI-Prolog
```

### Pipeline Flow

1. **Routing** — `llm.decide_fallback()` classifies the question's complexity.
2. **GraphRAG Retrieval** — Hybrid search over user documents + KBPedia concepts.
3. **Prolog Reasoning** — LLM generates s(CASP) Prolog code, validated against Janus-SWI.
4. **LLM Synthesis** — Merges context + Prolog explanation into a final answer.
5. **Hallucination Check** — Semantic entropy over multiple samples flags uncertain answers.

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running (for Docker setup)
- A [Together AI](https://www.together.ai/) API key for the Llama-3.3-70B model

## Environment Variables

| Variable            | Required | Default         | Description                          |
|---------------------|----------|-----------------|--------------------------------------|
| `TOGETHER_API_KEY`  | Yes      | —               | Together AI API key                  |
| `NEO4J_URI`         | No       | `bolt://localhost:7687` | Neo4j connection URI          |
| `NEO4J_USERNAME`    | No       | `neo4j`         | Neo4j username                       |
| `NEO4J_PASSWORD`    | No       | `graphrag`      | Neo4j password                       |
| `CORS_ORIGIN`       | No       | `http://localhost:5173` | Allowed CORS origin           |
| `LOG_LEVEL`         | No       | `INFO`          | Python logging level                 |

## Docker Setup

### 1. Environment Configuration
```bash
cp .env.example .env
# Edit .env and set TOGETHER_API_KEY=your_actual_key_here
```

### 2. Knowledge Base Data
Ensure the `neo4j_kbpedia/` directory contains the KBPedia TTL/N3 files. These are mounted automatically into the Neo4j container.

### 3. Build and Start
```bash
docker compose up --build
```
- **Backend API**: `http://localhost:5000`
- **Frontend UI**: `http://localhost:80`
- **Neo4j Browser**: `http://localhost:7474`

### 4. Background Mode
```bash
docker compose up -d     # Start in background
docker compose down      # Stop
```

## Local Development

### Backend
```bash
python -m venv .venv
.venv\Scripts\activate       # Windows
# source .venv/bin/activate  # Linux/macOS
pip install -r backend/requirements.txt
cd backend && python app.py
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```