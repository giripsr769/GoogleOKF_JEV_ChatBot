---
table: categories
schema: public
description: "Product categories, optionally nested under a parent category."
tags: ["category", "taxonomy", "department", "group", "catalog"]
columns:
  - {name: id, type: "integer", key: primary, description: "Unique category id"}
  - {name: name, type: "text", description: "Category name"}
  - {name: parent_id, type: "integer", key: foreign, description: "Parent category, null for top level"}
  - {name: description, type: "text", description: "Short description"}
relationships:
  - categories.parent_id -> categories.id
---
# categories
Products.category is free text; this table is the managed taxonomy.
