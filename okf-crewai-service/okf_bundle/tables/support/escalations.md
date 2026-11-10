---
type: "Postgres Table"
title: "escalations"
description: "Tickets escalated to a higher tier or manager."
resource: "postgres://shop/public/escalations"
tags: ["escalation", "escalated", "tier", "manager", "urgent", "breach"]
columns: ["id", "ticket_id", "from_team_id", "to_team_id", "reason", "escalated_at"]
generated:
  by: "okf-chat/0.1.0"
  at: "2026-11-03T18:31:49Z"
---

Tickets escalated to a higher tier or manager.

# Schema

| Column | Type | Key | Description |
|---|---|---|---|
| `id` | integer | PK | Unique id |
| `ticket_id` | integer | FK → [tickets](/tables/support/tickets.md) | Escalated ticket |
| `from_team_id` | integer | FK → [support_teams](/tables/support/support_teams.md) | Team escalating |
| `to_team_id` | integer | FK → [support_teams](/tables/support/support_teams.md) | Team receiving |
| `reason` | text |  | Why escalated |
| `escalated_at` | timestamp without time zone |  | When escalated |

# Relationships

- `from_team_id` references [support_teams](/tables/support/support_teams.md) (`id`).
- `ticket_id` references [tickets](/tables/support/tickets.md) (`id`).
- `to_team_id` references [support_teams](/tables/support/support_teams.md) (`id`).

# Notes

Tickets escalated to a higher tier or manager.

# Examples

**Q:** Which reasons cause the most ticket escalations?

```sql
SELECT reason, COUNT(*) AS escalations FROM escalations GROUP BY reason ORDER BY escalations DESC LIMIT 10
```
