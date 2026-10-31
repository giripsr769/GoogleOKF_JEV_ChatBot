---
table: tickets
schema: public
description: "Customer support tickets raised about problems or questions."
tags: ["ticket", "support", "issue", "case", "complaint", "helpdesk", "open", "resolved", "customer"]
columns:
  - {name: id, type: "integer", key: primary, description: "Unique ticket id"}
  - {name: customer_id, type: "integer", key: foreign, description: "Customer who raised it"}
  - {name: order_id, type: "integer", key: foreign, description: "Related order if any"}
  - {name: category_id, type: "integer", key: foreign, description: "Ticket category"}
  - {name: agent_id, type: "integer", key: foreign, description: "Assigned agent"}
  - {name: priority, type: "text", description: "Priority (one of: low, medium, high, urgent)"}
  - {name: status, type: "text", description: "Status (one of: open, pending, resolved, closed)"}
  - {name: subject, type: "text", description: "Ticket subject"}
  - {name: created_at, type: "timestamp", description: "When opened"}
  - {name: resolved_at, type: "timestamp", description: "When resolved, null if open"}
relationships:
  - tickets.customer_id -> customers.id
  - tickets.order_id -> orders.id
  - tickets.category_id -> ticket_categories.id
  - tickets.agent_id -> support_agents.id
  - ticket_comments.ticket_id -> tickets.id
  - escalations.ticket_id -> tickets.id
  - customer_feedback.ticket_id -> tickets.id
---
# tickets
Customer support tickets raised about problems or questions.
