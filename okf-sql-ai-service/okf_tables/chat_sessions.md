---
table: chat_sessions
schema: public
description: "Live chat sessions between customers and agents."
tags: ["chat", "live", "session", "conversation", "messaging", "agent", "customer"]
columns:
  - {name: id, type: "integer", key: primary, description: "Unique id"}
  - {name: customer_id, type: "integer", key: foreign, description: "Customer"}
  - {name: agent_id, type: "integer", key: foreign, description: "Agent"}
  - {name: started_at, type: "timestamp", description: "Start time"}
  - {name: duration_minutes, type: "integer", description: "Length in minutes"}
  - {name: resolved, type: "boolean", description: "Whether resolved in chat"}
relationships:
  - chat_sessions.customer_id -> customers.id
  - chat_sessions.agent_id -> support_agents.id
---
# chat_sessions
Live chat sessions between customers and agents.
