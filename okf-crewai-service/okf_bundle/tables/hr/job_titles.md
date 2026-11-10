---
type: "Postgres Table"
title: "job_titles"
description: "Job titles and their pay grade bands."
resource: "postgres://shop/public/job_titles"
tags: ["job", "title", "role", "position", "grade", "level", "designation"]
columns: ["id", "title", "grade", "min_salary", "max_salary"]
generated:
  by: "okf-chat/0.1.0"
  at: "2026-11-03T18:31:49Z"
---

Job titles and their pay grade bands.

# Schema

| Column | Type | Key | Description |
|---|---|---|---|
| `id` | integer | PK | Unique id |
| `title` | text |  | Job title |
| `grade` | integer |  | Pay grade level |
| `min_salary` | numeric(12,2) |  | Band minimum |
| `max_salary` | numeric(12,2) |  | Band maximum |

# Relationships

- Referenced by [employees](/tables/hr/employees.md) through `job_title_id`.

# Notes

Job titles and their pay grade bands.

# Examples

**Q:** Which job titles have the widest salary range?

```sql
SELECT title, min_salary, max_salary, max_salary - min_salary AS spread FROM job_titles ORDER BY spread DESC LIMIT 5
```
