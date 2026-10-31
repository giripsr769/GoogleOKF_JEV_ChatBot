---
table: order_coupons
schema: public
description: "Coupons applied to sales orders."
tags: ["coupon", "discount", "applied", "order", "redemption"]
columns:
  - {name: id, type: "integer", key: primary, description: "Unique id"}
  - {name: order_id, type: "integer", key: foreign, description: "Order the coupon was used on"}
  - {name: coupon_id, type: "integer", key: foreign, description: "Coupon applied"}
  - {name: discount_amount, type: "numeric(12,2)", description: "Discount given in USD"}
relationships:
  - order_coupons.order_id -> orders.id
  - order_coupons.coupon_id -> coupons.id
---
# order_coupons
Coupons applied to sales orders.
