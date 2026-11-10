---
type: "Postgres Table"
title: "vendors"
description: "External companies the business pays for services and goods (accounts payable)."
resource: "postgres://shop/public/vendors"
tags: ["vendor", "payable", "service", "provider", "creditor", "external", "company"]
columns: ["id", "name", "category", "payment_terms_days"]
generated:
  by: "okf-chat/0.1.0"
  at: "2026-11-03T18:31:49Z"
---

External companies the business pays for services and goods (accounts payable).

# Schema

| Column | Type | Key | Description |
|---|---|---|---|
| `id` | integer | PK | Unique vendor id |
| `name` | text |  | Vendor name |
| `category` | text |  | Service category |
| `payment_terms_days` | integer |  | Days allowed to pay |

# Relationships

- Referenced by [vendor_bills](/tables/finance/vendor_bills.md) through `vendor_id`.

# Notes

External companies the business pays for services and goods (accounts payable).

# Examples

**Q:** What are the payment terms for each vendor category?

```sql
SELECT category, AVG(payment_terms_days) AS avg_terms_days, COUNT(*) AS vendors FROM vendors GROUP BY category ORDER BY category
```
