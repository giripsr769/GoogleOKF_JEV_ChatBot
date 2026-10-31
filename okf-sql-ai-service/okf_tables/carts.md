---
table: carts
schema: public
description: "Shopping carts, open or abandoned, belonging to customers."
tags: ["cart", "basket", "shopping", "abandoned", "checkout", "customer"]
columns:
  - {name: id, type: "integer", key: primary, description: "Unique cart id"}
  - {name: customer_id, type: "integer", key: foreign, description: "Cart owner"}
  - {name: status, type: "text", description: "Cart state (one of: open, abandoned, converted)"}
  - {name: created_at, type: "timestamp", description: "When created"}
relationships:
  - carts.customer_id -> customers.id
  - cart_items.cart_id -> carts.id
---
# carts
Shopping carts, open or abandoned, belonging to customers.
