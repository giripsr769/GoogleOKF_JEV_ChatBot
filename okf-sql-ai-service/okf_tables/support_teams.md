---
table: support_teams
schema: public
description: "Support teams that agents belong to."
tags: ["support", "team", "group", "queue", "tier", "helpdesk"]
columns:
  - {name: id, type: "integer", key: primary, description: "Unique team id"}
  - {name: name, type: "text", description: "Team name"}
  - {name: tier, type: "integer", description: "Support tier 1-3"}
relationships:
  - support_agents.team_id -> support_teams.id
  - escalations.from_team_id -> support_teams.id
  - escalations.to_team_id -> support_teams.id
---
# support_teams
Support teams that agents belong to.
