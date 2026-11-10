---
type: "Postgres Table"
title: "addresses"
description: "Shipping and billing addresses saved by customers."
resource: "postgres://shop/public/addresses"
tags: ["address", "shipping", "billing", "street", "postcode", "location", "customer"]
columns: ["id", "customer_id", "type", "street", "city", "postal_code", "country"]
generated:
  by: "okf-chat/0.1.0"
  at: "2026-11-03T18:31:49Z"
---

Shipping and billing addresses saved by customers.

# Schema

| Column | Type | Key | Description |
|---|---|---|---|
| `id` | integer | PK | Unique address id |
| `customer_id` | integer | FK → [customers](/tables/ecommerce/customers.md) | Owner of the address |
| `type` | text |  | Address type (one of: shipping, billing) |
| `street` | text |  | Street line |
| `city` | text |  | City |
| `postal_code` | text |  | Postal code |
| `country` | text |  | Country |

# Relationships

- `customer_id` references [customers](/tables/ecommerce/customers.md) (`id`).

# Notes

Shipping and billing addresses saved by customers.

# Examples

**Q:** How many customers have a shipping address in each country?

```sql
SELECT country, COUNT(DISTINCT customer_id) AS customers FROM addresses WHERE type = 'shipping' GROUP BY country ORDER BY customers DESC
```
