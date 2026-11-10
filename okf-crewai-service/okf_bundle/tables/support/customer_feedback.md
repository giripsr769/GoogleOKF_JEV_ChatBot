---
type: "Postgres Table"
title: "customer_feedback"
description: "Post-support satisfaction (CSAT) scores from customers."
resource: "postgres://shop/public/customer_feedback"
tags: ["csat", "nps", "satisfaction", "survey", "score", "feedback", "support", "rating"]
columns: ["id", "ticket_id", "customer_id", "score", "comment", "submitted_at"]
generated:
  by: "okf-chat/0.1.0"
  at: "2026-11-03T18:31:49Z"
---

Post-support satisfaction (CSAT) scores from customers.

# Schema

| Column | Type | Key | Description |
|---|---|---|---|
| `id` | integer | PK | Unique id |
| `ticket_id` | integer | FK → [tickets](/tables/support/tickets.md) | Ticket rated |
| `customer_id` | integer | FK → [customers](/tables/ecommerce/customers.md) | Customer |
| `score` | integer |  | Satisfaction 1 to 5 |
| `comment` | text |  | Free text |
| `submitted_at` | timestamp without time zone |  | When submitted |

# Relationships

- `customer_id` references [customers](/tables/ecommerce/customers.md) (`id`).
- `ticket_id` references [tickets](/tables/support/tickets.md) (`id`).

# Notes

Support satisfaction. Product ratings are in reviews.

# Examples

**Q:** What is the average feedback score per ticket category?

```sql
SELECT tc.name, AVG(cf.score) AS avg_score, COUNT(*) AS responses FROM customer_feedback cf JOIN tickets t ON t.id = cf.ticket_id JOIN ticket_categories tc ON tc.id = t.category_id GROUP BY tc.name ORDER BY avg_score DESC
```
