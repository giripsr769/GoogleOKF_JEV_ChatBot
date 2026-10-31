---
table: ledger_entries
schema: public
description: "General ledger postings: debits and credits against accounts."
tags: ["ledger", "journal", "entry", "debit", "credit", "posting", "gl", "accounting"]
columns:
  - {name: id, type: "integer", key: primary, description: "Unique entry id"}
  - {name: account_id, type: "integer", key: foreign, description: "Account posted to"}
  - {name: debit, type: "numeric(12,2)", description: "Debit amount in USD"}
  - {name: credit, type: "numeric(12,2)", description: "Credit amount in USD"}
  - {name: posted_at, type: "timestamp", description: "Posting time"}
  - {name: memo, type: "text", description: "Description"}
relationships:
  - ledger_entries.account_id -> accounts.id
---
# ledger_entries
General ledger postings: debits and credits against accounts.
