---
table: products
schema: public
description: Catalogue of items for sale with category and unit price.
tags: [product, item, catalogue, category, price, stock, inventory]
columns:
  - {name: id, type: integer, key: primary, description: Unique product id}
  - {name: name, type: text, description: Product name}
  - {name: category, type: text, description: Product category e.g. Electronics, Books}
  - {name: price, type: "numeric(10,2)", description: Current unit price}
  - {name: stock, type: integer, description: Units currently in stock}
relationships:
  - order_items.product_id -> products.id
---
# products
Product catalogue. Use `order_items` to find which products were sold.
