---
type: "Postgres Table"
title: "support_agents"
description: "Customer support agents."
resource: "postgres://shop/public/support_agents"
tags: ["agent", "support", "helpdesk", "representative", "csr", "staff"]
columns: ["id", "full_name", "team_id", "email", "active"]
generated:
  by: "okf-chat/0.1.0"
  at: "2026-11-03T18:31:49Z"
---

Customer support agents.

# Schema

| Column | Type | Key | Description |
|---|---|---|---|
| `id` | integer | PK | Unique agent id |
| `full_name` | text |  | Agent name |
| `team_id` | integer | FK → [support_teams](/tables/support/support_teams.md) | Team |
| `email` | text |  | Agent email |
| `active` | boolean |  | Whether the agent is active |

# Relationships

- `team_id` references [support_teams](/tables/support/support_teams.md) (`id`).
- Referenced by [chat_sessions](/tables/support/chat_sessions.md) through `agent_id`.
- Referenced by [ticket_comments](/tables/support/ticket_comments.md) through `author_agent_id`.
- Referenced by [tickets](/tables/support/tickets.md) through `agent_id`.

# Notes

Customer support agents. Agents are NOT rows of [employees](/tables/hr/employees.md): the two tables hold different people and share no key. An agent's "team", "department", "group" or "domain" is the support team in [support_teams](/tables/support/support_teams.md) (`team_id`), never a row of `departments`. Do not look agents up by name in `employees`.

# Examples

**Q:** How many tickets does each active support agent handle?

```sql
SELECT sa.full_name, COUNT(t.id) AS tickets FROM support_agents sa LEFT JOIN tickets t ON t.agent_id = sa.id WHERE sa.active GROUP BY sa.id, sa.full_name ORDER BY tickets DESC LIMIT 10
```
