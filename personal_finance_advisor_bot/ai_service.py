import os
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()

try:
    from google import genai
except ImportError:
    genai = None
def _rule_based(summary):
    income = summary.get('income', 0.0)
    expenses = summary.get('expenses', 0.0)
    savings = income - expenses
    rate = (savings / income * 100) if income else 0
    categories = summary.get('categories', {})
    top = sorted(categories.items(), key=lambda x: x[1], reverse=True)[:3] if categories else []

    tips = []
    if income <= 0:
        tips.append('Add your income records first so a personalized budget can be calculated.')
    if expenses > income and income > 0:
        tips.append('Your recorded expenses exceed income. Review discretionary spending and reduce non-essential categories first.')
    elif rate < 10 and income > 0:
        tips.append('Your current savings rate is below 10%. Consider setting aside a fixed amount immediately after receiving income.')
    elif rate >= 20:
        tips.append('Your savings rate is healthy in this period. Keep the saving amount consistent and build an emergency reserve.')
    if top:
        tips.append(f"Your highest spending category is {top[0][0]} (₹{top[0][1]:,.0f}). Review recurring purchases in this category.")
    tips.append('Keep at least one month of essential expenses as an initial emergency-fund milestone.')
    return '### Financial Insight\n\n' + '\n'.join(f'- {x}' for x in tips) + '\n\n*Demo mode: add GEMINI_API_KEY in .env to enable Gemini-generated recommendations.*'


def chat_response_without_ai(summary, user_goal=0, question=''):
    q = (question or '').lower()
    income = summary.get('income', 0.0)
    expenses = summary.get('expenses', 0.0)
    savings = income - expenses
    categories = summary.get('categories', {})
    top = sorted(categories.items(), key=lambda x: x[1], reverse=True)[:3] if categories else []

    if any(x in q for x in ['overspend', 'spending', 'expense', 'where']):
        if top:
            return 'Here is your current spending picture:\n\n' + '\n'.join(f'- **{k}:** ₹{v:,.0f}' for k, v in top) + f'\n\nYou spent **₹{expenses:,.0f}** this month against **₹{income:,.0f}** of income.'
        return 'I do not have any expense records for this month yet. Add a few expenses and I can analyze your spending patterns.'
    if 'save' in q or 'saving' in q or 'goal' in q:
        return f'You currently have **₹{savings:,.0f}** left after recorded expenses. Your savings goal is **₹{user_goal:,.0f}**. Try setting aside a fixed amount immediately after income arrives and review discretionary spending weekly.'
    if 'budget' in q:
        return 'A practical starting point is to protect essentials first, set category limits from your actual spending, and reserve a fixed amount for savings. Add your income, expenses, and budgets so I can make this more specific.'
    return f'Based on your recorded data, your income is **₹{income:,.0f}**, expenses are **₹{expenses:,.0f}**, and the current difference is **₹{savings:,.0f}**. Add more financial records or ask me about spending, budgeting, or savings for a more useful analysis.'


def chat_response(summary, user_goal=0, question=''):
    """Answer a user's natural-language finance question using their current data."""
    api_key = os.getenv('GEMINI_API_KEY', '').strip().strip('\'"')
    if not api_key or genai is None:
        return chat_response_without_ai(summary, user_goal, question)

    income = summary.get('income', 0.0)
    expenses = summary.get('expenses', 0.0)
    available = income - expenses
    categories = summary.get('categories', {})
    budgets = summary.get('budgets', {})

    prompt = f"""You are Finny, a friendly personal finance planning assistant inside a budgeting web app.
Answer the user's question directly and conversationally using the financial context below. Be practical, concise, and explain calculations when useful. Never claim to be a licensed financial advisor. Do not recommend specific securities, loans, or regulated financial products.

CURRENT DATA
Income: ₹{income:.2f}
Expenses: ₹{expenses:.2f}
Available after expenses: ₹{available:.2f}
Savings goal: ₹{user_goal:.2f}
Category spending: {categories}
Budget limits: {budgets}

USER QUESTION: {question}

Reply in plain text/Markdown suitable for a chat bubble. Use short headings or bullets only when they improve readability. Give concrete rupee amounts or percentages from the supplied data where relevant.
"""
    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=os.getenv('GEMINI_MODEL', 'gemini-3.8-flash'),
            contents=prompt,
        )
        text = getattr(response, 'text', None)
        return text.strip() if text else chat_response_without_ai(summary, user_goal, question)
    except Exception:
        return chat_response_without_ai(summary, user_goal, question)


def generate_advice(summary, user_goal=0):
    api_key = os.getenv('GEMINI_API_KEY', '').strip().strip('\'"')
    if not api_key or genai is None:
        return _rule_based(summary)

    income = summary.get('income', 0.0)
    expenses = summary.get('expenses', 0.0)
    available = income - expenses
    categories = summary.get('categories', {})
    budgets = summary.get('budgets', {})

    prompt = f"""You are a personal finance planning assistant inside a student/consumer budgeting app.
Give educational, practical budgeting guidance, not regulated investment advice. Do not recommend specific securities.
Analyze this user's current-period data:
Income: ₹{income:.2f}
Expenses: ₹{expenses:.2f}
Savings: ₹{available:.2f}
Savings goal: ₹{user_goal:.2f}
Category spending: {categories}
Budget limits: {budgets}

Return concise Markdown with these headings:
### Financial Health
### Budget Recommendations
### Overspending Alerts
### Savings Strategy
### Next Month Actions
Use concrete rupee amounts or percentages where appropriate. Mention that this is educational guidance.
"""
    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=os.getenv('GEMINI_MODEL', 'gemini-3.8-flash'),
            contents=prompt,
        )
        text = getattr(response, 'text', None)
        return text.strip() if text else _rule_based(summary)
    except Exception as exc:
        return _rule_based(summary) + f"\n\nAI service note: Gemini could not be reached ({type(exc).__name__})."
