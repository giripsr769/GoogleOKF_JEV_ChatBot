---
type: "Postgres Table"
title: "tickets"
description: "Customer support tickets raised about problems or questions."
resource: "postgres://shop/public/tickets"
tags: ["ticket", "support", "issue", "case", "complaint", "helpdesk", "open", "resolved", "customer"]
columns: ["id", "customer_id", "order_id", "category_id", "agent_id", "priority", "status", "subject", "created_at", "resolved_at"]
generated:
  by: "okf-chat/0.1.0"
  at: "2026-11-03T18:31:49Z"
---

Customer support tickets raised about problems or questions.

# Schema

| Column | Type | Key | Description |
|---|---|---|---|
| `id` | integer | PK | Unique ticket id |
| `customer_id` | integer | FK → [customers](/tables/ecommerce/customers.md) | Customer who raised it |
| `order_id` | integer | FK → [orders](/tables/ecommerce/orders.md) | Related order if any |
| `category_id` | integer | FK → [ticket_categories](/tables/support/ticket_categories.md) | Ticket category |
| `agent_id` | integer | FK → [support_agents](/tables/support/support_agents.md) | Assigned agent |
| `priority` | text |  | Priority (one of: low, medium, high, urgent) |
| `status` | text |  | Status (one of: open, pending, resolved, closed) |
| `subject` | text |  | Ticket subject |
| `created_at` | timestamp without time zone |  | When opened |
| `resolved_at` | timestamp without time zone |  | When resolved, null if open |

# Relationships

- `agent_id` references [support_agents](/tables/support/support_agents.md) (`id`).
- `category_id` references [ticket_categories](/tables/support/ticket_categories.md) (`id`).
- `customer_id` references [customers](/tables/ecommerce/customers.md) (`id`).
- `order_id` references [orders](/tables/ecommerce/orders.md) (`id`).
- Referenced by [customer_feedback](/tables/support/customer_feedback.md) through `ticket_id`.
- Referenced by [escalations](/tables/support/escalations.md) through `ticket_id`.
- Referenced by [ticket_comments](/tables/support/ticket_comments.md) through `ticket_id`.

# Notes

Customer support tickets raised about problems or questions.

# Examples

**Q:** How many open tickets are there by priority?

```sql
SELECT priority, COUNT(*) AS open_tickets FROM tickets WHERE status IN ('open', 'pending') GROUP BY priority ORDER BY open_tickets DESC
```

**Q:** What is the average time to resolve a ticket, per priority?

```sql
SELECT priority, AVG(EXTRACT(EPOCH FROM (resolved_at - created_at)) / 3600) AS avg_hours FROM tickets WHERE resolved_at IS NOT NULL GROUP BY priority ORDER BY avg_hours
```
