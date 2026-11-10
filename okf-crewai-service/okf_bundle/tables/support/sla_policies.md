---
type: "Postgres Table"
title: "sla_policies"
description: "Service level targets for response and resolution by priority."
resource: "postgres://shop/public/sla_policies"
tags: ["sla", "policy", "response", "resolution", "target", "priority", "hours", "deadline"]
columns: ["id", "priority", "first_response_hours", "resolution_hours"]
generated:
  by: "okf-chat/0.1.0"
  at: "2026-11-03T18:31:49Z"
---

Service level targets for response and resolution by priority.

# Schema

| Column | Type | Key | Description |
|---|---|---|---|
| `id` | integer | PK | Unique id |
| `priority` | text |  | Ticket priority (one of: low, medium, high, urgent) |
| `first_response_hours` | integer |  | Target hours to first reply |
| `resolution_hours` | integer |  | Target hours to resolve |

# Notes

Service level targets for response and resolution by priority.

# Examples

**Q:** What are the response and resolution targets for each priority?

```sql
SELECT priority, first_response_hours, resolution_hours FROM sla_policies ORDER BY resolution_hours
```
