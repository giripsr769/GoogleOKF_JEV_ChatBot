---
table: purchase_orders
schema: public
description: "Orders the company places WITH suppliers to buy stock (procurement). Not customer sales orders."
tags: ["purchase", "order", "procurement", "buying", "restock", "supplier", "po", "inbound"]
columns:
  - {name: id, type: "integer", key: primary, description: "Unique purchase order id"}
  - {name: supplier_id, type: "integer", key: foreign, description: "Supplier ordered from"}
  - {name: warehouse_id, type: "integer", key: foreign, description: "Delivery warehouse"}
  - {name: status, type: "text", description: "PO status (one of: draft, sent, received, cancelled)"}
  - {name: total_cost, type: "numeric(12,2)", description: "PO total cost in USD"}
  - {name: ordered_at, type: "timestamp", description: "When placed"}
relationships:
  - purchase_orders.supplier_id -> suppliers.id
  - purchase_orders.warehouse_id -> warehouses.id
  - purchase_order_items.purchase_order_id -> purchase_orders.id
---
# purchase_orders
Look-alike of orders: orders are customer SALES, purchase_orders are company BUYING from suppliers.
