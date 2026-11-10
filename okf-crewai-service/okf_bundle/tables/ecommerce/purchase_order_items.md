---
type: "Postgres Table"
title: "purchase_order_items"
description: "Line items of purchase orders sent to suppliers."
resource: "postgres://shop/public/purchase_order_items"
tags: ["purchase", "order", "item", "procurement", "line", "product", "quantity", "cost"]
columns: ["id", "purchase_order_id", "product_id", "quantity", "unit_cost"]
generated:
  by: "okf-chat/0.1.0"
  at: "2026-11-03T18:31:49Z"
---

Line items of purchase orders sent to suppliers.

# Schema

| Column | Type | Key | Description |
|---|---|---|---|
| `id` | integer | PK | Unique id |
| `purchase_order_id` | integer | FK → [purchase_orders](/tables/ecommerce/purchase_orders.md) | Parent purchase order |
| `product_id` | integer | FK → [products](/tables/ecommerce/products.md) | Product bought |
| `quantity` | integer |  | Units ordered |
| `unit_cost` | numeric(12,2) |  | Cost per unit in USD |

# Relationships

- `product_id` references [products](/tables/ecommerce/products.md) (`id`).
- `purchase_order_id` references [purchase_orders](/tables/ecommerce/purchase_orders.md) (`id`).

# Notes

Line items of purchase orders sent to suppliers.

# Examples

**Q:** How many units have we ordered from suppliers per product?

```sql
SELECT p.name, SUM(poi.quantity) AS units_ordered FROM purchase_order_items poi JOIN products p ON p.id = poi.product_id GROUP BY p.name ORDER BY units_ordered DESC LIMIT 10
```
