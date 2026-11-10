---
type: "Postgres Table"
title: "payments"
description: "Customer payments received against sales orders."
resource: "postgres://shop/public/payments"
tags: ["payment", "paid", "transaction", "card", "upi", "refund", "customer", "order"]
columns: ["id", "order_id", "method", "amount", "status", "paid_at"]
generated:
  by: "okf-chat/0.1.0"
  at: "2026-11-03T18:31:49Z"
---

Customer payments received against sales orders.

# Schema

| Column | Type | Key | Description |
|---|---|---|---|
| `id` | integer | PK | Unique payment id |
| `order_id` | integer | FK → [orders](/tables/ecommerce/orders.md) | Sales order being paid |
| `method` | text |  | Payment method (one of: card, upi, cash, netbanking) |
| `amount` | numeric(12,2) |  | Amount paid in USD |
| `status` | text |  | Payment status (one of: completed, failed, refunded) |
| `paid_at` | timestamp without time zone |  | When payment was made |

# Relationships

- `order_id` references [orders](/tables/ecommerce/orders.md) (`id`).

# Notes

Customer money IN. Not the same as vendor_bills (money OUT) or invoices (billing documents).

# Examples

**Q:** How much was paid by each payment method?

```sql
SELECT method, SUM(amount) AS total_paid, COUNT(*) AS payments FROM payments WHERE status = 'completed' GROUP BY method ORDER BY total_paid DESC
```
