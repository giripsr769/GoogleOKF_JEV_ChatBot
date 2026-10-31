---
table: job_titles
schema: public
description: "Job titles and their pay grade bands."
tags: ["job", "title", "role", "position", "grade", "level", "designation"]
columns:
  - {name: id, type: "integer", key: primary, description: "Unique id"}
  - {name: title, type: "text", description: "Job title"}
  - {name: grade, type: "integer", description: "Pay grade level"}
  - {name: min_salary, type: "numeric(12,2)", description: "Band minimum"}
  - {name: max_salary, type: "numeric(12,2)", description: "Band maximum"}
relationships:
  - employees.job_title_id -> job_titles.id
---
# job_titles
Job titles and their pay grade bands.
