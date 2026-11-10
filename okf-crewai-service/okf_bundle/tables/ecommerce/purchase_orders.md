---
type: "Postgres Table"
title: "purchase_orders"
description: "Orders the company places WITH suppliers to buy stock (procurement). Not customer sales orders."
resource: "postgres://shop/public/purchase_orders"
tags: ["purchase", "order", "procurement", "buying", "restock", "supplier", "po", "inbound"]
columns: ["id", "supplier_id", "warehouse_id", "status", "total_cost", "ordered_at"]
generated:
  by: "okf-chat/0.1.0"
  at: "2026-11-03T18:31:49Z"
---

Orders the company places WITH suppliers to buy stock (procurement). Not customer sales orders.

# Schema

| Column | Type | Key | Description |
|---|---|---|---|
| `id` | integer | PK | Unique purchase order id |
| `supplier_id` | integer | FK → [suppliers](/tables/ecommerce/suppliers.md) | Supplier ordered from |
| `warehouse_id` | integer | FK → [warehouses](/tables/ecommerce/warehouses.md) | Delivery warehouse |
| `status` | text |  | PO status (one of: draft, sent, received, cancelled) |
| `total_cost` | numeric(12,2) |  | PO total cost in USD |
| `ordered_at` | timestamp without time zone |  | When placed |

# Relationships

- `supplier_id` references [suppliers](/tables/ecommerce/suppliers.md) (`id`).
- `warehouse_id` references [warehouses](/tables/ecommerce/warehouses.md) (`id`).
- Referenced by [purchase_order_items](/tables/ecommerce/purchase_order_items.md) through `purchase_order_id`.

# Notes

Look-alike of orders: orders are customer SALES, purchase_orders are company BUYING from suppliers.

# Examples

**Q:** What is the total cost of purchase orders per supplier?

```sql
SELECT s.name, SUM(po.total_cost) AS total_cost FROM purchase_orders po JOIN suppliers s ON s.id = po.supplier_id WHERE po.status <> 'cancelled' GROUP BY s.name ORDER BY total_cost DESC
```
