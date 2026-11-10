---
type: "Postgres Table"
title: "vendor_bills"
description: "Bills received from vendors that the company must pay (money OUT)."
resource: "postgres://shop/public/vendor_bills"
tags: ["vendor", "bill", "payable", "owed", "pay", "supplier", "cost", "outgoing"]
columns: ["id", "vendor_id", "amount", "status", "due_on"]
generated:
  by: "okf-chat/0.1.0"
  at: "2026-11-03T18:31:49Z"
---

Bills received from vendors that the company must pay (money OUT).

# Schema

| Column | Type | Key | Description |
|---|---|---|---|
| `id` | integer | PK | Unique id |
| `vendor_id` | integer | FK → [vendors](/tables/finance/vendors.md) | Vendor who billed |
| `amount` | numeric(12,2) |  | Bill amount in USD |
| `status` | text |  | Bill status (one of: open, paid, overdue) |
| `due_on` | date |  | Due date |

# Relationships

- `vendor_id` references [vendors](/tables/finance/vendors.md) (`id`).

# Notes

Money OUT. Customer payments are in payments.

# Examples

**Q:** How much do we still owe vendors in open or overdue bills?

```sql
SELECT v.name, SUM(vb.amount) AS owed FROM vendor_bills vb JOIN vendors v ON v.id = vb.vendor_id WHERE vb.status IN ('open', 'overdue') GROUP BY v.name ORDER BY owed DESC
```
