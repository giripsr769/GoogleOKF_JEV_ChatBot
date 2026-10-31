---
table: expenses
schema: public
description: "Employee expense claims such as travel and meals."
tags: ["expense", "claim", "reimbursement", "travel", "meals", "spend", "employee"]
columns:
  - {name: id, type: "integer", key: primary, description: "Unique id"}
  - {name: employee_id, type: "integer", key: foreign, description: "Employee claiming"}
  - {name: category, type: "text", description: "Expense category (one of: travel, meals, software, equipment)"}
  - {name: amount, type: "numeric(12,2)", description: "Amount in USD"}
  - {name: status, type: "text", description: "Claim status (one of: submitted, approved, reimbursed, rejected)"}
  - {name: incurred_on, type: "date", description: "Date spent"}
relationships:
  - expenses.employee_id -> employees.id
---
# expenses
Employee expense claims such as travel and meals.
