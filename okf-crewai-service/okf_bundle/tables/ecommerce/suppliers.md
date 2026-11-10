---
type: "Postgres Table"
title: "suppliers"
description: "Companies that supply products to the store."
resource: "postgres://shop/public/suppliers"
tags: ["supplier", "vendor", "manufacturer", "sourcing"]
columns: ["id", "name", "country", "contact_email", "rating"]
generated:
  by: "okf-chat/0.1.0"
  at: "2026-11-03T18:31:49Z"
---

Companies that supply products to the store.

# Schema

| Column | Type | Key | Description |
|---|---|---|---|
| `id` | integer | PK | Unique supplier id |
| `name` | text |  | Supplier company name |
| `country` | text |  | Supplier country |
| `contact_email` | text |  | Supplier contact email |
| `rating` | numeric(12,2) |  | Supplier quality rating 1-5 |

# Relationships

- Referenced by [product_suppliers](/tables/ecommerce/product_suppliers.md) through `supplier_id`.
- Referenced by [purchase_orders](/tables/ecommerce/purchase_orders.md) through `supplier_id`.

# Notes

Companies that supply products to the store.

# Examples

**Q:** Which suppliers have the best rating?

```sql
SELECT name, country, rating FROM suppliers ORDER BY rating DESC LIMIT 5
```
