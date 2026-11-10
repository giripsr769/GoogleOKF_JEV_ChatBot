---
type: "Postgres Table"
title: "customers"
description: "People or companies who buy from the store. One row per customer account."
resource: "postgres://shop/public/customers"
tags: ["customer", "user", "account", "buyer", "country", "city", "signup"]
columns: ["id", "full_name", "email", "country", "city", "created_at"]
generated:
  by: "okf-chat/0.1.0"
  at: "2026-11-03T18:31:49Z"
---

People or companies who buy from the store. One row per customer account.

# Schema

| Column | Type | Key | Description |
|---|---|---|---|
| `id` | integer | PK | Unique customer id |
| `full_name` | text |  | Customer full name |
| `email` | text |  | Customer email address |
| `country` | text |  | Country of residence |
| `city` | text |  | City of residence |
| `created_at` | timestamp without time zone |  | When the customer signed up |

# Relationships

- Referenced by [addresses](/tables/ecommerce/addresses.md) through `customer_id`.
- Referenced by [carts](/tables/ecommerce/carts.md) through `customer_id`.
- Referenced by [chat_sessions](/tables/support/chat_sessions.md) through `customer_id`.
- Referenced by [customer_feedback](/tables/support/customer_feedback.md) through `customer_id`.
- Referenced by [invoices](/tables/finance/invoices.md) through `customer_id`.
- Referenced by [orders](/tables/ecommerce/orders.md) through `customer_id`.
- Referenced by [reviews](/tables/ecommerce/reviews.md) through `customer_id`.
- Referenced by [tickets](/tables/support/tickets.md) through `customer_id`.
- Referenced by [wishlists](/tables/ecommerce/wishlists.md) through `customer_id`.

# Notes

Master list of customers. Join to `orders` via `orders.customer_id = customers.id`.

# Examples

**Q:** How many customers do we have in each country?

```sql
SELECT country, COUNT(*) AS customers FROM customers GROUP BY country ORDER BY customers DESC
```

**Q:** Who are the top 3 customers by total order value?

```sql
SELECT c.full_name, SUM(o.total_amount) AS total_value FROM customers c JOIN orders o ON o.customer_id = c.id WHERE o.status <> 'cancelled' GROUP BY c.id, c.full_name ORDER BY total_value DESC LIMIT 3
```
