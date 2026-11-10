---
type: "Postgres Table"
title: "invoices"
description: "Invoices billed to customers for sales orders (billing documents with due dates)."
resource: "postgres://shop/public/invoices"
tags: ["invoice", "billing", "receivable", "due", "overdue", "customer", "bill", "outstanding"]
columns: ["id", "customer_id", "order_id", "amount", "status", "issued_on", "due_on"]
generated:
  by: "okf-chat/0.1.0"
  at: "2026-11-03T18:31:49Z"
---

Invoices billed to customers for sales orders (billing documents with due dates).

# Schema

| Column | Type | Key | Description |
|---|---|---|---|
| `id` | integer | PK | Unique invoice id |
| `customer_id` | integer | FK → [customers](/tables/ecommerce/customers.md) | Customer billed |
| `order_id` | integer | FK → [orders](/tables/ecommerce/orders.md) | Related sales order |
| `amount` | numeric(12,2) |  | Invoice amount in USD |
| `status` | text |  | Invoice status (one of: draft, sent, paid, overdue) |
| `issued_on` | date |  | Issue date |
| `due_on` | date |  | Due date |

# Relationships

- `customer_id` references [customers](/tables/ecommerce/customers.md) (`id`).
- `order_id` references [orders](/tables/ecommerce/orders.md) (`id`).
- Referenced by [invoice_items](/tables/finance/invoice_items.md) through `invoice_id`.

# Notes

Look-alike of payments: an invoice is the bill; a payment is money received.

# Examples

**Q:** How much is overdue in unpaid invoices?

```sql
SELECT COUNT(*) AS overdue_invoices, SUM(amount) AS overdue_amount FROM invoices WHERE status = 'overdue'
```
