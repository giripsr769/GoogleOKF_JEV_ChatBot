OKF + TypeSafe Jev & OpenAI Text-to-SQL Python FastAPI Microservice - Requirements & Architecture Spec

1. Project Overview

A production-grade, standalone, plug-and-play Text-to-SQL Python FastAPI microservice designed to securely bridge modern frontends (such as Angular) and relational databases (PostgreSQL) using natural language.

To eliminate the latency, token costs, and non-deterministic recursion loops, this architecture utilizes a strict, highly reliable Deterministic Pipeline combining TypeSafe AI's Jev (as an ultra-fast System 1 decision layer for safety, intent routing, and schema reranking) with OpenAI for core SQL generation.

2. Technology Stack & API Keys

Web Framework: Python FastAPI, Uvicorn

Decision / Security Model: TypeSafe AI Jev SDK (typesafe-sdk using TYPESAFE_API_KEY)

Core Generation LLM: OpenAI API (openai using OPENAI_API_KEY)

Knowledge Metadata Layer: Open Knowledge Format (OKF) Markdown files (.md with YAML frontmatter)

Vector Search: FAISS (for high-speed local schema retrieval)

Output Security & Guardrails: sqlglot (abstract syntax tree parsing and validation)

Database: PostgreSQL (with strict statement timeouts)

3. End-to-End Execution Pipeline Flow

Client Tier (Angular UI): Submits natural language query via POST /api/text-to-sql.

Ingress Security Gate (FastAPI + Jev Choice & Noul): Evaluates prompt intent, checks for prompt injection, and verifies safety in milliseconds (70–500ms).

Knowledge Retrieval Layer (FAISS + OKF): Embeds prompt and pulls relevant table schema markdown files.

Schema Reranker (Post-Retrieval Jev Noul / Score): Evaluates whether fetched table .md files are strictly required to answer the prompt, filtering out noisy schemas.

Generation Core (OpenAI): Combines question and filtered schemas to generate deterministic PostgreSQL SQL.

Validation & Guardrails (sqlglot + Jev Score): Enforces strict read-only SELECT, blocks mutations (DROP, DELETE), evaluates semantic risk score, and auto-injects LIMIT 100.

Database Execution (PostgreSQL): Runs query safely under a strict 3-second statement timeout.

Response Delivery: Returns clean structured JSON back to the Angular UI.

4. Jev Decision Model Integration Points (typesafe-sdk)

Jev acts as a fast, typed "System 1" decision model (jev-latest) across three critical control points using dedicated primitives:

Input Gatekeeper (Pre-Retrieval): Uses Choice (to classify intent like valid_data_query vs prompt_injection) and Noul (binary safety check probability).

Schema Reranker (Post-Retrieval): Uses Noul or Score primitives to check if retrieved table .md schemas are necessary, eliminating table noise before hitting OpenAI.

Semantic Guard & Risk Evaluator (Post-Generation): Uses Score primitives alongside sqlglot to evaluate the semantic risk rubric of generated SQL queries.

5. Project Directory Structure

okf-sql-ai-service/
├── okf_tables/                 # OKF Markdown data dictionary layers (.md files)
├── vector_store/               # Local persistent FAISS index storage folder
├── src/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application entrypoint and REST API endpoints
│   ├── okf_loader.py           # Markdown parser, chunking, and FAISS vector index builder
│   ├── jev_guard.py            # TypeSafe Jev client wrapper using Choice, Score, and Noul primitives
│   ├── sql_generator.py        # OpenAI LLM pipeline runner for SQL conversion
│   └── security.py             # sqlglot validation, read-only SELECT enforcement, and LIMIT injector
├── .env                        # Environment configuration (TYPESAFE_API_KEY, OPENAI_API_KEY, DATABASE_URL)
├── requirements.txt            # Python dependencies (fastapi, uvicorn, typesafe-sdk, openai, faiss-cpu, sqlglot, psycopg2-binary, python-dotenv)
├── Dockerfile                  # Container specification for VPS deployment
└── docker-compose.yml          # Container orchestration configuration with persistent volumes


6. Non-Functional Requirements & Security

Zero Schema Leakage: Raw database schemas are never exposed directly to the LLM without OKF filtering and Jev reranking.

Read-Only Enforcement: sqlglot must parse every generated query to confirm zero data modification statements exist.

Resource Governance: All PostgreSQL executions must enforce a hard 3-second statement timeout and auto-injected LIMIT 100.