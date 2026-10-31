---
table: knowledge_articles
schema: public
description: "Help-centre articles agents and customers can read."
tags: ["knowledge", "base", "article", "help", "faq", "documentation", "guide"]
columns:
  - {name: id, type: "integer", key: primary, description: "Unique id"}
  - {name: title, type: "text", description: "Article title"}
  - {name: category_id, type: "integer", key: foreign, description: "Related category"}
  - {name: views, type: "integer", description: "Number of views"}
  - {name: published_on, type: "date", description: "Publish date"}
relationships:
  - knowledge_articles.category_id -> ticket_categories.id
---
# knowledge_articles
Help-centre articles agents and customers can read.
