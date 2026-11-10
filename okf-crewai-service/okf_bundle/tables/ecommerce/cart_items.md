---
type: "Postgres Table"
title: "cart_items"
description: "Products and quantities inside shopping carts."
resource: "postgres://shop/public/cart_items"
tags: ["cart", "item", "basket", "product", "quantity"]
columns: ["id", "cart_id", "product_id", "quantity"]
generated:
  by: "okf-chat/0.1.0"
  at: "2026-11-03T18:31:49Z"
---

Products and quantities inside shopping carts.

# Schema

| Column | Type | Key | Description |
|---|---|---|---|
| `id` | integer | PK | Unique id |
| `cart_id` | integer | FK → [carts](/tables/ecommerce/carts.md) | Cart containing the item |
| `product_id` | integer | FK → [products](/tables/ecommerce/products.md) | Product in cart |
| `quantity` | integer |  | Units in cart |

# Relationships

- `cart_id` references [carts](/tables/ecommerce/carts.md) (`id`).
- `product_id` references [products](/tables/ecommerce/products.md) (`id`).

# Notes

Products and quantities inside shopping carts.

# Examples

**Q:** Which products are in the most carts?

```sql
SELECT p.name, COUNT(DISTINCT ci.cart_id) AS carts FROM cart_items ci JOIN products p ON p.id = ci.product_id GROUP BY p.name ORDER BY carts DESC LIMIT 10
```
