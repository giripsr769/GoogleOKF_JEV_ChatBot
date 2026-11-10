---
type: "Postgres Table"
title: "salaries"
description: "Employee salary records. SENSITIVE."
resource: "postgres://shop/public/salaries"
tags: ["salary", "pay", "compensation", "wage", "bonus", "payroll", "sensitive"]
columns: ["id", "employee_id", "base_salary", "bonus", "effective_from"]
sensitive: true
generated:
  by: "okf-chat/0.1.0"
  at: "2026-11-03T18:31:49Z"
---

Employee salary records. SENSITIVE.

> **Sensitive table.** The chatbot's database role cannot read it, so questions about it are refused.

# Schema

| Column | Type | Key | Description |
|---|---|---|---|
| `id` | integer | PK | Unique id |
| `employee_id` | integer | FK → [employees](/tables/hr/employees.md) | Employee paid |
| `base_salary` | numeric(12,2) |  | Annual base salary in USD |
| `bonus` | numeric(12,2) |  | Annual bonus in USD |
| `effective_from` | date |  | Date this salary applies from |

# Relationships

- `employee_id` references [employees](/tables/hr/employees.md) (`id`).

# Notes

Restricted: not readable by the API role.
