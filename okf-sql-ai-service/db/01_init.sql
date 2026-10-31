CREATE TABLE customers (id SERIAL PRIMARY KEY, full_name TEXT, email TEXT, country TEXT, city TEXT, created_at TIMESTAMP DEFAULT now());
CREATE TABLE products (id SERIAL PRIMARY KEY, name TEXT, category TEXT, price NUMERIC(10,2), stock INT);
CREATE TABLE orders (id SERIAL PRIMARY KEY, customer_id INT REFERENCES customers(id), status TEXT, total_amount NUMERIC(12,2), ordered_at TIMESTAMP DEFAULT now());
CREATE TABLE order_items (id SERIAL PRIMARY KEY, order_id INT REFERENCES orders(id), product_id INT REFERENCES products(id), quantity INT, unit_price NUMERIC(10,2));

INSERT INTO customers (full_name,email,country,city) VALUES
 ('Asha Rao','asha@example.com','India','Chennai'),('Liam Smith','liam@example.com','USA','Austin'),
 ('Mei Chen','mei@example.com','Singapore','Singapore'),('Ravi Kumar','ravi@example.com','India','Mumbai');
INSERT INTO products (name,category,price,stock) VALUES
 ('Laptop','Electronics',899.00,25),('Headphones','Electronics',59.99,100),('SQL Cookbook','Books',34.50,40),('Desk Lamp','Home',22.00,60);
INSERT INTO orders (customer_id,status,total_amount,ordered_at) VALUES
 (1,'delivered',958.99,now()-interval '20 days'),(2,'shipped',34.50,now()-interval '5 days'),
 (3,'cancelled',59.99,now()-interval '10 days'),(4,'pending',44.00,now()-interval '1 day');
INSERT INTO order_items (order_id,product_id,quantity,unit_price) VALUES
 (1,1,1,899.00),(1,2,1,59.99),(2,3,1,34.50),(3,2,1,59.99),(4,4,2,22.00);

-- Least-privilege role used by the API: SELECT only on the OKF-documented tables.
-- Change the password outside local development.
-- Roles are cluster-wide, so create it only if missing (lets the setup script run on a server that already has it).
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'okf_readonly') THEN
    CREATE ROLE okf_readonly LOGIN PASSWORD 'okf_readonly'
      NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
  END IF;
END
$$;
ALTER ROLE okf_readonly SET default_transaction_read_only = on;
ALTER ROLE okf_readonly SET statement_timeout = '3s';
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT CONNECT ON DATABASE shop TO okf_readonly;
GRANT USAGE ON SCHEMA public TO okf_readonly;
GRANT SELECT ON customers, products, orders, order_items TO okf_readonly;
