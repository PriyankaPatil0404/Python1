import unittest
from datetime import date
from app import app, db, User, Income, Expense, Budget, summary_for
from ai_service import _rule_based, chat_response_without_ai, chat_response, generate_advice


class FinPilotTestCase(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.app = app
        self.client = app.test_client()

        with app.app_context():
            db.create_all()
            Budget.query.delete()
            Expense.query.delete()
            Income.query.delete()
            User.query.delete()
            db.session.commit()

            # Create standard test user
            user = User(name='Test User', email='test@example.com', savings_goal=5000.0)
            user.set_password('password123')
            db.session.add(user)
            db.session.commit()
            self.user_id = user.id

    def tearDown(self):
        with app.app_context():
            db.session.rollback()
            Budget.query.delete()
            Expense.query.delete()
            Income.query.delete()
            User.query.delete()
            db.session.commit()
            db.session.remove()

    def login(self, email='test@example.com', password='password123'):
        return self.client.post('/login', data={'email': email, 'password': password}, follow_redirects=True)

    def logout(self):
        return self.client.get('/logout', follow_redirects=True)

    # 1. Authentication Tests
    def test_registration_and_login(self):
        res = self.client.post('/register', data={
            'name': 'New User',
            'email': 'new@example.com',
            'password': 'secretpassword'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Dashboard', res.data)

        # Logout before testing duplicate registration
        self.logout()
        res_dup = self.client.post('/register', data={
            'name': 'Duplicate',
            'email': 'new@example.com',
            'password': 'secretpassword'
        }, follow_redirects=True)
        self.assertIn(b'already exists', res_dup.data)

        # Invalid password
        res_short = self.client.post('/register', data={
            'name': 'Short Pass',
            'email': 'short@example.com',
            'password': '123'
        }, follow_redirects=True)
        self.assertIn(b'at least 6 characters', res_short.data)

    def test_login_invalid_credentials(self):
        res = self.client.post('/login', data={
            'email': 'test@example.com',
            'password': 'wrongpassword'
        }, follow_redirects=True)
        self.assertIn(b'Invalid email or password', res.data)

    def test_protected_routes(self):
        routes = ['/dashboard', '/income', '/expenses', '/budgets', '/advisor', '/reports', '/profile']
        for r in routes:
            res = self.client.get(r, follow_redirects=False)
            self.assertEqual(res.status_code, 302, f"Route {r} should redirect when unauthorized")

    # 2. Income Tests
    def test_income_crud(self):
        self.login()
        # Add valid income
        res = self.client.post('/income', data={
            'source': 'Salary',
            'amount': '50000.00',
            'date': '2026-09-01',
            'notes': 'Monthly pay'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Income added', res.data)

        with self.app.app_context():
            item = Income.query.filter_by(user_id=self.user_id, source='Salary').first()
            self.assertIsNotNone(item)
            item_id = item.id

        # Delete income
        res_del = self.client.post(f'/income/delete/{item_id}', follow_redirects=True)
        self.assertEqual(res_del.status_code, 200)
        self.assertIn(b'Income removed', res_del.data)

        with self.app.app_context():
            item = Income.query.filter_by(id=item_id).first()
            self.assertIsNone(item)

    # 3. Expense Tests
    def test_expense_crud(self):
        self.login()
        res = self.client.post('/expenses', data={
            'category': 'Food',
            'description': 'Groceries',
            'amount': '2500.50',
            'date': '2026-09-05'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Expense added', res.data)

        # Invalid category
        res_bad = self.client.post('/expenses', data={
            'category': 'NonExistentCategory',
            'description': 'Something',
            'amount': '100',
            'date': '2026-09-05'
        }, follow_redirects=True)
        self.assertIn(b'Please enter valid expense details', res_bad.data)

        with self.app.app_context():
            item = Expense.query.filter_by(user_id=self.user_id, description='Groceries').first()
            self.assertIsNotNone(item)
            item_id = item.id

        # Delete expense
        res_del = self.client.post(f'/expenses/delete/{item_id}', follow_redirects=True)
        self.assertEqual(res_del.status_code, 200)
        self.assertIn(b'Expense removed', res_del.data)

    # 4. Budget Tests
    def test_budget_crud(self):
        self.login()
        res = self.client.post('/budgets', data={
            'category': 'Food',
            'amount': '15000.00',
            'month': '2026-09'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Budget saved', res.data)

        with self.app.app_context():
            b = Budget.query.filter_by(user_id=self.user_id, category='Food', month='2026-09').first()
            self.assertIsNotNone(b)
            self.assertEqual(b.limit_amount, 15000.0)
            budget_id = b.id

        # Update existing budget
        res_update = self.client.post('/budgets', data={
            'category': 'Food',
            'amount': '18000.00',
            'month': '2026-09'
        }, follow_redirects=True)
        self.assertIn(b'Budget saved', res_update.data)

        with self.app.app_context():
            b = Budget.query.filter_by(id=budget_id).first()
            self.assertEqual(b.limit_amount, 18000.0)

        # Delete budget
        res_del = self.client.post(f'/budgets/delete/{budget_id}', follow_redirects=True)
        self.assertEqual(res_del.status_code, 200)
        self.assertIn(b'Budget removed', res_del.data)

    # 5. Financial Summary Calculation Tests
    def test_summary_calculation(self):
        with self.app.app_context():
            inc = Income(user_id=self.user_id, source='Salary', amount=60000.0, date=date(2026, 9, 1))
            exp1 = Expense(user_id=self.user_id, category='Food', description='Food', amount=10000.0, date=date(2026, 9, 2))
            exp2 = Expense(user_id=self.user_id, category='Rent', description='Rent', amount=20000.0, date=date(2026, 9, 3))
            bud = Budget(user_id=self.user_id, category='Food', month='2026-09', limit_amount=12000.0)
            db.session.add_all([inc, exp1, exp2, bud])
            db.session.commit()

            s = summary_for(self.user_id, '2026-09')
            self.assertEqual(s['income'], 60000.0)
            self.assertEqual(s['expenses'], 30000.0)
            self.assertEqual(s['savings'], 30000.0)
            self.assertEqual(s['categories']['Food'], 10000.0)
            self.assertEqual(s['categories']['Rent'], 20000.0)
            self.assertEqual(s['budgets']['Food'], 12000.0)

    # 6. Profile and Safety Tests
    def test_profile_update(self):
        self.login()
        res = self.client.post('/profile', data={
            'name': 'Updated Name',
            'monthly_income_target': '80000',
            'savings_goal': '20000'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Profile updated', res.data)

        # Empty name rejection
        res_empty = self.client.post('/profile', data={
            'name': '   ',
            'monthly_income_target': '80000',
            'savings_goal': '20000'
        }, follow_redirects=True)
        self.assertIn(b'Please enter valid profile values', res_empty.data)

    # 7. AI Service and Fallbacks Tests
    def test_ai_service_rule_based_and_fallbacks(self):
        summary = {
            'income': 50000.0,
            'expenses': 20000.0,
            'categories': {'Food': 12000.0, 'Rent': 8000.0},
            'budgets': {'Food': 10000.0}
        }
        # Test rule based advice
        advice = _rule_based(summary)
        self.assertIn('### Financial Insight', advice)
        self.assertIn('Food', advice)

        # Test empty summary
        advice_empty = _rule_based({})
        self.assertIn('### Financial Insight', advice_empty)

        # Test offline chat response
        chat1 = chat_response_without_ai(summary, 5000.0, 'Where am I overspending?')
        self.assertIn('spending picture', chat1)
        self.assertIn('Food', chat1)

        chat2 = chat_response_without_ai(summary, 5000.0, 'How can I save?')
        self.assertIn('savings goal', chat2)

        chat3 = chat_response_without_ai(summary, 5000.0, 'What about budget?')
        self.assertIn('practical starting point', chat3)

        # Empty question / general fallback
        chat4 = chat_response_without_ai(summary, 5000.0, '')
        self.assertIn('50,000', chat4)

    # 8. API Endpoints
    def test_api_endpoints(self):
        # Unauthenticated
        res = self.client.get('/api/month-summary')
        self.assertEqual(res.status_code, 401)

        res_chat = self.client.post('/api/advisor/chat', json={'message': 'hello'})
        self.assertEqual(res_chat.status_code, 401)

        # Authenticated
        self.login()
        res_summary = self.client.get('/api/month-summary?month=2026-09')
        self.assertEqual(res_summary.status_code, 200)
        data = res_summary.get_json()
        self.assertEqual(data['month'], '2026-09')

        res_chat_auth = self.client.post('/api/advisor/chat', json={'message': 'How is my budget?'})
        self.assertEqual(res_chat_auth.status_code, 200)
        chat_data = res_chat_auth.get_json()
        self.assertIn('reply', chat_data)
        self.assertTrue(len(chat_data['reply']) > 0)

        # Empty question
        res_chat_empty = self.client.post('/api/advisor/chat', json={'message': ''})
        self.assertEqual(res_chat_empty.status_code, 400)

    # 9. 404 Handler
    def test_404(self):
        res = self.client.get('/nonexistent-page')
        self.assertEqual(res.status_code, 404)
        self.assertIn(b'404', res.data)


if __name__ == '__main__':
    unittest.main()
