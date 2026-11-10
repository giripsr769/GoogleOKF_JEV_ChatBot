---
type: "Postgres Table"
title: "attendance"
description: "Daily attendance records for employees."
resource: "postgres://shop/public/attendance"
tags: ["attendance", "present", "absent", "checkin", "checkout", "hours", "clock"]
columns: ["id", "employee_id", "work_date", "hours_worked", "status"]
generated:
  by: "okf-chat/0.1.0"
  at: "2026-11-03T18:31:49Z"
---

Daily attendance records for employees.

# Schema

| Column | Type | Key | Description |
|---|---|---|---|
| `id` | integer | PK | Unique id |
| `employee_id` | integer | FK → [employees](/tables/hr/employees.md) | Employee |
| `work_date` | date |  | Date |
| `hours_worked` | numeric(12,2) |  | Hours worked that day |
| `status` | text |  | Attendance status (one of: present, absent, remote) |

# Relationships

- `employee_id` references [employees](/tables/hr/employees.md) (`id`).

# Notes

Daily attendance records for employees.

# Examples

**Q:** How many hours did each employee work in total?

```sql
SELECT e.full_name, SUM(a.hours_worked) AS total_hours FROM attendance a JOIN employees e ON e.id = a.employee_id WHERE a.status <> 'absent' GROUP BY e.full_name ORDER BY total_hours DESC LIMIT 10
```
