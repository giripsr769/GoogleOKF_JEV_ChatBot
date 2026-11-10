# Requirements and Architecture

**OKF + TypeSafe Jev + CrewAI Text-to-SQL service, with an Angular chat window**

| About | Details |
|---|---|
| **Status** | Built and tested. This document says what the system must do and how it is put together. |
| **Last updated** | 2026-11-10 |
| **Plain-language overview** | [README.md](README.md) |
| **Setup and usage guides** | [Backend guide](okf-crewai-service/README.md), [Chat window guide](okf-chat-ui/README.md) |
| **Knowledge format** | Google [Open Knowledge Format (OKF) v0.2](https://github.com/GoogleCloudPlatform/open-knowledge-format) |

**Contents:** [1. Purpose](#1-purpose-and-scope) · [2. Technology](#2-technology-stack) · [3. Pipeline](#3-end-to-end-pipeline) · [4. Jev](#4-where-jev-is-used) · [5. Functional requirements](#5-functional-requirements) · [6. Non-functional requirements](#6-non-functional-requirements) · [7. API](#7-api-contract) · [8. Verification](#8-verification-and-results) · [9. Structure](#9-project-structure) · [10. Limits and future work](#10-limits-and-future-work) · [11. Glossary](#11-glossary) · [12. Changes since v1](#12-what-changed-since-the-first-version)

---

## 1. Purpose and scope

### 1.1 Goal
Let people ask questions about a PostgreSQL database **in plain English** and get a **short, human reply**, without writing SQL. The system must do this **safely**: it may only read data, and it must resist misuse such as prompt injection, requests to change data, and attempts to see private tables.

### 1.2 Approach
A fixed, step-by-step **deterministic pipeline**, not a free-running AI agent. This keeps cost, delay and behaviour predictable and avoids looping. Only the creative steps use agents; everything else is plain code or Jev.
- **TypeSafe Jev** is a fast, typed "System 1" decision model. It makes the quick judgement calls: is this request safe, which tables matter, does this SQL answer the question, does this reply leak anything.
- **CrewAI agents** (backed by OpenAI) do the creative work: an SQL Writer writes the SQL, an Answer Writer phrases the reply, and a Rewriter (called only for follow-ups) turns a follow-up into a standalone question.
- **An OKF bundle** (Google Open Knowledge Format v0.2: Markdown files with YAML front matter, one file per table, linked to each other) is the knowledge layer. It decides which table descriptions the models are allowed to see.

### 1.3 In scope
A FastAPI backend, an Angular chat window, a 50-table sample database with a generated OKF bundle, Docker setup, chat memory for follow-up questions, use as an embeddable Python library, and automated evaluation.

### 1.4 Out of scope (today)
User login and permissions, memory that survives a restart, databases other than PostgreSQL, streaming replies, and a hosted vector database. See [section 10](#10-limits-and-future-work).

---

## 2. Technology stack

| Layer | Choice | Notes |
|---|---|---|
| Backend | Python 3.10 to 3.13, FastAPI, Uvicorn | package `okf_chat`, command `okf-chat` |
| Chat window | Angular 21 (standalone components, signals), plain CSS | no UI library |
| Safety and decisions | TypeSafe AI Jev (`typesafe-sdk`, model `jev-latest`) | `Noul` (yes/no probability) questions; needs `TYPESAFE_API_KEY` |
| Agents | CrewAI | only `agents/llm.py` imports it, so it can be swapped |
| Language model | OpenAI-compatible, default `gpt-6-luna`, configurable | writes SQL and replies; needs `OPENAI_API_KEY`; no temperature is ever set |
| Knowledge layer | **OKF v0.2 bundle** in `okf_bundle/` | `index.md`, `log.md`, one concept file per table, grouped in folders; built from the database by `okf-chat build`, checked by `okf-chat check` |
| Table selection | Jev scores each table; OKF links give the join paths | no vector index or embeddings |
| SQL checking | `sqlglot` | parses every generated query; the checked tree is what runs |
| Database | PostgreSQL 13 or newer (16 tested) | read-only login, READ ONLY transaction, statement timeout |
| Packaging | Docker Compose (database, optional API container), `pip install -e .` | exact package pins in `pyproject.toml` |
| Configuration | `.env` file and environment variables | secrets never committed |

---

## 3. End-to-end pipeline

```
 Angular chat window
        |  POST /api/text-to-sql  {"question": "...", "session_id": "..."}
        v
 [0] REWRITE ........... Rewriter agent, only when the session has history: follow-up -> standalone question
        |               (the raw follow-up is screened for injection and data changes first)
 [1] INPUT GUARD ....... Jev: injection, data change, sensitive request, off-topic                -> 400 / 422
        |
 [2] NAVIGATE .......... Jev scores each OKF table; follow OKF links to add join bridges
        |               and a few neighbours; sensitive tables are never offered
 [3] SQL WRITE ......... SQL Writer agent: ONE read-only SELECT from the question + chosen tables
        |
 [4] VALIDATE .......... sqlglot: SELECT only, known tables only, safe functions, LIMIT 100     -> retry, then 422
        |
 [5] SQL JUDGE ......... Jev: answers the question? exposes contact details? risky?             -> retry or 422
        |
 [6] EXECUTE ........... PostgreSQL, read-only login, READ ONLY transaction, 3 s limit          -> 504 if slow
        |
 [7] ANSWER ............ Answer Writer agent: rows -> short chat reply (fallback sentence if it fails)
        |
 [8] OUTPUT GUARD ...... Jev: leaked sensitive data? followed injected text?                    -> refuse
        v
 JSON: answer, show_table, sql, rows, columns, row_count, tables_used, risk_score, timings_ms
```

The whole request runs under one **30 second budget**; see [6.3](#63-time-limits).

| Step | Module (`okf-crewai-service/src/okf_chat/`) | What it guarantees |
|---|---|---|
| 0 Rewrite | `agents/rewriter.py`, `core/memory.py` | follow-ups run through every guard as standalone questions; only questions and replies that reached the user are remembered |
| 1 Input guard | `guardrails/guards.py` | injection, data-change, sensitive and off-topic requests never reach schema or SQL generation |
| 2 Navigate | `core/navigator.py`, `core/okf_loader.py` | only the chosen tables' descriptions are shown to the SQL Writer; no data rows are ever involved |
| 3 SQL write | `agents/sql_writer.py` | the model sees the question and the chosen tables only |
| 4 Validate | `core/sql_validator.py` | nothing but a safe single `SELECT` can pass; the SQL that runs is regenerated from the parsed tree |
| 5 SQL judge | `guardrails/sql_judge.py` | queries that match the question badly, expose contact details or look risky are stopped |
| 6 Execute | `core/sql_executor.py` | even a bypassed check cannot write, and cannot read ungranted tables |
| 7 Answer | `agents/answer_writer.py` | a human sentence, with a table only on request |
| 8 Output guard | `guardrails/guards.py` | a reply that leaks sensitive data or follows text found in the rows is not returned |

`core/pipeline.py` runs these steps in order and turns every failure into a `Refusal` that the API returns as an HTTP error.

---

## 4. Where Jev is used

Jev is called at **four control points**, all as `Noul` yes/no probabilities. All thresholds are constants in `guardrails/policy.py` and `core/navigator.py`.

| # | Control point | Questions asked | Decision | Threshold |
|---|---|---|---|---|
| 1 | **Input guard** (before any SQL exists) | `injection`, `modify_data`, `sensitive`, and `data_question` (told what tables the database holds) | block when a hazard reaches the limit; block as off-topic when `data_question` is below its minimum | hazards `0.5`; `data_question` below `0.3` |
| 2 | **Navigator** (table selection) | one question per candidate table, all in one request; large bundles score `index.md` sections first | keep a table at or above the limit, or the single best one when nothing is clear | select `0.5`, floor `0.25`, neighbours `0.15`, at most 4 tables |
| 3 | **SQL judge** (after validation) | `answers_question`, `exposes_personal_data`, `risky` | reject when a hazard reaches the limit; retry the SQL Writer when the query does not answer the question | hazards `0.7`; mismatch below `0.2` |
| 4 | **Output guard** (before the reply leaves) | `leaked_sensitive`, `followed_injected_text`, `unsafe_reply` | refuse when a hazard reaches the limit | `0.7` |

The reported `risk_score` is the larger of the SQL judge's two hazard scores, from 0 to 1.

Each Jev call is limited to 10 seconds. If Jev cannot be reached the service refuses the question by default (`JEV_FAIL_OPEN=false`). Wording of the Jev questions affects results more than the thresholds do, so calibrate with `tools/eval_guards.py` rather than by guessing.

---

## 5. Functional requirements

IDs are stable so tests and reviews can refer to them.

### 5.1 Question handling
| ID | The system shall |
|---|---|
| FR-1 | accept a question of 1 to 1000 characters and an optional `session_id` (up to 64 characters of `A-Za-z0-9_-`) at `POST /api/text-to-sql`, and reject anything else with HTTP 422 |
| FR-2 | block prompt injection, requests to insert, change or delete data, and off-topic questions **before** any SQL is generated, returning HTTP 400 with the detected intent; refuse requests for sensitive data (salaries, credentials) with HTTP 422 |
| FR-3 | pick relevant tables from the OKF bundle with Jev, so that **only the chosen tables' descriptions** are sent to the SQL Writer |
| FR-4 | follow OKF links to add the fewest bridge tables (up to two) that let the chosen tables be joined, never routing through a sensitive table, and add a few linked tables as neighbours for recall |
| FR-5 | ask the SQL Writer for **exactly one** read-only `SELECT`, and let it try again (up to `SQL_MAX_RETRIES`, default 2) when a draft is rejected by the validator, does not answer the question, or fails in the database |
| FR-5a | answer follow-up questions ("show me in table view", "and last month?") when the request carries a `session_id` with history, by rewriting them into standalone questions that then pass every guard; and refuse a bare display request that has no earlier question to show |

### 5.2 Safety checks on generated SQL
| ID | The system shall reject (HTTP 422) any generated SQL that |
|---|---|
| FR-6 | is not a single `SELECT` (or `UNION`, `INTERSECT`, `EXCEPT` of `SELECT`s) statement |
| FR-7 | contains `INSERT`, `UPDATE`, `DELETE`, `MERGE`, `DROP`, `CREATE`, `ALTER`, `TRUNCATE`, `COPY`, `SET`, `GRANT`, `EXPLAIN`, `SELECT ... INTO`, row locks or `FETCH`, anywhere in the tree including inside a CTE |
| FR-8 | reads a table that is not among the chosen tables, or any system schema (this blocks catalogs such as `pg_user`); tables are resolved by sqlglot scope analysis, so a CTE cannot shadow a real table |
| FR-9 | calls a denied function, which includes anything starting `pg_`, `lo_`, `dblink` or `txid_` and functions such as `set_config`, `current_setting` and `version`; table functions are not allowed except `generate_series` |
| FR-10 | is held back by the SQL judge for exposing personal contact details, for being risky, or (after the allowed retries) for not answering the question |

The system shall also **add a row limit of 100** when there is none, and **lower any larger limit to 100** (FR-11).

### 5.3 Execution and response
| ID | The system shall |
|---|---|
| FR-12 | run every query with a dedicated **read-only database login**, inside a READ ONLY transaction, with a **3 second** statement timeout, and refuse to start if the login can write or is a superuser |
| FR-13 | return, for a successful query: `question`, `sql`, `tables_used`, `columns`, `rows`, `row_count`, `risk_score`, `timings_ms`, `answer`, `show_table` |
| FR-14 | write a short human reply (`answer`) from the result, and set `show_table` to true **only** when the question explicitly asks for a table, or when no reply text could be produced |
| FR-15 | still answer successfully with a plain fallback sentence if the Answer Writer fails, times out or is switched off (`NATURAL_ANSWERS=false`) |
| FR-16 | reply with a fixed friendly message, without running a query, when the data cannot answer the question or the question's subject is not stated |
| FR-17 | provide `GET /health` reporting the number of tables in the bundle, answering only once startup (including the database role check) has succeeded |
| FR-17a | check the reply with the output guard and refuse it rather than return leaked sensitive data or text that followed instructions found in the rows |

### 5.4 Knowledge layer and sample database
| ID | The system shall |
|---|---|
| FR-18 | describe each table in one OKF v0.2 concept file: YAML front matter with at least `type`, and recommended `title`, `description`, `resource`, `tags`, plus a Markdown body with `# Schema`, relationships as links to other table files, and `# Examples` (a question and its SQL) |
| FR-19 | keep the bundle conformant with OKF v0.2: a root `index.md` carrying `okf_version: "0.2"`, `index.md` files without front matter elsewhere, a `log.md` of dated entries, and bundle-relative links; and provide `okf-chat check` to verify this. Consumers shall tolerate unknown keys, broken links and a missing `index.md` |
| FR-19a | build and rebuild the bundle from the live database (`okf-chat build`): regenerate facts from the database, keep hand edits (existing bundle, then seed directory, then database `COMMENT`, then an automatic placeholder), remove files of dropped tables, and mark tables the read-only role cannot SELECT as `sensitive: true` |
| FR-20 | ship a 50-table sample database (e-commerce 21, HR 9, finance 10, support 10) of realistic, internally consistent data, loaded by numbered SQL files in `db/` |
| FR-21 | keep at least one sensitive table (`salaries`) **deliberately unreadable** by the application's login, and never describe sensitive tables to any model |
| FR-21a | be usable inside another Python application (`from okf_chat import OKFChat`, with async `ask` and sync `ask_sync`), loading CrewAI only on first use |

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
| FR-29a | send its chat id as `session_id`, so follow-up questions work inside one chat |

### 5.6 Setup
| ID | The system shall |
|---|---|
| FR-30 | start the sample database with one command (`docker compose up -d db`), and the API too with `docker compose up -d --build` |
| FR-31 | install with `pip install -e ".[dev]"` and start with `okf-chat serve` (default port 8001); also provide `okf-chat ask "question"`, `okf-chat build` and `okf-chat check` |

---

## 6. Non-functional requirements

### 6.1 Security (defence in depth)
Each layer must work **on its own**, so a failure in one is caught by the next.

| ID | Requirement |
|---|---|
| NFR-1 | **Zero schema leakage.** The raw database schema is never sent to a model. Models only receive OKF descriptions of tables that survived navigation, and never those of sensitive tables. |
| NFR-2 | **Read-only enforcement in two places.** sqlglot must parse every generated query and confirm no data-changing statement exists (FR-6, FR-7), **and** the database login itself must be unable to write. The validator's function list is a blocklist and is not the last line of defence; the read-only role, READ ONLY transaction and statement timeout are. |
| NFR-3 | **Least privilege.** The application login (`okf_readonly`) has `SELECT` only on the documented tables, runs read-only transactions, and has its own 3 second timeout. The admin login is used only at build time (`okf-chat build`). |
| NFR-4 | **Secrets.** API keys live only in `.env` or the environment. `.env` must never be committed (`.gitignore` excludes it; `.env.example` is the template). |
| NFR-5 | **No instructions from data.** Text found in query results is treated as data. The Answer Writer is told to ignore any instructions inside it, and the output guard checks the reply. |
| NFR-6 | **Demo credentials.** The sample login password is for local use only and must be changed before real data is connected. |
| NFR-6a | **Fail closed.** If Jev is unreachable, questions are refused (`JEV_FAIL_OPEN=false`). |

### 6.2 Privacy and data flow
| ID | Requirement |
|---|---|
| NFR-7 | The question and the chosen table descriptions go to the SQL Writer's model. **No data rows** are sent at that step. |
| NFR-8 | To write the reply, **result rows** go to the Answer Writer's model: at most 30 rows (`ANSWER_MAX_ROWS`). This step must be switchable off (`NATURAL_ANSWERS=false`), after which no rows leave the service. |
| NFR-9 | Chat history shown in the window is stored only in the user's browser (`localStorage`). The backend keeps only a short in-process memory for follow-ups (last 4 turns, 30 minutes idle, 500 sessions), which holds only questions and replies already returned to the user, and is lost on restart. |

### 6.3 Time limits
A request must never hang. Every wait has a limit.

| Limit | Value | When exceeded |
|---|---|---|
| Database query (`STATEMENT_TIMEOUT_MS`) | 3 s | database cancels it; HTTP 504 `Query exceeded the 3 second limit` |
| One Jev call (`JEV_TIMEOUT_S`) | 10 s | refused (or let through when `JEV_FAIL_OPEN=true`) |
| One OpenAI call (`OPENAI_TIMEOUT_S`) | 20 s | HTTP 504 `Request timed out: the AI model did not answer in time` |
| Whole request (`PIPELINE_TIMEOUT_S`) | 30 s | HTTP 504 `Request timed out: the service took longer than N seconds` |
| Chat window | 40 s | the window stops waiting, cancels the request and tells the user |

The chat window's limit stays above the backend's, so the backend's clean 504 normally arrives first.

### 6.4 Quality attributes
| ID | Requirement |
|---|---|
| NFR-10 | **Performance.** A typical answer takes about 5 seconds (median 5.4 s, 95th percentile 10 s on the last live run), almost all of it in model calls; the database query itself is usually a few milliseconds. A follow-up adds 1 to 2 seconds for the rewrite. |
| NFR-11 | **Reliability.** A failure of the Answer Writer never fails a question whose data is ready. A rejected or failing SQL draft is retried up to twice. |
| NFR-12 | **Observability.** Every response includes per-step timings (`rewrite`, `guard_in`, `navigate`, `sql_write`, `validate`, `judge`, `execute`, `answer`, `guard_out`; a step that runs twice adds up). |
| NFR-13 | **Portability.** Runs on Windows, macOS and Linux. Tested on Windows 11 with PostgreSQL 16 in Docker. On Windows the executor uses synchronous psycopg in a worker thread, because psycopg's async mode does not work on the default event loop. |
| NFR-14 | **Maintainability.** Tables are added by rebuilding the bundle from the database; thresholds are named constants; behaviour is covered by automated tests; packages are pinned exactly. |
| NFR-15 | **Accessibility basics.** The chat window gives its buttons text labels and uses a proper switch control (`role="switch"`). Full keyboard and screen-reader testing has not been done. |
| NFR-16 | **Standards.** The bundle follows OKF v0.2 and must keep passing `okf-chat check`. |

---

## 7. API contract

Full details, including the settings table, are in the [backend guide](okf-crewai-service/README.md#http-api).

| Endpoint | Purpose |
|---|---|
| `GET /health` | `{"status":"ok","tables_indexed":50}` |
| `POST /api/text-to-sql` | body `{"question": "...", "session_id": "optional"}`; returns the response described in FR-13 |

| Status | Meaning |
|---|---|
| 200 | answered |
| 400 | blocked by the input guard: `prompt_injection`, `data_modification` or `off_topic` |
| 422 | invalid body; sensitive data requested; SQL rejected by the validator or the SQL judge (`semantic risk 0.xx`); or the database refused the query (for example permission denied) |
| 502 | the AI model returned an error |
| 503 | the safety check (Jev) or the database is unavailable |
| 504 | database query over 3 s, or the whole request over its budget |

Refusals carry `{"detail": "..."}`. The chat window matches on these exact texts, so they must not be reworded. Browser access is limited to the origins in `CORS_ORIGINS` (default `http://localhost:4200`).

---

## 8. Verification and results

| What | How it is checked | Result at the last run |
|---|---|---|
| Automated tests | `python -m pytest -q` (15 test files: validator, executor, guards, SQL judge, navigator, loader, builder, agents, memory, pipeline, API, sample data) | about 330 pass; database tests skip without Docker |
| Full pipeline, live | `tools/eval_pipeline.py` on 72 answerable questions, plus attacks and restricted-data questions | **72 of 72** answered, **21 of 21** attacks and restricted questions refused |
| Overfitting check | held-out question sets in `tests/data/` (the navigator was tuned on 55 questions and confirmed on 18 held-out ones) | tuning and held-out results unchanged |
| Follow-ups, live | `tools/eval_followups.py`: 21 conversations, 46 turns, including attacks hidden in follow-ups | **21 of 21** conversations, **46 of 46** turns |
| Guards | `tools/eval_guards.py`: good questions score at most 0.11 on every input hazard, bad ones at least 0.96; good replies at most 0.08 on output hazards, bad ones at least 0.94 | calibrated; thresholds sit mid-gap |
| OKF conformance | `okf-chat check`; independently checked against the official v0.2 spec (front matter, reserved files, links, timestamps) | 50 concepts, 286 links, 0 problems |
| SQL validator rules | `tests/test_sql_validator.py` | passes |
| Chat window | scripted real-browser run: sidebar, history, SQL switch, reload persistence, delete and clear, mobile layout, error messages, 40 s timeout | passed when last run |

**Reading these numbers:** the model-based steps vary a little between runs, so each figure is a single sample. The question sets are small (guard wording was calibrated on 58 good and 15 bad questions), and one set is not independent of the output-guard tuning. Get an independent set, ideally real user questions, before trusting the numbers further. Re-run the evaluation after changing any threshold or prompt.

---

## 9. Project structure

```
OKF_JEV/
├── README.md                        plain-language overview and quick start
├── okf_jev_requirement.md           this document
├── docs/                            flow chart image (+ source)
├── okf-crewai-service/              the backend
│   ├── src/okf_chat/
│   │   ├── api/                     FastAPI app and request/response schemas
│   │   ├── core/
│   │   │   ├── pipeline.py          step order, retries, 30 s budget, refusals
│   │   │   ├── navigator.py         Jev table scoring, OKF-link bridges and neighbours
│   │   │   ├── okf_loader.py        OKF v0.2 reader and conformance checker
│   │   │   ├── sql_validator.py     sqlglot safety rules, row limit
│   │   │   ├── sql_executor.py      read-only Postgres run, role check
│   │   │   └── memory.py            short per-session chat memory
│   │   ├── agents/                  SQL Writer, Answer Writer, Rewriter (CrewAI; llm.py is the only import)
│   │   ├── guardrails/              Jev client, input/output guards, SQL judge, thresholds and messages
│   │   ├── builder/                 database introspection and OKF bundle builder
│   │   ├── cli.py                   okf-chat serve | ask | build | check
│   │   ├── factory.py               wires everything together
│   │   └── config.py                settings from the environment
│   ├── okf_bundle/                  the OKF v0.2 bundle: index.md, log.md, tables/<domain>/<table>.md
│   ├── db/                          numbered SQL files for the sample database, domains.yaml
│   ├── tools/                       live smoke and evaluation scripts, examples.yaml
│   ├── tests/                       deterministic tests, question sets in data/
│   ├── HANDOFF.md                   decisions, known limits, how to resume
│   └── Dockerfile, docker-compose.yml, pyproject.toml, .env.example
└── okf-chat-ui/                     the Angular chat window
    └── src/app/                     chat, sidebar, store (history and settings), service, environment
```

---

## 10. Limits and future work

**Known limits**
- **Memory is short and in-process.** Follow-ups work within a chat, but memory holds only the last 4 turns, expires after 30 minutes idle, and is lost on restart.
- **Extra tables.** The navigator picks about one extra table per question; the SQL Writer ignored them in every live case. Bridging by hop count can pick an odd route.
- **One ambiguous question remains.** "How much has Ravi Kumar spent" is genuinely ambiguous with the `expenses` table.
- **Reply wording.** A reply can state something true of the rows shown but not of the whole table.
- **Small evidence.** See the note in [section 8](#8-verification-and-results).
- **Single provider.** If OpenAI or Jev is down there is no fallback model; questions fail with a 502, 503 or 504 until it recovers.
- **No connection pool.** Each query opens a connection (15 to 35 ms).
- **Tested platforms.** Tested on Windows 11 only; macOS and Linux are expected to work but are not yet tried.
- **Bundle covers tables only.** All 50 concept files are of type `Postgres Table`. OKF also allows business concepts, metrics and glossary entries, which are not used yet.

**Possible next steps**
1. An independent set of real user questions to re-measure accuracy, and a measurement of the effect of the `# Examples` sections.
2. Business-concept and metric files in the OKF bundle, and `verified`, `status` and `stale_after` front matter for trust and freshness.
3. OKF Attested Computation entries for fixed, approved queries.
4. A request concurrency limit for model rate limits, and a connection pool.
5. Sign-in and per-user table permissions.
6. Streaming replies.

---

## 11. Glossary

| Term | Meaning |
|---|---|
| **SQL** | the language used to query a database |
| **OKF** | Open Knowledge Format: Google's format for written knowledge, a folder of Markdown files with YAML front matter. Here, one file per table (name, purpose, tags, columns, relationships as links, examples), plus an `index.md` and a `log.md` |
| **Bundle** | the OKF folder (`okf_bundle/`) that holds all the knowledge about the database |
| **Concept** | one non-reserved file in an OKF bundle; here, one table |
| **Jev** | TypeSafe AI's fast decision model, used as a "System 1" judge for quick yes/no decisions |
| **Noul** | the Jev primitive used here: give a yes/no probability for a question |
| **CrewAI** | the agent library behind the SQL Writer, Answer Writer and Rewriter |
| **Navigator** | the step that chooses which tables a question needs, using Jev scores and OKF links |
| **sqlglot** | a library that parses SQL into a syntax tree, so it can be inspected instead of trusted |
| **Read-only login** | a database account that can look but cannot change anything |
| **Sensitive table** | a table the read-only login cannot read (such as `salaries`), marked `sensitive: true` in the bundle and never shown to any model |
| **Prompt injection** | text crafted to make an AI ignore its instructions or reveal secrets |
| **Deterministic pipeline** | a fixed sequence of steps, as opposed to an AI agent that decides its own steps |
| **Session** | one chat, identified by `session_id`, whose recent turns the backend remembers so follow-ups work |

---

## 12. What changed since the first version

The first version used plain code calling OpenAI, a FAISS vector index over one OKF-style file per table, and no memory. It lived in `okf-sql-ai-service`, which has been removed. The current system replaces it:

| Area | Change |
|---|---|
| Knowledge layer | the FAISS index and custom table files are replaced by a conformant **OKF v0.2 bundle** with an index, a log, linked concept files and `# Examples`, built from the database and checked by `okf-chat check` |
| Table selection | Jev scores every table directly, and OKF links supply join bridges; no embeddings are needed |
| Agents | SQL and reply writing moved to **CrewAI agents**, with a third Rewriter agent for follow-ups |
| Memory | follow-up questions now work, with short in-process session memory |
| Safety | an output guard and a Jev SQL judge (contact details, risk, mismatch with retry) replace the single risk score; a stricter validator (scope-resolved tables, no system schemas, denied function families); the service refuses to start with a login that can write |
| Embedding | `OKFChat` library entry for use inside another Python application |
| Data | the sample database now has realistic names, consistent money and about 100 customers |
| Interface | the Angular chat window sends its chat id and talks to port 8001 |
