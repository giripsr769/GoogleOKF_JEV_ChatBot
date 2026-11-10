---
type: "Postgres Table"
title: "leave_requests"
description: "Employee leave and time-off requests."
resource: "postgres://shop/public/leave_requests"
tags: ["leave", "vacation", "holiday", "sick", "time", "off", "absence", "request"]
columns: ["id", "employee_id", "leave_type", "start_date", "end_date", "status"]
generated:
  by: "okf-chat/0.1.0"
  at: "2026-11-03T18:31:49Z"
---

Employee leave and time-off requests.

# Schema

| Column | Type | Key | Description |
|---|---|---|---|
| `id` | integer | PK | Unique id |
| `employee_id` | integer | FK → [employees](/tables/hr/employees.md) | Requesting employee |
| `leave_type` | text |  | Type of leave (one of: annual, sick, unpaid, parental) |
| `start_date` | date |  | First day |
| `end_date` | date |  | Last day |
| `status` | text |  | Decision status (one of: pending, approved, rejected) |

# Relationships

- `employee_id` references [employees](/tables/hr/employees.md) (`id`).

# Notes

Employee leave and time-off requests.

# Examples

**Q:** How many pending leave requests are there by leave type?

```sql
SELECT leave_type, COUNT(*) AS pending_requests FROM leave_requests WHERE status = 'pending' GROUP BY leave_type ORDER BY pending_requests DESC
```
