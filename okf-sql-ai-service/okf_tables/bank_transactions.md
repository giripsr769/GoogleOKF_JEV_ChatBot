---
table: bank_transactions
schema: public
description: "Bank statement lines: deposits and withdrawals."
tags: ["bank", "transaction", "deposit", "withdrawal", "statement", "cash", "reconciliation"]
columns:
  - {name: id, type: "integer", key: primary, description: "Unique id"}
  - {name: account_id, type: "integer", key: foreign, description: "Related ledger account"}
  - {name: amount, type: "numeric(12,2)", description: "Positive deposit, negative withdrawal, USD"}
  - {name: description, type: "text", description: "Bank narration"}
  - {name: txn_at, type: "timestamp", description: "Transaction time"}
relationships:
  - bank_transactions.account_id -> accounts.id
---
# bank_transactions
Bank statement lines: deposits and withdrawals.
