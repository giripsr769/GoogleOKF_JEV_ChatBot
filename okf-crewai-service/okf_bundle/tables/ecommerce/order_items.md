---
type: "Postgres Table"
title: "order_items"
description: "Line items of each order - which product, how many, at what price."
resource: "postgres://shop/public/order_items"
tags: ["order item", "line item", "quantity", "product sold", "best selling", "units"]
columns: ["id", "order_id", "product_id", "quantity", "unit_price"]
generated:
  by: "okf-chat/0.1.0"
  at: "2026-11-03T18:31:49Z"
---

Line items of each order - which product, how many, at what price.

# Schema

| Column | Type | Key | Description |
|---|---|---|---|
| `id` | integer | PK | Unique line item id |
| `order_id` | integer | FK → [orders](/tables/ecommerce/orders.md) | References orders.id |
| `product_id` | integer | FK → [products](/tables/ecommerce/products.md) | References products.id |
| `quantity` | integer |  | Units purchased |
| `unit_price` | numeric(10,2) |  | Price per unit at time of sale |

# Relationships

- `order_id` references [orders](/tables/ecommerce/orders.md) (`id`).
- `product_id` references [products](/tables/ecommerce/products.md) (`id`).

# Notes

Bridge between orders and products. Line revenue = quantity * unit_price.

# Examples

**Q:** Which products sold the most units?

```sql
SELECT p.name, SUM(oi.quantity) AS units_sold FROM order_items oi JOIN orders o ON o.id = oi.order_id JOIN products p ON p.id = oi.product_id WHERE o.status <> 'cancelled' GROUP BY p.name ORDER BY units_sold DESC LIMIT 5
```
