---
type: "Postgres Table"
title: "training_courses"
description: "Internal training courses employees can take."
resource: "postgres://shop/public/training_courses"
tags: ["training", "course", "learning", "skill", "certification", "workshop"]
columns: ["id", "title", "duration_hours", "provider"]
generated:
  by: "okf-chat/0.1.0"
  at: "2026-11-03T18:31:49Z"
---

Internal training courses employees can take.

# Schema

| Column | Type | Key | Description |
|---|---|---|---|
| `id` | integer | PK | Unique course id |
| `title` | text |  | Course title |
| `duration_hours` | integer |  | Course length in hours |
| `provider` | text |  | Training provider |

# Relationships

- Referenced by [training_enrollments](/tables/hr/training_enrollments.md) through `course_id`.

# Notes

Internal training courses employees can take.

# Examples

**Q:** Which training courses are the longest?

```sql
SELECT title, duration_hours, provider FROM training_courses ORDER BY duration_hours DESC LIMIT 5
```
