# FinPilot — Personal Finance Advisor Bot

A full-stack AI-powered personal finance management application built with Flask, SQLAlchemy, SQLite and Gemini.

## Features
- Secure registration/login/logout with password hashing and protected routes
- Income and expense tracking with categories
- Monthly category budgets
- Dashboard with income, expense, savings and savings-rate cards
- Interactive expense breakdown chart
- AI Advisor using Google's `google-genai` SDK
- Rule-based fallback advisor when no Gemini key is configured
- Monthly reports and spending analysis
- Financial profile and savings goal
- User-isolated database records
- API endpoint for month summary
- Responsive UI
- Ready for Ngrok/public demo

## 1. Requirements
Python 3.10+ recommended.

## 2. Install
Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 3. Configure environment
Copy `.env.example` to `.env` and change the secret key.

For Gemini, create an API key in Google AI Studio and set:

```env
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-3.8-flash
```

The application still works without this key; AI Advisor will use deterministic rule-based demo recommendations.

## 4. Run

```bash
python app.py
```

Open `http://127.0.0.1:5000`.

## 5. Demo flow
1. Register an account.
2. Add income.
3. Add several expenses across categories.
4. Create monthly budgets.
5. Open Dashboard.
6. Open AI Advisor to analyze your data.
7. Open Reports for the monthly financial summary.
8. Set a savings goal in Profile.

## 6. Ngrok
Install Ngrok, then run the Flask app and in another terminal:

```bash
ngrok http 5000
```

Use the generated HTTPS forwarding URL for your demonstration.

## Database
SQLite is used by default and `finance.db` is created automatically on first launch. To use PostgreSQL, set `DATABASE_URL` to a SQLAlchemy PostgreSQL URL and install an appropriate PostgreSQL driver.

## Project structure
```
personal_finance_advisor_bot/
├── app.py
├── models.py
├── ai_service.py
├── requirements.txt
├── .env.example
├── README.md
├── templates/
│   ├── base.html
│   ├── landing.html
│   ├── auth.html
│   ├── dashboard.html
│   ├── income.html
│   ├── expenses.html
│   ├── budgets.html
│   ├── advisor.html
│   ├── reports.html
│   ├── profile.html
│   └── error.html
└── static/
    ├── css/style.css
    └── js/
        ├── app.js
        └── dashboard.js
```
