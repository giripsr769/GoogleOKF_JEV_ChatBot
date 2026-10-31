---
table: ticket_categories
schema: public
description: "Categories used to classify support tickets."
tags: ["ticket", "category", "type", "issue", "classification"]
columns:
  - {name: id, type: "integer", key: primary, description: "Unique id"}
  - {name: name, type: "text", description: "Category name such as Billing or Shipping"}
  - {name: description, type: "text", description: "What it covers"}
relationships:
  - tickets.category_id -> ticket_categories.id
  - knowledge_articles.category_id -> ticket_categories.id
---
# ticket_categories
Categories used to classify support tickets.
