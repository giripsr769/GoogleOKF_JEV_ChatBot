---
type: "Postgres Table"
title: "training_enrollments"
description: "Which employees enrolled in which training courses and their completion."
resource: "postgres://shop/public/training_enrollments"
tags: ["training", "enrollment", "course", "completion", "employee", "learning"]
columns: ["id", "employee_id", "course_id", "status", "completed_on"]
generated:
  by: "okf-chat/0.1.0"
  at: "2026-11-03T18:31:49Z"
---

Which employees enrolled in which training courses and their completion.

# Schema

| Column | Type | Key | Description |
|---|---|---|---|
| `id` | integer | PK | Unique id |
| `employee_id` | integer | FK → [employees](/tables/hr/employees.md) | Employee |
| `course_id` | integer | FK → [training_courses](/tables/hr/training_courses.md) | Course |
| `status` | text |  | Progress status (one of: enrolled, completed, dropped) |
| `completed_on` | date |  | Completion date, null if not done |

# Relationships

- `course_id` references [training_courses](/tables/hr/training_courses.md) (`id`).
- `employee_id` references [employees](/tables/hr/employees.md) (`id`).

# Notes

Which employees enrolled in which training courses and their completion.

# Examples

**Q:** How many employees completed each course?

```sql
SELECT tc.title, COUNT(*) AS completed FROM training_enrollments te JOIN training_courses tc ON tc.id = te.course_id WHERE te.status = 'completed' GROUP BY tc.title ORDER BY completed DESC
```
