---
type: "Postgres Table"
title: "reviews"
description: "Customer ratings and written reviews of products."
resource: "postgres://shop/public/reviews"
tags: ["review", "rating", "stars", "feedback", "comment", "product", "customer"]
columns: ["id", "product_id", "customer_id", "rating", "comment", "created_at"]
generated:
  by: "okf-chat/0.1.0"
  at: "2026-11-03T18:31:49Z"
---

Customer ratings and written reviews of products.

# Schema

| Column | Type | Key | Description |
|---|---|---|---|
| `id` | integer | PK | Unique review id |
| `product_id` | integer | FK → [products](/tables/ecommerce/products.md) | Product reviewed |
| `customer_id` | integer | FK → [customers](/tables/ecommerce/customers.md) | Customer who wrote it |
| `rating` | integer |  | Star rating 1 to 5 |
| `comment` | text |  | Review text |
| `created_at` | timestamp without time zone |  | When posted |

# Relationships

- `customer_id` references [customers](/tables/ecommerce/customers.md) (`id`).
- `product_id` references [products](/tables/ecommerce/products.md) (`id`).

# Notes

Customer ratings and written reviews of products.

# Examples

**Q:** Which products have the best average review rating?

```sql
SELECT p.name, AVG(r.rating) AS avg_rating, COUNT(*) AS reviews FROM reviews r JOIN products p ON p.id = r.product_id GROUP BY p.id, p.name ORDER BY avg_rating DESC, reviews DESC LIMIT 5
```
