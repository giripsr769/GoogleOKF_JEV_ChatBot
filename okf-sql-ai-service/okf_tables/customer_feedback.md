---
table: customer_feedback
schema: public
description: "Post-support satisfaction (CSAT) scores from customers."
tags: ["csat", "nps", "satisfaction", "survey", "score", "feedback", "support", "rating"]
columns:
  - {name: id, type: "integer", key: primary, description: "Unique id"}
  - {name: ticket_id, type: "integer", key: foreign, description: "Ticket rated"}
  - {name: customer_id, type: "integer", key: foreign, description: "Customer"}
  - {name: score, type: "integer", description: "Satisfaction 1 to 5"}
  - {name: comment, type: "text", description: "Free text"}
  - {name: submitted_at, type: "timestamp", description: "When submitted"}
relationships:
  - customer_feedback.ticket_id -> tickets.id
  - customer_feedback.customer_id -> customers.id
---
# customer_feedback
Support satisfaction. Product ratings are in reviews.
