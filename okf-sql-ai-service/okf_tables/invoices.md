---
table: invoices
schema: public
description: "Invoices billed to customers for sales orders (billing documents with due dates)."
tags: ["invoice", "billing", "receivable", "due", "overdue", "customer", "bill", "outstanding"]
columns:
  - {name: id, type: "integer", key: primary, description: "Unique invoice id"}
  - {name: customer_id, type: "integer", key: foreign, description: "Customer billed"}
  - {name: order_id, type: "integer", key: foreign, description: "Related sales order"}
  - {name: amount, type: "numeric(12,2)", description: "Invoice amount in USD"}
  - {name: status, type: "text", description: "Invoice status (one of: draft, sent, paid, overdue)"}
  - {name: issued_on, type: "date", description: "Issue date"}
  - {name: due_on, type: "date", description: "Due date"}
relationships:
  - invoices.customer_id -> customers.id
  - invoices.order_id -> orders.id
  - invoice_items.invoice_id -> invoices.id
---
# invoices
Look-alike of payments: an invoice is the bill; a payment is money received.
