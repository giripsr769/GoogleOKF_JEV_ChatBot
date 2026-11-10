---
type: "Postgres Table"
title: "categories"
description: "Product categories, optionally nested under a parent category."
resource: "postgres://shop/public/categories"
tags: ["category", "taxonomy", "department", "group", "catalog"]
columns: ["id", "name", "parent_id", "description"]
generated:
  by: "okf-chat/0.1.0"
  at: "2026-11-03T18:31:49Z"
---

Product categories, optionally nested under a parent category.

# Schema

| Column | Type | Key | Description |
|---|---|---|---|
| `id` | integer | PK | Unique category id |
| `name` | text |  | Category name |
| `parent_id` | integer | FK → [categories](/tables/ecommerce/categories.md) | Parent category, null for top level |
| `description` | text |  | Short description |

# Relationships

- `parent_id` references [categories](/tables/ecommerce/categories.md) (`id`).

# Notes

Products.category is free text; this table is the managed taxonomy.

# Examples

**Q:** List the top-level categories.

```sql
SELECT id, name FROM categories WHERE parent_id IS NULL ORDER BY name
```
