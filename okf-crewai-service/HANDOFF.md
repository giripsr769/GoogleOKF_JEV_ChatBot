# okf-crewai-service: handoff

Notes for resuming work in a new session: decisions, gotchas, known limits and open items. How to install, configure and use the
service is in `README.md`. Nothing is committed to git (the owner asked for that). Last updated 2026-11-10.

## State

The service is complete: setup, sample database, OKF builder and checker, guards, navigator, SQL safety, the three CrewAI agents,
pipeline, FastAPI API, CLI (`serve`, `ask`, `build`, `check`), the `OKFChat` library entry, Docker, and docs.

- 378 tests pass (`python -m pytest -q`, about 20 s) with the Docker database up. Without Docker the 45 database tests skip.
- Latest live end-to-end run (`tools/eval_pipeline.py`, real OpenAI + Jev + database): 72/72 good questions answered,
  21/21 attack or restricted questions refused. Median 5.4 s, p95 10 s per question.
- Follow-ups (`tools/eval_followups.py`): 21/21 conversations, 46/46 turns.
- The bundled `okf_bundle/` conforms to OKF v0.2 (`okf-chat check`: 50 concepts, 0 warnings), and was also checked by hand against
  the official spec on 2026-11-10 (front matter, reserved files, links, timestamps: no problems).
- The old `okf-sql-ai-service` was removed on 2026-11-10. Root `README.md` and `okf_jev_requirement.md` describe only this service.

## Resume checklist

Use absolute paths in shell commands. A bare `cd` into another folder earlier shifted the working directory and caused mistakes.

```bash
cd "D:/GIRITHARAN.P/AI Social Eagel/AI_Gen_learnings/OKF_JEV/okf-crewai-service"
docker compose up -d db                    # Postgres 16 on host port 5433, database "shop" (Docker Desktop must be running)
./.venv/Scripts/python.exe -m pytest -q    # expect 378 passed with the database up
./.venv/Scripts/okf-chat.exe check         # expect: conforms to OKF v0.2 (50 concepts, 0 warnings)
```

Test database logins (Docker only, for local development):
- chatbot login, read-only: `postgresql://okf_readonly:okf_readonly@localhost:5433/shop` (`salaries` is deliberately not granted)
- admin, build time only: `postgresql://postgres:postgres@localhost:5433/shop`

The owner's `.env` `DATABASE_URL` is the read-only login above (fixed by the owner after the first handoff). `ReadOnlyExecutor.verify()` refuses
any superuser or write-capable login, so the API stops at startup if that changes. Ask before editing `.env`: it holds real API keys.
The `tools/` scripts read `SMOKE_DATABASE_URL` (default: the Docker read-only login) and never `DATABASE_URL` from `.env`.

## Gotchas

- Windows: the executor uses sync psycopg in a worker thread because psycopg's async mode does not work on the default Windows event loop. Keep it that way.
- `agents/runtime.py` must be imported before `crewai` (silences CrewAI's tracing prompt, telemetry, console panels, and a cp1252 emoji crash). `agents/llm.py` already does this.
- `gpt-6-luna` (the owner's model, real for their key) **rejects `temperature=0`**: never set a temperature.
- The chat UI (`../okf-chat-ui`) matches the exact `detail` texts of the API's refusals (see `friendlyError` in `chat.component.ts`). Do not reword them.
- Chat memory: optional `session_id` (the UI sends its chat id). `core/memory.py` keeps the last `MEMORY_TURNS` standalone questions + reply texts per session, in process, with TTL and LRU cap. `agents/rewriter.py` rewrites follow-ups only when history exists (extra ~1-2 s on follow-ups, none on first questions). Raw follow-up text is guarded for injection/data changes (not off_topic), the rewritten one fully. Refused questions are never stored.
- When editing files from shell scripts, avoid backslash escapes in heredocs (they inserted real line breaks twice); use the editor tool.
- Guard wording matters more than thresholds. Tune with `tools/eval_guards.py` using the cached scores in `tests/last_run_*.json`; the pipeline eval records every Jev call. The SQL writer is told to never select email, phone or address unasked.

## Decisions already made (do not re-open without a reason)

- CrewAI, not AutoGen (AutoGen is archived). Only `agents/llm.py` imports CrewAI, so it can be swapped.
- Only three LLM agents (SQL Writer, Answer Writer, and the follow-up Rewriter, added 2026-11-07 for chat memory); every other step is plain Python or Jev.
- API port 8001 and database port 5433 (not the defaults 8000 / 5432), so they do not clash with services already on the host. The UI's `apiUrl` is 8001.
- Exact package pins on the last patch of an older, mature minor line (`pyproject.toml`); `python-dotenv 1.2.2` is forced by `crewai 1.14.7`.
- Sensitive tables are marked `sensitive: true` in the OKF files automatically (the read-only role cannot SELECT them) and are never shown to any model.
- Sample data (2026-11-07): `db/03_realistic_names.sql` replaces every generated placeholder (210 values in 30 columns of 21 tables, plus `CODE001` coupon/account codes and `...N@example.com` emails) with realistic text, and un-inverts one job-title salary range. It runs on a fresh database after 01 and 02, and was applied to the running one with the admin login. `tests/test_sample_data.py` fails if a placeholder returns. Numbers (budgets, salaries, amounts) are untouched and still small random values.
- Sample money (2026-11-07): `db/04_consistent_money.sql` makes every money column agree (US dollars). The shop core (products, orders, order_items) was already consistent and is the source of truth. Derived from `orders.total_amount`: payments (the order total; a failed and a refunded attempt on one order each carry it), invoices and returns on one order (split so they add up exactly), invoice lines (quantity x list price), coupon discounts (percent of order total). Supplier costs are 57-66% of list price, purchase lines use them, purchase orders with lines are the sum. HR: job-title ranges in realistic annual dollars, salaries (restricted table) inside the range and rising with date, department budgets in the millions, yearly budgets 90-95% of that with one over-budget year per kind. Finance: balanced double-entry ledger, realistic vendor bills, bank transactions, expenses and tax rates. Run it on a fresh database after 01-03 (automatic in Docker) or apply it to an existing one with the admin login; safe to repeat. `tests/test_sample_money.py` checks all of it. Not reconciled: invoice lines do not sum to their invoice (the seed links lines to unrelated products), and purchase orders without lines keep their stored total.
- Sample scale (`db/05_scale_up.sql`): grows the database to about 100 customers and 124 orders so ties, empty results, low stock, overdue invoices, failed payments, refunds and similar cases exist. Deterministic, safe to repeat, and every rule checked by `tests/test_sample_money.py` still holds.
- `# Examples` sections (55 checked question/SQL pairs, 49 tables) come from `tools/examples.yaml` via `tools/add_examples.py`. The builder keeps them on rebuild.

## Open items

- **Measure the `# Examples` effect.** Run `tools/eval_pipeline.py` and compare with the 72/72 and 21/21 baseline. Not done yet.
- **Get an independent question set**, ideally real user questions. Guard wording was calibrated on 58 good and 15 bad questions plus hand-written bad SQL and replies. `fresh_questions.json` is independent of the input-guard and SQL-judge tuning but **not** of the output-guard tuning.
- **OKF bundle is tables only.** Possible later: business-concept and metric files, `verified` / `status` / `stale_after` front matter, and Attested Computation entries for fixed approved queries.
- **Request concurrency limit** for LLM rate limits; **connection pool** (each query now opens a connection, 15 to 35 ms).

## Known limits (not bugs to fix blindly)

- **The retry loop never fired in live runs** (every question needed one SQL draft). It is covered only by tests with fakes.
- **Navigator picks about one extra table per question** (for example `invoices`, `payments`). The SQL writer ignored them in every live case.
  Bridging by hop count can pick an odd route (`customers -> reviews -> products`); neighbour expansion and scores compensate.
- **Named-item recall** is 11/12 on `tests/data/entity_questions.json`. The one miss, "How much has Ravi Kumar spent", is genuinely ambiguous with `expenses`.
- The validator's dangerous-function list is a blocklist. The read-only role, READ ONLY transaction and statement timeout are the real backstops.
- `EMBEDDING_MODEL` in the owner's `.env` is unused.
- A bare display request with no history ("show me in a table") is refused (`no_context`, 422, `is_display_only`), and the SQL writer must decline questions whose subject is not stated.

## Tools (all live tools cost money; the full pipeline eval runs about 90 pipeline calls)

| Command | Purpose |
|---|---|
| `tools/smoke_jev.py` | guards on a few examples |
| `tools/smoke_navigator.py` | navigator on 14 questions |
| `tools/smoke_sql.py` | validator + judge + executor chain |
| `tools/smoke_agents.py ["question"]` | navigator + both agents + database |
| `tools/eval_navigator.py` | compare navigator wordings and rules (cached scores) |
| `tools/eval_guards.py [--output] [--refresh]` | calibrate input guard, SQL judge, output guard |
| `tools/eval_pipeline.py [--only held] [-v]` | the whole pipeline on all question sets; records every Jev call |
| `tools/eval_followups.py [--only attack] [-v]` | follow-up conversations from `tests/data/followup_conversations.json`. History: a screenshot showed invented wording ('eligible') leaking from a reply into the next question, so two typo-after-challenge conversations were added and the answer writer and rewriter prompts tightened. The navigator question now also says a table is needed when the message names an item stored in it (named-item recall 7/12 -> 11/12; tuning and held-out sets unchanged). |

Cached scores and run results live in `tests/last_run_*.json` (git-ignored). The question sets are in `tests/data/`.
Run tools with `./.venv/Scripts/python.exe tools/<name>.py`. The tools need `OPENAI_API_KEY` and `TYPESAFE_API_KEY` in `.env`.
