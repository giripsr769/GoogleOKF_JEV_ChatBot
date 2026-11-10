-- Replaces every generated placeholder ("departments name 1", "CODE001", "employees1@example.com", ...) with realistic sample text.
-- Runs on a fresh database after 01 and 02 (files in docker-entrypoint-initdb.d run in sorted order), and can be applied
-- to an existing database with an admin login:
--   docker compose exec -T db psql -U postgres -d shop -v ON_ERROR_STOP=1 < db/03_realistic_names.sql
-- Only text is changed (plus one salary range that was upside down); ids, links and numbers are untouched.
BEGIN;

-- ---------------------------------------------------------------- HR
UPDATE departments SET name = v.name, location = v.location
FROM (VALUES (1,'Engineering','Bengaluru'),(2,'Sales','Mumbai'),(3,'Human Resources','Chennai'),
             (4,'Finance','Pune'),(5,'Customer Support','Hyderabad'),(6,'Operations','Delhi')) AS v(id,name,location)
WHERE departments.id = v.id;

UPDATE job_titles SET title = v.title
FROM (VALUES (1,'Department Head'),(2,'Senior Executive'),(3,'Intern'),(4,'Team Lead'),(5,'Analyst'),(6,'Associate')) AS v(id,title)
WHERE job_titles.id = v.id;
-- one range had its minimum above its maximum
UPDATE job_titles SET min_salary = max_salary, max_salary = min_salary WHERE min_salary > max_salary;

UPDATE employees SET full_name = v.full_name, work_email = v.email
FROM (VALUES (1,'Priya Nair','priya.nair@example.com'),(2,'Arjun Mehta','arjun.mehta@example.com'),
             (3,'Sneha Iyer','sneha.iyer@example.com'),(4,'Rahul Verma','rahul.verma@example.com'),
             (5,'Kavya Reddy','kavya.reddy@example.com'),(6,'Daniel Fernandes','daniel.fernandes@example.com')) AS v(id,full_name,email)
WHERE employees.id = v.id;

UPDATE performance_reviews SET review_period = v.period, comments = v.comments
FROM (VALUES (1,'H1 2025','Missed most targets; an improvement plan was agreed.'),
             (2,'H1 2025','Frequent delays; needs closer supervision.'),
             (3,'H2 2025','Some progress, but still below expectations.'),
             (4,'H1 2025','Meets expectations with steady delivery.'),
             (5,'H2 2025','Outstanding results and strong teamwork.'),
             (6,'H2 2025','Slipped on deadlines this period.')) AS v(id,period,comments)
WHERE performance_reviews.id = v.id;

UPDATE training_courses SET title = v.title, provider = v.provider
FROM (VALUES (1,'Effective Customer Communication','LinkedIn Learning'),(2,'Data Analysis with SQL','Coursera'),
             (3,'Project Management Fundamentals','Udemy'),(4,'Workplace Safety Basics','Internal Academy'),
             (5,'Leadership for New Managers','edX'),(6,'Cloud Engineering Bootcamp','NASSCOM FutureSkills')) AS v(id,title,provider)
WHERE training_courses.id = v.id;

-- ---------------------------------------------------------------- Customer support
UPDATE support_teams SET name = v.name
FROM (VALUES (1,'Escalation Desk'),(2,'Technical Specialists'),(3,'General Helpdesk'),
             (4,'Product Experts'),(5,'Order Support'),(6,'Billing Support')) AS v(id,name)
WHERE support_teams.id = v.id;

UPDATE support_agents SET full_name = v.full_name, email = v.email
FROM (VALUES (1,'Meera Pillai','meera.pillai@example.com'),(2,'Vikram Singh','vikram.singh@example.com'),
             (3,'Ananya Das','ananya.das@example.com'),(4,'Rohan Gupta','rohan.gupta@example.com'),
             (5,'Fatima Khan','fatima.khan@example.com'),(6,'Thomas George','thomas.george@example.com')) AS v(id,full_name,email)
WHERE support_agents.id = v.id;

UPDATE ticket_categories SET name = v.name, description = v.description
FROM (VALUES (1,'Order Status','Questions about where an order is and when it will arrive.'),
             (2,'Returns and Refunds','Returning an item or asking for money back.'),
             (3,'Payment Issue','Failed, duplicate or unexpected charges.'),
             (4,'Product Question','Questions about features, compatibility and warranty.'),
             (5,'Account Access','Passwords, locked accounts and sign-in problems.'),
             (6,'Delivery Delay','Late, lost or misdelivered parcels.')) AS v(id,name,description)
WHERE ticket_categories.id = v.id;

UPDATE tickets SET subject = v.subject
FROM (VALUES (1,'My parcel has not arrived yet'),(2,'Does the laptop come with a warranty?'),
             (3,'The delivery address on my parcel was wrong'),(4,'Where is my order? It was due yesterday'),
             (5,'I was charged twice for the same order'),(6,'Is the desk lamp compatible with LED bulbs?')) AS v(id,subject)
WHERE tickets.id = v.id;

UPDATE ticket_comments SET body = v.body
FROM (VALUES (1,'Checked with the carrier: the parcel is still in transit.'),
             (2,'Asked the customer which type of bulb they use.'),
             (3,'Corrected the delivery address and rebooked the courier.'),
             (4,'Customer confirmed it is a standard E27 bulb.'),
             (5,'Confirmed that the lamp supports E27 LED bulbs.'),
             (6,'Sent the customer an update on the carrier status.')) AS v(id,body)
WHERE ticket_comments.id = v.id;

UPDATE customer_feedback SET comment = v.comment
FROM (VALUES (1,'Quick and clear answer, thank you.'),(2,'The refund was processed, but it took a while.'),
             (3,'Helpful, but the reply was slow.'),(4,'The answer was correct but not very detailed.'),
             (5,'I found my order quickly.'),(6,'Resolved after a follow-up.')) AS v(id,comment)
WHERE customer_feedback.id = v.id;

UPDATE escalations SET reason = v.reason
FROM (VALUES (1,'Customer asked for a warranty exception'),(2,'Needs confirmation from the product team'),
             (3,'Carrier has not updated tracking for three days'),(4,'Technical detail beyond first-line support'),
             (5,'Duplicate charge needs finance approval'),(6,'Parcel may be lost in transit')) AS v(id,reason)
WHERE escalations.id = v.id;

UPDATE knowledge_articles SET title = v.title
FROM (VALUES (1,'How to reset your password'),(2,'Why is my account locked?'),(3,'Laptop warranty and support'),
             (4,'How to track your order'),(5,'What to do if your parcel is late'),(6,'Delivery times by country')) AS v(id,title)
WHERE knowledge_articles.id = v.id;

-- ---------------------------------------------------------------- Shop
UPDATE categories SET name = v.name, description = v.description
FROM (VALUES (1,'Electronics','Computers, audio and other gadgets.'),(2,'Laptops','Portable computers.'),
             (3,'Books','Printed and technical books.'),(4,'Audio','Headphones and speakers.'),
             (5,'Accessories','Cables, bags and add-ons.'),(6,'Home','Lighting and household items.')) AS v(id,name,description)
WHERE categories.id = v.id;

UPDATE reviews SET comment = v.comment
FROM (VALUES (1,'Bright and sturdy, great for my desk.'),(2,'Fast laptop and the battery lasts all day.'),
             (3,'The examples are outdated and several were wrong.'),(4,'Good lamp, but the cable could be longer.'),
             (5,'Clear explanations and useful recipes.'),(6,'Great screen and very light.')) AS v(id,comment)
WHERE reviews.id = v.id;

UPDATE coupons SET code = v.code
FROM (VALUES (1,'WELCOME'),(2,'FESTIVE'),(3,'SUMMER'),(4,'LOYALTY'),(5,'THANKYOU'),(6,'NEWYEAR')) AS v(id,code)
WHERE coupons.id = v.id;

UPDATE addresses SET street = v.street, postal_code = v.postal_code
FROM (VALUES (1,'12 Anna Salai','600002'),(2,'2100 Congress Avenue','78701'),(3,'18 Orchard Road','238839'),
             (4,'25 Friedrichstrasse','10117'),(5,'10 Baker Street','NW1 6XE'),(6,'45 Marine Drive','400020')) AS v(id,street,postal_code)
WHERE addresses.id = v.id;

-- ---------------------------------------------------------------- Supply chain
UPDATE suppliers SET name = v.name, contact_email = v.email
FROM (VALUES (1,'Bharat Electronics Supply','orders@bharat-electronics.example.com'),
             (2,'Lone Star Components','sales@lonestar-components.example.com'),
             (3,'Lion City Trading','hello@lioncity-trading.example.com'),
             (4,'Rhein Tech GmbH','vertrieb@rhein-tech.example.com'),
             (5,'Thames Distribution Ltd','orders@thames-distribution.example.com'),
             (6,'Deccan Home Goods','sales@deccan-homegoods.example.com')) AS v(id,name,email)
WHERE suppliers.id = v.id;

UPDATE warehouses SET name = v.name
FROM (VALUES (1,'Chennai Fulfilment Centre'),(2,'Austin Distribution Hub'),(3,'Singapore Regional Warehouse'),
             (4,'Berlin Logistics Centre'),(5,'London Depot'),(6,'Mumbai Central Warehouse')) AS v(id,name)
WHERE warehouses.id = v.id;

-- ---------------------------------------------------------------- Finance
UPDATE accounts SET code = v.code, name = v.name
FROM (VALUES (1,'1000','Cash and Bank'),(2,'2000','Accounts Payable'),(3,'3000','Retained Earnings'),
             (4,'4000','Product Sales'),(5,'5000','Operating Expenses'),(6,'1100','Accounts Receivable')) AS v(id,code,name)
WHERE accounts.id = v.id;

UPDATE bank_transactions SET description = v.description
FROM (VALUES (1,'Owner capital contribution'),(2,'Payment to supplier'),(3,'Customer invoice payment received'),
             (4,'Cash deposit'),(5,'Office rent payment'),(6,'Vendor bill settlement')) AS v(id,description)
WHERE bank_transactions.id = v.id;

UPDATE ledger_entries SET memo = v.memo
FROM (VALUES (1,'Retained earnings adjustment'),(2,'Cash receipt from customer'),(3,'Cash deposit to bank'),
             (4,'Monthly office expenses'),(5,'Year-end equity adjustment'),(6,'Supplier invoice booked')) AS v(id,memo)
WHERE ledger_entries.id = v.id;

UPDATE tax_rates SET tax_name = v.tax_name
FROM (VALUES (1,'GST Standard'),(2,'State Sales Tax'),(3,'GST'),(4,'VAT'),(5,'VAT'),(6,'GST Higher Slab')) AS v(id,tax_name)
WHERE tax_rates.id = v.id;

UPDATE vendors SET name = v.name, category = v.category
FROM (VALUES (1,'Apex Logistics Services','Logistics'),(2,'BrightOffice Supplies','Office Supplies'),
             (3,'CloudNine Hosting','IT Services'),(4,'GreenLeaf Facilities','Facilities'),
             (5,'SecureGuard Security','Security'),(6,'PrimePrint Marketing','Marketing')) AS v(id,name,category)
WHERE vendors.id = v.id;

COMMIT;
