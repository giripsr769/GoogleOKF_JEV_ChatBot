"""Spec for the 46 extra test tables (4 existing + 46 = 50). Consumed by gen_schema.py.

Column syntax: "name|type|description"
  type: pk | fk:<table> | int | text | text:a/b/c (enum) | num | ts | date | bool
Table tuple: (description, tags, [columns], notes)
"""

# row counts of tables already created by 01_init.sql (FK targets)
EXISTING = {"customers": 4, "products": 4, "orders": 4, "order_items": 5}

# tables created but NOT granted to okf_readonly (tests database-level denial)
RESTRICTED = {"salaries"}

SPEC = {
    # ---------------- E-COMMERCE (17) ----------------
    "categories": ("Product categories, optionally nested under a parent category.",
        "category taxonomy department group catalog", [
        "id|pk|Unique category id", "name|text|Category name", "parent_id|fk:categories|Parent category, null for top level",
        "description|text|Short description"], "Products.category is free text; this table is the managed taxonomy."),
    "suppliers": ("Companies that supply products to the store.",
        "supplier vendor manufacturer sourcing", [
        "id|pk|Unique supplier id", "name|text|Supplier company name", "country|text|Supplier country",
        "contact_email|text|Supplier contact email", "rating|num|Supplier quality rating 1-5"], ""),
    "product_suppliers": ("Which suppliers provide which products, with cost price and lead time.",
        "supplier product cost sourcing lead time", [
        "id|pk|Unique id", "product_id|fk:products|Product supplied", "supplier_id|fk:suppliers|Supplier",
        "cost_price|num|Cost per unit paid to supplier in USD", "lead_time_days|int|Days from order to delivery"], ""),
    "warehouses": ("Physical warehouses that store inventory.",
        "warehouse storage location fulfilment depot", [
        "id|pk|Unique warehouse id", "name|text|Warehouse name", "city|text|City", "country|text|Country",
        "capacity_units|int|Maximum units the warehouse can hold"], ""),
    "inventory": ("Current stock level of each product in each warehouse.",
        "inventory stock quantity on hand reorder warehouse", [
        "id|pk|Unique id", "product_id|fk:products|Product", "warehouse_id|fk:warehouses|Warehouse holding the stock",
        "quantity_on_hand|int|Units currently in stock", "reorder_level|int|Reorder when stock falls below this"],
        "Total stock of a product = SUM(quantity_on_hand) across warehouses."),
    "payments": ("Customer payments received against sales orders.",
        "payment paid transaction card upi refund customer order", [
        "id|pk|Unique payment id", "order_id|fk:orders|Sales order being paid", "method|text:card/upi/cash/netbanking|Payment method",
        "amount|num|Amount paid in USD", "status|text:completed/failed/refunded|Payment status", "paid_at|ts|When payment was made"],
        "Customer money IN. Not the same as vendor_bills (money OUT) or invoices (billing documents)."),
    "shipments": ("Delivery shipments for sales orders, with carrier and delivery dates.",
        "shipment delivery carrier tracking shipped dispatch courier", [
        "id|pk|Unique shipment id", "order_id|fk:orders|Sales order shipped", "warehouse_id|fk:warehouses|Warehouse shipped from",
        "carrier|text:DHL/FedEx/BlueDart/UPS|Carrier name", "status|text:in_transit/delivered/lost|Shipment status",
        "shipped_at|ts|Dispatch time", "delivered_at|ts|Delivery time, null if not delivered"], ""),
    "returns": ("Customer return requests for sales orders and the reason given.",
        "return refund rma reverse exchange complaint order", [
        "id|pk|Unique return id", "order_id|fk:orders|Sales order being returned", "reason|text:damaged/wrong_item/not_needed/late|Reason for return",
        "status|text:requested/approved/rejected/refunded|Return status", "refund_amount|num|Amount refunded in USD", "requested_at|ts|When requested"], ""),
    "reviews": ("Customer ratings and written reviews of products.",
        "review rating stars feedback comment product customer", [
        "id|pk|Unique review id", "product_id|fk:products|Product reviewed", "customer_id|fk:customers|Customer who wrote it",
        "rating|int|Star rating 1 to 5", "comment|text|Review text", "created_at|ts|When posted"], ""),
    "coupons": ("Discount coupon codes and their rules.",
        "coupon discount promo code voucher offer", [
        "id|pk|Unique coupon id", "code|text|Coupon code", "discount_percent|num|Percentage off", "valid_from|date|Start date",
        "valid_until|date|Expiry date", "max_uses|int|Maximum redemptions"], ""),
    "order_coupons": ("Coupons applied to sales orders.",
        "coupon discount applied order redemption", [
        "id|pk|Unique id", "order_id|fk:orders|Order the coupon was used on", "coupon_id|fk:coupons|Coupon applied",
        "discount_amount|num|Discount given in USD"], ""),
    "addresses": ("Shipping and billing addresses saved by customers.",
        "address shipping billing street postcode location customer", [
        "id|pk|Unique address id", "customer_id|fk:customers|Owner of the address", "type|text:shipping/billing|Address type",
        "street|text|Street line", "city|text|City", "postal_code|text|Postal code", "country|text|Country"], ""),
    "carts": ("Shopping carts, open or abandoned, belonging to customers.",
        "cart basket shopping abandoned checkout customer", [
        "id|pk|Unique cart id", "customer_id|fk:customers|Cart owner", "status|text:open/abandoned/converted|Cart state", "created_at|ts|When created"], ""),
    "cart_items": ("Products and quantities inside shopping carts.",
        "cart item basket product quantity", [
        "id|pk|Unique id", "cart_id|fk:carts|Cart containing the item", "product_id|fk:products|Product in cart", "quantity|int|Units in cart"], ""),
    "wishlists": ("Products customers saved to wishlists for later.",
        "wishlist saved favourite later product customer", [
        "id|pk|Unique id", "customer_id|fk:customers|Customer", "product_id|fk:products|Product saved", "added_at|ts|When added"], ""),
    "purchase_orders": ("Orders the company places WITH suppliers to buy stock (procurement). Not customer sales orders.",
        "purchase order procurement buying restock supplier po inbound", [
        "id|pk|Unique purchase order id", "supplier_id|fk:suppliers|Supplier ordered from", "warehouse_id|fk:warehouses|Delivery warehouse",
        "status|text:draft/sent/received/cancelled|PO status", "total_cost|num|PO total cost in USD", "ordered_at|ts|When placed"],
        "Look-alike of orders: orders are customer SALES, purchase_orders are company BUYING from suppliers."),
    "purchase_order_items": ("Line items of purchase orders sent to suppliers.",
        "purchase order item procurement line product quantity cost", [
        "id|pk|Unique id", "purchase_order_id|fk:purchase_orders|Parent purchase order", "product_id|fk:products|Product bought",
        "quantity|int|Units ordered", "unit_cost|num|Cost per unit in USD"], ""),

    # ---------------- HR (9) ----------------
    "departments": ("Company departments such as Sales, Engineering and HR.",
        "department team division org unit cost center", [
        "id|pk|Unique department id", "name|text|Department name", "location|text|Office location", "budget|num|Annual department budget in USD"], ""),
    "job_titles": ("Job titles and their pay grade bands.",
        "job title role position grade level designation", [
        "id|pk|Unique id", "title|text|Job title", "grade|int|Pay grade level", "min_salary|num|Band minimum", "max_salary|num|Band maximum"], ""),
    "employees": ("Company staff members. Internal people, not store customers.",
        "employee staff worker personnel hire manager headcount internal", [
        "id|pk|Unique employee id", "full_name|text|Employee name", "work_email|text|Company email", "department_id|fk:departments|Department",
        "job_title_id|fk:job_titles|Job title", "manager_id|fk:employees|Manager, null for top", "hired_on|date|Hire date",
        "status|text:active/on_leave/terminated|Employment status"], "Look-alike of customers: employees are internal staff."),
    "salaries": ("Employee salary records. SENSITIVE.",
        "salary pay compensation wage bonus payroll sensitive", [
        "id|pk|Unique id", "employee_id|fk:employees|Employee paid", "base_salary|num|Annual base salary in USD",
        "bonus|num|Annual bonus in USD", "effective_from|date|Date this salary applies from"], "Restricted: not readable by the API role."),
    "leave_requests": ("Employee leave and time-off requests.",
        "leave vacation holiday sick time off absence request", [
        "id|pk|Unique id", "employee_id|fk:employees|Requesting employee", "leave_type|text:annual/sick/unpaid/parental|Type of leave",
        "start_date|date|First day", "end_date|date|Last day", "status|text:pending/approved/rejected|Decision status"], ""),
    "attendance": ("Daily attendance records for employees.",
        "attendance present absent checkin checkout hours clock", [
        "id|pk|Unique id", "employee_id|fk:employees|Employee", "work_date|date|Date", "hours_worked|num|Hours worked that day",
        "status|text:present/absent/remote|Attendance status"], ""),
    "performance_reviews": ("Periodic performance reviews and ratings of employees.",
        "performance review appraisal rating evaluation score staff", [
        "id|pk|Unique id", "employee_id|fk:employees|Employee reviewed", "reviewer_id|fk:employees|Employee who reviewed",
        "rating|int|Performance rating 1 to 5", "review_period|text|Review period such as 2025-H1", "comments|text|Reviewer comments"], ""),
    "training_courses": ("Internal training courses employees can take.",
        "training course learning skill certification workshop", [
        "id|pk|Unique course id", "title|text|Course title", "duration_hours|int|Course length in hours", "provider|text|Training provider"], ""),
    "training_enrollments": ("Which employees enrolled in which training courses and their completion.",
        "training enrollment course completion employee learning", [
        "id|pk|Unique id", "employee_id|fk:employees|Employee", "course_id|fk:training_courses|Course",
        "status|text:enrolled/completed/dropped|Progress status", "completed_on|date|Completion date, null if not done"], ""),

    # ---------------- FINANCE (10) ----------------
    "accounts": ("Chart of accounts used by the general ledger.",
        "account ledger chart gl asset liability revenue expense accounting", [
        "id|pk|Unique account id", "code|text|Account code", "name|text|Account name",
        "type|text:asset/liability/equity/revenue/expense|Account type"], ""),
    "ledger_entries": ("General ledger postings: debits and credits against accounts.",
        "ledger journal entry debit credit posting gl accounting", [
        "id|pk|Unique entry id", "account_id|fk:accounts|Account posted to", "debit|num|Debit amount in USD",
        "credit|num|Credit amount in USD", "posted_at|ts|Posting time", "memo|text|Description"], ""),
    "invoices": ("Invoices billed to customers for sales orders (billing documents with due dates).",
        "invoice billing receivable due overdue customer bill outstanding", [
        "id|pk|Unique invoice id", "customer_id|fk:customers|Customer billed", "order_id|fk:orders|Related sales order",
        "amount|num|Invoice amount in USD", "status|text:draft/sent/paid/overdue|Invoice status", "issued_on|date|Issue date", "due_on|date|Due date"],
        "Look-alike of payments: an invoice is the bill; a payment is money received."),
    "invoice_items": ("Line items on customer invoices.",
        "invoice line item billing product amount", [
        "id|pk|Unique id", "invoice_id|fk:invoices|Parent invoice", "product_id|fk:products|Product billed",
        "quantity|int|Units billed", "line_total|num|Line total in USD"], ""),
    "budgets": ("Planned spend per department per fiscal year.",
        "budget plan forecast fiscal year allocation department spend", [
        "id|pk|Unique id", "department_id|fk:departments|Department", "fiscal_year|int|Fiscal year",
        "planned_amount|num|Budgeted amount in USD", "spent_amount|num|Actual spent so far in USD"], ""),
    "expenses": ("Employee expense claims such as travel and meals.",
        "expense claim reimbursement travel meals spend employee", [
        "id|pk|Unique id", "employee_id|fk:employees|Employee claiming", "category|text:travel/meals/software/equipment|Expense category",
        "amount|num|Amount in USD", "status|text:submitted/approved/reimbursed/rejected|Claim status", "incurred_on|date|Date spent"], ""),
    "tax_rates": ("Sales tax rates by country.",
        "tax vat gst rate country duty", [
        "id|pk|Unique id", "country|text|Country", "tax_name|text|Tax name such as VAT or GST", "rate_percent|num|Tax rate percent"], ""),
    "vendors": ("External companies the business pays for services and goods (accounts payable).",
        "vendor payable service provider creditor external company", [
        "id|pk|Unique vendor id", "name|text|Vendor name", "category|text|Service category", "payment_terms_days|int|Days allowed to pay"], ""),
    "vendor_bills": ("Bills received from vendors that the company must pay (money OUT).",
        "vendor bill payable owed pay supplier cost outgoing", [
        "id|pk|Unique id", "vendor_id|fk:vendors|Vendor who billed", "amount|num|Bill amount in USD",
        "status|text:open/paid/overdue|Bill status", "due_on|date|Due date"], "Money OUT. Customer payments are in payments."),
    "bank_transactions": ("Bank statement lines: deposits and withdrawals.",
        "bank transaction deposit withdrawal statement cash reconciliation", [
        "id|pk|Unique id", "account_id|fk:accounts|Related ledger account", "amount|num|Positive deposit, negative withdrawal, USD",
        "description|text|Bank narration", "txn_at|ts|Transaction time"], ""),

    # ---------------- SUPPORT (10) ----------------
    "support_teams": ("Support teams that agents belong to.",
        "support team group queue tier helpdesk", [
        "id|pk|Unique team id", "name|text|Team name", "tier|int|Support tier 1-3"], ""),
    "support_agents": ("Customer support agents.",
        "agent support helpdesk representative csr staff", [
        "id|pk|Unique agent id", "full_name|text|Agent name", "team_id|fk:support_teams|Team", "email|text|Agent email",
        "active|bool|Whether the agent is active"], ""),
    "ticket_categories": ("Categories used to classify support tickets.",
        "ticket category type issue classification", [
        "id|pk|Unique id", "name|text|Category name such as Billing or Shipping", "description|text|What it covers"], ""),
    "sla_policies": ("Service level targets for response and resolution by priority.",
        "sla policy response resolution target priority hours deadline", [
        "id|pk|Unique id", "priority|text:low/medium/high/urgent|Ticket priority", "first_response_hours|int|Target hours to first reply",
        "resolution_hours|int|Target hours to resolve"], ""),
    "tickets": ("Customer support tickets raised about problems or questions.",
        "ticket support issue case complaint helpdesk open resolved customer", [
        "id|pk|Unique ticket id", "customer_id|fk:customers|Customer who raised it", "order_id|fk:orders|Related order if any",
        "category_id|fk:ticket_categories|Ticket category", "agent_id|fk:support_agents|Assigned agent",
        "priority|text:low/medium/high/urgent|Priority", "status|text:open/pending/resolved/closed|Status",
        "subject|text|Ticket subject", "created_at|ts|When opened", "resolved_at|ts|When resolved, null if open"], ""),
    "ticket_comments": ("Conversation messages on support tickets.",
        "ticket comment reply message conversation note", [
        "id|pk|Unique id", "ticket_id|fk:tickets|Ticket", "author_agent_id|fk:support_agents|Agent author, null if customer",
        "body|text|Message text", "created_at|ts|When posted"], ""),
    "escalations": ("Tickets escalated to a higher tier or manager.",
        "escalation escalated tier manager urgent breach", [
        "id|pk|Unique id", "ticket_id|fk:tickets|Escalated ticket", "from_team_id|fk:support_teams|Team escalating",
        "to_team_id|fk:support_teams|Team receiving", "reason|text|Why escalated", "escalated_at|ts|When escalated"], ""),
    "knowledge_articles": ("Help-centre articles agents and customers can read.",
        "knowledge base article help faq documentation guide", [
        "id|pk|Unique id", "title|text|Article title", "category_id|fk:ticket_categories|Related category",
        "views|int|Number of views", "published_on|date|Publish date"], ""),
    "chat_sessions": ("Live chat sessions between customers and agents.",
        "chat live session conversation messaging agent customer", [
        "id|pk|Unique id", "customer_id|fk:customers|Customer", "agent_id|fk:support_agents|Agent",
        "started_at|ts|Start time", "duration_minutes|int|Length in minutes", "resolved|bool|Whether resolved in chat"], ""),
    "customer_feedback": ("Post-support satisfaction (CSAT) scores from customers.",
        "csat nps satisfaction survey score feedback support rating", [
        "id|pk|Unique id", "ticket_id|fk:tickets|Ticket rated", "customer_id|fk:customers|Customer", "score|int|Satisfaction 1 to 5",
        "comment|text|Free text", "submitted_at|ts|When submitted"], "Support satisfaction. Product ratings are in reviews."),
}
