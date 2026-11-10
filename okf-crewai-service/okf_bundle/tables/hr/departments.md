---
type: "Postgres Table"
title: "departments"
description: "Company departments such as Sales, Engineering and HR."
resource: "postgres://shop/public/departments"
tags: ["department", "team", "division", "org", "unit", "cost", "center"]
columns: ["id", "name", "location", "budget"]
generated:
  by: "okf-chat/0.1.0"
  at: "2026-11-03T18:31:49Z"
---

Company departments such as Sales, Engineering and HR.

# Schema

| Column | Type | Key | Description |
|---|---|---|---|
| `id` | integer | PK | Unique department id |
| `name` | text |  | Department name |
| `location` | text |  | Office location |
| `budget` | numeric(12,2) |  | Annual department budget in USD |

# Relationships

- Referenced by [budgets](/tables/finance/budgets.md) through `department_id`.
- Referenced by [employees](/tables/hr/employees.md) through `department_id`.

# Notes

Company departments such as Sales, Engineering and HR. These are for [employees](/tables/hr/employees.md) only. Customer support agents belong to a support team ([support_teams](/tables/support/support_teams.md)), not to a department.

# Examples

**Q:** How many active employees are in each department?

```sql
SELECT d.name, COUNT(*) AS employees FROM departments d JOIN employees e ON e.department_id = d.id WHERE e.status = 'active' GROUP BY d.name ORDER BY employees DESC
```
