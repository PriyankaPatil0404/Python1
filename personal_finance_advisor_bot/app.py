import os
from collections import defaultdict
from datetime import date, datetime, timedelta
from functools import wraps

from dotenv import load_dotenv
from flask import Flask, flash, jsonify, redirect, render_template, request, url_for
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
from sqlalchemy import func

from models import db, User, Income, Expense, Budget
from ai_service import generate_advice, chat_response

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-change-me')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///finance.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'warning'

CATEGORIES = ['Food', 'Rent', 'Transport', 'Utilities', 'Healthcare', 'Education', 'Entertainment', 'Shopping', 'Subscriptions', 'Other']

with app.app_context():
    db.create_all()


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def current_month():
    return date.today().strftime('%Y-%m')


def parse_date(value):
    return datetime.strptime(value, '%Y-%m-%d').date()


def summary_for(user_id, month=None):
    month = month or current_month()
    try:
        start = datetime.strptime(month + '-01', '%Y-%m-%d').date()
    except ValueError:
        start = date.today().replace(day=1)
        month = start.strftime('%Y-%m')
    if start.month == 12:
        end = date(start.year + 1, 1, 1)
    else:
        end = date(start.year, start.month + 1, 1)

    incomes = Income.query.filter(Income.user_id == user_id, Income.date >= start, Income.date < end).all()
    expenses = Expense.query.filter(Expense.user_id == user_id, Expense.date >= start, Expense.date < end).all()
    budgets = Budget.query.filter_by(user_id=user_id, month=month).all()
    cat = defaultdict(float)
    for e in expenses:
        cat[e.category] += e.amount
    budget_map = {b.category: b.limit_amount for b in budgets}
    income_total = sum(x.amount for x in incomes)
    expense_total = sum(x.amount for x in expenses)
    return {
        'month': month, 'incomes': incomes, 'expenses_list': expenses, 'budgets_list': budgets,
        'income': income_total, 'expenses': expense_total, 'savings': income_total - expense_total,
        'categories': dict(cat), 'budgets': budget_map,
    }


def login_required_json(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({'error': 'Authentication required'}), 401
        return fn(*args, **kwargs)
    return wrapped


@app.context_processor
def inject_globals():
    return {'categories': CATEGORIES, 'today': date.today(), 'current_month': current_month()}


@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('landing.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        if not name or not email or len(password) < 6:
            flash('Enter your name/email and use a password of at least 6 characters.', 'danger')
        elif User.query.filter_by(email=email).first():
            flash('An account with this email already exists.', 'warning')
        else:
            user = User(name=name, email=email)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash('Account created successfully.', 'success')
            return redirect(url_for('dashboard'))
    return render_template('auth.html', mode='register')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user, remember=True)
            flash('Welcome back!', 'success')
            return redirect(url_for('dashboard'))
        flash('Invalid email or password.', 'danger')
    return render_template('auth.html', mode='login')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('index'))


@app.route('/dashboard')
@login_required
def dashboard():
    month = request.args.get('month', current_month())
    s = summary_for(current_user.id, month)
    recent_expenses = Expense.query.filter_by(user_id=current_user.id).order_by(Expense.date.desc(), Expense.id.desc()).limit(8).all()
    budget_rows = []
    for b in s['budgets_list']:
        spent = s['categories'].get(b.category, 0)
        budget_rows.append({'category': b.category, 'limit': b.limit_amount, 'spent': spent, 'percent': min(100, round(spent / b.limit_amount * 100, 1)) if b.limit_amount else 0})
    return render_template('dashboard.html', s=s, recent_expenses=recent_expenses, budget_rows=budget_rows)


@app.route('/income', methods=['GET', 'POST'])
@login_required
def income():
    if request.method == 'POST':
        try:
            item = Income(user_id=current_user.id, source=request.form['source'].strip(), amount=float(request.form['amount']), date=parse_date(request.form['date']), notes=request.form.get('notes', '').strip())
            if item.amount <= 0: raise ValueError
            db.session.add(item); db.session.commit(); flash('Income added.', 'success')
        except Exception:
            db.session.rollback(); flash('Please enter valid income details.', 'danger')
        return redirect(url_for('income'))
    items = Income.query.filter_by(user_id=current_user.id).order_by(Income.date.desc(), Income.id.desc()).all()
    return render_template('income.html', items=items)


@app.post('/income/delete/<int:item_id>')
@login_required
def delete_income(item_id):
    item = Income.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()
    try:
        db.session.delete(item)
        db.session.commit()
        flash('Income removed.', 'success')
    except Exception:
        db.session.rollback()
        flash('Could not remove income.', 'danger')
    return redirect(url_for('income'))


@app.route('/expenses', methods=['GET', 'POST'])
@login_required
def expenses():
    if request.method == 'POST':
        try:
            item = Expense(user_id=current_user.id, category=request.form['category'], description=request.form['description'].strip(), amount=float(request.form['amount']), date=parse_date(request.form['date']))
            if item.amount <= 0 or item.category not in CATEGORIES: raise ValueError
            db.session.add(item); db.session.commit(); flash('Expense added.', 'success')
        except Exception:
            db.session.rollback(); flash('Please enter valid expense details.', 'danger')
        return redirect(url_for('expenses'))
    items = Expense.query.filter_by(user_id=current_user.id).order_by(Expense.date.desc(), Expense.id.desc()).all()
    return render_template('expenses.html', items=items)


@app.post('/expenses/delete/<int:item_id>')
@login_required
def delete_expense(item_id):
    item = Expense.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()
    try:
        db.session.delete(item)
        db.session.commit()
        flash('Expense removed.', 'success')
    except Exception:
        db.session.rollback()
        flash('Could not remove expense.', 'danger')
    return redirect(url_for('expenses'))


@app.route('/budgets', methods=['GET', 'POST'])
@login_required
def budgets():
    raw_month = request.form.get('month') or request.args.get('month') or current_month()
    try:
        datetime.strptime(raw_month + '-01', '%Y-%m-%d')
        month = raw_month
    except (ValueError, TypeError):
        month = current_month()

    if request.method == 'POST':
        try:
            category = request.form['category']
            amount = float(request.form['amount'])
            if category not in CATEGORIES or amount <= 0:
                raise ValueError
            existing = Budget.query.filter_by(user_id=current_user.id, category=category, month=month).first()
            if existing:
                existing.limit_amount = amount
            else:
                db.session.add(Budget(user_id=current_user.id, category=category, month=month, limit_amount=amount))
            db.session.commit()
            flash('Budget saved.', 'success')
        except Exception:
            db.session.rollback()
            flash('Please enter a valid budget.', 'danger')
        return redirect(url_for('budgets', month=month))
    s = summary_for(current_user.id, month)
    return render_template('budgets.html', s=s)


@app.post('/budgets/delete/<int:item_id>')
@login_required
def delete_budget(item_id):
    item = Budget.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()
    month = item.month
    try:
        db.session.delete(item)
        db.session.commit()
        flash('Budget removed.', 'success')
    except Exception:
        db.session.rollback()
        flash('Could not remove budget.', 'danger')
    return redirect(url_for('budgets', month=month))


@app.route('/advisor')
@login_required
def advisor():
    s = summary_for(current_user.id)
    return render_template('advisor.html', s=s)


@app.post('/api/advisor/chat')
@login_required_json
def api_advisor_chat():
    payload = request.get_json(silent=True) or {}
    question = str(payload.get('message', '')).strip()[:1000]
    if not question:
        return jsonify({'error': 'Please enter a question.'}), 400
    s = summary_for(current_user.id)
    try:
        reply = chat_response(s, current_user.savings_goal or 0, question)
    except Exception:
        from ai_service import chat_response_without_ai
        reply = chat_response_without_ai(s, current_user.savings_goal or 0, question)
    return jsonify({'reply': reply})


@app.route('/reports')
@login_required
def reports():
    month = request.args.get('month', current_month())
    s = summary_for(current_user.id, month)
    total_budget = sum(s['budgets'].values())
    utilization = (s['expenses'] / total_budget * 100) if total_budget else 0
    savings_rate = (s['savings'] / s['income'] * 100) if s['income'] else 0
    return render_template('reports.html', s=s, total_budget=total_budget, utilization=utilization, savings_rate=savings_rate)


@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        try:
            name = request.form.get('name', '').strip()
            if not name:
                raise ValueError('Name is required.')
            current_user.name = name
            current_user.monthly_income_target = max(0.0, float(request.form.get('monthly_income_target') or 0))
            current_user.savings_goal = max(0.0, float(request.form.get('savings_goal') or 0))
            db.session.commit()
            flash('Profile updated.', 'success')
        except Exception:
            db.session.rollback()
            flash('Please enter valid profile values.', 'danger')
        return redirect(url_for('profile'))
    return render_template('profile.html')


@app.route('/api/month-summary')
@login_required_json
def api_month_summary():
    s = summary_for(current_user.id, request.args.get('month', current_month()))
    return jsonify({'month': s['month'], 'income': s['income'], 'expenses': s['expenses'], 'savings': s['savings'], 'categories': s['categories'], 'budgets': s['budgets']})


@app.errorhandler(404)
def not_found(_):
    return render_template('error.html', code=404, message='Page not found.'), 404


@app.errorhandler(500)
def server_error(_):
    db.session.rollback()
    return render_template('error.html', code=500, message='Something went wrong. Please try again.'), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
