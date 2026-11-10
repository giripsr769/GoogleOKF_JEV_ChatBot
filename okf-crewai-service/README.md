# okf-crewai-service

A chatbot service that answers plain-English questions about a Postgres database.

What the database means (tables, columns, keys, descriptions) is kept in an **OKF v0.2 bundle**: Markdown files with YAML
frontmatter, generated from the real schema and editable by hand. Two CrewAI agents write the SQL and the answer. Everything else
(guardrails, table selection, SQL checks) is plain Python or TypeSafe **Jev**.

```
question
  -> input guard (Jev)            core/pipeline.py + guardrails/guards.py
  -> navigator (Jev scores OKF tables, follows links to join)   core/navigator.py
  -> SQL Writer (CrewAI agent)                                  agents/sql_writer.py
  -> validator (sqlglot, hard rules)                            core/sql_validator.py
  -> SQL judge (Jev: matches question? exposes contact details?) guardrails/sql_judge.py
  -> read-only Postgres run (3 s limit, READ ONLY transaction)  core/sql_executor.py
  -> Answer Writer (CrewAI agent)                               agents/answer_writer.py
  -> output guard (Jev)
  -> reply
```

Follow-up questions work: send the same `session_id` with each question of a chat and a short rewriter agent (the third agent, only
called when the session already has history) turns "show me in table view" or "and last month?" into a standalone question, which then
runs through every guard as usual. Memory is in-process, short (last 4 turns, 30 minutes idle) and holds only questions and replies that
already reached the user; a restart forgets it. Without a `session_id` each question stands alone.

## Quick start

You need Python 3.10 to 3.13, Docker Desktop, an OpenAI-compatible key and a TypeSafe (Jev) key.

```bash
cd okf-crewai-service
python -m venv .venv
./.venv/Scripts/pip install -e ".[dev]"     # Linux/macOS: .venv/bin/pip
cp .env.example .env                        # then put your two API keys in .env
docker compose up -d db                     # sample Postgres 16 on host port 5433, database "shop" (db/01-05 seed it with realistic names, consistent money and about 100 customers)
okf-chat check                              # the bundled okf_bundle/ should conform to OKF v0.2
okf-chat serve                              # http://127.0.0.1:8001
```

Try it:

```bash
okf-chat ask "How many customers do we have?"
curl -X POST localhost:8001/api/text-to-sql -H "content-type: application/json" -d '{"question":"Top 3 products by revenue"}'
```

Or run the API in Docker too: `docker compose up -d --build` (service `api`, port 8001; it mounts `okf_bundle/` read-only and
connects to the database as the read-only login).

The sample database logins (Docker only):
- chatbot, read-only: `postgresql://okf_readonly:okf_readonly@localhost:5433/shop` (`salaries` is deliberately not granted)
- admin, build time only: `postgresql://postgres:postgres@localhost:5433/shop`

## HTTP API

| Endpoint | Purpose |
|---|---|
| `GET /health` | `{"status": "ok", "tables_indexed": N}`. Only answers once startup, including the database role check, has succeeded. |
| `POST /api/text-to-sql` | Body `{"question": "...", "session_id": "optional chat id"}` (question 1 to 1000 characters; id up to 64 of `A-Za-z0-9_-`). Returns `question, sql, tables_used, columns, rows, row_count, risk_score, timings_ms, answer, show_table`. |

Refused questions return an HTTP error with `{"detail": "..."}`:

| Status | Meaning | Detail starts with |
|---|---|---|
| 400 | blocked by the input guard | `Request blocked: classified as 'data_modification' \| 'prompt_injection' \| 'off_topic'` |
| 422 | blocked by the SQL judge, the validator, or database permissions; or an invalid body | `... semantic risk 0.xx`, `... permission denied ...` |
| 504 | timeout | `Query exceeded the 3 second limit`, `Request timed out: the service took longer than N seconds` |

The chat UI in `../okf-chat-ui` matches on these exact texts, so do not reword them. The UI points at this service's port 8001
(`apiUrl` in `okf-chat-ui/src/app/environment.ts`); change it if you run the service on another port.

## Configuration

Set as environment variables or in `.env`.

| Variable | Default | Meaning |
|---|---|---|
| `OPENAI_API_KEY` | | key for the SQL Writer and Answer Writer |
| `TYPESAFE_API_KEY` | | key for Jev (guards, navigator, SQL judge) |
| `OPENAI_MODEL` | `gpt-6-luna` | model for both agents (no temperature is ever set) |
| `JEV_MODEL` | `jev-latest` | Jev model |
| `DATABASE_URL` | `postgresql://okf_readonly:okf_readonly@localhost:5433/shop` | **read-only** login used at run time |
| `ADMIN_DATABASE_URL` | | build time only (`okf-chat build`); the running service never uses it |
| `OKF_BUNDLE_DIR` | `okf_bundle` | folder of the OKF bundle |
| `CORS_ORIGINS` | `http://localhost:4200` | comma-separated allowed origins |
| `PIPELINE_TIMEOUT_S` | `30` | total time budget per question |
| `OPENAI_TIMEOUT_S` | `20` | per model call |
| `JEV_TIMEOUT_S` | `10` | per Jev call |
| `JEV_FAIL_OPEN` | `false` | if Jev is unreachable: `false` refuses the question, `true` lets it through |
| `NATURAL_ANSWERS` | `true` | write a sentence answer (otherwise a plain fallback) |
| `ANSWER_MAX_ROWS` | `30` | rows shown to the Answer Writer |
| `MAX_RESULT_ROWS` | `100` | row limit on every query |
| `STATEMENT_TIMEOUT_MS` | `3000` | database statement timeout |
| `SQL_MAX_RETRIES` | `2` | extra SQL drafts when a draft is rejected or fails |
| `NAVIGATOR_MAX_TABLES` | `4` | tables handed to the SQL Writer |
| `MEMORY_TURNS` | `4` | earlier turns remembered per session; `0` switches memory off |
| `MEMORY_TTL_S` | `1800` | a session is forgotten after this many idle seconds |
| `MEMORY_MAX_SESSIONS` | `500` | sessions kept in memory (least recently used dropped) |
| `PORT` | `8001` | default port of `okf-chat serve` |

## Safety model

Several independent layers, so no single one has to be perfect:

1. **Input guard (Jev):** blocks data modification, prompt injection, off-topic and sensitive requests before any SQL exists.
2. **Sensitive tables:** tables the read-only role cannot SELECT are marked `sensitive: true` in the bundle and are never shown to any model.
3. **SQL validator (sqlglot):** one SELECT statement only, known tables only, no dangerous functions, a row `LIMIT` is forced. The function list is a blocklist, so it is not the last line of defence.
4. **SQL judge (Jev):** does the SQL answer the question, and does it expose personal contact details?
5. **Read-only database:** the login must be SELECT-only (checked at startup; a superuser or write-capable login stops the service), each query runs in a READ ONLY transaction with a statement timeout.
6. **Output guard (Jev):** checks the reply for leaked sensitive data or followed injected text.

For a follow-up, the raw message is also screened for injection and data changes before the rewritten question is, so an attack cannot be hidden by the rewrite.

If Jev is down the service refuses by default (`JEV_FAIL_OPEN=false`).

## Use it in another application

1. **Build the bundle** from your database with a login that can see every table:
   `okf-chat build --admin-url postgresql://admin:...@host/db --out okf_bundle [--schema public] [--readonly-role your_ro_role] [--seed-dir older_okf_files] [--domains domains.yaml]`
   Tables the read-only role cannot SELECT become `sensitive`. `domains.yaml` groups tables into folders (see `db/domains.yaml`).
2. **Edit the descriptions by hand.** Better table and column descriptions are the cheapest accuracy gain, and so are `# Examples` sections (a question plus its SQL; see `tools/examples.yaml` and `tools/add_examples.py` for a checked way to add them). Rebuilds keep hand edits
   (existing bundle > seed dir > database `COMMENT` > automatic placeholder), regenerate facts from the database, and remove files of dropped tables.
   Run `okf-chat check` afterwards.
3. **Set the environment:** the two API keys, `DATABASE_URL` (a read-only login), `OKF_BUNDLE_DIR`, `CORS_ORIGINS`.
4. **Run the service** (`okf-chat serve`, or Docker) **or embed it:**

```python
from okf_chat import OKFChat

chat = OKFChat(bundle="okf_bundle", database_url="postgresql://readonly:...@host/db")
result = chat.ask_sync("How many orders were placed last month?", session_id="user-42")   # or: await chat.ask(...)
print(result.answer, result.sql)
```

`ask` raises `okf_chat.core.pipeline.Refusal` (with `status_code`, `detail`, `message`) when a question is not answered.
`import okf_chat` is cheap; CrewAI loads on first use.

## Development

```bash
docker compose up -d db
./.venv/Scripts/python.exe -m pytest -q     # about 380 tests; the 45 database tests skip without Docker
```

Live tools (they call OpenAI and Jev and cost money; they read `OPENAI_API_KEY` and `TYPESAFE_API_KEY` from `.env`, but take the database login from `SMOKE_DATABASE_URL`, which defaults to the Docker read-only login, never from `DATABASE_URL`). Run them with `./.venv/Scripts/python.exe tools/<name>.py`:

| Command | Purpose |
|---|---|
| `tools/smoke_jev.py` | guards on a few examples |
| `tools/smoke_navigator.py` | navigator on 14 questions |
| `tools/smoke_sql.py` | validator + judge + executor chain |
| `tools/smoke_agents.py ["question"]` | navigator + both agents + database |
| `tools/eval_navigator.py` | compare navigator wordings and rules |
| `tools/eval_guards.py [--output] [--refresh]` | calibrate the guards |
| `tools/eval_pipeline.py [--only held] [-v]` | the whole pipeline on all question sets (about 90 calls) |
| `tools/eval_followups.py [--only attack] [-v]` | follow-up conversations (chat memory), 21 conversations, 46 turns |

Sample database: `db/01` to `db/05` run in order on a fresh Docker volume. `03` replaces placeholder text with realistic names, `04` makes every money column agree (`tests/test_sample_money.py` checks it), and `05` grows the data to about 100 customers. Known gaps: invoice lines do not sum to their invoice, and purchase orders without lines keep their stored total.

Notes:
- The model `gpt-6-luna` rejects `temperature=0`, so no temperature is ever set.
- CrewAI is chosen over AutoGen, which is archived.
- `python-dotenv` is pinned to `1.2.2` because `crewai 1.14.7` forces it.
- The retry loop has only been exercised by tests with fakes; every live question needed one SQL draft.
- `EMBEDDING_MODEL` in an older `.env` is unused.
- Windows: the executor uses synchronous psycopg in a worker thread, because psycopg's async mode does not work on the default Windows event loop.
- `agents/runtime.py` must be imported before `crewai`.

See `HANDOFF.md` for decisions and known limits.
