---
table: vendor_bills
schema: public
description: "Bills received from vendors that the company must pay (money OUT)."
tags: ["vendor", "bill", "payable", "owed", "pay", "supplier", "cost", "outgoing"]
columns:
  - {name: id, type: "integer", key: primary, description: "Unique id"}
  - {name: vendor_id, type: "integer", key: foreign, description: "Vendor who billed"}
  - {name: amount, type: "numeric(12,2)", description: "Bill amount in USD"}
  - {name: status, type: "text", description: "Bill status (one of: open, paid, overdue)"}
  - {name: due_on, type: "date", description: "Due date"}
relationships:
  - vendor_bills.vendor_id -> vendors.id
---
# vendor_bills
Money OUT. Customer payments are in payments.
