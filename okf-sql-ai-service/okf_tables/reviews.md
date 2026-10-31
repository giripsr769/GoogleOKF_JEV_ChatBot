---
table: reviews
schema: public
description: "Customer ratings and written reviews of products."
tags: ["review", "rating", "stars", "feedback", "comment", "product", "customer"]
columns:
  - {name: id, type: "integer", key: primary, description: "Unique review id"}
  - {name: product_id, type: "integer", key: foreign, description: "Product reviewed"}
  - {name: customer_id, type: "integer", key: foreign, description: "Customer who wrote it"}
  - {name: rating, type: "integer", description: "Star rating 1 to 5"}
  - {name: comment, type: "text", description: "Review text"}
  - {name: created_at, type: "timestamp", description: "When posted"}
relationships:
  - reviews.product_id -> products.id
  - reviews.customer_id -> customers.id
---
# reviews
Customer ratings and written reviews of products.
