---
table: ticket_comments
schema: public
description: "Conversation messages on support tickets."
tags: ["ticket", "comment", "reply", "message", "conversation", "note"]
columns:
  - {name: id, type: "integer", key: primary, description: "Unique id"}
  - {name: ticket_id, type: "integer", key: foreign, description: "Ticket"}
  - {name: author_agent_id, type: "integer", key: foreign, description: "Agent author, null if customer"}
  - {name: body, type: "text", description: "Message text"}
  - {name: created_at, type: "timestamp", description: "When posted"}
relationships:
  - ticket_comments.ticket_id -> tickets.id
  - ticket_comments.author_agent_id -> support_agents.id
---
# ticket_comments
Conversation messages on support tickets.
