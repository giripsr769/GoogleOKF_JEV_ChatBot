---
table: escalations
schema: public
description: "Tickets escalated to a higher tier or manager."
tags: ["escalation", "escalated", "tier", "manager", "urgent", "breach"]
columns:
  - {name: id, type: "integer", key: primary, description: "Unique id"}
  - {name: ticket_id, type: "integer", key: foreign, description: "Escalated ticket"}
  - {name: from_team_id, type: "integer", key: foreign, description: "Team escalating"}
  - {name: to_team_id, type: "integer", key: foreign, description: "Team receiving"}
  - {name: reason, type: "text", description: "Why escalated"}
  - {name: escalated_at, type: "timestamp", description: "When escalated"}
relationships:
  - escalations.ticket_id -> tickets.id
  - escalations.from_team_id -> support_teams.id
  - escalations.to_team_id -> support_teams.id
---
# escalations
Tickets escalated to a higher tier or manager.
