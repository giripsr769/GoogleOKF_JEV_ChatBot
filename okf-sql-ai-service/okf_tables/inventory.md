---
table: inventory
schema: public
description: "Current stock level of each product in each warehouse."
tags: ["inventory", "stock", "quantity", "on", "hand", "reorder", "warehouse"]
columns:
  - {name: id, type: "integer", key: primary, description: "Unique id"}
  - {name: product_id, type: "integer", key: foreign, description: "Product"}
  - {name: warehouse_id, type: "integer", key: foreign, description: "Warehouse holding the stock"}
  - {name: quantity_on_hand, type: "integer", description: "Units currently in stock"}
  - {name: reorder_level, type: "integer", description: "Reorder when stock falls below this"}
relationships:
  - inventory.product_id -> products.id
  - inventory.warehouse_id -> warehouses.id
---
# inventory
Total stock of a product = SUM(quantity_on_hand) across warehouses.
