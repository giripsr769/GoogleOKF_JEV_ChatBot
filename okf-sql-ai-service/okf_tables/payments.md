---
table: payments
schema: public
description: "Customer payments received against sales orders."
tags: ["payment", "paid", "transaction", "card", "upi", "refund", "customer", "order"]
columns:
  - {name: id, type: "integer", key: primary, description: "Unique payment id"}
  - {name: order_id, type: "integer", key: foreign, description: "Sales order being paid"}
  - {name: method, type: "text", description: "Payment method (one of: card, upi, cash, netbanking)"}
  - {name: amount, type: "numeric(12,2)", description: "Amount paid in USD"}
  - {name: status, type: "text", description: "Payment status (one of: completed, failed, refunded)"}
  - {name: paid_at, type: "timestamp", description: "When payment was made"}
relationships:
  - payments.order_id -> orders.id
---
# payments
Customer money IN. Not the same as vendor_bills (money OUT) or invoices (billing documents).
