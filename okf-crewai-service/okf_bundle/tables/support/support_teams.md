---
type: "Postgres Table"
title: "support_teams"
description: "Support teams that agents belong to."
resource: "postgres://shop/public/support_teams"
tags: ["support", "team", "group", "queue", "tier", "helpdesk"]
columns: ["id", "name", "tier"]
generated:
  by: "okf-chat/0.1.0"
  at: "2026-11-03T18:31:49Z"
---

Support teams that agents belong to.

# Schema

| Column | Type | Key | Description |
|---|---|---|---|
| `id` | integer | PK | Unique team id |
| `name` | text |  | Team name |
| `tier` | integer |  | Support tier 1-3 |

# Relationships

- Referenced by [escalations](/tables/support/escalations.md) through `from_team_id`.
- Referenced by [escalations](/tables/support/escalations.md) through `to_team_id`.
- Referenced by [support_agents](/tables/support/support_agents.md) through `team_id`.

# Notes

Support teams that agents belong to. When a question asks for the department, team, group or domain of support agents, answer with the team `name` (and `tier`) from this table. This is not the HR [departments](/tables/hr/departments.md) table.

# Examples

**Q:** How many agents are in each support team?

```sql
SELECT st.name, st.tier, COUNT(sa.id) AS agents FROM support_teams st LEFT JOIN support_agents sa ON sa.team_id = st.id GROUP BY st.id, st.name, st.tier ORDER BY st.tier, st.name
```
