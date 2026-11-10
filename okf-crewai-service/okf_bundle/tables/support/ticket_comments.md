---
type: "Postgres Table"
title: "ticket_comments"
description: "Conversation messages on support tickets."
resource: "postgres://shop/public/ticket_comments"
tags: ["ticket", "comment", "reply", "message", "conversation", "note"]
columns: ["id", "ticket_id", "author_agent_id", "body", "created_at"]
generated:
  by: "okf-chat/0.1.0"
  at: "2026-11-03T18:31:49Z"
---

Conversation messages on support tickets.

# Schema

| Column | Type | Key | Description |
|---|---|---|---|
| `id` | integer | PK | Unique id |
| `ticket_id` | integer | FK → [tickets](/tables/support/tickets.md) | Ticket |
| `author_agent_id` | integer | FK → [support_agents](/tables/support/support_agents.md) | Agent author, null if customer |
| `body` | text |  | Message text |
| `created_at` | timestamp without time zone |  | When posted |

# Relationships

- `author_agent_id` references [support_agents](/tables/support/support_agents.md) (`id`).
- `ticket_id` references [tickets](/tables/support/tickets.md) (`id`).

# Notes

Conversation messages on support tickets.

# Examples

**Q:** Which tickets have the most comments?

```sql
SELECT t.id, t.subject, COUNT(*) AS comments FROM ticket_comments c JOIN tickets t ON t.id = c.ticket_id GROUP BY t.id, t.subject ORDER BY comments DESC LIMIT 5
```
