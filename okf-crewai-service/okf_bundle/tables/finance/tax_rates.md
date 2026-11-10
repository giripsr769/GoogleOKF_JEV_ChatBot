---
type: "Postgres Table"
title: "tax_rates"
description: "Sales tax rates by country."
resource: "postgres://shop/public/tax_rates"
tags: ["tax", "vat", "gst", "rate", "country", "duty"]
columns: ["id", "country", "tax_name", "rate_percent"]
generated:
  by: "okf-chat/0.1.0"
  at: "2026-11-03T18:31:49Z"
---

Sales tax rates by country.

# Schema

| Column | Type | Key | Description |
|---|---|---|---|
| `id` | integer | PK | Unique id |
| `country` | text |  | Country |
| `tax_name` | text |  | Tax name such as VAT or GST |
| `rate_percent` | numeric(12,2) |  | Tax rate percent |

# Notes

Sales tax rates by country.

# Examples

**Q:** What are the tax rates by country?

```sql
SELECT country, tax_name, rate_percent FROM tax_rates ORDER BY country
```
