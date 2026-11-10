-- Grows the sample database to about 100 customers and 124 orders so every kind of question has something to find:
-- ties, empty results, customers with no orders, out-of-stock and low-stock products, overdue invoices, failed payments,
-- refunds, lost parcels, escalated tickets, abandoned carts, busy and quiet months.
-- Runs on a fresh database after 01-04, and can be applied to an existing one with an admin login:
--   docker compose exec -T db psql -U postgres -d shop -v ON_ERROR_STOP=1 < db/05_scale_up.sql
-- Does nothing when the database already has 100 customers. Deterministic: the random numbers are seeded, so a fresh build
-- always gives the same rows (dates are relative to the day the script runs).
-- Every rule checked by tests/test_sample_money.py holds for the new rows: order total = sum of its lines at list price,
-- payment / invoice / refund = order total, coupon discount = percentage of the total, supplier cost below list price.
BEGIN;
SELECT setseed(0.42);

CREATE FUNCTION pg_temp.pick(a text[]) RETURNS text LANGUAGE sql VOLATILE AS
$$ SELECT a[1 + floor(random() * array_length(a, 1))::int] $$;

DO $$
DECLARE
  first_names text[] := ARRAY['Aarav','Aditi','Akash','Amit','Anjali','Arun','Bhavna','Chitra','Deepak','Divya','Farhan','Gauri','Harish','Isha','Jayesh',
                              'Karthik','Lakshmi','Manoj','Neha','Omar','Pooja','Rajesh','Sanjay','Tara','Uma','Varun','Wei','Yash','Zoya','Nikhil'];
  last_names  text[] := ARRAY['Sharma','Patel','Menon','Joshi','Kapoor','Bose','Chopra','Desai','Gill','Hegde','Iyengar','Jain','Khan','Lal','Malhotra',
                              'Naidu','Oberoi','Pillai','Rastogi','Saxena','Thakur','Upadhyay','Varma','Wagh','Yadav','Zaveri','Banerjee','Chatterjee','Krishnan'];
  places text[][] := ARRAY[['Chennai','India'],['Mumbai','India'],['Bengaluru','India'],['Delhi','India'],['Hyderabad','India'],['Pune','India'],
                           ['Kolkata','India'],['Kochi','India'],['Austin','USA'],['Seattle','USA'],['Chicago','USA'],['Singapore','Singapore'],
                           ['London','UK'],['Manchester','UK'],['Berlin','Germany'],['Munich','Germany']];
  streets text[] := ARRAY['MG Road','Park Street','Lake View Road','Gandhi Nagar','Station Road','Residency Road','Main Street','Church Lane','Hill Road','Market Street'];
  i int; k int; n int; r float8; oid int; cid int; pl int; ostatus text; odate timestamp; total numeric; n_items int;
  pay_status text; inv_status text; ship_status text; shipped timestamp; delivered timestamp; tid int; agent int; tstatus text; tcreated timestamp;
  tname text; prio text; cat int; cpn int; pct numeric; rid int; pid int;
BEGIN
  IF (SELECT count(*) FROM customers) >= 100 THEN RETURN; END IF;

  -- sequences are not rolled back with a failed run, so line them up with the rows that exist (ids below rely on 5.. / 1..100)
  FOREACH tname IN ARRAY ARRAY['customers','addresses','categories','products','product_suppliers','inventory','orders','order_items','payments',
                               'invoices','invoice_items','shipments','returns','reviews','order_coupons','carts','cart_items','wishlists',
                               'tickets','ticket_comments','escalations','customer_feedback','chat_sessions'] LOOP
    EXECUTE format('SELECT setval(pg_get_serial_sequence(%L, ''id''), coalesce(max(id), 1), max(id) IS NOT NULL) FROM %I', tname, tname);
  END LOOP;

  -- ------------------------------------------------------------ customers (96 new, 100 in all) and their addresses
  FOR i IN 5..100 LOOP
    pl := 1 + (i * 5) % 16;
    INSERT INTO customers (full_name, email, country, city, created_at)
    VALUES (first_names[1 + (i * 7) % 30] || ' ' || last_names[1 + (i * 11) % 29],
            lower(first_names[1 + (i * 7) % 30] || '.' || last_names[1 + (i * 11) % 29]) || '@example.com',
            places[pl][2], places[pl][1], now() - random() * interval '700 days')
    RETURNING id INTO cid;
    INSERT INTO addresses (customer_id, type, street, city, postal_code, country)
    VALUES (cid, 'shipping', (1 + floor(random() * 220))::int || ' ' || pg_temp.pick(streets), places[pl][1], lpad((100000 + floor(random() * 899999))::int::text, 6, '0'), places[pl][2]);
    IF random() < 0.4 THEN
      INSERT INTO addresses (customer_id, type, street, city, postal_code, country)
      VALUES (cid, 'billing', (1 + floor(random() * 220))::int || ' ' || pg_temp.pick(streets), places[pl][1], lpad((100000 + floor(random() * 899999))::int::text, 6, '0'), places[pl][2]);
    END IF;
  END LOOP;

  -- ------------------------------------------------------------ products (16 new, 20 in all), categories, suppliers, stock
  INSERT INTO categories (name, parent_id, description) VALUES
    ('Fitness', NULL, 'Exercise gear and accessories.'), ('Clothing', NULL, 'Everyday clothing and footwear.'),
    ('Stationery', NULL, 'Notebooks, pens and office supplies.');
  INSERT INTO products (name, category, price, stock) VALUES
    ('Wireless Mouse','Electronics',24.99,0),('Mechanical Keyboard','Electronics',89.00,0),('USB-C Hub','Electronics',39.50,0),
    ('Bluetooth Speaker','Electronics',49.99,0),('Python Crash Course','Books',29.99,0),('Clean Code','Books',37.00,0),
    ('World Atlas','Books',45.00,0),('Ceramic Mug Set','Home',18.75,0),('Air Purifier','Home',129.00,0),
    ('Yoga Mat','Fitness',21.00,0),('Dumbbell Set','Fitness',64.50,0),('Running Shoes','Clothing',72.00,0),
    ('Cotton T-Shirt','Clothing',15.99,0),('Notebook Pack','Stationery',9.50,0),('Gel Pen Set','Stationery',6.25,0),
    ('Standing Desk','Home',349.00,0);
  FOR pid IN 5..20 LOOP
    INSERT INTO product_suppliers (product_id, supplier_id, cost_price, lead_time_days)
    SELECT pid, 1 + (pid % 6), round((price * (0.55 + random() * 0.15))::numeric, 2), 3 + floor(random() * 25)::int FROM products WHERE id = pid;
    IF pid IN (13, 20) THEN
      -- Air Purifier and Standing Desk: out of stock everywhere, so "out of stock" questions have an answer
      INSERT INTO inventory (product_id, warehouse_id, quantity_on_hand, reorder_level) VALUES (pid, 1 + (pid % 6), 0, 10), (pid, 1 + ((pid + 2) % 6), 0, 10);
    ELSE
      INSERT INTO inventory (product_id, warehouse_id, quantity_on_hand, reorder_level)
      VALUES (pid, 1 + (pid % 6), CASE WHEN pid IN (6, 9, 17) THEN 3 + floor(random() * 5)::int ELSE 20 + floor(random() * 120)::int END, 15),
             (pid, 1 + ((pid + 3) % 6), 25 + floor(random() * 100)::int, 15);
    END IF;
    UPDATE products SET stock = (SELECT coalesce(sum(quantity_on_hand), 0) FROM inventory WHERE product_id = pid) WHERE id = pid;
  END LOOP;

  -- ------------------------------------------------------------ orders (120 new, 124 in all) with everything that hangs off an order
  FOR i IN 1..120 LOOP
    cid := 1 + floor(100 * power(random(), 1.6))::int;            -- skewed: some customers order often, some never
    r := random();
    ostatus := CASE WHEN r < 0.55 THEN 'delivered' WHEN r < 0.70 THEN 'shipped' WHEN r < 0.82 THEN 'pending' ELSE 'cancelled' END;
    odate := CASE ostatus
               WHEN 'delivered' THEN now() - (10 + random() * 520) * interval '1 day'
               WHEN 'shipped'   THEN now() - (1 + random() * 29) * interval '1 day'
               WHEN 'pending'   THEN now() - random() * 10 * interval '1 day'
               ELSE now() - random() * 400 * interval '1 day' END;
    INSERT INTO orders (customer_id, status, total_amount, ordered_at) VALUES (cid, ostatus, 0, odate) RETURNING id INTO oid;

    n_items := 1 + floor(random() * 4)::int;
    INSERT INTO order_items (order_id, product_id, quantity, unit_price)
    SELECT oid, p.id, 1 + floor(random() * 3)::int, p.price FROM (SELECT id, price FROM products ORDER BY random() LIMIT n_items) p;
    SELECT sum(quantity * unit_price) INTO total FROM order_items WHERE order_id = oid;
    UPDATE orders SET total_amount = total WHERE id = oid;

    -- payment: paid for shipped / delivered orders; cancelled orders were refunded or failed; most pending orders have none yet
    pay_status := CASE WHEN ostatus IN ('delivered', 'shipped') THEN 'completed'
                       WHEN ostatus = 'cancelled' THEN CASE WHEN random() < 0.5 THEN 'refunded' ELSE 'failed' END
                       WHEN random() < 0.3 THEN 'failed' ELSE NULL END;
    IF pay_status IS NOT NULL THEN
      INSERT INTO payments (order_id, method, amount, status, paid_at)
      VALUES (oid, pg_temp.pick(ARRAY['card','card','upi','upi','netbanking','cash']), total, pay_status, odate + interval '1 hour');
    END IF;

    -- invoice (one per order, equal to the total) with a line per order line
    IF ostatus <> 'cancelled' THEN
      inv_status := CASE WHEN ostatus = 'pending' THEN 'draft'
                         WHEN ostatus = 'shipped' THEN 'sent'
                         WHEN odate < now() - interval '45 days' AND random() < 0.15 THEN 'overdue' ELSE 'paid' END;
      INSERT INTO invoices (customer_id, order_id, amount, status, issued_on, due_on)
      VALUES (cid, oid, total, inv_status, odate::date, odate::date + 30);
      INSERT INTO invoice_items (invoice_id, product_id, quantity, line_total)
      SELECT currval(pg_get_serial_sequence('invoices', 'id')), oi.product_id, oi.quantity, round(oi.quantity * oi.unit_price, 2)
      FROM order_items oi WHERE oi.order_id = oid;
    END IF;

    -- shipment for orders that left the warehouse
    IF ostatus IN ('shipped', 'delivered') THEN
      shipped := odate + interval '1 day';
      IF ostatus = 'delivered' THEN
        ship_status := 'delivered'; delivered := shipped + (2 + random() * 7) * interval '1 day';
      ELSE
        ship_status := CASE WHEN odate < now() - interval '20 days' AND random() < 0.3 THEN 'lost' ELSE 'in_transit' END; delivered := NULL;
      END IF;
      INSERT INTO shipments (order_id, warehouse_id, carrier, status, shipped_at, delivered_at)
      VALUES (oid, 1 + floor(random() * 6)::int, pg_temp.pick(ARRAY['FedEx','DHL','UPS','BlueDart','BlueDart']), ship_status, shipped, delivered);

      -- some delivered orders come back; the refund is the whole order total
      IF ostatus = 'delivered' AND random() < 0.12 THEN
        INSERT INTO returns (order_id, reason, status, refund_amount, requested_at)
        VALUES (oid, pg_temp.pick(ARRAY['damaged','wrong_item','not_needed','late']),
                pg_temp.pick(ARRAY['requested','approved','refunded','refunded','rejected']), total, least(now(), delivered + interval '1 day'));
      END IF;

      -- a review of one product from the order
      IF ostatus = 'delivered' AND random() < 0.55 THEN
        r := random();
        k := CASE WHEN r < 0.45 THEN 5 WHEN r < 0.75 THEN 4 WHEN r < 0.88 THEN 3 WHEN r < 0.95 THEN 2 ELSE 1 END;
        INSERT INTO reviews (product_id, customer_id, rating, comment, created_at)
        SELECT oi.product_id, cid, k,
               CASE k WHEN 5 THEN pg_temp.pick(ARRAY['Excellent quality, exactly as described.','Love it, would buy again.','Arrived early and works perfectly.'])
                      WHEN 4 THEN pg_temp.pick(ARRAY['Good value for the price.','Works well, packaging could be better.','Solid product, happy with it.'])
                      WHEN 3 THEN pg_temp.pick(ARRAY['It is okay, nothing special.','Does the job but feels average.','Decent, though delivery was slow.'])
                      WHEN 2 THEN pg_temp.pick(ARRAY['Not as good as the photos.','Stopped working after a few weeks.','Disappointing build quality.'])
                      ELSE pg_temp.pick(ARRAY['Arrived broken and support was slow.','Completely different from the listing.','Would not recommend.']) END,
               least(now(), delivered + interval '3 days')
        FROM order_items oi WHERE oi.order_id = oid ORDER BY random() LIMIT 1;
      END IF;
    END IF;

    -- a coupon on one order in five (one coupon at most; the discount is the coupon percentage of the total)
    IF random() < 0.2 THEN
      cpn := 1 + floor(random() * 6)::int;
      SELECT discount_percent INTO pct FROM coupons WHERE id = cpn;
      INSERT INTO order_coupons (order_id, coupon_id, discount_amount) VALUES (oid, cpn, round(total * pct / 100, 2));
    END IF;
  END LOOP;

  -- ------------------------------------------------------------ carts and wishlists
  FOR i IN 1..35 LOOP
    r := random();
    INSERT INTO carts (customer_id, status, created_at)
    VALUES (1 + floor(random() * 100)::int, CASE WHEN r < 0.35 THEN 'open' WHEN r < 0.7 THEN 'abandoned' ELSE 'converted' END, now() - random() * 120 * interval '1 day')
    RETURNING id INTO k;
    INSERT INTO cart_items (cart_id, product_id, quantity)
    SELECT k, p.id, 1 + floor(random() * 3)::int FROM (SELECT id FROM products ORDER BY random() LIMIT 1 + floor(random() * 3)::int) p;
  END LOOP;
  INSERT INTO wishlists (customer_id, product_id, added_at)
  SELECT c, p, now() - random() * 200 * interval '1 day'
  FROM (SELECT DISTINCT 1 + floor(random() * 100)::int AS c, 1 + floor(random() * 20)::int AS p FROM generate_series(1, 60)) w;

  -- ------------------------------------------------------------ support: tickets, comments, escalations, feedback, chats
  FOR i IN 1..50 LOOP
    cat := 1 + floor(random() * 6)::int;
    agent := 1 + floor(6 * power(random(), 1.5))::int;            -- skewed: some agents are busier
    r := random();
    tstatus := CASE WHEN r < 0.25 THEN 'open' WHEN r < 0.45 THEN 'pending' WHEN r < 0.75 THEN 'resolved' ELSE 'closed' END;
    prio := CASE WHEN random() < 0.1 THEN 'urgent' WHEN random() < 0.3 THEN 'high' WHEN random() < 0.6 THEN 'medium' ELSE 'low' END;
    tcreated := now() - random() * 200 * interval '1 day';
    IF i <= 8 THEN tcreated := now() - random() * 28 * interval '1 day'; END IF;     -- a few recent ones for "last month" questions
    IF random() < 0.7 THEN
      SELECT id, customer_id INTO oid, cid FROM orders ORDER BY random() LIMIT 1;
    ELSE
      oid := NULL; cid := 1 + floor(random() * 100)::int;
    END IF;
    INSERT INTO tickets (customer_id, order_id, category_id, agent_id, priority, status, subject, created_at, resolved_at)
    VALUES (cid, oid, cat, agent, prio, tstatus,
            CASE cat WHEN 1 THEN pg_temp.pick(ARRAY['Where is my order?','Order status has not changed','Can I change my delivery date?'])
                     WHEN 2 THEN pg_temp.pick(ARRAY['I want to return an item','Refund not received yet','Wrong item in the package'])
                     WHEN 3 THEN pg_temp.pick(ARRAY['I was charged twice','Payment failed but money was deducted','Unexpected charge on my card'])
                     WHEN 4 THEN pg_temp.pick(ARRAY['Is this compatible with my device?','What does the warranty cover?','Missing item from the box'])
                     WHEN 5 THEN pg_temp.pick(ARRAY['I cannot sign in','My account is locked','Reset link never arrives'])
                     ELSE pg_temp.pick(ARRAY['Parcel is late','Tracking has not updated','Delivered to the wrong address']) END,
            tcreated, CASE WHEN tstatus IN ('resolved', 'closed') THEN least(now(), tcreated + (2 + random() * 120) * interval '1 hour') END)
    RETURNING id INTO tid;
    INSERT INTO ticket_comments (ticket_id, author_agent_id, body, created_at)
    SELECT tid, agent, pg_temp.pick(ARRAY['Looking into this now.','Checked with the carrier and the warehouse.','Asked the customer for more details.',
                                          'Shared the steps to fix this.','Refund request has been raised.','Confirmed the fix with the customer.']),
           least(now(), tcreated + g * interval '6 hours') FROM generate_series(1, 1 + floor(random() * 3)::int) g;
    IF random() < 0.3 THEN
      INSERT INTO escalations (ticket_id, from_team_id, to_team_id, reason, escalated_at)
      SELECT tid, a.team_id, CASE WHEN a.team_id = 1 THEN 2 ELSE pg_temp.pick(ARRAY['1','2'])::int END,
             pg_temp.pick(ARRAY['Duplicate charge needs finance approval','Customer asked for a warranty exception','Carrier has not updated tracking for three days',
                                'Needs confirmation from the product team','Technical detail beyond first-line support','Parcel may be lost in transit']),
             least(now(), tcreated + interval '4 hours')
      FROM support_agents a WHERE a.id = agent;
    END IF;
    IF tstatus IN ('resolved', 'closed') AND random() < 0.6 THEN
      k := CASE WHEN random() < 0.5 THEN 5 WHEN random() < 0.7 THEN 4 WHEN random() < 0.6 THEN 3 WHEN random() < 0.5 THEN 2 ELSE 1 END;
      INSERT INTO customer_feedback (ticket_id, customer_id, score, comment, submitted_at)
      VALUES (tid, cid, k,
              CASE WHEN k >= 4 THEN pg_temp.pick(ARRAY['Quick and clear answer, thank you.','Very helpful agent.','Problem fixed on the first reply.'])
                   WHEN k = 3 THEN pg_temp.pick(ARRAY['It got sorted, but it took a while.','Average experience.'])
                   ELSE pg_temp.pick(ARRAY['I had to explain the problem three times.','Slow replies and no clear answer.']) END,
              least(now(), tcreated + interval '3 days'));
    END IF;
  END LOOP;
  INSERT INTO chat_sessions (customer_id, agent_id, started_at, duration_minutes, resolved)
  SELECT 1 + floor(random() * 100)::int, 1 + floor(6 * power(random(), 1.5))::int, now() - random() * 150 * interval '1 day',
         3 + floor(random() * 57)::int, random() < 0.75
  FROM generate_series(1, 30);
END
$$;

-- every sample customer, order and ticket now has data to join to
COMMIT;
