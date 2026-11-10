---
type: "Postgres Table"
title: "carts"
description: "Shopping carts, open or abandoned, belonging to customers."
resource: "postgres://shop/public/carts"
tags: ["cart", "basket", "shopping", "abandoned", "checkout", "customer"]
columns: ["id", "customer_id", "status", "created_at"]
generated:
  by: "okf-chat/0.1.0"
  at: "2026-11-03T18:31:49Z"
---

Shopping carts, open or abandoned, belonging to customers.

# Schema

| Column | Type | Key | Description |
|---|---|---|---|
| `id` | integer | PK | Unique cart id |
| `customer_id` | integer | FK → [customers](/tables/ecommerce/customers.md) | Cart owner |
| `status` | text |  | Cart state (one of: open, abandoned, converted) |
| `created_at` | timestamp without time zone |  | When created |

# Relationships

- `customer_id` references [customers](/tables/ecommerce/customers.md) (`id`).
- Referenced by [cart_items](/tables/ecommerce/cart_items.md) through `cart_id`.

# Notes

Shopping carts, open or abandoned, belonging to customers.

# Examples

**Q:** How many carts were abandoned?

```sql
SELECT COUNT(*) AS abandoned_carts FROM carts WHERE status = 'abandoned'
```
