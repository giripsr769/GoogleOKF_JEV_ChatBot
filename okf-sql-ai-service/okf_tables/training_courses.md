---
table: training_courses
schema: public
description: "Internal training courses employees can take."
tags: ["training", "course", "learning", "skill", "certification", "workshop"]
columns:
  - {name: id, type: "integer", key: primary, description: "Unique course id"}
  - {name: title, type: "text", description: "Course title"}
  - {name: duration_hours, type: "integer", description: "Course length in hours"}
  - {name: provider, type: "text", description: "Training provider"}
relationships:
  - training_enrollments.course_id -> training_courses.id
---
# training_courses
Internal training courses employees can take.
