---
table: addresses
schema: public
description: "Shipping and billing addresses saved by customers."
tags: ["address", "shipping", "billing", "street", "postcode", "location", "customer"]
columns:
  - {name: id, type: "integer", key: primary, description: "Unique address id"}
  - {name: customer_id, type: "integer", key: foreign, description: "Owner of the address"}
  - {name: type, type: "text", description: "Address type (one of: shipping, billing)"}
  - {name: street, type: "text", description: "Street line"}
  - {name: city, type: "text", description: "City"}
  - {name: postal_code, type: "text", description: "Postal code"}
  - {name: country, type: "text", description: "Country"}
relationships:
  - addresses.customer_id -> customers.id
---
# addresses
Shipping and billing addresses saved by customers.
