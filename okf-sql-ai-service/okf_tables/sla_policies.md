---
table: sla_policies
schema: public
description: "Service level targets for response and resolution by priority."
tags: ["sla", "policy", "response", "resolution", "target", "priority", "hours", "deadline"]
columns:
  - {name: id, type: "integer", key: primary, description: "Unique id"}
  - {name: priority, type: "text", description: "Ticket priority (one of: low, medium, high, urgent)"}
  - {name: first_response_hours, type: "integer", description: "Target hours to first reply"}
  - {name: resolution_hours, type: "integer", description: "Target hours to resolve"}
---
# sla_policies
Service level targets for response and resolution by priority.
