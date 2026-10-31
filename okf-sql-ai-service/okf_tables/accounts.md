---
table: accounts
schema: public
description: "Chart of accounts used by the general ledger."
tags: ["account", "ledger", "chart", "gl", "asset", "liability", "revenue", "expense", "accounting"]
columns:
  - {name: id, type: "integer", key: primary, description: "Unique account id"}
  - {name: code, type: "text", description: "Account code"}
  - {name: name, type: "text", description: "Account name"}
  - {name: type, type: "text", description: "Account type (one of: asset, liability, equity, revenue, expense)"}
relationships:
  - ledger_entries.account_id -> accounts.id
  - bank_transactions.account_id -> accounts.id
---
# accounts
Chart of accounts used by the general ledger.
