---
table: departments
schema: public
description: "Company departments such as Sales, Engineering and HR."
tags: ["department", "team", "division", "org", "unit", "cost", "center"]
columns:
  - {name: id, type: "integer", key: primary, description: "Unique department id"}
  - {name: name, type: "text", description: "Department name"}
  - {name: location, type: "text", description: "Office location"}
  - {name: budget, type: "numeric(12,2)", description: "Annual department budget in USD"}
relationships:
  - employees.department_id -> departments.id
  - budgets.department_id -> departments.id
---
# departments
Company departments such as Sales, Engineering and HR.
