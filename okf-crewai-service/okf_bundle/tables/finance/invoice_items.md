---
type: "Postgres Table"
title: "invoice_items"
description: "Line items on customer invoices."
resource: "postgres://shop/public/invoice_items"
tags: ["invoice", "line", "item", "billing", "product", "amount"]
columns: ["id", "invoice_id", "product_id", "quantity", "line_total"]
generated:
  by: "okf-chat/0.1.0"
  at: "2026-11-03T18:31:49Z"
---

Line items on customer invoices.

# Schema

| Column | Type | Key | Description |
|---|---|---|---|
| `id` | integer | PK | Unique id |
| `invoice_id` | integer | FK → [invoices](/tables/finance/invoices.md) | Parent invoice |
| `product_id` | integer | FK → [products](/tables/ecommerce/products.md) | Product billed |
| `quantity` | integer |  | Units billed |
| `line_total` | numeric(12,2) |  | Line total in USD |

# Relationships

- `invoice_id` references [invoices](/tables/finance/invoices.md) (`id`).
- `product_id` references [products](/tables/ecommerce/products.md) (`id`).

# Notes

Line items on customer invoices.

# Examples

**Q:** Which products bring in the most invoiced revenue?

```sql
SELECT p.name, SUM(ii.line_total) AS invoiced FROM invoice_items ii JOIN products p ON p.id = ii.product_id GROUP BY p.name ORDER BY invoiced DESC LIMIT 5
```
