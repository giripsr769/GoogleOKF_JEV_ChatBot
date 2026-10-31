---
table: purchase_order_items
schema: public
description: "Line items of purchase orders sent to suppliers."
tags: ["purchase", "order", "item", "procurement", "line", "product", "quantity", "cost"]
columns:
  - {name: id, type: "integer", key: primary, description: "Unique id"}
  - {name: purchase_order_id, type: "integer", key: foreign, description: "Parent purchase order"}
  - {name: product_id, type: "integer", key: foreign, description: "Product bought"}
  - {name: quantity, type: "integer", description: "Units ordered"}
  - {name: unit_cost, type: "numeric(12,2)", description: "Cost per unit in USD"}
relationships:
  - purchase_order_items.purchase_order_id -> purchase_orders.id
  - purchase_order_items.product_id -> products.id
---
# purchase_order_items
Line items of purchase orders sent to suppliers.
