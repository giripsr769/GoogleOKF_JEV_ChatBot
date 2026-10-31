---
table: vendors
schema: public
description: "External companies the business pays for services and goods (accounts payable)."
tags: ["vendor", "payable", "service", "provider", "creditor", "external", "company"]
columns:
  - {name: id, type: "integer", key: primary, description: "Unique vendor id"}
  - {name: name, type: "text", description: "Vendor name"}
  - {name: category, type: "text", description: "Service category"}
  - {name: payment_terms_days, type: "integer", description: "Days allowed to pay"}
relationships:
  - vendor_bills.vendor_id -> vendors.id
---
# vendors
External companies the business pays for services and goods (accounts payable).
