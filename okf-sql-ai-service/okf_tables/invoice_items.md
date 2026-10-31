---
table: invoice_items
schema: public
description: "Line items on customer invoices."
tags: ["invoice", "line", "item", "billing", "product", "amount"]
columns:
  - {name: id, type: "integer", key: primary, description: "Unique id"}
  - {name: invoice_id, type: "integer", key: foreign, description: "Parent invoice"}
  - {name: product_id, type: "integer", key: foreign, description: "Product billed"}
  - {name: quantity, type: "integer", description: "Units billed"}
  - {name: line_total, type: "numeric(12,2)", description: "Line total in USD"}
relationships:
  - invoice_items.invoice_id -> invoices.id
  - invoice_items.product_id -> products.id
---
# invoice_items
Line items on customer invoices.
