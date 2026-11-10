---
type: "Postgres Table"
title: "employees"
description: "Company staff members. Internal people, not store customers."
resource: "postgres://shop/public/employees"
tags: ["employee", "staff", "worker", "personnel", "hire", "manager", "headcount", "internal"]
columns: ["id", "full_name", "work_email", "department_id", "job_title_id", "manager_id", "hired_on", "status"]
generated:
  by: "okf-chat/0.1.0"
  at: "2026-11-03T18:31:49Z"
---

Company staff members. Internal people, not store customers.

# Schema

| Column | Type | Key | Description |
|---|---|---|---|
| `id` | integer | PK | Unique employee id |
| `full_name` | text |  | Employee name |
| `work_email` | text |  | Company email |
| `department_id` | integer | FK → [departments](/tables/hr/departments.md) | Department |
| `job_title_id` | integer | FK → [job_titles](/tables/hr/job_titles.md) | Job title |
| `manager_id` | integer | FK → [employees](/tables/hr/employees.md) | Manager, null for top |
| `hired_on` | date |  | Hire date |
| `status` | text |  | Employment status (one of: active, on_leave, terminated) |

# Relationships

- `department_id` references [departments](/tables/hr/departments.md) (`id`).
- `job_title_id` references [job_titles](/tables/hr/job_titles.md) (`id`).
- `manager_id` references [employees](/tables/hr/employees.md) (`id`).
- Referenced by [attendance](/tables/hr/attendance.md) through `employee_id`.
- Referenced by [expenses](/tables/finance/expenses.md) through `employee_id`.
- Referenced by [leave_requests](/tables/hr/leave_requests.md) through `employee_id`.
- Referenced by [performance_reviews](/tables/hr/performance_reviews.md) through `employee_id`.
- Referenced by [performance_reviews](/tables/hr/performance_reviews.md) through `reviewer_id`.
- Referenced by [salaries](/tables/hr/salaries.md) through `employee_id`.
- Referenced by [training_enrollments](/tables/hr/training_enrollments.md) through `employee_id`.

# Notes

Look-alike of customers: employees are internal staff. Employees are not support agents: a person in [support_agents](/tables/support/support_agents.md) has no row here, so never join or look them up by name. Use `departments` only for employees; an agent's team comes from `support_teams`. "Email domain" means the part of an email after `@`, only when the question says so.

# Examples

**Q:** Who joined in the last year?

```sql
SELECT full_name, hired_on FROM employees WHERE hired_on >= CURRENT_DATE - INTERVAL '1 year' ORDER BY hired_on DESC
```

**Q:** Who reports to each manager, and how many people do they manage?

```sql
SELECT m.full_name AS manager, COUNT(*) AS direct_reports FROM employees e JOIN employees m ON m.id = e.manager_id GROUP BY m.id, m.full_name ORDER BY direct_reports DESC
```
