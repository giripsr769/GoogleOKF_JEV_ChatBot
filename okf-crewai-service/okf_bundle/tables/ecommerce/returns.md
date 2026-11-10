---
type: "Postgres Table"
title: "returns"
description: "Customer return requests for sales orders and the reason given."
resource: "postgres://shop/public/returns"
tags: ["return", "refund", "rma", "reverse", "exchange", "complaint", "order"]
columns: ["id", "order_id", "reason", "status", "refund_amount", "requested_at"]
generated:
  by: "okf-chat/0.1.0"
  at: "2026-11-03T18:31:49Z"
---

Customer return requests for sales orders and the reason given.

# Schema

| Column | Type | Key | Description |
|---|---|---|---|
| `id` | integer | PK | Unique return id |
| `order_id` | integer | FK → [orders](/tables/ecommerce/orders.md) | Sales order being returned |
| `reason` | text |  | Reason for return (one of: damaged, wrong_item, not_needed, late) |
| `status` | text |  | Return status (one of: requested, approved, rejected, refunded) |
| `refund_amount` | numeric(12,2) |  | Amount refunded in USD |
| `requested_at` | timestamp without time zone |  | When requested |

# Relationships

- `order_id` references [orders](/tables/ecommerce/orders.md) (`id`).

# Notes

Customer return requests for sales orders and the reason given.

# Examples

**Q:** How much was refunded, by return reason?

```sql
SELECT reason, COUNT(*) AS returns, SUM(refund_amount) AS refunded FROM returns WHERE status = 'refunded' GROUP BY reason ORDER BY refunded DESC
```
