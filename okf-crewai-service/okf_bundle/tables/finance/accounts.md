---
type: "Postgres Table"
title: "accounts"
description: "Chart of accounts used by the general ledger."
resource: "postgres://shop/public/accounts"
tags: ["account", "ledger", "chart", "gl", "asset", "liability", "revenue", "expense", "accounting"]
columns: ["id", "code", "name", "type"]
generated:
  by: "okf-chat/0.1.0"
  at: "2026-11-03T18:31:49Z"
---

Chart of accounts used by the general ledger.

# Schema

| Column | Type | Key | Description |
|---|---|---|---|
| `id` | integer | PK | Unique account id |
| `code` | text |  | Account code |
| `name` | text |  | Account name |
| `type` | text |  | Account type (one of: asset, liability, equity, revenue, expense) |

# Relationships

- Referenced by [bank_transactions](/tables/finance/bank_transactions.md) through `account_id`.
- Referenced by [ledger_entries](/tables/finance/ledger_entries.md) through `account_id`.

# Notes

Chart of accounts used by the general ledger.

# Examples

**Q:** How many accounts are there of each type?

```sql
SELECT type, COUNT(*) AS accounts FROM accounts GROUP BY type ORDER BY accounts DESC
```
