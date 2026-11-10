---
type: "Postgres Table"
title: "ledger_entries"
description: "General ledger postings: debits and credits against accounts."
resource: "postgres://shop/public/ledger_entries"
tags: ["ledger", "journal", "entry", "debit", "credit", "posting", "gl", "accounting"]
columns: ["id", "account_id", "debit", "credit", "posted_at", "memo"]
generated:
  by: "okf-chat/0.1.0"
  at: "2026-11-03T18:31:49Z"
---

General ledger postings: debits and credits against accounts.

# Schema

| Column | Type | Key | Description |
|---|---|---|---|
| `id` | integer | PK | Unique entry id |
| `account_id` | integer | FK → [accounts](/tables/finance/accounts.md) | Account posted to |
| `debit` | numeric(12,2) |  | Debit amount in USD |
| `credit` | numeric(12,2) |  | Credit amount in USD |
| `posted_at` | timestamp without time zone |  | Posting time |
| `memo` | text |  | Description |

# Relationships

- `account_id` references [accounts](/tables/finance/accounts.md) (`id`).

# Notes

General ledger postings: debits and credits against accounts.

# Examples

**Q:** What are total debits and credits per account?

```sql
SELECT ac.name, SUM(le.debit) AS debits, SUM(le.credit) AS credits FROM ledger_entries le JOIN accounts ac ON ac.id = le.account_id GROUP BY ac.name ORDER BY ac.name
```
