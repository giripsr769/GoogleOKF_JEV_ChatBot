---
type: "Postgres Table"
title: "bank_transactions"
description: "Bank statement lines: deposits and withdrawals."
resource: "postgres://shop/public/bank_transactions"
tags: ["bank", "transaction", "deposit", "withdrawal", "statement", "cash", "reconciliation"]
columns: ["id", "account_id", "amount", "description", "txn_at"]
generated:
  by: "okf-chat/0.1.0"
  at: "2026-11-03T18:31:49Z"
---

Bank statement lines: deposits and withdrawals.

# Schema

| Column | Type | Key | Description |
|---|---|---|---|
| `id` | integer | PK | Unique id |
| `account_id` | integer | FK → [accounts](/tables/finance/accounts.md) | Related ledger account |
| `amount` | numeric(12,2) |  | Positive deposit, negative withdrawal, USD |
| `description` | text |  | Bank narration |
| `txn_at` | timestamp without time zone |  | Transaction time |

# Relationships

- `account_id` references [accounts](/tables/finance/accounts.md) (`id`).

# Notes

Bank statement lines: deposits and withdrawals.

# Examples

**Q:** What is the total amount of bank transactions per account?

```sql
SELECT ac.name, SUM(bt.amount) AS total_amount FROM bank_transactions bt JOIN accounts ac ON ac.id = bt.account_id GROUP BY ac.name ORDER BY total_amount DESC
```
