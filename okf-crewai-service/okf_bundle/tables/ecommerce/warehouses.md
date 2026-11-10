---
type: "Postgres Table"
title: "warehouses"
description: "Physical warehouses that store inventory."
resource: "postgres://shop/public/warehouses"
tags: ["warehouse", "storage", "location", "fulfilment", "depot"]
columns: ["id", "name", "city", "country", "capacity_units"]
generated:
  by: "okf-chat/0.1.0"
  at: "2026-11-03T18:31:49Z"
---

Physical warehouses that store inventory.

# Schema

| Column | Type | Key | Description |
|---|---|---|---|
| `id` | integer | PK | Unique warehouse id |
| `name` | text |  | Warehouse name |
| `city` | text |  | City |
| `country` | text |  | Country |
| `capacity_units` | integer |  | Maximum units the warehouse can hold |

# Relationships

- Referenced by [inventory](/tables/ecommerce/inventory.md) through `warehouse_id`.
- Referenced by [purchase_orders](/tables/ecommerce/purchase_orders.md) through `warehouse_id`.
- Referenced by [shipments](/tables/ecommerce/shipments.md) through `warehouse_id`.

# Notes

Physical warehouses that store inventory.

# Examples

**Q:** How much stock does each warehouse hold?

```sql
SELECT w.name, w.city, SUM(i.quantity_on_hand) AS units FROM warehouses w JOIN inventory i ON i.warehouse_id = w.id GROUP BY w.id, w.name, w.city ORDER BY units DESC
```
