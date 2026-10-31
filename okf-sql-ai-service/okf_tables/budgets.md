---
table: budgets
schema: public
description: "Planned spend per department per fiscal year."
tags: ["budget", "plan", "forecast", "fiscal", "year", "allocation", "department", "spend"]
columns:
  - {name: id, type: "integer", key: primary, description: "Unique id"}
  - {name: department_id, type: "integer", key: foreign, description: "Department"}
  - {name: fiscal_year, type: "integer", description: "Fiscal year"}
  - {name: planned_amount, type: "numeric(12,2)", description: "Budgeted amount in USD"}
  - {name: spent_amount, type: "numeric(12,2)", description: "Actual spent so far in USD"}
relationships:
  - budgets.department_id -> departments.id
---
# budgets
Planned spend per department per fiscal year.
