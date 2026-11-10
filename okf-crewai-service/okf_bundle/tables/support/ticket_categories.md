---
type: "Postgres Table"
title: "ticket_categories"
description: "Categories used to classify support tickets."
resource: "postgres://shop/public/ticket_categories"
tags: ["ticket", "category", "type", "issue", "classification"]
columns: ["id", "name", "description"]
generated:
  by: "okf-chat/0.1.0"
  at: "2026-11-03T18:31:49Z"
---

Categories used to classify support tickets.

# Schema

| Column | Type | Key | Description |
|---|---|---|---|
| `id` | integer | PK | Unique id |
| `name` | text |  | Category name such as Billing or Shipping |
| `description` | text |  | What it covers |

# Relationships

- Referenced by [knowledge_articles](/tables/support/knowledge_articles.md) through `category_id`.
- Referenced by [tickets](/tables/support/tickets.md) through `category_id`.

# Notes

Categories used to classify support tickets.

# Examples

**Q:** Which ticket categories get the most tickets?

```sql
SELECT tc.name, COUNT(*) AS tickets FROM ticket_categories tc JOIN tickets t ON t.category_id = tc.id GROUP BY tc.name ORDER BY tickets DESC
```
