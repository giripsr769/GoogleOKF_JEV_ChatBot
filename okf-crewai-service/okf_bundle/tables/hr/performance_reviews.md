---
type: "Postgres Table"
title: "performance_reviews"
description: "Periodic performance reviews and ratings of employees."
resource: "postgres://shop/public/performance_reviews"
tags: ["performance", "review", "appraisal", "rating", "evaluation", "score", "staff"]
columns: ["id", "employee_id", "reviewer_id", "rating", "review_period", "comments"]
generated:
  by: "okf-chat/0.1.0"
  at: "2026-11-03T18:31:49Z"
---

Periodic performance reviews and ratings of employees.

# Schema

| Column | Type | Key | Description |
|---|---|---|---|
| `id` | integer | PK | Unique id |
| `employee_id` | integer | FK → [employees](/tables/hr/employees.md) | Employee reviewed |
| `reviewer_id` | integer | FK → [employees](/tables/hr/employees.md) | Employee who reviewed |
| `rating` | integer |  | Performance rating 1 to 5 |
| `review_period` | text |  | Review period such as 2025-H1 |
| `comments` | text |  | Reviewer comments |

# Relationships

- `employee_id` references [employees](/tables/hr/employees.md) (`id`).
- `reviewer_id` references [employees](/tables/hr/employees.md) (`id`).

# Notes

Periodic performance reviews and ratings of employees.

# Examples

**Q:** Which employees have the highest average performance rating?

```sql
SELECT e.full_name, AVG(pr.rating) AS avg_rating FROM performance_reviews pr JOIN employees e ON e.id = pr.employee_id GROUP BY e.id, e.full_name ORDER BY avg_rating DESC LIMIT 5
```
