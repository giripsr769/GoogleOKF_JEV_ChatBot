---
type: "Postgres Table"
title: "shipments"
description: "Delivery shipments for sales orders, with carrier and delivery dates."
resource: "postgres://shop/public/shipments"
tags: ["shipment", "delivery", "carrier", "tracking", "shipped", "dispatch", "courier"]
columns: ["id", "order_id", "warehouse_id", "carrier", "status", "shipped_at", "delivered_at"]
generated:
  by: "okf-chat/0.1.0"
  at: "2026-11-03T18:31:49Z"
---

Delivery shipments for sales orders, with carrier and delivery dates.

# Schema

| Column | Type | Key | Description |
|---|---|---|---|
| `id` | integer | PK | Unique shipment id |
| `order_id` | integer | FK → [orders](/tables/ecommerce/orders.md) | Sales order shipped |
| `warehouse_id` | integer | FK → [warehouses](/tables/ecommerce/warehouses.md) | Warehouse shipped from |
| `carrier` | text |  | Carrier name (one of: DHL, FedEx, BlueDart, UPS) |
| `status` | text |  | Shipment status (one of: in_transit, delivered, lost) |
| `shipped_at` | timestamp without time zone |  | Dispatch time |
| `delivered_at` | timestamp without time zone |  | Delivery time, null if not delivered |

# Relationships

- `order_id` references [orders](/tables/ecommerce/orders.md) (`id`).
- `warehouse_id` references [warehouses](/tables/ecommerce/warehouses.md) (`id`).

# Notes

Delivery shipments for sales orders, with carrier and delivery dates.

# Examples

**Q:** How many shipments does each carrier have by status?

```sql
SELECT carrier, status, COUNT(*) AS shipments FROM shipments GROUP BY carrier, status ORDER BY carrier, status
```

**Q:** What is the average delivery time in days per carrier?

```sql
SELECT carrier, AVG(EXTRACT(EPOCH FROM (delivered_at - shipped_at)) / 86400) AS avg_days FROM shipments WHERE delivered_at IS NOT NULL GROUP BY carrier ORDER BY avg_days
```
