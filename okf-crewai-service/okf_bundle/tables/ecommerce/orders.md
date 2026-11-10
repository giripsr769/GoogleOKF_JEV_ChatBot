---
type: "Postgres Table"
title: "orders"
description: "Sales orders placed by customers, with status and total amount."
resource: "postgres://shop/public/orders"
tags: ["order", "sale", "revenue", "purchase", "status", "total", "date", "shipped", "cancelled"]
columns: ["id", "customer_id", "status", "total_amount", "ordered_at"]
generated:
  by: "okf-chat/0.1.0"
  at: "2026-11-03T18:31:49Z"
---

Sales orders placed by customers, with status and total amount.

# Schema

| Column | Type | Key | Description |
|---|---|---|---|
| `id` | integer | PK | Unique order id |
| `customer_id` | integer | FK → [customers](/tables/ecommerce/customers.md) | References customers.id |
| `status` | text |  | One of: pending, shipped, delivered, cancelled |
| `total_amount` | numeric(12,2) |  | Order total in USD |
| `ordered_at` | timestamp without time zone |  | When the order was placed |

# Relationships

- `customer_id` references [customers](/tables/ecommerce/customers.md) (`id`).
- Referenced by [invoices](/tables/finance/invoices.md) through `order_id`.
- Referenced by [order_coupons](/tables/ecommerce/order_coupons.md) through `order_id`.
- Referenced by [order_items](/tables/ecommerce/order_items.md) through `order_id`.
- Referenced by [payments](/tables/ecommerce/payments.md) through `order_id`.
- Referenced by [returns](/tables/ecommerce/returns.md) through `order_id`.
- Referenced by [shipments](/tables/ecommerce/shipments.md) through `order_id`.
- Referenced by [tickets](/tables/support/tickets.md) through `order_id`.

# Notes

One row per order. Revenue = SUM(total_amount) excluding status 'cancelled'.

# Examples

**Q:** What was our revenue by month this year?

```sql
SELECT DATE_TRUNC('month', ordered_at) AS month, SUM(total_amount) AS revenue FROM orders WHERE status <> 'cancelled' AND ordered_at >= DATE_TRUNC('year', CURRENT_DATE) GROUP BY month ORDER BY month
```

**Q:** How many orders are in each status?

```sql
SELECT status, COUNT(*) AS orders FROM orders GROUP BY status ORDER BY orders DESC
```
