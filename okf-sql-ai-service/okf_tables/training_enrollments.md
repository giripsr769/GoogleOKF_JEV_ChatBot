---
table: training_enrollments
schema: public
description: "Which employees enrolled in which training courses and their completion."
tags: ["training", "enrollment", "course", "completion", "employee", "learning"]
columns:
  - {name: id, type: "integer", key: primary, description: "Unique id"}
  - {name: employee_id, type: "integer", key: foreign, description: "Employee"}
  - {name: course_id, type: "integer", key: foreign, description: "Course"}
  - {name: status, type: "text", description: "Progress status (one of: enrolled, completed, dropped)"}
  - {name: completed_on, type: "date", description: "Completion date, null if not done"}
relationships:
  - training_enrollments.employee_id -> employees.id
  - training_enrollments.course_id -> training_courses.id
---
# training_enrollments
Which employees enrolled in which training courses and their completion.
