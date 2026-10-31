---
table: orders
schema: public
description: Sales orders placed by customers, with status and total amount.
tags: [order, sale, revenue, purchase, status, total, date, shipped, cancelled]
columns:
  - {name: id, type: integer, key: primary, description: Unique order id}
  - {name: customer_id, type: integer, key: foreign, description: References customers.id}
  - {name: status, type: text, description: "One of: pending, shipped, delivered, cancelled"}
  - {name: total_amount, type: "numeric(12,2)", description: Order total in USD}
  - {name: ordered_at, type: timestamp, description: When the order was placed}
relationships:
  - orders.customer_id -> customers.id
  - order_items.order_id -> orders.id
---
# orders
One row per order. Revenue = SUM(total_amount) excluding status 'cancelled'.
