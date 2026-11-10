---
type: "Postgres Table"
title: "order_coupons"
description: "Coupons applied to sales orders."
resource: "postgres://shop/public/order_coupons"
tags: ["coupon", "discount", "applied", "order", "redemption"]
columns: ["id", "order_id", "coupon_id", "discount_amount"]
generated:
  by: "okf-chat/0.1.0"
  at: "2026-11-03T18:31:49Z"
---

Coupons applied to sales orders.

# Schema

| Column | Type | Key | Description |
|---|---|---|---|
| `id` | integer | PK | Unique id |
| `order_id` | integer | FK → [orders](/tables/ecommerce/orders.md) | Order the coupon was used on |
| `coupon_id` | integer | FK → [coupons](/tables/ecommerce/coupons.md) | Coupon applied |
| `discount_amount` | numeric(12,2) |  | Discount given in USD |

# Relationships

- `coupon_id` references [coupons](/tables/ecommerce/coupons.md) (`id`).
- `order_id` references [orders](/tables/ecommerce/orders.md) (`id`).

# Notes

Coupons applied to sales orders.

# Examples

**Q:** How much discount did each coupon give in total?

```sql
SELECT cp.code, SUM(oc.discount_amount) AS total_discount FROM order_coupons oc JOIN coupons cp ON cp.id = oc.coupon_id GROUP BY cp.code ORDER BY total_discount DESC
```
