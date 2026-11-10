---
type: "Postgres Table"
title: "product_suppliers"
description: "Which suppliers provide which products, with cost price and lead time."
resource: "postgres://shop/public/product_suppliers"
tags: ["supplier", "product", "cost", "sourcing", "lead", "time"]
columns: ["id", "product_id", "supplier_id", "cost_price", "lead_time_days"]
generated:
  by: "okf-chat/0.1.0"
  at: "2026-11-03T18:31:49Z"
---

Which suppliers provide which products, with cost price and lead time.

# Schema

| Column | Type | Key | Description |
|---|---|---|---|
| `id` | integer | PK | Unique id |
| `product_id` | integer | FK → [products](/tables/ecommerce/products.md) | Product supplied |
| `supplier_id` | integer | FK → [suppliers](/tables/ecommerce/suppliers.md) | Supplier |
| `cost_price` | numeric(12,2) |  | Cost per unit paid to supplier in USD |
| `lead_time_days` | integer |  | Days from order to delivery |

# Relationships

- `product_id` references [products](/tables/ecommerce/products.md) (`id`).
- `supplier_id` references [suppliers](/tables/ecommerce/suppliers.md) (`id`).

# Notes

Which suppliers provide which products, with cost price and lead time.

# Examples

**Q:** Which supplier offers the lowest cost price for each product?

```sql
SELECT DISTINCT ON (p.name) p.name AS product, s.name AS supplier, ps.cost_price FROM product_suppliers ps JOIN products p ON p.id = ps.product_id JOIN suppliers s ON s.id = ps.supplier_id ORDER BY p.name, ps.cost_price LIMIT 20
```
