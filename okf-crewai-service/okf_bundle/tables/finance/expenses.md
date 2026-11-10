---
type: "Postgres Table"
title: "expenses"
description: "Employee expense claims such as travel and meals."
resource: "postgres://shop/public/expenses"
tags: ["expense", "claim", "reimbursement", "travel", "meals", "spend", "employee"]
columns: ["id", "employee_id", "category", "amount", "status", "incurred_on"]
generated:
  by: "okf-chat/0.1.0"
  at: "2026-11-03T18:31:49Z"
---

Employee expense claims such as travel and meals.

# Schema

| Column | Type | Key | Description |
|---|---|---|---|
| `id` | integer | PK | Unique id |
| `employee_id` | integer | FK → [employees](/tables/hr/employees.md) | Employee claiming |
| `category` | text |  | Expense category (one of: travel, meals, software, equipment) |
| `amount` | numeric(12,2) |  | Amount in USD |
| `status` | text |  | Claim status (one of: submitted, approved, reimbursed, rejected) |
| `incurred_on` | date |  | Date spent |

# Relationships

- `employee_id` references [employees](/tables/hr/employees.md) (`id`).

# Notes

Employee expense claims such as travel and meals.

# Examples

**Q:** What is the total approved expense amount per category?

```sql
SELECT category, SUM(amount) AS total FROM expenses WHERE status IN ('approved', 'reimbursed') GROUP BY category ORDER BY total DESC
```
