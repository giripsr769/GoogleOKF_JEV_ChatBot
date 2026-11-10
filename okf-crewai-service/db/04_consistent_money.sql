-- Makes the money columns of the sample database agree with each other (all amounts are US dollars).
-- Runs on a fresh database after 01-03, and can be applied to an existing one with an admin login:
--   docker compose exec -T db psql -U postgres -d shop -v ON_ERROR_STOP=1 < db/04_consistent_money.sql
-- Safe to run twice: every value is derived from stable inputs. Only money columns change; ids, links, quantities and statuses do not.
--
-- The core shop tables (products, orders, order_items) were already consistent and are the source of truth:
--   orders.total_amount = sum(quantity * unit_price) of its order_items, and unit_price = products.price.
-- Everything money-related that points at an order is derived from that total.
BEGIN;

-- ---------------------------------------------------------------- derived from orders.total_amount
-- a payment attempt is for the order total (a failed or refunded payment keeps the amount it was for)
UPDATE payments p SET amount = o.total_amount FROM orders o WHERE o.id = p.order_id;

-- invoices on one order share its total, so they add up to it exactly (any odd cent goes on the last one)
UPDATE invoices i SET amount = s.share
FROM (
  SELECT x.id, CASE WHEN x.rn = x.n THEN o.total_amount - round(o.total_amount / x.n, 2) * (x.n - 1)
                    ELSE round(o.total_amount / x.n, 2) END AS share
  FROM (SELECT id, order_id, row_number() OVER (PARTITION BY order_id ORDER BY id) AS rn,
               count(*) OVER (PARTITION BY order_id) AS n FROM invoices) x
  JOIN orders o ON o.id = x.order_id
) s WHERE i.id = s.id;

-- returns on one order share its total, so refunds never exceed what was paid
UPDATE returns r SET refund_amount = s.share
FROM (
  SELECT x.id, CASE WHEN x.rn = x.n THEN o.total_amount - round(o.total_amount / x.n, 2) * (x.n - 1)
                    ELSE round(o.total_amount / x.n, 2) END AS share
  FROM (SELECT id, order_id, row_number() OVER (PARTITION BY order_id ORDER BY id) AS rn,
               count(*) OVER (PARTITION BY order_id) AS n FROM returns) x
  JOIN orders o ON o.id = x.order_id
) s WHERE r.id = s.id;

-- invoice lines are quantity x list price
UPDATE invoice_items ii SET line_total = round(ii.quantity * p.price, 2) FROM products p WHERE p.id = ii.product_id;

-- coupons: realistic percentages, and the discount given on an order is that percentage of the order total
UPDATE coupons SET discount_percent = v.pct
FROM (VALUES (1, 10.00), (2, 15.00), (3, 20.00), (4, 5.00), (5, 8.00), (6, 25.00)) AS v(id, pct)
WHERE coupons.id = v.id;
UPDATE order_coupons oc SET discount_amount = round(o.total_amount * c.discount_percent / 100, 2)
FROM orders o, coupons c WHERE o.id = oc.order_id AND c.id = oc.coupon_id;

-- ---------------------------------------------------------------- supply chain: suppliers sell below the shop's list price
UPDATE product_suppliers ps SET cost_price = round(p.price * v.factor, 2)
FROM products p, (VALUES (1, 0.62), (2, 0.58), (3, 0.66), (4, 0.60), (5, 0.64), (6, 0.57)) AS v(id, factor)
WHERE p.id = ps.product_id AND v.id = ps.id;

-- a purchase line costs what that supplier charges for the product, or 60% of list price when no price is on file
UPDATE purchase_order_items poi SET unit_cost = COALESCE(
  (SELECT round(avg(ps.cost_price), 2) FROM product_suppliers ps WHERE ps.product_id = poi.product_id AND ps.supplier_id = po.supplier_id),
  round(p.price * 0.60, 2))
FROM purchase_orders po, products p WHERE po.id = poi.purchase_order_id AND p.id = poi.product_id;
-- purchase orders that have lines are the sum of them (orders without lines keep their stored total)
UPDATE purchase_orders po SET total_cost = s.total
FROM (SELECT purchase_order_id, sum(quantity * unit_cost) AS total FROM purchase_order_items GROUP BY purchase_order_id) s
WHERE s.purchase_order_id = po.id;

-- ---------------------------------------------------------------- HR (annual amounts)
UPDATE job_titles SET min_salary = v.lo, max_salary = v.hi
FROM (VALUES (1, 120000.00, 180000.00),  -- Department Head
             (2,  80000.00, 120000.00),  -- Senior Executive
             (3,  12000.00,  18000.00),  -- Intern
             (4,  65000.00,  95000.00),  -- Team Lead
             (5,  45000.00,  70000.00),  -- Analyst
             (6,  28000.00,  45000.00)) AS v(id, lo, hi)  -- Associate
WHERE job_titles.id = v.id;

-- salaries (restricted table): inside the employee's job-title range and rising with each new effective date; bonus 8-14% of base
UPDATE salaries s SET base_salary = x.base, bonus = round(x.base * (0.05 + 0.03 * x.rn) / 100) * 100
FROM (
  SELECT sa.id, sa.rn, round((jt.min_salary + (jt.max_salary - jt.min_salary) * (0.30 + 0.20 * (sa.rn - 1))) / 100) * 100 AS base
  FROM (SELECT id, employee_id, row_number() OVER (PARTITION BY employee_id ORDER BY effective_from, id) AS rn FROM salaries) sa
  JOIN employees e ON e.id = sa.employee_id
  JOIN job_titles jt ON jt.id = e.job_title_id
) x WHERE s.id = x.id;

UPDATE departments SET budget = v.budget
FROM (VALUES (1, 4800000.00), (2, 2600000.00), (3, 1200000.00), (4, 1500000.00), (5, 2100000.00), (6, 3300000.00)) AS v(id, budget)
WHERE departments.id = v.id;

-- yearly budgets: 95% (this year) or 90% (last year) of the department budget; actual spending close to plan, one year over
UPDATE budgets b SET planned_amount = round(d.budget * CASE b.fiscal_year WHEN 2026 THEN 0.95 ELSE 0.90 END, 2)
FROM departments d WHERE d.id = b.department_id;
UPDATE budgets b SET spent_amount = round(b.planned_amount * v.ratio, 2)
FROM (VALUES (1, 0.82), (2, 0.97), (3, 1.04), (4, 1.03), (5, 0.79), (6, 0.94)) AS v(id, ratio)
WHERE b.id = v.id;

UPDATE expenses SET amount = v.amount
FROM (VALUES (1, 482.60),   -- travel
             (2,  42.75),   -- meals
             (3, 129.00),   -- software
             (4, 349.99),   -- equipment
             (5, 925.50),   -- travel
             (6,  68.20)) AS v(id, amount)  -- meals
WHERE expenses.id = v.id;

-- ---------------------------------------------------------------- finance
UPDATE vendor_bills SET amount = v.amount
FROM (VALUES (1, 3450.00),  -- GreenLeaf Facilities, open
             (2, 3450.00),  -- GreenLeaf Facilities, paid
             (3, 1280.75),  -- BrightOffice Supplies, overdue
             (4, 5200.00),  -- SecureGuard Security, open
             (5, 2150.00),  -- CloudNine Hosting, paid
             (6, 2150.00)) AS v(id, amount)  -- CloudNine Hosting, overdue
WHERE vendor_bills.id = v.id;

UPDATE bank_transactions SET amount = v.amount
FROM (VALUES (1, 50000.00),  -- owner capital contribution
             (2, 12480.00),  -- payment to supplier
             (3,   958.99),  -- customer invoice payment received (order 1)
             (4,  5000.00),  -- cash deposit
             (5,  4200.00),  -- office rent payment
             (6,  3450.00)) AS v(id, amount)  -- vendor bill settlement (vendor bill 2)
WHERE bank_transactions.id = v.id;

-- double-entry ledger: each line is a debit or a credit, and total debits equal total credits
UPDATE ledger_entries SET debit = v.debit, credit = v.credit
FROM (VALUES (1,    0.00, 2500.00),   -- retained earnings adjustment
             (2,  958.99,    0.00),   -- cash receipt from customer
             (3, 5000.00,    0.00),   -- cash deposit to bank
             (4, 4200.00,    0.00),   -- monthly office expenses
             (5, 4821.01,    0.00),   -- year-end equity adjustment
             (6,    0.00, 12480.00)) AS v(id, debit, credit)  -- supplier invoice booked
WHERE ledger_entries.id = v.id;

UPDATE tax_rates SET rate_percent = v.rate
FROM (VALUES (1, 18.00), (2, 7.25), (3, 9.00), (4, 19.00), (5, 20.00), (6, 28.00)) AS v(id, rate)
WHERE tax_rates.id = v.id;

COMMIT;
