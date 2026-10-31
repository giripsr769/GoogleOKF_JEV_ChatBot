---
table: attendance
schema: public
description: "Daily attendance records for employees."
tags: ["attendance", "present", "absent", "checkin", "checkout", "hours", "clock"]
columns:
  - {name: id, type: "integer", key: primary, description: "Unique id"}
  - {name: employee_id, type: "integer", key: foreign, description: "Employee"}
  - {name: work_date, type: "date", description: "Date"}
  - {name: hours_worked, type: "numeric(12,2)", description: "Hours worked that day"}
  - {name: status, type: "text", description: "Attendance status (one of: present, absent, remote)"}
relationships:
  - attendance.employee_id -> employees.id
---
# attendance
Daily attendance records for employees.
