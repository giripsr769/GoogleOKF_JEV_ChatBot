---
table: customers
schema: public
description: People or companies who buy from the store. One row per customer account.
tags: [customer, user, account, buyer, country, city, signup]
columns:
  - {name: id, type: integer, key: primary, description: Unique customer id}
  - {name: full_name, type: text, description: Customer full name}
  - {name: email, type: text, description: Customer email address}
  - {name: country, type: text, description: Country of residence}
  - {name: city, type: text, description: City of residence}
  - {name: created_at, type: timestamp, description: When the customer signed up}
relationships:
  - orders.customer_id -> customers.id
---
# customers
Master list of customers. Join to `orders` via `orders.customer_id = customers.id`.
