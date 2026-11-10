---
type: "Postgres Table"
title: "inventory"
description: "Current stock level of each product in each warehouse."
resource: "postgres://shop/public/inventory"
tags: ["inventory", "stock", "quantity", "on", "hand", "reorder", "warehouse"]
columns: ["id", "product_id", "warehouse_id", "quantity_on_hand", "reorder_level"]
generated:
  by: "okf-chat/0.1.0"
  at: "2026-11-03T18:31:49Z"
---

Current stock level of each product in each warehouse.

# Schema

| Column | Type | Key | Description |
|---|---|---|---|
| `id` | integer | PK | Unique id |
| `product_id` | integer | FK → [products](/tables/ecommerce/products.md) | Product |
| `warehouse_id` | integer | FK → [warehouses](/tables/ecommerce/warehouses.md) | Warehouse holding the stock |
| `quantity_on_hand` | integer |  | Units currently in stock |
| `reorder_level` | integer |  | Reorder when stock falls below this |

# Relationships

- `product_id` references [products](/tables/ecommerce/products.md) (`id`).
- `warehouse_id` references [warehouses](/tables/ecommerce/warehouses.md) (`id`).

# Notes

Total stock of a product = SUM(quantity_on_hand) across warehouses.

# Examples

**Q:** Which products are below their reorder level?

```sql
SELECT p.name, w.name AS warehouse, i.quantity_on_hand, i.reorder_level FROM inventory i JOIN products p ON p.id = i.product_id JOIN warehouses w ON w.id = i.warehouse_id WHERE i.quantity_on_hand < i.reorder_level ORDER BY i.quantity_on_hand LIMIT 20
```
