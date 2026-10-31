---
table: warehouses
schema: public
description: "Physical warehouses that store inventory."
tags: ["warehouse", "storage", "location", "fulfilment", "depot"]
columns:
  - {name: id, type: "integer", key: primary, description: "Unique warehouse id"}
  - {name: name, type: "text", description: "Warehouse name"}
  - {name: city, type: "text", description: "City"}
  - {name: country, type: "text", description: "Country"}
  - {name: capacity_units, type: "integer", description: "Maximum units the warehouse can hold"}
relationships:
  - inventory.warehouse_id -> warehouses.id
  - shipments.warehouse_id -> warehouses.id
  - purchase_orders.warehouse_id -> warehouses.id
---
# warehouses
Physical warehouses that store inventory.
