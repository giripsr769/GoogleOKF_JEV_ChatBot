---
table: coupons
schema: public
description: "Discount coupon codes and their rules."
tags: ["coupon", "discount", "promo", "code", "voucher", "offer"]
columns:
  - {name: id, type: "integer", key: primary, description: "Unique coupon id"}
  - {name: code, type: "text", description: "Coupon code"}
  - {name: discount_percent, type: "numeric(12,2)", description: "Percentage off"}
  - {name: valid_from, type: "date", description: "Start date"}
  - {name: valid_until, type: "date", description: "Expiry date"}
  - {name: max_uses, type: "integer", description: "Maximum redemptions"}
relationships:
  - order_coupons.coupon_id -> coupons.id
---
# coupons
Discount coupon codes and their rules.
