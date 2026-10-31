---
table: support_agents
schema: public
description: "Customer support agents."
tags: ["agent", "support", "helpdesk", "representative", "csr", "staff"]
columns:
  - {name: id, type: "integer", key: primary, description: "Unique agent id"}
  - {name: full_name, type: "text", description: "Agent name"}
  - {name: team_id, type: "integer", key: foreign, description: "Team"}
  - {name: email, type: "text", description: "Agent email"}
  - {name: active, type: "boolean", description: "Whether the agent is active"}
relationships:
  - support_agents.team_id -> support_teams.id
  - tickets.agent_id -> support_agents.id
  - ticket_comments.author_agent_id -> support_agents.id
  - chat_sessions.agent_id -> support_agents.id
---
# support_agents
Customer support agents.
