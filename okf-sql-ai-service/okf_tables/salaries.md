---
table: salaries
schema: public
description: "Employee salary records. SENSITIVE."
tags: ["salary", "pay", "compensation", "wage", "bonus", "payroll", "sensitive"]
columns:
  - {name: id, type: "integer", key: primary, description: "Unique id"}
  - {name: employee_id, type: "integer", key: foreign, description: "Employee paid"}
  - {name: base_salary, type: "numeric(12,2)", description: "Annual base salary in USD"}
  - {name: bonus, type: "numeric(12,2)", description: "Annual bonus in USD"}
  - {name: effective_from, type: "date", description: "Date this salary applies from"}
relationships:
  - salaries.employee_id -> employees.id
---
# salaries
Restricted: not readable by the API role.
