---
type: "Postgres Table"
title: "coupons"
description: "Discount coupon codes and their rules."
resource: "postgres://shop/public/coupons"
tags: ["coupon", "discount", "promo", "code", "voucher", "offer"]
columns: ["id", "code", "discount_percent", "valid_from", "valid_until", "max_uses"]
generated:
  by: "okf-chat/0.1.0"
  at: "2026-11-03T18:31:49Z"
---

Discount coupon codes and their rules.

# Schema

| Column | Type | Key | Description |
|---|---|---|---|
| `id` | integer | PK | Unique coupon id |
| `code` | text |  | Coupon code |
| `discount_percent` | numeric(12,2) |  | Percentage off |
| `valid_from` | date |  | Start date |
| `valid_until` | date |  | Expiry date |
| `max_uses` | integer |  | Maximum redemptions |

# Relationships

- Referenced by [order_coupons](/tables/ecommerce/order_coupons.md) through `coupon_id`.

# Notes

Discount coupon codes and their rules.

# Examples

**Q:** Which coupons are valid today?

```sql
SELECT code, discount_percent, valid_until FROM coupons WHERE CURRENT_DATE BETWEEN valid_from AND valid_until ORDER BY discount_percent DESC
```
