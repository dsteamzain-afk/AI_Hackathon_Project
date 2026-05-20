import gradio as gr
import pandas as pd
import os

import db
import ai

# ── helpers ──────────────────────────────────────────────────────────────────

def _fmt(val, prefix="", suffix="", decimals=2):
    if val is None:
        return "N/A"
    if isinstance(val, float):
        return f"{prefix}{val:,.{decimals}f}{suffix}"
    return f"{prefix}{val}{suffix}"


def _risk_badge(level):
    colors = {"High": "🔴", "Medium": "🟡", "Low": "🟢"}
    return f"{colors.get(level, '⚪')} {level}"


def _value_badge(seg):
    icons = {"VIP": "💎", "High Value": "⭐", "Mid Value": "📊", "Low Value": "📉"}
    return f"{icons.get(seg, '')} {seg}"


# ── TAB 1: Customer 360 ───────────────────────────────────────────────────────

def load_customer_360(customer_id_input, api_key):
    try:
        cid = int(str(customer_id_input).strip())
    except ValueError:
        return ("❌ Please enter a valid numeric customer ID.",) + ("",) * 8 + (None, None, None, None)

    if not db.customer_exists(cid):
        return (f"❌ Customer ID {cid} not found in database.",) + ("",) * 8 + (None, None, None, None)

    profile = db.get_customer_profile(cid)
    account = db.get_customer_account(cid)
    churn   = db.get_customer_churn(cid)
    value   = db.get_customer_value(cid)
    usage   = db.get_customer_usage_summary(cid)
    subs_df = db.get_customer_subscriptions(cid)
    comp_df = db.get_customer_complaints(cid)
    supp_df = db.get_customer_support(cid)
    inv_df  = db.get_customer_invoices(cid)

    # Header card
    header = f"""## 👤 {profile.get('full_name', 'Unknown')}  &nbsp;&nbsp; ID: `{cid}`

| Field | Value |
|-------|-------|
| City / Governorate | {profile.get('city')} / {profile.get('governorate')} |
| Segment | {profile.get('customer_segment')} · {profile.get('customer_type')} |
| Status | {'✅ Active' if profile.get('status')=='Active' else '❌ Inactive'} |
| Language | {profile.get('preferred_language')} |
| Age Group | {profile.get('age_group')} · {profile.get('gender')} |
| Phone | {profile.get('phone_number')} |
| Customer Since | {profile.get('signup_date')} |
"""

    # Risk & value card
    risk_md = f"""### 📊 Risk & Value

| Metric | Value |
|--------|-------|
| Churn Risk | {_risk_badge(churn.get('risk_level','N/A'))} |
| Churn Score | {_fmt(churn.get('churn_score'), decimals=3)} |
| Risk Reason | {churn.get('main_risk_reason','N/A')} |
| Recommended Action | {churn.get('recommended_action','N/A')} |
| Value Segment | {_value_badge(value.get('value_segment','N/A'))} |
| ARPU | {_fmt(value.get('arpu_jod'), prefix='JOD ', decimals=2)} |
| 6-Month Revenue | {_fmt(value.get('total_revenue_6m_jod'), prefix='JOD ', decimals=2)} |
| Lifetime (months) | {value.get('lifetime_months','N/A')} |
"""

    # Usage summary card
    usage_md = f"""### 📡 Usage Summary

| Metric | Value |
|--------|-------|
| Total Revenue (all-time) | {_fmt(usage.get('total_rev'), prefix='JOD ', decimals=2)} |
| Avg Monthly Data | {_fmt(usage.get('avg_data_gb'), suffix=' GB', decimals=2)} |
| Total Voice Minutes | {_fmt(usage.get('total_minutes'), decimals=0)} |
| Total Support Interactions | {usage.get('total_interactions','N/A')} |
| Total Complaints | {usage.get('total_complaints','N/A')} |
| Account Credit Limit | {_fmt(account.get('credit_limit_jod'), prefix='JOD ', decimals=2)} |
| Billing Cycle Day | {account.get('billing_cycle_day','N/A')} |
"""

    # AI analysis
    ai_analysis = ""
    if api_key.strip():
        combined = {**profile, **churn, **value, **usage,
                    "complaints_count": len(comp_df),
                    "open_complaints": len(comp_df[comp_df.get('status', pd.Series()) != 'Resolved']) if not comp_df.empty else 0}
        ai_analysis = ai.analyze_customer(combined, api_key)
    else:
        ai_analysis = "_Enter your Anthropic API key in the ⚙️ Settings tab to get AI-powered analysis._"

    return header, risk_md, usage_md, ai_analysis, subs_df, comp_df, supp_df, inv_df


def generate_message(customer_id_input, api_key):
    if not api_key.strip():
        return "⚠️ Please enter your Anthropic API key in the ⚙️ Settings tab."
    try:
        cid = int(str(customer_id_input).strip())
    except ValueError:
        return "❌ Invalid customer ID."

    profile = db.get_customer_profile(cid)
    churn   = db.get_customer_churn(cid)
    value   = db.get_customer_value(cid)
    comp_df = db.get_customer_complaints(cid)

    combined = {**profile, **churn, **value,
                "open_complaints": len(comp_df[comp_df["status"] != "Resolved"]) if not comp_df.empty else 0}
    return ai.generate_retention_message(combined, api_key)


# ── TAB 2: Churn Rescue ───────────────────────────────────────────────────────

def load_churn_rescue(top_n, api_key):
    df = db.get_churn_rescue_list(int(top_n))
    if df.empty:
        return "No high-risk, high-value customers found.", df, ""

    summary_md = f"""### 🚨 Churn Rescue Dashboard

Found **{len(df)} high-priority customers** (High Risk + VIP/High Value)

| Metric | Value |
|--------|-------|
| Avg Churn Score | {df['churn_score'].mean():.3f} |
| Avg ARPU | JOD {df['arpu_jod'].mean():.2f} |
| Total 6M Revenue at Risk | JOD {df['total_revenue_6m_jod'].sum():,.2f} |
| Top Risk Reason | {df['main_risk_reason'].mode().iloc[0] if not df.empty else 'N/A'} |
"""

    display_df = df[["customer_id","full_name","city","value_segment",
                      "arpu_jod","churn_score","risk_level",
                      "main_risk_reason","recommended_action"]].copy()
    display_df.columns = ["ID","Name","City","Value Seg","ARPU (JOD)",
                          "Churn Score","Risk","Risk Reason","Action"]

    ai_summary = ""
    if api_key.strip():
        ai_summary = ai.generate_churn_rescue_summary(
            df[["customer_id","full_name","city","value_segment",
                "arpu_jod","churn_score","main_risk_reason","recommended_action"]]
            .head(10).to_string(), api_key
        )
    else:
        ai_summary = "_Enter API key in ⚙️ Settings for AI-powered rescue strategy._"

    return summary_md, display_df, ai_summary


# ── TAB 3: Billing Support ────────────────────────────────────────────────────

def load_billing(customer_id_input, api_key):
    try:
        cid = int(str(customer_id_input).strip())
    except ValueError:
        return "❌ Invalid customer ID.", None, ""

    if not db.customer_exists(cid):
        return f"❌ Customer {cid} not found.", None, ""

    profile = db.get_customer_profile(cid)
    billing = db.get_billing_details(cid)
    bs = billing.get("billing_summary", {})
    ps = billing.get("payment_summary", {})
    inv_df = billing.get("invoices", pd.DataFrame())

    summary = f"""### 🧾 Billing Summary — {profile.get('full_name','Unknown')} (ID: {cid})

| Metric | Value |
|--------|-------|
| Total Ever Billed | {_fmt(bs.get('total_billed'), prefix='JOD ')} |
| Overdue Amount | {_fmt(bs.get('overdue_amount'), prefix='JOD ')} |
| Overdue Invoices | {bs.get('overdue_count', 0)} |
| Total Payments Made | {_fmt(ps.get('total_paid'), prefix='JOD ')} |
| Payment Count | {ps.get('payment_count', 0)} |
| Last Payment Date | {ps.get('last_payment','N/A')} |
"""

    ai_response = ""
    if api_key.strip():
        context = f"Customer: {profile.get('full_name')}, City: {profile.get('city')}, "
        context += f"Total billed: JOD {bs.get('total_billed',0):.2f}, "
        context += f"Overdue: JOD {bs.get('overdue_amount',0):.2f} ({bs.get('overdue_count',0)} invoices), "
        context += f"Last payment: {ps.get('last_payment','unknown')}"
        ai_response = ai.answer_business_question(
            f"Analyze the billing situation for customer {cid} and suggest how to handle overdue payments.",
            context, api_key
        )
    else:
        ai_response = "_Enter API key in ⚙️ Settings for AI billing analysis._"

    return summary, inv_df, ai_response


# ── TAB 4: Executive Dashboard ────────────────────────────────────────────────

def load_dashboard(api_key):
    kpis = db.get_executive_kpis()
    churn = kpis.get("churn_breakdown", {})
    value = kpis.get("value_segments", {})

    overview = f"""## 📊 Executive KPI Dashboard — Zain Jordan

### Customer Overview
| KPI | Value |
|-----|-------|
| Total Customers | {kpis['total_customers']:,} |
| Active Customers | {kpis['active_customers']:,} |
| Active Rate | {kpis['active_customers']/kpis['total_customers']*100:.1f}% |

### Revenue
| KPI | Value |
|-----|-------|
| Recent Revenue | JOD {kpis['monthly_revenue_jod']:,.2f} |
| Overdue Invoices | {kpis['overdue_invoices']} |

### Churn Risk
| Risk Level | Count |
|------------|-------|
| 🔴 High | {churn.get('High', 0)} |
| 🟡 Medium | {churn.get('Medium', 0)} |
| 🟢 Low | {churn.get('Low', 0)} |

### Customer Value Segments
| Segment | Count |
|---------|-------|
| 💎 VIP | {value.get('VIP', 0)} |
| ⭐ High Value | {value.get('High Value', 0)} |
| 📊 Mid Value | {value.get('Mid Value', 0)} |
| 📉 Low Value | {value.get('Low Value', 0)} |

### Operations
| KPI | Value |
|-----|-------|
| Open Complaints | {kpis['open_complaints']} |
| Active Network Events | {kpis['active_network_events']} |
"""

    city_df = db.get_top_complaint_cities()
    campaign_df = db.get_campaign_performance()
    network_df = db.get_network_events()

    ai_summary = ""
    if api_key.strip():
        ai_summary = ai.generate_executive_summary(kpis, api_key)
    else:
        ai_summary = "_Enter API key in ⚙️ Settings for AI executive summary._"

    return overview, city_df, campaign_df, network_df, ai_summary


# ── TAB 5: SQL Assistant ──────────────────────────────────────────────────────

EXAMPLE_QUERIES = {
    "Top 10 highest ARPU customers": "SELECT c.customer_id, c.full_name, c.city, v.arpu_jod, v.value_segment FROM customer_value_segments v JOIN customers c ON v.customer_id=c.customer_id ORDER BY v.arpu_jod DESC LIMIT 10",
    "High churn risk customers in Amman": "SELECT c.customer_id, c.full_name, cs.churn_score, cs.main_risk_reason FROM customer_churn_scores cs JOIN customers c ON cs.customer_id=c.customer_id WHERE cs.risk_level='High' AND c.city='Amman' ORDER BY cs.churn_score DESC",
    "Campaign conversion rates": "SELECT ca.campaign_name, ca.campaign_type, COUNT(cr.response_id) as sent, SUM(cr.converted_flag) as converted, ROUND(100.0*SUM(cr.converted_flag)/COUNT(cr.response_id),1) as conv_pct FROM campaigns ca LEFT JOIN customer_campaign_responses cr ON ca.campaign_id=cr.campaign_id GROUP BY ca.campaign_id ORDER BY conv_pct DESC",
    "Monthly revenue trend": "SELECT strftime('%Y-%m', i.issue_date) as month, ROUND(SUM(i.total_amount_jod),2) as revenue FROM invoices i GROUP BY month ORDER BY month DESC LIMIT 12",
    "Worst complaint categories": "SELECT complaint_category, COUNT(*) as count, SUM(CASE WHEN severity='High' THEN 1 ELSE 0 END) as high_sev FROM complaints GROUP BY complaint_category ORDER BY count DESC",
    "Customers with overdue invoices + churn risk": "SELECT c.customer_id, c.full_name, c.city, cs.risk_level, COUNT(i.invoice_id) as overdue_invoices, ROUND(SUM(i.total_amount_jod),2) as overdue_jod FROM customers c JOIN accounts a ON c.customer_id=a.customer_id JOIN invoices i ON a.account_id=i.account_id JOIN customer_churn_scores cs ON c.customer_id=cs.customer_id WHERE i.payment_status='Overdue' GROUP BY c.customer_id ORDER BY overdue_jod DESC LIMIT 15",
    "Network events by severity and city": "SELECT nt.city, ne.severity, ne.event_type, COUNT(*) as events, SUM(ne.affected_customers) as affected FROM network_events ne JOIN network_towers nt ON ne.tower_id=nt.tower_id GROUP BY nt.city, ne.severity ORDER BY affected DESC",
}

def run_sql_query(sql, question, api_key):
    if not sql.strip():
        return "⚠️ Please enter a SQL query.", None, ""
    try:
        result_df = db.run_sql(sql)
    except Exception as e:
        return f"❌ SQL Error: {e}", None, ""

    if result_df.empty:
        return "✅ Query ran successfully — no rows returned.", result_df, ""

    summary = f"✅ **{len(result_df)} rows** returned · {len(result_df.columns)} columns"

    ai_insight = ""
    if api_key.strip() and question.strip():
        ai_insight = ai.answer_business_question(question, result_df.head(20).to_string(), api_key)
    elif not api_key.strip():
        ai_insight = "_Enter API key in ⚙️ Settings to get AI insights on query results._"

    return summary, result_df, ai_insight


def load_example_query(example_name):
    return EXAMPLE_QUERIES.get(example_name, "")


# ── GRADIO UI ─────────────────────────────────────────────────────────────────

THEME = gr.themes.Soft(
    primary_hue="blue",
    secondary_hue="slate",
    neutral_hue="slate",
)

CSS = """
.header-banner {
    background: linear-gradient(135deg, #1a237e 0%, #0d47a1 50%, #006064 100%);
    padding: 24px;
    border-radius: 12px;
    margin-bottom: 16px;
    color: white;
    text-align: center;
}
.kpi-card { border-radius: 8px; padding: 12px; }
footer { display: none !important; }
"""


with gr.Blocks(title="Zain Jordan — Customer 360 AI") as demo:

    # ── Header ────────────────────────────────────────────────────────────────
    gr.HTML("""
    <div class="header-banner">
        <h1 style="color:white;margin:0;font-size:2rem;">📡 Zain Jordan — Customer 360 AI</h1>
        <p style="color:#b3e5fc;margin:8px 0 0;">AI-Powered Customer Intelligence · Churn Rescue · Executive Insights</p>
    </div>
    """)

    # Shared API key state
    api_key_state = gr.State("")

    with gr.Tabs():

        # ─── TAB 1: Customer 360 ─────────────────────────────────────────────
        with gr.Tab("👤 Customer 360"):
            gr.Markdown("### Look up a complete customer profile with AI-powered analysis")
            with gr.Row():
                c360_id   = gr.Number(label="Customer ID (1–1000)", value=42, precision=0, scale=2)
                c360_btn  = gr.Button("🔍 Load Customer", variant="primary", scale=1)

            with gr.Row():
                c360_header   = gr.Markdown()

            with gr.Row():
                c360_risk  = gr.Markdown()
                c360_usage = gr.Markdown()

            with gr.Accordion("📋 Subscriptions & Plans", open=True):
                c360_subs = gr.DataFrame(label="Active Subscriptions")

            with gr.Row():
                with gr.Column():
                    c360_complaints = gr.DataFrame(label="Recent Complaints")
                with gr.Column():
                    c360_support = gr.DataFrame(label="Recent Support Interactions")

            with gr.Accordion("🧾 Recent Invoices", open=False):
                c360_invoices = gr.DataFrame(label="Invoices")

            with gr.Accordion("🤖 AI Analysis", open=True):
                c360_ai = gr.Markdown()
                with gr.Row():
                    c360_msg_btn = gr.Button("✉️ Generate Retention Message", variant="secondary")
                c360_msg = gr.Markdown()

            c360_btn.click(
                fn=load_customer_360,
                inputs=[c360_id, api_key_state],
                outputs=[c360_header, c360_risk, c360_usage, c360_ai,
                         c360_subs, c360_complaints, c360_support, c360_invoices],
            )
            c360_msg_btn.click(
                fn=generate_message,
                inputs=[c360_id, api_key_state],
                outputs=c360_msg,
            )

        # ─── TAB 2: Churn Rescue ─────────────────────────────────────────────
        with gr.Tab("🚨 Churn Rescue"):
            gr.Markdown("### Identify high-value customers at high churn risk — prioritize retention actions")
            with gr.Row():
                cr_n   = gr.Slider(5, 50, value=15, step=5, label="Number of customers to show", scale=3)
                cr_btn = gr.Button("🔍 Find At-Risk Customers", variant="primary", scale=1)

            cr_summary  = gr.Markdown()
            cr_table    = gr.DataFrame(label="High-Priority Customers — Sorted by Churn Score")

            with gr.Accordion("🤖 AI Rescue Strategy", open=True):
                cr_ai = gr.Markdown()

            cr_btn.click(
                fn=load_churn_rescue,
                inputs=[cr_n, api_key_state],
                outputs=[cr_summary, cr_table, cr_ai],
            )

        # ─── TAB 3: Billing Support ──────────────────────────────────────────
        with gr.Tab("🧾 Billing Support"):
            gr.Markdown("### Analyze customer billing history — identify overdue invoices and payment issues")
            with gr.Row():
                bill_id  = gr.Number(label="Customer ID", value=42, precision=0, scale=2)
                bill_btn = gr.Button("🔍 Load Billing", variant="primary", scale=1)

            bill_summary  = gr.Markdown()
            bill_invoices = gr.DataFrame(label="Invoice History")

            with gr.Accordion("🤖 AI Billing Analysis", open=True):
                bill_ai = gr.Markdown()

            bill_btn.click(
                fn=load_billing,
                inputs=[bill_id, api_key_state],
                outputs=[bill_summary, bill_invoices, bill_ai],
            )

        # ─── TAB 4: Executive Dashboard ──────────────────────────────────────
        with gr.Tab("📊 Executive Dashboard"):
            gr.Markdown("### Real-time KPI overview — churn, revenue, campaigns, and network health")
            dash_btn = gr.Button("🔄 Refresh Dashboard", variant="primary")

            dash_overview  = gr.Markdown()

            with gr.Accordion("🤖 AI Executive Summary", open=True):
                dash_ai = gr.Markdown()

            with gr.Row():
                with gr.Column():
                    dash_cities   = gr.DataFrame(label="Top Cities by Complaints")
                with gr.Column():
                    dash_campaigns = gr.DataFrame(label="Campaign Performance")

            with gr.Accordion("🌐 Recent Network Events", open=False):
                dash_network = gr.DataFrame(label="Network Events")

            dash_btn.click(
                fn=load_dashboard,
                inputs=[api_key_state],
                outputs=[dash_overview, dash_cities, dash_campaigns, dash_network, dash_ai],
            )

        # ─── TAB 5: SQL Assistant ────────────────────────────────────────────
        with gr.Tab("🔍 SQL Assistant"):
            gr.Markdown("### Run SQL queries on the Zain Jordan Customer 360 database")

            with gr.Row():
                example_dd = gr.Dropdown(
                    choices=list(EXAMPLE_QUERIES.keys()),
                    label="📂 Load Example Query",
                    scale=3,
                )
                ex_load_btn = gr.Button("Load", scale=1)

            sql_box  = gr.Code(language="sql", label="SQL Query", lines=6,
                               value="SELECT * FROM customers LIMIT 10")
            q_box    = gr.Textbox(label="Business question (optional — for AI interpretation)",
                                  placeholder="e.g. Which city has the most at-risk customers?")

            with gr.Row():
                sql_btn  = gr.Button("▶ Run Query", variant="primary", scale=2)

            sql_status = gr.Markdown()
            sql_result = gr.DataFrame(label="Query Results")

            with gr.Accordion("🤖 AI Interpretation", open=True):
                sql_ai = gr.Markdown()

            ex_load_btn.click(fn=load_example_query, inputs=example_dd, outputs=sql_box)
            sql_btn.click(
                fn=run_sql_query,
                inputs=[sql_box, q_box, api_key_state],
                outputs=[sql_status, sql_result, sql_ai],
            )

        # ─── TAB 6: Database Explorer ────────────────────────────────────────
        with gr.Tab("🗄️ Database Explorer"):
            gr.Markdown("""### Zain Jordan Customer 360 Database — 27 Tables

| Table | Rows | Description |
|-------|------|-------------|
| customers | 1,000 | Core customer profiles (Jordanian market) |
| accounts | 1,000 | Billing accounts |
| subscriptions | 1,631 | Active service subscriptions |
| plans | 25 | Available mobile/fiber plans |
| addons | 20 | Service add-ons |
| devices | 1,631 | Customer devices |
| sim_cards | 1,631 | SIM card management |
| call_detail_records | 50,000 | Voice call logs |
| data_usage_sessions | 60,000 | Data session records |
| sms_usage | 20,000 | SMS logs |
| roaming_usage | 3,000 | International roaming |
| network_towers | 150 | Base station locations |
| network_events | 500 | Network incidents |
| invoices | 4,542 | Customer invoices |
| invoice_items | 11,322 | Invoice line items |
| payments | 4,007 | Payment transactions |
| topups | 5,000 | Prepaid top-ups |
| transactions | 14,007 | All financial transactions |
| support_interactions | 4,000 | Customer service records |
| complaints | 800 | Formal complaints |
| customer_satisfaction | 2,000 | NPS/CSAT surveys |
| campaigns | 20 | Marketing campaigns |
| customer_campaign_responses | 5,000 | Campaign engagement |
| customer_value_segments | 1,000 | ARPU & value scoring |
| customer_churn_scores | 1,000 | Churn risk predictions |
| customer_monthly_summary | 9,786 | Monthly KPI aggregates |
| subscription_addons | 3,000 | Addon assignments |

**Customer IDs range from 1 to 1,000** — try any ID in the Customer 360 tab.
""")

        # ─── TAB 7: Settings ─────────────────────────────────────────────────
        with gr.Tab("⚙️ Settings"):
            gr.Markdown("""### API Configuration

Enter your Anthropic API key to enable AI-powered features:
- Customer analysis and recommendations
- Retention message generation
- Churn rescue strategy summaries
- Executive KPI summaries
- Business intelligence interpretation

Get your API key at [console.anthropic.com](https://console.anthropic.com)

_Your key is stored only in memory for this session and never saved to disk._
""")
            api_key_input = gr.Textbox(
                label="Anthropic API Key",
                placeholder="sk-ant-...",
                type="password",
                value=os.environ.get("ANTHROPIC_API_KEY", ""),
            )
            save_key_btn = gr.Button("💾 Save API Key", variant="primary")
            key_status   = gr.Markdown()

            def save_key(key):
                if key.strip().startswith("sk-ant-"):
                    return gr.State(key.strip()), "✅ API key saved for this session."
                elif key.strip():
                    return gr.State(key.strip()), "⚠️ Key saved but format looks unusual — double-check if AI features fail."
                return gr.State(""), "❌ No key entered."

            save_key_btn.click(
                fn=lambda k: (k.strip(), "✅ API key saved." if k.strip() else "❌ No key entered."),
                inputs=api_key_input,
                outputs=[api_key_state, key_status],
            )

    # ── Auto-load dashboard on start ─────────────────────────────────────────
    demo.load(
        fn=load_dashboard,
        inputs=[api_key_state],
        outputs=[dash_overview, dash_cities, dash_campaigns, dash_network, dash_ai],
    )
    demo.load(
        fn=load_churn_rescue,
        inputs=[cr_n, api_key_state],
        outputs=[cr_summary, cr_table, cr_ai],
    )


if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True,
        theme=THEME,
        css=CSS,
    )
