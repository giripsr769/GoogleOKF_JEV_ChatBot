---
type: "Postgres Table"
title: "chat_sessions"
description: "Live chat sessions between customers and agents."
resource: "postgres://shop/public/chat_sessions"
tags: ["chat", "live", "session", "conversation", "messaging", "agent", "customer"]
columns: ["id", "customer_id", "agent_id", "started_at", "duration_minutes", "resolved"]
generated:
  by: "okf-chat/0.1.0"
  at: "2026-11-03T18:31:49Z"
---

Live chat sessions between customers and agents.

# Schema

| Column | Type | Key | Description |
|---|---|---|---|
| `id` | integer | PK | Unique id |
| `customer_id` | integer | FK → [customers](/tables/ecommerce/customers.md) | Customer |
| `agent_id` | integer | FK → [support_agents](/tables/support/support_agents.md) | Agent |
| `started_at` | timestamp without time zone |  | Start time |
| `duration_minutes` | integer |  | Length in minutes |
| `resolved` | boolean |  | Whether resolved in chat |

# Relationships

- `agent_id` references [support_agents](/tables/support/support_agents.md) (`id`).
- `customer_id` references [customers](/tables/ecommerce/customers.md) (`id`).

# Notes

Live chat sessions between customers and agents.

# Examples

**Q:** What is the average chat session length, and how many were resolved?

```sql
SELECT AVG(duration_minutes) AS avg_minutes, COUNT(*) FILTER (WHERE resolved) AS resolved_sessions, COUNT(*) AS sessions FROM chat_sessions
```
