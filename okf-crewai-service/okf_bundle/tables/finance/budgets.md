---
type: "Postgres Table"
title: "budgets"
description: "Planned spend per department per fiscal year."
resource: "postgres://shop/public/budgets"
tags: ["budget", "plan", "forecast", "fiscal", "year", "allocation", "department", "spend"]
columns: ["id", "department_id", "fiscal_year", "planned_amount", "spent_amount"]
generated:
  by: "okf-chat/0.1.0"
  at: "2026-11-03T18:31:49Z"
---

Planned spend per department per fiscal year.

# Schema

| Column | Type | Key | Description |
|---|---|---|---|
| `id` | integer | PK | Unique id |
| `department_id` | integer | FK → [departments](/tables/hr/departments.md) | Department |
| `fiscal_year` | integer |  | Fiscal year |
| `planned_amount` | numeric(12,2) |  | Budgeted amount in USD |
| `spent_amount` | numeric(12,2) |  | Actual spent so far in USD |

# Relationships

- `department_id` references [departments](/tables/hr/departments.md) (`id`).

# Notes

Planned spend per department per fiscal year.

# Examples

**Q:** Which departments spent more than they planned in the latest fiscal year?

```sql
SELECT d.name, b.planned_amount, b.spent_amount FROM budgets b JOIN departments d ON d.id = b.department_id WHERE b.fiscal_year = (SELECT MAX(fiscal_year) FROM budgets) AND b.spent_amount > b.planned_amount ORDER BY b.spent_amount - b.planned_amount DESC
```
