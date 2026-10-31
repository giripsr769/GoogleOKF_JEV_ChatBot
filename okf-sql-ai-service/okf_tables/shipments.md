---
table: shipments
schema: public
description: "Delivery shipments for sales orders, with carrier and delivery dates."
tags: ["shipment", "delivery", "carrier", "tracking", "shipped", "dispatch", "courier"]
columns:
  - {name: id, type: "integer", key: primary, description: "Unique shipment id"}
  - {name: order_id, type: "integer", key: foreign, description: "Sales order shipped"}
  - {name: warehouse_id, type: "integer", key: foreign, description: "Warehouse shipped from"}
  - {name: carrier, type: "text", description: "Carrier name (one of: DHL, FedEx, BlueDart, UPS)"}
  - {name: status, type: "text", description: "Shipment status (one of: in_transit, delivered, lost)"}
  - {name: shipped_at, type: "timestamp", description: "Dispatch time"}
  - {name: delivered_at, type: "timestamp", description: "Delivery time, null if not delivered"}
relationships:
  - shipments.order_id -> orders.id
  - shipments.warehouse_id -> warehouses.id
---
# shipments
Delivery shipments for sales orders, with carrier and delivery dates.
