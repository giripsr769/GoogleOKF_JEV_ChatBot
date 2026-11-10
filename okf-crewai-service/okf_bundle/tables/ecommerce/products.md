---
type: "Postgres Table"
title: "products"
description: "Catalogue of items for sale with category and unit price."
resource: "postgres://shop/public/products"
tags: ["product", "item", "catalogue", "category", "price", "stock", "inventory"]
columns: ["id", "name", "category", "price", "stock"]
generated:
  by: "okf-chat/0.1.0"
  at: "2026-11-03T18:31:49Z"
---

Catalogue of items for sale with category and unit price.

# Schema

| Column | Type | Key | Description |
|---|---|---|---|
| `id` | integer | PK | Unique product id |
| `name` | text |  | Product name |
| `category` | text |  | Product category e.g. Electronics |
| `price` | numeric(10,2) |  | Current unit price |
| `stock` | integer |  | Units currently in stock |

# Relationships

- Referenced by [cart_items](/tables/ecommerce/cart_items.md) through `product_id`.
- Referenced by [inventory](/tables/ecommerce/inventory.md) through `product_id`.
- Referenced by [invoice_items](/tables/finance/invoice_items.md) through `product_id`.
- Referenced by [order_items](/tables/ecommerce/order_items.md) through `product_id`.
- Referenced by [product_suppliers](/tables/ecommerce/product_suppliers.md) through `product_id`.
- Referenced by [purchase_order_items](/tables/ecommerce/purchase_order_items.md) through `product_id`.
- Referenced by [reviews](/tables/ecommerce/reviews.md) through `product_id`.
- Referenced by [wishlists](/tables/ecommerce/wishlists.md) through `product_id`.

# Notes

Product catalogue. Use `order_items` to find which products were sold.

# Examples

**Q:** What are the most expensive products in each category?

```sql
SELECT DISTINCT ON (category) category, name, price FROM products ORDER BY category, price DESC
```

**Q:** Which products have fewer than 50 units in stock?

```sql
SELECT name, category FROM products WHERE stock < 50 ORDER BY stock, name
```
