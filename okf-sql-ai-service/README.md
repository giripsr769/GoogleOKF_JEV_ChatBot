# OKF + Jev Text-to-SQL Service

The backend. It takes a question in plain English, works out which database tables matter, writes one safe `SELECT`, runs it with a read-only database login, and returns a short human reply together with the SQL, the rows and timings. The chat window is in [`../okf-chat-ui`](../okf-chat-ui/README.md); the overview of the whole project is in the [root README](../README.md).

```
question -> Jev gate -> FAISS over OKF files -> Jev rerank -> join-path expansion -> OpenAI writes SQL
         -> sqlglot checks + Jev risk score -> PostgreSQL (read-only, 3 s, 100 rows) -> OpenAI writes the reply
```

## Contents
[Requirements](#requirements) · [Run with Docker](#run-with-docker) · [Run without Docker](#run-without-docker) · [Configuration](#configuration) · [API](#api) · [How a question is processed](#how-a-question-is-processed) · [Security layers](#security-layers) · [Time limits](#time-limits) · [Natural-language replies](#natural-language-replies) · [The sample database](#the-sample-database) · [Tests and evaluation](#tests-and-evaluation) · [Tunables](#tunables) · [Troubleshooting](#troubleshooting) · [Known limitations](#known-limitations)

## Requirements
| You need | Why |
|---|---|
| A **TypeSafe AI** API key | the Jev models (gate, rerank, risk check). Required: the app does not start without it |
| An **OpenAI** API key | writes the SQL and the reply, and creates the table embeddings |
| **Docker Desktop**, *or* **Python 3.11** + **PostgreSQL 13 or newer** | Docker brings its own database; otherwise you install both yourself. Tested on Python 3.11 and PostgreSQL 16 |
| Node.js 20+ | only for the chat window |

Both keys are paid services: every question makes several calls (roughly 4 to 6 Jev calls and 2 to 3 OpenAI calls).

## Run with Docker
```
cp .env.example .env            # Windows (cmd): copy .env.example .env
# open .env and set TYPESAFE_API_KEY and OPENAI_API_KEY
docker compose up --build
```
This starts the API on **http://localhost:8000** and a seeded PostgreSQL (database `shop`, 50 tables). On a fresh start Postgres runs `db/01_init.sql` then `db/02_init_extra.sql` automatically. The API builds its vector index on first start (one small OpenAI call).

Check it: open http://localhost:8000/health (expect `{"status":"ok","tables_indexed":50}`) and the interactive docs at http://localhost:8000/docs, or:
```
curl -X POST http://localhost:8000/api/text-to-sql -H "Content-Type: application/json" -d "{\"question\":\"Top 3 customers by total order value\"}"
```
Notes: inside Docker the database address comes from `docker-compose.yml`, so the `DATABASE_URL` in `.env` is ignored. The database is **not** published to your machine (no port 5432); to inspect it use `docker compose exec db psql -U postgres -d shop`. Stop with `Ctrl+C`; `docker compose down` removes the containers but keeps the data (`down -v` also deletes it).

## Run without Docker
Everything runs directly on your machine: a Python virtual environment for the API, and a PostgreSQL server you install yourself.

### 1. Install the prerequisites
**Python 3.11** (3.10 to 3.12 should work): https://www.python.org/downloads/ (on Windows tick "Add python.exe to PATH"). Check with `python --version` (`python3 --version` on macOS/Linux).

**PostgreSQL 13+** with a superuser you know the password of:
- **Windows:** the installer from https://www.postgresql.org/download/windows/ (or `winget install PostgreSQL.PostgreSQL.16`). Remember the password you choose for the `postgres` user; the service starts by itself.
- **macOS:** `brew install postgresql@16 && brew services start postgresql@16`. Homebrew's superuser is **your macOS username, with no password**, so pass `--pg-user YOURNAME` below.
- **Ubuntu/Debian:** `sudo apt install postgresql python3-venv`, then give the `postgres` user a password: `sudo -u postgres psql -c "ALTER USER postgres PASSWORD 'choose-one'"`.

Make sure it is running and listening on port 5432 (or note the port you chose).

### 2. One command
From this folder (`okf-sql-ai-service/`):
```
python scripts/setup_local.py --pg-password YOUR_POSTGRES_PASSWORD
```
It does five things and is safe to run again (it never overwrites an existing `.env`, environment or database):

| Step | What it does |
|---|---|
| 1 | creates a virtual environment in `.venv` |
| 2 | installs `requirements.txt` into it (a few minutes the first time) |
| 3 | creates `.env` from `.env.example` if you have none, and tells you which keys are still missing |
| 4 | creates the `shop` database, loads the 50 tables and sample rows, creates the read-only `okf_readonly` login, then checks it works |
| 5 | prints the command to start the API |

Options (all optional): `--pg-host`, `--pg-port`, `--pg-user`, `--pg-password` (or the standard `PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD` variables) say how to reach PostgreSQL as an administrator; `--venv PATH` puts the environment elsewhere; `--skip-db` leaves the database alone; `--reset-db --yes` drops and rebuilds the `shop` database (**deletes its data**); `--start` launches the API when setup finishes. If you give no password and the server needs one, you are asked for it.

### 3. Add your API keys
Open `.env` and set `TYPESAFE_API_KEY` and `OPENAI_API_KEY`. The `DATABASE_URL` line is already right for a PostgreSQL on this machine at port 5432; change the port in it if yours differs (the database step prints the exact line to use).

### 4. Start the API
```
# Windows (PowerShell or cmd)
.venv\Scripts\python -m uvicorn src.main:app --reload
# macOS / Linux
.venv/bin/python -m uvicorn src.main:app --reload
```
Open http://localhost:8000/health (expect `"tables_indexed":50`) and http://localhost:8000/docs. The first start creates `vector_store/okf.faiss` (the table index) with one small OpenAI call. Then start the chat window as described in [`../okf-chat-ui/README.md`](../okf-chat-ui/README.md).

### Doing the steps by hand instead
```
python -m venv .venv
.venv/bin/pip install -r requirements.txt            # Windows: .venv\Scripts\pip install -r requirements.txt
cp .env.example .env                                  # then add the two keys

psql -U postgres -c "CREATE DATABASE shop"
psql -U postgres -d shop -f db/01_init.sql            # the order matters: 01 before 02
psql -U postgres -d shop -f db/02_init_extra.sql
```
or run just the database part with `python scripts/db_setup.py` (same `--host/--port/--user/--password/--reset/--yes` options; it checks that the 50 tables exist, that `okf_readonly` can read, and that it cannot write or see `salaries`).

## Configuration
Set in `.env` (the app reads it at startup; real environment variables win over the file).

| Variable | Default | Meaning |
|---|---|---|
| `TYPESAFE_API_KEY` | none, required | TypeSafe AI (Jev) key |
| `OPENAI_API_KEY` | none, required | OpenAI key |
| `DATABASE_URL` | `postgresql://okf_readonly:okf_readonly@localhost:5432/shop` | connection used for queries; always use the read-only login |
| `OPENAI_MODEL` | `gpt-4o` | model that writes the SQL and the reply. The code does not set `temperature`, so models that only allow the default also work |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | model for the table index; changing it rebuilds the index |
| `JEV_MODEL` | `jev-latest` | Jev model |
| `CORS_ORIGINS` | `http://localhost:4200` | browser origins allowed to call the API, comma-separated |
| `SEARCH_K` | `8` | tables FAISS hands to the Jev rerank |
| `NATURAL_ANSWERS` | `1` | `0` turns off the reply writer: no result rows go to OpenAI and the UI shows the table |
| `ANSWER_MAX_ROWS` | `30` | most rows sent to OpenAI to write a reply |
| `ANSWER_TIMEOUT_S` / `PIPELINE_TIMEOUT_S` / `OPENAI_TIMEOUT_S` / `JEV_TIMEOUT_S` | `10` / `30` / `20` / `10` | see [Time limits](#time-limits) |

## API
**`GET /health`** returns `{"status":"ok","tables_indexed":50}`.

**`POST /api/text-to-sql`** with `{"question": "..."}` (3 to 500 characters). Example response:
```json
{
  "question": "Top 3 customers by total order value",
  "sql": "SELECT customers.id, customers.full_name, SUM(orders.total_amount) AS total_spent FROM customers JOIN orders ON ... LIMIT 3",
  "tables_used": ["orders", "customers", "order_items"],
  "columns": ["id", "full_name", "total_spent"],
  "rows": [{"id": 1, "full_name": "Asha Rao", "total_spent": 958.99}, "..."],
  "row_count": 3,
  "risk_score": 0.34,
  "timings_ms": {"gate": 511, "retrieve": 896, "rerank": 394, "expand": 0, "generate": 3502, "validate": 401, "execute": 8, "answer": 1500},
  "answer": "Asha Rao leads at 958.99, followed by Mei Chen at 59.99 and Ravi Kumar at 44.00.",
  "show_table": false
}
```
`answer` is the human reply. `show_table` is `true` only if the question explicitly asked for a table (or no reply text could be written); the rows are always returned.

| Status | Meaning |
|---|---|
| 200 | answered |
| 400 | blocked by the Jev gate: `Request blocked: classified as 'prompt_injection' / 'data_modification' / 'off_topic'` |
| 422 | the question is outside 3 to 500 characters; or the generated SQL was rejected by the validator (`Generated SQL rejected: ...`) or the risk score (`semantic risk 1.84`); or the database refused it (`Database error: ...`, for example permission denied) |
| 504 | the database query passed 3 s (`Query exceeded the 3 second limit`) or the whole request passed its budget (`Request timed out: the service took longer than 30 seconds`) |
| 500 | an unexpected failure, including invalid API keys: check the API log |

## How a question is processed
1. **Gate** (`src/jev_guard.py`): Jev classifies the intent (`valid_data_query`, `data_modification`, `prompt_injection`, `off_topic`) and scores prompt injection. It is told what the database covers (each OKF table name plus its first tags), so "What is the VAT in India" is a data question, not general knowledge.
2. **Retrieve** (`src/okf_loader.py`): the question is embedded and FAISS returns the `SEARCH_K` nearest tables. The index holds one vector per table (built from the OKF description, tags and column names), never any data rows.
3. **Rerank**: Jev scores every candidate table for "is it required to answer this" (the prompt includes the column names). Tables scoring at or above `RERANK_THRESHOLD` are kept; if none qualify, the top vector hit is kept.
4. **Join-path expansion** (`src/join_paths.py`): if the kept tables cannot be joined directly (for example `customers` and `products`), the foreign-key graph proposes bridge tables up to two hops away and Jev picks the needed ones (`orders`, `order_items`). Already-connected selections skip this step.
5. **Generate** (`src/sql_generator.py`): OpenAI sees the question and only the kept tables and writes one `SELECT`. If the output does not parse it is regenerated once.
6. **Validate** (`src/security.py`) and **risk score**: see below.
7. **Execute** (`src/main.py`): `okf_readonly` login, read-only transaction, 3 s statement timeout.
8. **Reply** (`src/answer_writer.py`): see [Natural-language replies](#natural-language-replies).

## Security layers
Each layer works on its own, so a miss in one is caught by the next.
1. **Jev gate**: stops prompt injection, requests to change data, and off-topic chatter before any model sees schema.
2. **Schema filtering**: OpenAI only ever sees the tables that survived retrieval, rerank and expansion.
3. **sqlglot validator** on every generated query:
   - exactly one statement, and it must be a `SELECT` or `UNION`;
   - no `INSERT/UPDATE/DELETE/DROP/CREATE/ALTER/TRUNCATE/INTO/COPY/SET`, including inside CTEs;
   - only the filtered tables (blocks `pg_user`, other catalogs, unselected tables);
   - **function allow-list**: functions sqlglot does not recognise (`pg_sleep`, `pg_read_file`, `dblink`, `current_setting`, `lo_import`, ...) are rejected unless listed in `_ALLOWED_ANON_FUNCS`; ordinary ones (SUM, COUNT, LOWER, EXTRACT, ...) pass;
   - `LIMIT 100` is added, and any larger limit is clamped to 100;
   - only output that does not parse is regenerated; a policy rejection is never retried.
4. **Jev risk score**: SQL scoring above `MAX_RISK` (1.5 on a 0 to 3 scale) is rejected, for example bulk personal data.
5. **Read-only database login**: the API connects as `okf_readonly`, which can only `SELECT` from the documented tables, defaults to read-only transactions and has a 3 s statement timeout. `salaries` is deliberately not granted, so it fails with permission denied even if everything above were bypassed.

## Time limits
| Limit | Default | When exceeded |
|---|---|---|
| Database query | 3 s (fixed, `STATEMENT_TIMEOUT_MS`) | Postgres cancels it; 504 `Query exceeded the 3 second limit` |
| One Jev call (`JEV_TIMEOUT_S`) | 10 s | 504 |
| One OpenAI call (`OPENAI_TIMEOUT_S`, 1 retry) | 20 s | 504 |
| Writing the reply (`ANSWER_TIMEOUT_S`) | 10 s | not an error: plain fallback sentence plus the table |
| Whole request (`PIPELINE_TIMEOUT_S`) | 30 s | 504 `Request timed out ...` |
| Chat window (`requestTimeoutMs`) | 40 s | the UI stops waiting and says so |

A normal answer takes about 3 to 7 seconds, almost all of it in the AI calls; the database query itself is usually under 10 ms. Keep `ANSWER_TIMEOUT_S` well under `PIPELINE_TIMEOUT_S`.

## Natural-language replies
After the query runs, `src/answer_writer.py` asks OpenAI to phrase the result as a short chat reply. `show_table` is true only when the question explicitly asks for one ("in a table", "as a grid", "tabulate", "tabular format"); a bare "the orders table" does not count.
- **Data flow, please read:** this is the one step where result **rows** (not just the question and schema) go to OpenAI. At most `ANSWER_MAX_ROWS` rows are sent, long values are clipped, and the prompt treats the data as data, never as instructions. Set `NATURAL_ANSWERS=0` to stop it: no rows leave the service, `answer` is empty and the UI shows the table.
- If the model call fails, times out or returns nothing, the request still succeeds with a plain sentence ("I found 4 results.") and the table.
- A question the schema cannot answer gets a fixed friendly message, without a model call.

## The sample database
Database `shop`, 50 tables in four areas: e-commerce (21), HR (9), finance (10), support (10), with deliberate look-alikes such as `orders`/`purchase_orders`, `customers`/`employees`, `invoices`/`payments`/`vendor_bills`. Rows are generated placeholders (a few per table), so names like "suppliers name 2" are expected.
- `db/01_init.sql` creates the 4 base tables, their rows and the `okf_readonly` login (password `okf_readonly`, **for local use only**). `db/02_init_extra.sql` is **generated**: edit `tools/schema_spec.py` and run `python tools/gen_schema.py`, which rewrites it together with the matching `okf_tables/*.md`, so documentation and schema cannot drift. The numeric prefixes matter: Docker runs the folder in sorted order.
- **Add a table:** add it to `tools/schema_spec.py` and regenerate, or write the SQL and a new OKF file by hand. An OKF file is Markdown with YAML front matter (`table`, `description`, `tags`, `columns`, `relationships`) in `okf_tables/`. Then `GRANT SELECT ON <table> TO okf_readonly;` (otherwise queries on it fail with permission denied) and restart the API; it rebuilds the index when it sees changed OKF files.
- **Allow another SQL function:** if a legitimate question fails with `Function 'x' is not permitted`, add its lowercase name to `_ALLOWED_ANON_FUNCS` in `src/security.py` after checking it has no file, network or sleep side effects.
- Use your own database instead: write OKF files for your tables, point `DATABASE_URL` at a **read-only** login that can see only those tables, and drop the sample files.

## Tests and evaluation
Run from this folder. With Docker prefix the command with `docker compose exec -T api` (in Git Bash on Windows also set `MSYS_NO_PATHCONV=1`); without Docker use `.venv/bin/python` (`.venv\Scripts\python` on Windows). Everything except `test_retry.py` and `test_answer.py` needs real keys and a database.

| Script | What it checks | Needs keys/DB |
|---|---|---|
| `tests/run_eval.py` | the 55 questions in `tests/eval_questions.json`: gate accuracy, FAISS recall at k=4 to 12, rerank recall and noise, end-to-end correctness, latency; lists every failure; writes `tests/last_run*.json`. `--limit N`, `--domain hr`, `--concurrency 4` | yes |
| `tests/run_eval.py --file heldout_questions.json` | 18 more questions written after tuning, to catch overfitting | yes |
| `tests/test_retry.py` | SQL regeneration rules, with a fake OpenAI client | no |
| `tests/test_answer.py` | table detection and reply fallbacks, with a fake client | no |
| `tests/test_timeout.py` | the 504 paths with hung and timing-out fakes | yes (one normal request) |

At the last full runs the main set scored 55/55 and the held-out set 18/18. These are single samples of model-based stages and vary a little between runs; re-run the evaluation after changing a threshold or a prompt.

## Tunables
`SEARCH_K` (environment). In `src/jev_guard.py`: `INJECTION_THRESHOLD` 0.5, `RERANK_THRESHOLD` 0.35 (lower keeps more tables), `BRIDGE_THRESHOLD` 0.5, `MAX_RISK` 1.5.

## Troubleshooting
| Symptom | Likely cause and fix |
|---|---|
| `setup_local.py`: "Cannot reach PostgreSQL" | PostgreSQL is not running, or is on another port: start it, or pass `--pg-port` |
| "PostgreSQL has no role 'postgres'" | typical on macOS/Homebrew: pass `--pg-user YOURNAME` |
| "rejected the login" | wrong password (or unknown user): pass `--pg-password` / `--pg-user` |
| pip fails with `WinError 206` / "filename too long" | the folder path is too deep for Windows: use a shorter folder, or `--venv C:/okf-venv` |
| `docker compose up` stops with `relation "products" does not exist` | an old checkout where the SQL files were not numbered: use `01_init.sql` and `02_init_extra.sql` |
| API starts but every question returns 500 | wrong or missing API keys (the log shows the provider's error), or a model name your OpenAI account cannot use |
| `permission denied for table X` (422) | the table was added but not granted: `GRANT SELECT ON X TO okf_readonly;` (for `salaries` this is intended) |
| `connection refused` to the database on startup | wrong `DATABASE_URL` host or port for how you run (Docker uses `db`; local uses `localhost`) |
| Browser: CORS error / UI shows "API offline" | add the UI's address to `CORS_ORIGINS` |
| `docker compose exec ... /app/...` fails in Git Bash with `C:/Program Files/Git/app` | Git Bash rewrote the path: prefix with `MSYS_NO_PATHCONV=1` |
| New table is ignored | restart the API so it rebuilds the index (and check the OKF file's YAML: unquoted words like `off` or `no` become booleans) |
| Answers suddenly slow | OpenAI or Jev latency; see the timings under "details" in the UI, and [Time limits](#time-limits) |

## Known limitations
- No memory: each question stands alone, so follow-ups like "and last month?" do not work.
- Jev can rate several purchase-style paths equally likely (carts, invoices, orders), so a few harmless extra tables may reach the SQL step.
- Replies can mention things true of the rows but not of the whole table ("the data includes four customers"); the prompt discourages it but cannot guarantee otherwise.
- If OpenAI or Jev is down there is no fallback model: questions fail with a 504 or 500 until it recovers.
- The setup script and the no-Docker run were tested from a clean checkout on Windows 11 with Python 3.11, against a PostgreSQL 16 server reached over localhost (it happened to run in a container). A natively installed PostgreSQL, macOS and Linux have not been tried; the install steps for them above follow each platform's standard packages.

## Project layout
```
okf-sql-ai-service/
  src/                 main.py (API + pipeline) · jev_guard.py · okf_loader.py · join_paths.py · sql_generator.py
                       security.py · answer_writer.py
  okf_tables/          50 OKF files, one per table
  db/                  01_init.sql, 02_init_extra.sql (generated)
  scripts/             setup_local.py (one-command setup) · db_setup.py (database only)
  tools/               schema_spec.py + gen_schema.py (generate the extra tables and OKF files)
  tests/               evaluation, question sets, deterministic tests
  vector_store/        the FAISS index (generated; safe to delete)
  Dockerfile · docker-compose.yml · requirements.txt · .env.example
```
