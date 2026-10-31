---
table: leave_requests
schema: public
description: "Employee leave and time-off requests."
tags: ["leave", "vacation", "holiday", "sick", "time", "off", "absence", "request"]
columns:
  - {name: id, type: "integer", key: primary, description: "Unique id"}
  - {name: employee_id, type: "integer", key: foreign, description: "Requesting employee"}
  - {name: leave_type, type: "text", description: "Type of leave (one of: annual, sick, unpaid, parental)"}
  - {name: start_date, type: "date", description: "First day"}
  - {name: end_date, type: "date", description: "Last day"}
  - {name: status, type: "text", description: "Decision status (one of: pending, approved, rejected)"}
relationships:
  - leave_requests.employee_id -> employees.id
---
# leave_requests
Employee leave and time-off requests.
