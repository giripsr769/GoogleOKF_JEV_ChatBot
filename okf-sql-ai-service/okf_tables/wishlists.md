---
table: wishlists
schema: public
description: "Products customers saved to wishlists for later."
tags: ["wishlist", "saved", "favourite", "later", "product", "customer"]
columns:
  - {name: id, type: "integer", key: primary, description: "Unique id"}
  - {name: customer_id, type: "integer", key: foreign, description: "Customer"}
  - {name: product_id, type: "integer", key: foreign, description: "Product saved"}
  - {name: added_at, type: "timestamp", description: "When added"}
relationships:
  - wishlists.customer_id -> customers.id
  - wishlists.product_id -> products.id
---
# wishlists
Products customers saved to wishlists for later.
