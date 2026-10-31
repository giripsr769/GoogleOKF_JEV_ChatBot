---
table: performance_reviews
schema: public
description: "Periodic performance reviews and ratings of employees."
tags: ["performance", "review", "appraisal", "rating", "evaluation", "score", "staff"]
columns:
  - {name: id, type: "integer", key: primary, description: "Unique id"}
  - {name: employee_id, type: "integer", key: foreign, description: "Employee reviewed"}
  - {name: reviewer_id, type: "integer", key: foreign, description: "Employee who reviewed"}
  - {name: rating, type: "integer", description: "Performance rating 1 to 5"}
  - {name: review_period, type: "text", description: "Review period such as 2025-H1"}
  - {name: comments, type: "text", description: "Reviewer comments"}
relationships:
  - performance_reviews.employee_id -> employees.id
  - performance_reviews.reviewer_id -> employees.id
---
# performance_reviews
Periodic performance reviews and ratings of employees.
