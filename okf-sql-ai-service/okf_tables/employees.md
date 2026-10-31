---
table: employees
schema: public
description: "Company staff members. Internal people, not store customers."
tags: ["employee", "staff", "worker", "personnel", "hire", "manager", "headcount", "internal"]
columns:
  - {name: id, type: "integer", key: primary, description: "Unique employee id"}
  - {name: full_name, type: "text", description: "Employee name"}
  - {name: work_email, type: "text", description: "Company email"}
  - {name: department_id, type: "integer", key: foreign, description: "Department"}
  - {name: job_title_id, type: "integer", key: foreign, description: "Job title"}
  - {name: manager_id, type: "integer", key: foreign, description: "Manager, null for top"}
  - {name: hired_on, type: "date", description: "Hire date"}
  - {name: status, type: "text", description: "Employment status (one of: active, on_leave, terminated)"}
relationships:
  - employees.department_id -> departments.id
  - employees.job_title_id -> job_titles.id
  - employees.manager_id -> employees.id
  - salaries.employee_id -> employees.id
  - leave_requests.employee_id -> employees.id
  - attendance.employee_id -> employees.id
  - performance_reviews.employee_id -> employees.id
  - performance_reviews.reviewer_id -> employees.id
  - training_enrollments.employee_id -> employees.id
  - expenses.employee_id -> employees.id
---
# employees
Look-alike of customers: employees are internal staff.
