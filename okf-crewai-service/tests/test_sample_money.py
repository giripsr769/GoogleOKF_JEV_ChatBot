"""The money columns of the sample database must agree with each other. Skips without the Docker database.

The checks that read the restricted `salaries` table need the admin login and skip without it.
"""
import psycopg
import pytest
from test_sql_executor import ADMIN_URL, READONLY_URL, needs_admin, needs_db

pytestmark = needs_db


def rows(sql, url=READONLY_URL):
    with psycopg.connect(url) as conn:
        return conn.execute(sql).fetchall()


def none(sql, url=READONLY_URL):
    bad = rows(sql, url)
    assert not bad, bad


def test_order_totals_match_their_lines_and_list_prices():
    none("SELECT o.id FROM orders o JOIN order_items i ON i.order_id = o.id GROUP BY o.id, o.total_amount "
         "HAVING sum(i.quantity * i.unit_price) <> o.total_amount")
    none("SELECT i.id FROM order_items i JOIN products p ON p.id = i.product_id WHERE i.unit_price <> p.price")


def test_payments_are_for_the_order_total():
    none("SELECT p.id FROM payments p JOIN orders o ON o.id = p.order_id WHERE p.amount <> o.total_amount")


def test_invoices_and_refunds_add_up_to_the_order_total():
    none("SELECT o.id FROM orders o JOIN invoices i ON i.order_id = o.id GROUP BY o.id, o.total_amount HAVING sum(i.amount) <> o.total_amount")
    none("SELECT o.id FROM orders o JOIN returns r ON r.order_id = o.id GROUP BY o.id, o.total_amount HAVING sum(r.refund_amount) <> o.total_amount")


def test_invoice_lines_are_quantity_times_list_price():
    none("SELECT ii.id FROM invoice_items ii JOIN products p ON p.id = ii.product_id WHERE ii.line_total <> round(ii.quantity * p.price, 2)")


def test_coupon_discounts_are_the_percentage_of_the_order_total():
    none("SELECT oc.id FROM order_coupons oc JOIN orders o ON o.id = oc.order_id JOIN coupons c ON c.id = oc.coupon_id "
         "WHERE oc.discount_amount <> round(o.total_amount * c.discount_percent / 100, 2)")
    none("SELECT id FROM coupons WHERE discount_percent <= 0 OR discount_percent > 50")
    none("SELECT order_id FROM order_coupons GROUP BY order_id HAVING (SELECT sum(discount_percent) FROM coupons c "
         "JOIN order_coupons x ON x.coupon_id = c.id WHERE x.order_id = order_coupons.order_id) > 100")


def test_supplier_costs_are_below_list_price_and_purchase_orders_add_up():
    none("SELECT ps.id FROM product_suppliers ps JOIN products p ON p.id = ps.product_id WHERE ps.cost_price >= p.price")
    none("SELECT poi.id FROM purchase_order_items poi JOIN products p ON p.id = poi.product_id WHERE poi.unit_cost >= p.price")
    none("SELECT po.id FROM purchase_orders po JOIN purchase_order_items i ON i.purchase_order_id = po.id "
         "GROUP BY po.id, po.total_cost HAVING sum(i.quantity * i.unit_cost) <> po.total_cost")


def test_salary_ranges_and_budgets_are_realistic_and_consistent():
    none("SELECT id FROM job_titles WHERE min_salary > max_salary OR min_salary < 10000")
    none("SELECT b.id FROM budgets b JOIN departments d ON d.id = b.department_id WHERE b.planned_amount > d.budget")
    none("SELECT id FROM budgets WHERE spent_amount / planned_amount NOT BETWEEN 0.5 AND 1.2")
    assert rows("SELECT count(*) FROM budgets WHERE spent_amount > planned_amount")[0][0] >= 1  # the sample keeps an over-budget case
    none("SELECT id FROM expenses WHERE amount <= 0 OR amount > 5000")


def test_ledger_is_double_entry_and_balanced():
    none("SELECT id FROM ledger_entries WHERE debit > 0 AND credit > 0")
    assert rows("SELECT sum(debit) = sum(credit) FROM ledger_entries")[0][0]


@needs_admin
def test_salaries_sit_inside_the_job_title_range_and_rise_over_time():
    none("SELECT s.id FROM salaries s JOIN employees e ON e.id = s.employee_id JOIN job_titles j ON j.id = e.job_title_id "
         "WHERE s.base_salary NOT BETWEEN j.min_salary AND j.max_salary", ADMIN_URL)
    none("SELECT a.id FROM salaries a JOIN salaries b ON b.employee_id = a.employee_id AND b.effective_from > a.effective_from "
         "WHERE b.base_salary <= a.base_salary", ADMIN_URL)
    none("SELECT id FROM salaries WHERE bonus < 0 OR bonus > base_salary * 0.2", ADMIN_URL)
