---
table: suppliers
schema: public
description: "Companies that supply products to the store."
tags: ["supplier", "vendor", "manufacturer", "sourcing"]
columns:
  - {name: id, type: "integer", key: primary, description: "Unique supplier id"}
  - {name: name, type: "text", description: "Supplier company name"}
  - {name: country, type: "text", description: "Supplier country"}
  - {name: contact_email, type: "text", description: "Supplier contact email"}
  - {name: rating, type: "numeric(12,2)", description: "Supplier quality rating 1-5"}
relationships:
  - product_suppliers.supplier_id -> suppliers.id
  - purchase_orders.supplier_id -> suppliers.id
---
# suppliers
Companies that supply products to the store.
