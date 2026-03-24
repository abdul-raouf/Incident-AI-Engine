# Incident AI Engine

An AI-powered incident classification and SOP generation system. The system accepts text inputs (video transcriptions, call transcriptions, or written reports), classifies them into incident categories using a local LLM, generates actionable Standard Operating Procedures (SOPs), and flags low-confidence results for human review.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [API Reference](#api-reference)
- [Classification System](#classification-system)
- [SOP Engine](#sop-engine)
- [Human Review Queue](#human-review-queue)
- [Configuration](#configuration)
- [Roadmap](#roadmap)

---

## Overview

This system processes unstructured incident text and returns:

- **Multi-label classification** — every incident category scored with an independent confidence percentage
- **Automated SOP generation** — template-based SOPs filled using only facts present in the input text
- **Human review flagging** — low-confidence results are automatically queued for supervisor review
- **Full audit trail** — every result, confidence score, reasoning, and model version is persisted to SQL Server

The LLM runs **fully locally** via Ollama — no data leaves your infrastructure.

---

## Architecture
```
┌─────────────────────────────────────────────────────────────┐
│                     .NET Web API (Gateway)                   │
│         Accepts input → calls Python API → saves to DB       │
└─────────────────────────┬───────────────────────────────────┘
                          │ HTTP
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                   FastAPI (AI Engine)                        │
│  ┌──────────────┐  ┌────────────────┐  ┌─────────────────┐ │
│  │  Classifier  │  │   SOP Engine   │  │  Review Queue   │ │
│  │ (Pydantic +  │→ │ (Templates +   │→ │ (Low-confidence │ │
│  │  Ollama LLM) │  │  LLM fill-in)  │  │   flagging)     │ │
│  └──────────────┘  └────────────────┘  └─────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                       SQL Server                             │
│           incident_reports  +  review_queue                  │
└─────────────────────────────────────────────────────────────┘
```

---

## Features

- **Multi-label confidence scoring** — all categories scored independently; a single incident can score high across multiple categories (e.g. a fight that causes a fire scores both)
- **Concurrent multi-SOP generation** — when multiple categories are within a confidence threshold of each other, SOPs for all relevant categories are generated concurrently and merged
- **Template-grounded generation** — LLM only fills placeholders in predefined templates; it cannot invent new steps, reducing hallucination significantly
- **Zero external API calls** — classification and SOP generation run on Ollama locally with `qwen2.5:7b`
- **Structured JSON output** — Pydantic-enforced schema on all LLM responses; invalid outputs fall back gracefully rather than crashing
- **Temperature-controlled inference** — `temperature=0` for classification (deterministic), `temperature=0.2` for SOP fill-in (natural language)
- **Automatic review flagging** — incidents below the confidence threshold are added to a review queue automatically
- **Full audit trail** — model version, reasoning, raw input, and all scores stored per record

---

## Tech Stack

| Layer | Technology |
|---|---|
| AI Engine API | FastAPI |
| LLM Runtime | Ollama (`qwen2.5:7b`) |
| LLM Orchestration | LangChain (`langchain-ollama`) |
| Output Validation | Pydantic v2 |
| ORM | SQLAlchemy |
| Database | SQL Server (via pyodbc, ODBC Driver 17) |
| Schema Migrations | Alembic |

---

## Project Structure
```
fastapi_ai_engine/
├── app/
│   ├── main.py                    # FastAPI app entry point
│   ├── api/
│   │   └── routes.py              # All API endpoints
│   ├── core/
│   │   ├── config.py              # Settings loaded from .env
│   │   └── database.py            # SQLAlchemy engine + session
│   ├── models/
│   │   └── db_models.py           # ORM table definitions
│   ├── schemas/
│   │   └── pydantic_schemas.py    # Request/response + LLM output schemas
│   ├── services/
│   │   ├── classifier.py          # LLM classification chain
│   │   ├── sop_engine.py          # Multi-SOP template generation
│   │   └── review_queue.py        # Low-confidence queue management
│   └── sop_templates/
│       ├── fight.md
│       ├── fire.md
│       ├── accident.md
│       └── suspicious_behaviour.md
├── migrations/                    # Alembic migration files
├── .env.example
├── requirements.txt
└── README.md
```

---

## Getting Started

### Prerequisites

- Python 3.11+
- [Ollama](https://ollama.com) installed and running
- SQL Server with ODBC Driver 17
- `qwen2.5:7b` model pulled in Ollama

### 1. Pull the model
```bash
ollama pull qwen2.5:7b
```

### 2. Clone and install dependencies
```bash
git clone https://github.com/your-org/rta-incident-ai-engine.git
cd rta-incident-ai-engine
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

### 3. Configure environment
```bash
cp .env.example .env
```

Edit `.env`:
```env
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b

DB_HOST=localhost
DB_PORT=1433
DB_NAME=IncidentDB
DB_USER=sa
DB_PASSWORD=YourStrong@Passw0rd

CONFIDENCE_THRESHOLD=0.70
```

### 4. Run database migrations
```bash
alembic upgrade head
```

### 5. Start the server
```bash
uvicorn app.main:app --reload --port 8000
```

Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## API Reference

### `POST /api/v1/analyze`

Accepts incident text and returns classification scores, a generated SOP, and a flag if confidence is low.

**Request**
```json
{
  "text": "Two passengers were seen throwing punches near Gate 3 at Dubai Metro. An electric fire broke out in the duty free market. Security was alerted at 14:32.",
  "source": "video",
  "report_type": "Metro Station CCTV Report"
}
```

**Source options:** `video` · `call` · `text_report`

**Response**
```json
{
  "id": "a8a3c103-e2c6-4085-b3ff-829d8e68bd8b",
  "classifications": [
    { "category": "Fight",                "confidence": 1.0 },
    { "category": "Fire",                 "confidence": 1.0 },
    { "category": "Accident",             "confidence": 0.1 },
    { "category": "Suspicious Behaviour", "confidence": 0.9 }
  ],
  "primary_classification": "Fight",
  "primary_confidence": 1.0,
  "reasoning": "The incident involves a physical altercation that directly caused a fire.",
  "sop": "---\n## 🚨 Detected Incident: Fight\n\n...\n\n---\n## 🚨 Detected Incident: Fire\n\n...",
  "is_flagged": false,
  "created_at": "2026-03-18T10:02:40.362078Z"
}
```

---

### `GET /api/v1/review-queue`

Returns all unresolved low-confidence incidents awaiting human review.

**Response**
```json
[
  {
    "id": "uuid",
    "incident_id": "uuid",
    "primary_classification": "Suspicious Behaviour",
    "primary_confidence": 0.55,
    "all_scores": [
      { "category": "Fight",                "confidence": 0.4 },
      { "category": "Fire",                 "confidence": 0.0 },
      { "category": "Accident",             "confidence": 0.1 },
      { "category": "Suspicious Behaviour", "confidence": 0.55 }
    ],
    "created_at": "2026-03-18T10:05:00Z",
    "resolved": false
  }
]
```

---

### `PATCH /api/v1/review-queue/{review_id}/resolve`

Allows a human reviewer to correct the classification and mark the item as resolved.

**Request**
```json
{
  "correct_classification": "Suspicious Behaviour",
  "reviewer_notes": "Confirmed after reviewing CCTV footage."
}
```

---

## Classification System

All four categories are scored **independently** on every request. Scores do not need to sum to 1.0 — each represents how strongly the input matches that category.

| Category | Description |
|---|---|
| `Fight` | Physical altercations, assaults, brawls |
| `Fire` | Fire outbreaks, smoke, burning |
| `Accident` | Collisions, falls, unintentional incidents |
| `Suspicious Behaviour` | Unusual activity, loitering, unattended items |
| `Unknown` | Fallback when no category matches confidently |

**Primary classification** is always the highest-scoring category. When multiple categories score within `0.15` of each other, all are treated as active and receive their own SOP.

---

## SOP Engine

SOPs are **template-grounded** — the LLM can only fill placeholders, not invent new content. This is the primary mechanism for reducing hallucination in the generated output.

### Placeholder variables

| Placeholder | Extracted from text |
|---|---|
| `{{location}}` | Gate number, station name, zone |
| `{{incident_time}}` | Any time mention (e.g. 14:32, 2pm) |
| `{{parties_involved}}` | Description of people involved |
| `{{injuries_mentioned}}` | Any mention of injuries |
| `{{additional_context}}` | Other relevant details |

If a value cannot be found in the input text, the placeholder is filled with `"Not specified"`.

### Multi-incident SOP merging

When multiple categories are active, SOPs are generated **concurrently** via `asyncio.gather()` and merged into a single response with clear section headers per incident type.

---

## Human Review Queue

Any incident where the top classification confidence is below `CONFIDENCE_THRESHOLD` (default `0.70`) is automatically added to the review queue with:

- The LLM's best-guess classification
- Full confidence scores for all categories
- A `resolved: false` flag

Reviewers can correct the classification via the `PATCH /resolve` endpoint. Resolved items are timestamped and retained for audit purposes.

---

## Configuration

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `qwen2.5:7b` | Model to use for classification and SOP generation |
| `DB_HOST` | `localhost` | SQL Server host |
| `DB_PORT` | `1433` | SQL Server port |
| `DB_NAME` | `IncidentDB` | Target database name |
| `DB_USER` | — | SQL Server username |
| `DB_PASSWORD` | — | SQL Server password |
| `CONFIDENCE_THRESHOLD` | `0.70` | Minimum confidence to skip review queue |

---

## Roadmap

- [ ] .NET Web API gateway with authentication and request forwarding
- [ ] RAG-based SOP retrieval once real SOPs are available (ChromaDB)
- [ ] Arabic language support for incident text
- [ ] Dashboard UI for review queue management
- [ ] Webhook notifications for flagged incidents
- [ ] Fine-tuned classification model trained on RTA incident history