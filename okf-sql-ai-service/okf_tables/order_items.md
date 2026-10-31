---
table: order_items
schema: public
description: Line items of each order - which product, how many, at what price.
tags: [order item, line item, quantity, product sold, best selling, units]
columns:
  - {name: id, type: integer, key: primary, description: Unique line item id}
  - {name: order_id, type: integer, key: foreign, description: References orders.id}
  - {name: product_id, type: integer, key: foreign, description: References products.id}
  - {name: quantity, type: integer, description: Units purchased}
  - {name: unit_price, type: "numeric(10,2)", description: Price per unit at time of sale}
relationships:
  - order_items.order_id -> orders.id
  - order_items.product_id -> products.id
---
# order_items
Bridge between orders and products. Line revenue = quantity * unit_price.
