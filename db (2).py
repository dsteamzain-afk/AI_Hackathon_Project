import sqlite3
import os
import pandas as pd
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "zain_customer_360_ai_demo.db")


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def query_df(sql, params=()):
    with get_conn() as conn:
        return pd.read_sql_query(sql, conn, params=params)


def customer_exists(customer_id: int) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM customers WHERE customer_id=?", (customer_id,)
        ).fetchone()
    return row is not None


def get_customer_profile(customer_id: int) -> dict:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM customers WHERE customer_id=?", (customer_id,)
        ).fetchone()
        if not row:
            return {}
        return dict(row)


def get_customer_account(customer_id: int) -> dict:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM accounts WHERE customer_id=?", (customer_id,)
        ).fetchone()
        return dict(row) if row else {}


def get_customer_subscriptions(customer_id: int) -> pd.DataFrame:
    return query_df(
        """
        SELECT s.subscription_id, s.msisdn, s.service_type,
               p.plan_name, p.monthly_fee_jod, p.data_allowance_gb,
               p.technology, s.status, s.activation_date, s.contract_end_date
        FROM subscriptions s
        JOIN plans p ON s.plan_id = p.plan_id
        WHERE s.customer_id=?
        ORDER BY s.primary_subscription_flag DESC
        """,
        (customer_id,),
    )


def get_customer_churn(customer_id: int) -> dict:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM customer_churn_scores WHERE customer_id=?", (customer_id,)
        ).fetchone()
        return dict(row) if row else {}


def get_customer_value(customer_id: int) -> dict:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM customer_value_segments WHERE customer_id=?", (customer_id,)
        ).fetchone()
        return dict(row) if row else {}


def get_customer_complaints(customer_id: int, limit=5) -> pd.DataFrame:
    return query_df(
        """
        SELECT complaint_date, complaint_category, complaint_description,
               severity, status, compensation_amount_jod
        FROM complaints WHERE customer_id=? ORDER BY complaint_date DESC LIMIT ?
        """,
        (customer_id, limit),
    )


def get_customer_support(customer_id: int, limit=5) -> pd.DataFrame:
    return query_df(
        """
        SELECT interaction_datetime, channel, reason_category,
               issue_type, priority, resolution_status, customer_sentiment
        FROM support_interactions WHERE customer_id=? ORDER BY interaction_datetime DESC LIMIT ?
        """,
        (customer_id, limit),
    )


def get_customer_invoices(customer_id: int, limit=4) -> pd.DataFrame:
    return query_df(
        """
        SELECT i.invoice_id, i.billing_period_start, i.billing_period_end,
               i.total_amount_jod, i.payment_status, i.days_overdue
        FROM invoices i
        JOIN accounts a ON i.account_id = a.account_id
        WHERE a.customer_id=? ORDER BY i.issue_date DESC LIMIT ?
        """,
        (customer_id, limit),
    )


def get_customer_usage_summary(customer_id: int) -> dict:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT SUM(total_revenue_jod) as total_rev,
                   AVG(data_used_gb) as avg_data_gb,
                   SUM(voice_minutes) as total_minutes,
                   SUM(complaints_count) as total_complaints,
                   SUM(support_interactions_count) as total_interactions,
                   MAX(summary_month) as latest_month
            FROM customer_monthly_summary WHERE customer_id=?
            """,
            (customer_id,),
        ).fetchone()
        return dict(row) if row else {}


def get_churn_rescue_list(limit=20) -> pd.DataFrame:
    return query_df(
        """
        SELECT c.customer_id, c.full_name, c.city, c.customer_segment,
               c.status, cs.churn_score, cs.risk_level,
               cs.main_risk_reason, cs.recommended_action,
               vs.arpu_jod, vs.total_revenue_6m_jod, vs.value_segment,
               vs.lifetime_months
        FROM customers c
        JOIN customer_churn_scores cs ON c.customer_id = cs.customer_id
        JOIN customer_value_segments vs ON c.customer_id = vs.customer_id
        WHERE cs.risk_level = 'High'
          AND vs.value_segment IN ('VIP', 'High Value')
        ORDER BY cs.churn_score DESC, vs.arpu_jod DESC
        LIMIT ?
        """,
        (limit,),
    )


def get_executive_kpis() -> dict:
    with get_conn() as conn:
        kpis = {}

        row = conn.execute(
            "SELECT COUNT(*) as total, SUM(CASE WHEN status='Active' THEN 1 ELSE 0 END) as active FROM customers"
        ).fetchone()
        kpis["total_customers"] = row["total"]
        kpis["active_customers"] = row["active"]

        row = conn.execute(
            """SELECT SUM(total_amount_jod) as revenue, COUNT(*) as count
               FROM invoices WHERE billing_period_start >= (
                   SELECT date(MAX(issue_date), '-60 days') FROM invoices
               )"""
        ).fetchone()
        kpis["monthly_revenue_jod"] = round(row["revenue"] or 0, 2)
        kpis["invoices_count"] = row["count"] or 0

        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM invoices WHERE payment_status='Overdue'"
        ).fetchone()
        kpis["overdue_invoices"] = row["cnt"]

        rows = conn.execute(
            "SELECT risk_level, COUNT(*) as cnt FROM customer_churn_scores GROUP BY risk_level"
        ).fetchall()
        kpis["churn_breakdown"] = {r["risk_level"]: r["cnt"] for r in rows}

        rows = conn.execute(
            """SELECT value_segment, COUNT(*) as cnt
               FROM customer_value_segments GROUP BY value_segment ORDER BY cnt DESC"""
        ).fetchall()
        kpis["value_segments"] = {r["value_segment"]: r["cnt"] for r in rows}

        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM complaints WHERE status != 'Resolved'"
        ).fetchone()
        kpis["open_complaints"] = row["cnt"]

        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM network_events WHERE status != 'Resolved'"
        ).fetchone()
        kpis["active_network_events"] = row["cnt"]

        rows = conn.execute(
            """SELECT c.city, COUNT(*) as cnt FROM complaints co
               JOIN customers c ON co.customer_id=c.customer_id
               GROUP BY c.city ORDER BY cnt DESC LIMIT 5"""
        ).fetchall()
        kpis["top_complaint_cities"] = [(r["city"], r["cnt"]) for r in rows]

        return kpis


def get_top_complaint_cities() -> pd.DataFrame:
    return query_df(
        """
        SELECT cu.city, COUNT(*) as complaints,
               SUM(CASE WHEN co.severity='High' THEN 1 ELSE 0 END) as high_severity
        FROM complaints co
        JOIN customers cu ON co.customer_id = cu.customer_id
        GROUP BY cu.city ORDER BY complaints DESC LIMIT 10
        """
    )


def get_campaign_performance() -> pd.DataFrame:
    return query_df(
        """
        SELECT ca.campaign_name, ca.campaign_type, ca.target_segment,
               COUNT(cr.response_id) as total_sent,
               SUM(CASE WHEN cr.response_status='Responded' THEN 1 ELSE 0 END) as responded,
               SUM(CASE WHEN cr.converted_flag=1 THEN 1 ELSE 0 END) as converted,
               ROUND(SUM(cr.revenue_generated_jod),2) as revenue_jod
        FROM campaigns ca
        LEFT JOIN customer_campaign_responses cr ON ca.campaign_id = cr.campaign_id
        GROUP BY ca.campaign_id
        ORDER BY revenue_jod DESC
        """
    )


def get_network_events() -> pd.DataFrame:
    return query_df(
        """
        SELECT ne.event_type, ne.severity, ne.status,
               nt.city, nt.technology,
               ne.affected_customers,
               ne.event_start_time, ne.event_end_time
        FROM network_events ne
        JOIN network_towers nt ON ne.tower_id = nt.tower_id
        ORDER BY ne.event_start_time DESC LIMIT 20
        """
    )


def run_sql(sql: str) -> pd.DataFrame:
    return query_df(sql)


def search_customers(query: str) -> pd.DataFrame:
    like = f"%{query}%"
    return query_df(
        """
        SELECT customer_id, full_name, city, customer_segment,
               status, preferred_language, phone_number
        FROM customers
        WHERE full_name LIKE ? OR city LIKE ? OR customer_segment LIKE ?
        LIMIT 20
        """,
        (like, like, like),
    )


def get_billing_details(customer_id: int) -> dict:
    result = {}
    result["invoices"] = get_customer_invoices(customer_id, limit=6)

    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT SUM(amount_jod) as total_paid, COUNT(*) as payment_count,
                   MAX(payment_date) as last_payment
            FROM payments WHERE customer_id=?
            """,
            (customer_id,),
        ).fetchone()
        result["payment_summary"] = dict(row) if row else {}

        row = conn.execute(
            """
            SELECT SUM(total_amount_jod) as total_billed,
                   SUM(CASE WHEN payment_status='Overdue' THEN total_amount_jod ELSE 0 END) as overdue_amount,
                   COUNT(CASE WHEN payment_status='Overdue' THEN 1 END) as overdue_count
            FROM invoices i
            JOIN accounts a ON i.account_id = a.account_id
            WHERE a.customer_id=?
            """,
            (customer_id,),
        ).fetchone()
        result["billing_summary"] = dict(row) if row else {}

    return result
