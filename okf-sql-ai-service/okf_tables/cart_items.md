---
table: cart_items
schema: public
description: "Products and quantities inside shopping carts."
tags: ["cart", "item", "basket", "product", "quantity"]
columns:
  - {name: id, type: "integer", key: primary, description: "Unique id"}
  - {name: cart_id, type: "integer", key: foreign, description: "Cart containing the item"}
  - {name: product_id, type: "integer", key: foreign, description: "Product in cart"}
  - {name: quantity, type: "integer", description: "Units in cart"}
relationships:
  - cart_items.cart_id -> carts.id
  - cart_items.product_id -> products.id
---
# cart_items
Products and quantities inside shopping carts.
