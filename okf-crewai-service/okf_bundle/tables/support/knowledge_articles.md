---
type: "Postgres Table"
title: "knowledge_articles"
description: "Help-centre articles agents and customers can read."
resource: "postgres://shop/public/knowledge_articles"
tags: ["knowledge", "base", "article", "help", "faq", "documentation", "guide"]
columns: ["id", "title", "category_id", "views", "published_on"]
generated:
  by: "okf-chat/0.1.0"
  at: "2026-11-03T18:31:49Z"
---

Help-centre articles agents and customers can read.

# Schema

| Column | Type | Key | Description |
|---|---|---|---|
| `id` | integer | PK | Unique id |
| `title` | text |  | Article title |
| `category_id` | integer | FK → [ticket_categories](/tables/support/ticket_categories.md) | Related category |
| `views` | integer |  | Number of views |
| `published_on` | date |  | Publish date |

# Relationships

- `category_id` references [ticket_categories](/tables/support/ticket_categories.md) (`id`).

# Notes

Help-centre articles agents and customers can read.

# Examples

**Q:** What are the 5 most viewed knowledge articles?

```sql
SELECT title, views FROM knowledge_articles ORDER BY views DESC LIMIT 5
```
