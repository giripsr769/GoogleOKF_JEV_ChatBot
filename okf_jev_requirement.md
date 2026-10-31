# Requirements and Architecture

**OKF + TypeSafe Jev + OpenAI Text-to-SQL service, with an Angular chat window**

| About | Details |
|---|---|
| **Status** | Built and tested. This document says what the system must do and how it is put together. |
| **Last updated** | 2026-11-01 |
| **Plain-language overview** | [README.md](README.md) |
| **Setup and usage guides** | [Backend guide](okf-sql-ai-service/README.md), [Chat window guide](okf-chat-ui/README.md) |

**Contents:** [1. Purpose](#1-purpose-and-scope) · [2. Technology](#2-technology-stack) · [3. Pipeline](#3-end-to-end-pipeline) · [4. Jev](#4-where-jev-is-used) · [5. Functional requirements](#5-functional-requirements) · [6. Non-functional requirements](#6-non-functional-requirements) · [7. API](#7-api-contract) · [8. Verification](#8-verification-and-results) · [9. Structure](#9-project-structure) · [10. Limits and future work](#10-limits-and-future-work) · [11. Glossary](#11-glossary) · [12. Changes since v1](#12-what-changed-since-the-first-version)

---

## 1. Purpose and scope

### 1.1 Goal
Let people ask questions about a PostgreSQL database **in plain English** and get a **short, human reply**, without writing SQL. The system must do this **safely**: it may only read data, and it must resist misuse such as prompt injection, requests to change data, and attempts to see private tables.

### 1.2 Approach
A fixed, step-by-step **deterministic pipeline**, not a free-running AI agent. This keeps cost, delay and behaviour predictable and avoids looping.
- **TypeSafe Jev** is a fast, typed "System 1" decision model. It makes the quick judgement calls: is this request safe, which tables matter, how risky is this SQL.
- **OpenAI** does the creative work: it writes the SQL and phrases the reply.
- **OKF files** (Markdown data dictionary) and a **local FAISS index** decide which table descriptions the models are allowed to see.

### 1.3 In scope
A FastAPI backend, an Angular chat window, a 50-table sample database with generated documentation, Docker and no-Docker setup, and automated evaluation.

### 1.4 Out of scope (today)
User login and permissions, conversation memory, databases other than PostgreSQL, streaming replies, and a hosted vector database. See [section 10](#10-limits-and-future-work).

---

## 2. Technology stack

| Layer | Choice | Notes |
|---|---|---|
| Backend | Python 3.11, FastAPI, Uvicorn | tested on 3.11; 3.10 to 3.12 expected to work |
| Chat window | Angular 21 (standalone components, signals), plain CSS | no UI library |
| Safety and decisions | TypeSafe AI Jev (`typesafe-sdk`, model `jev-latest`) | `Choice`, `Noul` and `Score` primitives; needs `TYPESAFE_API_KEY` |
| Language model | OpenAI (`openai`, default model `gpt-4o`, configurable) | writes SQL and replies; needs `OPENAI_API_KEY` |
| Embeddings | OpenAI `text-embedding-3-small` (configurable) | one vector per table description |
| Knowledge layer | **OKF** (Open Knowledge Format): Markdown files with YAML front matter | one file per table in `okf_tables/` |
| Vector search | FAISS (`faiss-cpu`, exact inner-product index) | saved to `vector_store/`, rebuilt automatically when OKF files change |
| SQL checking | `sqlglot` | parses every generated query into a syntax tree |
| Database | PostgreSQL 13 or newer (16 tested) | read-only login, statement timeout |
| Packaging | Docker Compose, or `scripts/setup_local.py` | both documented |
| Configuration | `.env` file and environment variables | secrets never committed |

---

## 3. End-to-end pipeline

```
 Angular chat window
        |  POST /api/text-to-sql  {"question": "..."}
        v
 [1] GATE .............. Jev Choice + Noul: intent and prompt-injection check          -> 400 if blocked
        |
 [2] RETRIEVE .......... FAISS: top 8 candidate tables from the OKF index
        |
 [3] RERANK ............ Jev Noul per table (sees column names): keep the needed ones
        |
 [4] JOIN-PATH ......... if kept tables cannot be joined, FK graph proposes bridges;
        |               Jev Noul picks the needed ones (skipped when already connected)
        |
 [5] GENERATE .......... OpenAI writes ONE read-only SELECT from the question + kept tables
        |               (regenerated once if the output does not parse)
        |
 [6] VALIDATE .......... sqlglot: SELECT only, approved tables and functions, LIMIT 100  -> 422 if rejected
        |
 [7] RISK SCORE ........ Jev Score 0 to 3; above 1.5 is rejected                       -> 422 if too risky
        |
 [8] EXECUTE ........... PostgreSQL, read-only login, read-only transaction, 3 s limit  -> 504 if slow
        |
 [9] REPLY ............. OpenAI turns the rows into a short chat reply (fallback sentence if it fails)
        |
        v
 JSON: answer, show_table, sql, rows, tables_used, risk_score, timings_ms
```

The whole request runs under one **30 second budget**; see [6.3](#63-time-limits).

| Step | Module | What it guarantees |
|---|---|---|
| 1 Gate | `src/jev_guard.py` | injection, data-change and off-topic requests never reach schema or SQL generation |
| 2 Retrieve | `src/okf_loader.py` | only table *descriptions* are searched; no data rows are ever embedded |
| 3 Rerank | `src/jev_guard.py` | noise tables are removed before OpenAI sees any schema |
| 4 Join-path | `src/join_paths.py` | tables that need an intermediate table (customers to products via orders) can still be joined |
| 5 Generate | `src/sql_generator.py` | OpenAI sees the question and the kept tables only |
| 6 Validate | `src/security.py` | nothing but a safe single `SELECT` can pass |
| 7 Risk | `src/jev_guard.py` | queries that match the question badly or expose bulk personal data are stopped |
| 8 Execute | `src/main.py` | even a bypassed check cannot write, and cannot read ungranted tables |
| 9 Reply | `src/answer_writer.py` | a human sentence, with a table only on request |

---

## 4. Where Jev is used

Jev is called at **four control points**. All thresholds are constants in `src/jev_guard.py`.

| # | Control point | Primitive | Decision | Threshold |
|---|---|---|---|---|
| 1 | **Gate** (before retrieval) | `Choice` over `valid_data_query`, `data_modification`, `prompt_injection`, `off_topic`; plus `Noul` for injection | allowed only if intent is `valid_data_query` **and** injection probability is below the threshold | injection `0.5` |
| 2 | **Rerank** (after retrieval) | `Noul`, one question per candidate table, including its column names | keep a table when the probability is at or above the threshold | `0.35` |
| 3 | **Bridge selection** (join-path) | `Noul` per bridge candidate, told which tables are already selected | add a bridge table at or above the threshold | `0.5` |
| 4 | **Risk** (after generation) | `Score` on a 0 to 3 rubric (safe, low, elevated, dangerous) | reject when the score is above the limit | `1.5` |

The gate is also told **what the database covers** (each table name plus its first tags), so a data question that looks like general knowledge ("What is the VAT in India?") is not blocked as off-topic.

Each Jev call is limited to 10 seconds. All of this runs without any streaming or agent loop: one call per control point.

---

## 5. Functional requirements

IDs are stable so tests and reviews can refer to them.

### 5.1 Question handling
| ID | The system shall |
|---|---|
| FR-1 | accept a question of 3 to 500 characters at `POST /api/text-to-sql`, and reject anything else with HTTP 422 |
| FR-2 | block prompt injection, requests to insert, change or delete data, and off-topic questions **before** any SQL is generated, returning HTTP 400 with the detected intent |
| FR-3 | pick relevant tables from the OKF index, then filter them with Jev, so that **only the filtered tables' descriptions** are sent to OpenAI |
| FR-4 | add intermediate tables when the chosen tables cannot be joined directly (up to two intermediate tables) |
| FR-5 | ask OpenAI for **exactly one** read-only `SELECT`, and regenerate **once** if the output is empty or does not parse (never for a policy rejection) |

### 5.2 Safety checks on generated SQL
| ID | The system shall reject (HTTP 422) any generated SQL that |
|---|---|
| FR-6 | is not a single `SELECT` or `UNION` statement |
| FR-7 | contains `INSERT`, `UPDATE`, `DELETE`, `DROP`, `CREATE`, `ALTER`, `TRUNCATE`, `COPY`, `SET` or `SELECT ... INTO`, including inside a CTE |
| FR-8 | uses a table that is not among the filtered tables (this blocks catalogs such as `pg_user`) |
| FR-9 | calls a function that is not recognised as standard and not on the allow-list (`date_trunc`, `to_char`, `age`, `now`, `extract`, `round`, `coalesce`, `nullif`), which blocks `pg_sleep`, `pg_read_file`, `dblink`, `lo_import` and similar |
| FR-10 | scores above the risk limit of 1.5 |

The system shall also **add `LIMIT 100`** when there is no limit, and **lower any larger limit to 100** (FR-11).

### 5.3 Execution and response
| ID | The system shall |
|---|---|
| FR-12 | run every query with a dedicated **read-only database login**, inside a read-only transaction, with a **3 second** statement timeout |
| FR-13 | return, for a successful query: `answer`, `show_table`, `sql`, `rows`, `columns`, `row_count`, `tables_used`, `risk_score`, `timings_ms` |
| FR-14 | write a short human reply (`answer`) from the result, and set `show_table` to true **only** when the question explicitly asks for a table, or when no reply text could be produced |
| FR-15 | still answer successfully with a plain fallback sentence if the reply writer fails, times out or is switched off (`NATURAL_ANSWERS=0`) |
| FR-16 | reply with a fixed friendly message, without calling a model, when the data cannot answer the question |
| FR-17 | provide `GET /health` reporting the number of indexed tables |

### 5.4 Knowledge layer and sample database
| ID | The system shall |
|---|---|
| FR-18 | describe each table in one OKF file (Markdown with YAML front matter: `table`, `description`, `tags`, `columns`, `relationships`) |
| FR-19 | rebuild the vector index automatically on start when any OKF file or the embedding model has changed |
| FR-20 | ship a 50-table sample database (e-commerce 21, HR 9, finance 10, support 10) generated from one specification, so the SQL and the OKF files cannot drift apart |
| FR-21 | keep at least one sensitive table (`salaries`) **deliberately unreadable** by the application's login |

### 5.5 Chat window
| ID | The chat window shall |
|---|---|
| FR-22 | show replies as plain sentences, and a results table only when `show_table` is true |
| FR-23 | offer a **Show SQL query** switch (default on) that shows or hides the SQL and its Copy button in every reply, old chats included |
| FR-24 | fold the technical details (row count, tables, risk score, per-step timings) behind a "details" link |
| FR-25 | have a sidebar that expands and collapses (an overlay on phones), with **New chat**, a **chat history** grouped by Today, Yesterday and Earlier, per-chat delete, and a two-click **Clear all history** |
| FR-26 | keep history and settings only in the browser, with at most 30 chats, and never fail if browser storage is unavailable or full |
| FR-27 | turn every error into a plain sentence while keeping the technical detail in small print |
| FR-28 | stop waiting after 40 seconds, cancel the request and say so |
| FR-29 | answer to the chat that asked, even if the user switches chats while waiting |

### 5.6 Setup
| ID | The system shall |
|---|---|
| FR-30 | start with Docker using one command (`docker compose up --build`), including a seeded database |
| FR-31 | be installable **without Docker** with one command (`python scripts/setup_local.py`) that creates the environment, installs packages, creates `.env`, builds and verifies the database, and can be re-run safely |

---

## 6. Non-functional requirements

### 6.1 Security (defence in depth)
Each layer must work **on its own**, so a failure in one is caught by the next.

| ID | Requirement |
|---|---|
| NFR-1 | **Zero schema leakage.** The raw database schema is never sent to a model. Models only receive OKF descriptions of tables that survived retrieval, rerank and join-path filtering. |
| NFR-2 | **Read-only enforcement in two places.** sqlglot must parse every generated query and confirm no data-changing statement exists (FR-6, FR-7), **and** the database login itself must be unable to write. |
| NFR-3 | **Least privilege.** The application login (`okf_readonly`) has `SELECT` only on the documented tables, defaults to read-only transactions, and has its own 3 second timeout. |
| NFR-4 | **Secrets.** API keys live only in `.env` or the environment. `.env` must never be committed (`.gitignore` excludes it; `.env.example` is the template). |
| NFR-5 | **No instructions from data.** Text found in query results is treated as data. The reply writer is told to ignore any instructions inside it. |
| NFR-6 | **Demo credentials.** The sample login password is for local use only and must be changed before real data is connected. |

### 6.2 Privacy and data flow
| ID | Requirement |
|---|---|
| NFR-7 | The question and the filtered table descriptions go to OpenAI to write SQL. **No data rows** are sent at that step. |
| NFR-8 | To write the reply, **result rows** go to OpenAI: at most 30 rows (`ANSWER_MAX_ROWS`), with long values cut to 200 characters. This step must be switchable off (`NATURAL_ANSWERS=0`), after which no rows leave the service. |
| NFR-9 | Chat history is stored only in the user's browser (`localStorage`), never on a server. |

### 6.3 Time limits
A request must never hang. Every wait has a limit.

| Limit | Value | When exceeded |
|---|---|---|
| Database query | 3 s (fixed) | database cancels it; HTTP 504 `Query exceeded the 3 second limit` |
| One Jev call (`JEV_TIMEOUT_S`) | 10 s | HTTP 504 |
| One OpenAI call (`OPENAI_TIMEOUT_S`, one retry) | 20 s | HTTP 504 |
| Reply writer (`ANSWER_TIMEOUT_S`) | 10 s | not an error: fallback sentence plus table |
| Whole request (`PIPELINE_TIMEOUT_S`) | 30 s | HTTP 504 `Request timed out ...` |
| Chat window | 40 s | the window stops waiting, cancels the request and tells the user |

The reply writer's limit must stay well below the whole-request limit, so its fallback always wins.

### 6.4 Quality attributes
| ID | Requirement |
|---|---|
| NFR-10 | **Performance.** A typical answer takes 3 to 7 seconds, almost all of it in model calls; the database query itself is usually under 10 ms. |
| NFR-11 | **Reliability.** A failure of the reply writer never fails a question whose data is ready. Unparseable SQL is retried once. |
| NFR-12 | **Observability.** Every response includes per-step timings (`gate`, `retrieve`, `rerank`, `expand`, `generate`, `validate`, `execute`, `answer`). |
| NFR-13 | **Portability.** Runs on Windows, macOS and Linux, with or without Docker. Tested on Windows 11 with Python 3.11 and PostgreSQL 16. |
| NFR-14 | **Maintainability.** Tables are added by editing one specification and regenerating; thresholds are named constants; behaviour is covered by automated tests. |
| NFR-15 | **Accessibility basics.** The chat window gives its buttons text labels and uses a proper switch control (`role="switch"`). Full keyboard and screen-reader testing has not been done. |

---

## 7. API contract

Full field-by-field details and an example response are in the [backend guide](okf-sql-ai-service/README.md#api).

| Endpoint | Purpose |
|---|---|
| `GET /health` | `{"status":"ok","tables_indexed":50}` |
| `POST /api/text-to-sql` | body `{"question": "..."}`; returns the response described in FR-13 |

| Status | Meaning |
|---|---|
| 200 | answered |
| 400 | blocked by the gate: `prompt_injection`, `data_modification` or `off_topic` |
| 422 | invalid question length; SQL rejected by the validator; risk too high; or the database refused the query (for example permission denied) |
| 504 | database query over 3 s, or the whole request over its budget |
| 500 | unexpected failure, including invalid API keys |

Browser access is limited to the origins in `CORS_ORIGINS` (default `http://localhost:4200`).

---

## 8. Verification and results

| What | How it is checked | Result at the last run |
|---|---|---|
| Full pipeline on 47 answerable questions across all four areas, 6 attacks, 2 restricted-data questions | `tests/run_eval.py` | **55 of 55** |
| Same, on 18 further questions written after tuning (to detect overfitting) | `tests/run_eval.py --file heldout_questions.json` | **18 of 18** |
| Gate | answerable questions allowed; attack questions blocked | 47 of 47 allowed; 6 of 6 and 4 of 4 blocked |
| Retrieval | all needed tables inside the top 8 FAISS hits | 98% (the top 4 alone gave 78%, which is why 8 is used) |
| Rerank | all needed tables kept | 98%, about 2.6 tables kept per question |
| Restricted data | questions about salaries and bulk personal data never return rows | 5 of 5 |
| SQL regeneration rules | `tests/test_retry.py`, fake OpenAI client | passes |
| Reply writer and table detection | `tests/test_answer.py`, fake client | passes |
| Timeouts | `tests/test_timeout.py` (hung and timing-out fakes, plus one real request) | passes |
| Chat window | scripted real-browser run: sidebar, history, SQL switch, reload persistence, delete and clear, mobile layout, error messages, 40 s timeout | 56 and 11 checks pass |
| Fresh install without Docker | clean checkout, new virtual environment, scratch PostgreSQL: setup script, re-run, `--reset`, wrong password, no server, then the API and evaluation | works |
| Fresh Docker database start | the numbered SQL files run in order on an empty volume | works |

**Reading these numbers:** the model-based steps vary a little between runs, so each figure is a single sample. Re-run the evaluation after changing any threshold or prompt. The SQL validator's rules were exercised with adversarial queries during development (`DROP`, `DELETE`, stacked statements, `SELECT INTO`, `pg_sleep`, `pg_read_file`, `dblink`, unlisted tables); they are not yet a committed automated test.

---

## 9. Project structure

```
OKF_JEV/
├── README.md                        plain-language overview and quick start
├── okf_jev_requirement.md           this document
├── docs/                            flow chart image (+ source)
├── okf-sql-ai-service/              the backend
│   ├── src/
│   │   ├── main.py                  API, pipeline order, time budget
│   │   ├── jev_guard.py             Jev gate, rerank, bridge selection, risk score
│   │   ├── okf_loader.py            OKF parser, FAISS index build and search
│   │   ├── join_paths.py            foreign-key graph and bridge candidates
│   │   ├── sql_generator.py         OpenAI SQL generation and one-time retry
│   │   ├── security.py              sqlglot validation, allow-lists, LIMIT rules
│   │   └── answer_writer.py         human reply and "table only if asked" detection
│   ├── okf_tables/                  50 OKF files, one per table
│   ├── db/                          01_init.sql, 02_init_extra.sql (generated)
│   ├── scripts/                     setup_local.py, db_setup.py
│   ├── tools/                       schema_spec.py, gen_schema.py (sample schema generator)
│   ├── tests/                       evaluation, question sets, deterministic tests
│   ├── vector_store/                FAISS index (generated, not committed)
│   └── Dockerfile, docker-compose.yml, requirements.txt, .env.example
└── okf-chat-ui/                     the Angular chat window
    └── src/app/                     chat, sidebar, store (history and settings), service, environment
```

---

## 10. Limits and future work

**Known limits**
- **No memory.** Each question stands alone, so follow-ups such as "and last month?" do not work.
- **Extra tables.** Jev can rate several purchase-style paths equally likely (carts, invoices, orders), so a few harmless extra tables may reach SQL generation.
- **Reply wording.** A reply can state something true of the rows shown but not of the whole table ("the data includes four customers").
- **Single provider.** If OpenAI or Jev is down there is no fallback model; questions fail with a 504 or 500 until it recovers.
- **Tested platforms.** Native PostgreSQL installs, macOS and Linux are documented but not yet tried.

**Possible next steps**
1. Conversation memory, so follow-up questions work.
2. A committed automated test for the SQL validator's rules.
3. Sign-in and per-user table permissions.
4. Streaming replies, and clearer messages for provider outages (invalid keys currently surface as a 500).
5. A hosted vector store, only if the table count grows into the tens of thousands.

---

## 11. Glossary

| Term | Meaning |
|---|---|
| **SQL** | the language used to query a database |
| **OKF** | Open Knowledge Format: a Markdown file with a YAML header that describes one table (name, purpose, tags, columns, relationships) |
| **Jev** | TypeSafe AI's fast decision model, used as a "System 1" judge for quick yes/no and scoring decisions |
| **Choice / Noul / Score** | Jev primitives: pick one label from a set; give a yes/no probability; give a rating on a rubric |
| **FAISS** | a library for fast similarity search over vectors; here it finds the tables closest in meaning to the question |
| **Embedding** | a list of numbers that captures the meaning of a text, so similar texts have similar numbers |
| **sqlglot** | a library that parses SQL into a syntax tree, so it can be inspected instead of trusted |
| **Read-only login** | a database account that can look but cannot change anything |
| **Prompt injection** | text crafted to make an AI ignore its instructions or reveal secrets |
| **Deterministic pipeline** | a fixed sequence of steps, as opposed to an AI agent that decides its own steps |

---

## 12. What changed since the first version

The first version of this specification described a pipeline with three Jev control points and a JSON-only reply, and the first build had four sample tables. The system now also has:

| Area | Addition |
|---|---|
| Retrieval | candidate count raised from 4 to 8; rerank prompt includes column names; the gate is told what the database covers |
| Joins | **join-path expansion**: bridge tables chosen from the foreign-key graph and confirmed by Jev (a fourth Jev control point) |
| SQL safety | function allow-list; one regeneration for unparseable output; clamp, not just add, `LIMIT` |
| Replies | **natural-language answers**, with a table only when asked, and a safe fallback |
| Robustness | time budgets for every wait; friendly error messages |
| Data | 50-table sample database generated from one specification; a deliberately unreadable `salaries` table |
| Interface | the Angular chat window with sidebar, history and SQL switch |
| Operations | no-Docker setup script, database script, numbered SQL files, evaluation suite and deterministic tests |
