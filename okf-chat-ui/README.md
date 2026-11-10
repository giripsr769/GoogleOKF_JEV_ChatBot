# OKF Chat UI

A small Angular chat window for the [`okf-crewai-service`](../okf-crewai-service/README.md) backend. You type a question in plain English and get a short, human reply. The generated SQL, the result table and the timings are available when you want them.

## What you can do
- **Chat in plain English.** Replies are sentences, not tables. A table appears only when your question asks for one ("... in a table", "as a grid", "tabulate ...").
- **See how it was answered.** The sidebar's **Show SQL query** switch shows the generated SQL (with a Copy button) in every reply. Each reply also has a small **details** link with the row count, tables used, risk score and per-stage timings.
- **Sidebar.** The hamburger button expands it or collapses it to an icon rail (it becomes an overlay on phones). **New chat** starts a fresh conversation. **Chat history** lists past chats (Today / Yesterday / Earlier); click one to reopen it exactly as it was, or use the x to delete it. **Clear all history** needs two clicks.
- **Friendly errors.** Blocked or failed requests come back as a normal sentence ("I can only look things up, so I can't change, add or delete any data."), with the technical detail in small print underneath.
- **Never hangs.** If the backend does not answer within 40 seconds the UI stops waiting and says so.

Follow-ups work inside one chat: the window sends its chat id with each question, so the backend can understand "show me in table view" or "and last month?". The backend only remembers the last few messages for about 30 minutes, and forgets them when it restarts.

## Run it
You need **Node.js 20 or newer** (comes with npm), and the backend running on port 8001 (see the backend README).

```
cd okf-chat-ui
npm install
npm start
```
Open **http://localhost:4200**. The dot in the top-right corner is green when the backend is reachable ("API online · 50 tables"). Click it to re-check.

Other commands: `npm run build` (production build into `dist/`), `npm run watch` (rebuild on change). There are no unit tests yet.

## Configuration
Everything lives in `src/app/environment.ts`:

| Setting | Default | Meaning |
|---|---|---|
| `apiUrl` | `http://localhost:8001` | where the backend is |
| `requestTimeoutMs` | `40000` | how long the UI waits for one answer; keep it above the backend's `PIPELINE_TIMEOUT_S` (30 s) so the backend's own message normally arrives first |

The backend only accepts browser requests from origins listed in its `CORS_ORIGINS` setting (default `http://localhost:4200`). If you serve the UI from another address or port, add it there.

## Where your data is stored
Chats and settings are saved **in your browser only** (`localStorage` keys `okf.chats.v1` and `okf.settings.v1`): nothing is sent anywhere except the question to the backend. Up to 30 chats are kept; the oldest are dropped first, or sooner if the browser's storage fills up. Saved replies can contain whatever your queries returned, such as customer names, so use **Clear all history** on shared computers.

## Project layout
```
src/app/
  app.ts                    page layout: sidebar + chat
  sidebar.component.*       hamburger, New chat, history, settings
  chat.component.*          the conversation, composer, reply rendering, friendly errors
  chat-store.service.ts     chats, active chat and settings; saves them to localStorage
  chat.service.ts           HTTP calls to the backend (POST /api/text-to-sql, GET /health)
  environment.ts            settings above
```

## Troubleshooting
| Symptom | Likely cause |
|---|---|
| Red dot, "API offline" | backend is not running on `apiUrl`, or its `CORS_ORIGINS` does not include this page's address |
| "I can't reach the service right now" | same as above, seen after sending a question |
| "This is taking too long, so I stopped waiting" | the backend or one of its AI services (OpenAI, TypeSafe Jev) is slow or down; try again |
| History or settings vanished | browser storage was cleared, or you are in a private window |
| `npm start`: port 4200 in use | another copy is running; stop it or run `npx ng serve --port 4300` (and add `http://localhost:4300` to the backend's `CORS_ORIGINS`) |
