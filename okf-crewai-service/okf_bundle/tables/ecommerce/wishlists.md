---
type: "Postgres Table"
title: "wishlists"
description: "Products customers saved to wishlists for later."
resource: "postgres://shop/public/wishlists"
tags: ["wishlist", "saved", "favourite", "later", "product", "customer"]
columns: ["id", "customer_id", "product_id", "added_at"]
generated:
  by: "okf-chat/0.1.0"
  at: "2026-11-03T18:31:49Z"
---

Products customers saved to wishlists for later.

# Schema

| Column | Type | Key | Description |
|---|---|---|---|
| `id` | integer | PK | Unique id |
| `customer_id` | integer | FK → [customers](/tables/ecommerce/customers.md) | Customer |
| `product_id` | integer | FK → [products](/tables/ecommerce/products.md) | Product saved |
| `added_at` | timestamp without time zone |  | When added |

# Relationships

- `customer_id` references [customers](/tables/ecommerce/customers.md) (`id`).
- `product_id` references [products](/tables/ecommerce/products.md) (`id`).

# Notes

Products customers saved to wishlists for later.

# Examples

**Q:** Which products are on the most wishlists?

```sql
SELECT p.name, COUNT(*) AS wishlists FROM wishlists w JOIN products p ON p.id = w.product_id GROUP BY p.name ORDER BY wishlists DESC LIMIT 5
```
