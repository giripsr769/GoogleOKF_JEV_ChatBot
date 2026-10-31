---
table: returns
schema: public
description: "Customer return requests for sales orders and the reason given."
tags: ["return", "refund", "rma", "reverse", "exchange", "complaint", "order"]
columns:
  - {name: id, type: "integer", key: primary, description: "Unique return id"}
  - {name: order_id, type: "integer", key: foreign, description: "Sales order being returned"}
  - {name: reason, type: "text", description: "Reason for return (one of: damaged, wrong_item, not_needed, late)"}
  - {name: status, type: "text", description: "Return status (one of: requested, approved, rejected, refunded)"}
  - {name: refund_amount, type: "numeric(12,2)", description: "Amount refunded in USD"}
  - {name: requested_at, type: "timestamp", description: "When requested"}
relationships:
  - returns.order_id -> orders.id
---
# returns
Customer return requests for sales orders and the reason given.
