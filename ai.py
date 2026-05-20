import os
import anthropic

MODEL = "claude-sonnet-4-6"

def get_client(api_key: str = "") -> anthropic.Anthropic:
    key = api_key.strip() or os.environ.get("ANTHROPIC_API_KEY", "")
    return anthropic.Anthropic(api_key=key)


def _chat(client, system: str, user: str, max_tokens=1024) -> str:
    try:
        msg = client.messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return msg.content[0].text
    except Exception as e:
        return f"⚠️ AI error: {e}"


def analyze_customer(customer_data: dict, api_key: str = "") -> str:
    client = get_client(api_key)
    system = (
        "You are a senior customer success analyst at Zain Jordan, a telecom operator. "
        "Analyze customer data and provide actionable, concise insights in English. "
        "Format your response with clear sections using markdown."
    )
    user = f"""Analyze this Zain Jordan customer and provide:
1. **Risk Assessment** – churn risk level and main drivers
2. **Value Summary** – revenue contribution and segment
3. **Key Issues** – complaints/support patterns
4. **Recommended Actions** – 2-3 specific retention actions
5. **Suggested Offer** – best plan or add-on to propose

Customer data:
{customer_data}

Keep the response concise and actionable (under 400 words)."""
    return _chat(client, system, user, max_tokens=600)


def generate_retention_message(customer_data: dict, api_key: str = "") -> str:
    client = get_client(api_key)
    system = (
        "You are a customer care specialist at Zain Jordan. "
        "Write warm, professional messages in the style of a leading Middle Eastern telecom. "
        "Be empathetic, specific, and offer a clear value proposition."
    )
    name = customer_data.get("full_name", "Valued Customer")
    language = customer_data.get("preferred_language", "English")
    lang_note = "Write in Arabic." if language == "Arabic" else "Write in English."
    user = f"""Write a personalized retention SMS/WhatsApp message for this customer.

{lang_note}
Keep it under 160 characters for SMS, professional and warm.
Then write a longer care email version (150-200 words).

Customer context:
- Name: {name}
- Risk reason: {customer_data.get('main_risk_reason', 'N/A')}
- Value segment: {customer_data.get('value_segment', 'N/A')}
- ARPU: {customer_data.get('arpu_jod', 'N/A')} JOD
- Recommended action: {customer_data.get('recommended_action', 'N/A')}
- Open complaints: {customer_data.get('open_complaints', 0)}

Format:
**SMS/WhatsApp Message:**
[message]

**Email Message:**
Subject: [subject]
[body]"""
    return _chat(client, system, user, max_tokens=600)


def generate_churn_rescue_summary(df_json: str, api_key: str = "") -> str:
    client = get_client(api_key)
    system = (
        "You are a retention strategy director at Zain Jordan. "
        "Summarize churn rescue insights and recommend a prioritized action plan."
    )
    user = f"""These are the highest-priority customers at churn risk.
Provide a brief executive summary (under 300 words) covering:
1. **Overall Situation** – key patterns across these customers
2. **Top 3 Risk Drivers** – most common reasons
3. **Recommended Campaign** – what offer/action would address the most customers
4. **Immediate Priority** – which 1-2 customers need attention first and why

Customer data:
{df_json}"""
    return _chat(client, system, user, max_tokens=500)


def answer_business_question(question: str, sql_result: str, api_key: str = "") -> str:
    client = get_client(api_key)
    system = (
        "You are a business intelligence analyst at Zain Jordan. "
        "Interpret database query results and provide clear, business-focused insights. "
        "Use markdown formatting."
    )
    user = f"""Business question: {question}

Query result:
{sql_result}

Provide a clear business interpretation with key insights and any recommended actions."""
    return _chat(client, system, user, max_tokens=500)


def generate_executive_summary(kpis: dict, api_key: str = "") -> str:
    client = get_client(api_key)
    system = (
        "You are a Chief Customer Officer at Zain Jordan preparing a board briefing. "
        "Be concise, data-driven, and highlight what needs immediate attention."
    )
    user = f"""Prepare a 5-bullet executive summary from these KPIs.
End with 2 immediate action items.

KPIs:
{kpis}"""
    return _chat(client, system, user, max_tokens=400)
