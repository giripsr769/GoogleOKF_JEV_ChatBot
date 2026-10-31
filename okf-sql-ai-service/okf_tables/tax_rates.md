---
table: tax_rates
schema: public
description: "Sales tax rates by country."
tags: ["tax", "vat", "gst", "rate", "country", "duty"]
columns:
  - {name: id, type: "integer", key: primary, description: "Unique id"}
  - {name: country, type: "text", description: "Country"}
  - {name: tax_name, type: "text", description: "Tax name such as VAT or GST"}
  - {name: rate_percent, type: "numeric(12,2)", description: "Tax rate percent"}
---
# tax_rates
Sales tax rates by country.
