from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

DB_PATH = Path(__file__).parent / "zain_customer_360_ai_demo.db"


class ZainDB:
    """Read-only interface to the Zain Customer 360 SQLite database."""

    def __init__(self, path: str | Path = DB_PATH):
        self._path = str(path)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        return conn

    def _query(self, sql: str, params: tuple = ()) -> pd.DataFrame:
        with self._conn() as conn:
            return pd.read_sql_query(sql, conn, params=params)

    # ── Customer ────────────────────────────────────────────────────────────────

    def get_customer_profile(self, customer_id: int) -> dict:
        df = self._query(
            "SELECT * FROM customers WHERE customer_id = ?", (customer_id,)
        )
        return df.iloc[0].to_dict() if not df.empty else {}

    def get_customer_account(self, customer_id: int) -> dict:
        df = self._query(
            "SELECT * FROM accounts WHERE customer_id = ?", (customer_id,)
        )
        return df.iloc[0].to_dict() if not df.empty else {}

    # ── Billing ─────────────────────────────────────────────────────────────────

    def get_billing_details(self, customer_id: int) -> dict:
        account = self.get_customer_account(customer_id)
        if not account:
            return {}
        account_id = account["account_id"]

        invoices = self._query(
            "SELECT * FROM invoices WHERE account_id = ? ORDER BY issue_date DESC",
            (account_id,),
        )

        payments = self._query(
            """SELECT p.* FROM payments p
               JOIN invoices i ON p.invoice_id = i.invoice_id
               WHERE i.account_id = ?""",
            (account_id,),
        )

        billing_summary = {}
        payment_summary = {}
        if not invoices.empty:
            billing_summary = {
                "total_billed_jod": float(invoices["total_amount_jod"].sum()),
                "overdue_count": int((invoices["days_overdue"] > 0).sum()),
                "overdue_amount_jod": float(
                    invoices.loc[invoices["days_overdue"] > 0, "total_amount_jod"].sum()
                ),
            }
        if not payments.empty:
            payment_summary = {
                "total_paid_jod": float(payments["amount_jod"].sum()),
                "payment_count": len(payments),
            }

        return {
            "billing_summary": billing_summary,
            "payment_summary": payment_summary,
            "invoices": invoices.head(10),
        }

    def get_invoice_items_detail(self, invoice_id: int) -> pd.DataFrame:
        return self._query(
            "SELECT * FROM invoice_items WHERE invoice_id = ?", (invoice_id,)
        )

    # ── Churn & Value ────────────────────────────────────────────────────────────

    def get_customer_churn(self, customer_id: int) -> dict:
        df = self._query(
            "SELECT * FROM customer_churn_scores WHERE customer_id = ? ORDER BY score_month DESC LIMIT 1",
            (customer_id,),
        )
        return df.iloc[0].to_dict() if not df.empty else {}

    def get_customer_value(self, customer_id: int) -> dict:
        df = self._query(
            "SELECT * FROM customer_value_segments WHERE customer_id = ? ORDER BY segment_month DESC LIMIT 1",
            (customer_id,),
        )
        return df.iloc[0].to_dict() if not df.empty else {}

    # ── Overdue Dashboard ────────────────────────────────────────────────────────

    def get_overdue_customers(self, limit: int = 20) -> pd.DataFrame:
        return self._query(
            """SELECT c.customer_id, c.full_name, c.city, c.customer_segment,
                      a.account_id, a.credit_limit_jod,
                      SUM(i.total_amount_jod) AS overdue_amount_jod,
                      MAX(i.days_overdue) AS max_days_overdue,
                      COUNT(i.invoice_id) AS overdue_invoice_count
               FROM invoices i
               JOIN accounts a ON i.account_id = a.account_id
               JOIN customers c ON a.customer_id = c.customer_id
               WHERE i.days_overdue > 0
               GROUP BY c.customer_id
               ORDER BY overdue_amount_jod DESC
               LIMIT ?""",
            (limit,),
        )

    # ── Ad-hoc SQL ───────────────────────────────────────────────────────────────

    def run_sql(self, sql: str) -> pd.DataFrame:
        return self._query(sql)
