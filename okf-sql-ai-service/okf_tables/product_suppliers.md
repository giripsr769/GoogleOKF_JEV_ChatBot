---
table: product_suppliers
schema: public
description: "Which suppliers provide which products, with cost price and lead time."
tags: ["supplier", "product", "cost", "sourcing", "lead", "time"]
columns:
  - {name: id, type: "integer", key: primary, description: "Unique id"}
  - {name: product_id, type: "integer", key: foreign, description: "Product supplied"}
  - {name: supplier_id, type: "integer", key: foreign, description: "Supplier"}
  - {name: cost_price, type: "numeric(12,2)", description: "Cost per unit paid to supplier in USD"}
  - {name: lead_time_days, type: "integer", description: "Days from order to delivery"}
relationships:
  - product_suppliers.product_id -> products.id
  - product_suppliers.supplier_id -> suppliers.id
---
# product_suppliers
Which suppliers provide which products, with cost price and lead time.
