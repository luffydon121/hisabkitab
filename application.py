# application.py
import os
import csv
import json
from datetime import datetime
from io import StringIO

from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, jsonify, make_response
)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin, login_user,
    logout_user, login_required, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# Import configuration from config.py
from config import Config

# Create the Flask app and load configuration
app = Flask(__name__)
app.config.from_object(Config)

# Ensure upload folder exists
UPLOAD_FOLDER = app.config['UPLOAD_FOLDER']
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Initialize extensions
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# ----------------------
# Models
# ----------------------
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True)
    password = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), default='user')
    dark_mode = db.Column(db.Boolean, default=False)
    categories = db.relationship('Category', backref='user', lazy='dynamic')
    transactions = db.relationship('Transaction', backref='user', lazy='dynamic')

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    __table_args__ = (db.UniqueConstraint('user_id', 'name', name='_user_category_uc'),)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, default=datetime.utcnow)
    type = db.Column(db.String(20), nullable=False)  # "income" or "expense"
    category = db.Column(db.String(64), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text)
    recurring = db.Column(db.String(20), default='none')
    receipt = db.Column(db.String(120))
    archived = db.Column(db.Boolean, default=False)  # NEW: Marks whether transaction is archived
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))


# ----------------------
# User Loader
# ----------------------
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def allowed_file(filename):
    # Check if the file extension is allowed
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# ----------------------
# Routes
# ----------------------
@app.route('/')
@login_required
def dashboard():
    page = request.args.get('page', 1, type=int)
    sort_by = request.args.get('sort', 'date')
    order = request.args.get('order', 'desc')
    search_query = request.args.get('q', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')

    query = Transaction.query.filter_by(user_id=current_user.id, archived=False)
    if search_query:
        query = query.filter(
            Transaction.category.contains(search_query) |
            Transaction.description.contains(search_query)
        )
    if start_date:
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(Transaction.date >= start)
        except ValueError:
            pass
    if end_date:
        try:
            end = datetime.strptime(end_date, '%Y-%m-%d')
            query = query.filter(Transaction.date <= end)
        except ValueError:
            pass

    if sort_by == 'date':
        query = query.order_by(Transaction.date.asc() if order == 'asc' else Transaction.date.desc())
    elif sort_by == 'amount':
        query = query.order_by(Transaction.amount.asc() if order == 'asc' else Transaction.amount.desc())

    transactions = query.paginate(page=page, per_page=5)
    total_income = db.session.query(db.func.sum(Transaction.amount)).filter_by(user_id=current_user.id, type='income').scalar() or 0
    total_expense = db.session.query(db.func.sum(Transaction.amount)).filter_by(user_id=current_user.id, type='expense').scalar() or 0
    net = total_income - total_expense

    # Compute category breakdown for expense transactions
    category_totals = {}
    # Using transactions.items from the pagination object:
    for tx in transactions.items:
        if tx.type == 'expense':
            category_totals[tx.category] = category_totals.get(tx.category, 0) + tx.amount

    # Prepare lists for Chart.js
    categories = list(category_totals.keys())
    category_amounts = list(category_totals.values())

    return render_template('dashboard.html',
                           transactions=transactions,
                           total_income=total_income,
                           total_expense=total_expense,
                           net=net,
                           search_query=search_query,
                           sort_by=sort_by,
                           order=order,
                           start_date=start_date,
                           end_date=end_date,
                           categories=categories,
                           category_amounts=category_amounts)


@app.route('/archived_transactions')
@login_required
def archived_transactions():
    # Query transactions for the current user that are archived
    archived = Transaction.query.filter_by(user_id=current_user.id, archived=True).order_by(Transaction.date.desc()).all()
    return render_template('archived_transactions.html', transactions=archived)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        uname = request.form.get('username')
        pwd = request.form.get('password')
        user = User.query.filter_by(username=uname).first()
        if user and check_password_hash(user.password, pwd):
            login_user(user)
            flash('Logged in successfully!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials', 'danger')
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        uname = request.form.get('username')
        email = request.form.get('email')
        pwd = request.form.get('password')
        if User.query.filter_by(username=uname).first():
            flash('Username already exists', 'danger')
            return redirect(url_for('register'))
        hashed_pwd = generate_password_hash(pwd)
        new_user = User(username=uname, email=email, password=hashed_pwd)
        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out!', 'info')
    return redirect(url_for('login'))

@app.route('/add_transaction', methods=['GET', 'POST'])
@login_required
def add_transaction():
    # Get categories for the current user (for a dropdown, for example)
    categories = Category.query.filter_by(user_id=current_user.id).all()
    if request.method == 'POST':
        date_str = request.form.get('date')
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            date_obj = datetime.utcnow()
        tx_type = request.form.get('type')
        category = request.form.get('category')
        amount = float(request.form.get('amount'))
        description = request.form.get('description')
        recurring = request.form.get('recurring', 'none')
        
        # Process receipt file if provided
        receipt_file = request.files.get('receipt')
        receipt_filename = None
        if receipt_file and receipt_file.filename != '' and allowed_file(receipt_file.filename):
            filename = secure_filename(receipt_file.filename)
            receipt_filename = filename
            receipt_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        
        new_tx = Transaction(
            date=date_obj,
            type=tx_type,
            category=category,
            amount=amount,
            description=description,
            recurring=recurring,
            receipt=receipt_filename,
            user_id=current_user.id
        )
        db.session.add(new_tx)
        db.session.commit()
        flash('Transaction added!', 'success')
        return redirect(url_for('dashboard'))
    return render_template('add_transaction.html', categories=categories)

@app.route('/edit_transaction/<int:tx_id>', methods=['GET', 'POST'])
@login_required
def edit_transaction(tx_id):
    tx = Transaction.query.filter_by(id=tx_id, user_id=current_user.id).first_or_404()
    categories = Category.query.filter_by(user_id=current_user.id).all()
    if request.method == 'POST':
        date_str = request.form.get('date')
        try:
            tx.date = datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            tx.date = datetime.utcnow()
        tx.type = request.form.get('type')
        tx.category = request.form.get('category')
        tx.amount = float(request.form.get('amount'))
        tx.description = request.form.get('description')
        tx.recurring = request.form.get('recurring', 'none')
        # For simplicity, not handling receipt update in edit
        db.session.commit()
        flash('Transaction updated successfully!', 'success')
        return redirect(url_for('dashboard'))
    return render_template('edit_transaction.html', tx=tx, categories=categories)

@app.route('/delete_transaction/<int:tx_id>', methods=['POST'])
@login_required
def delete_transaction(tx_id):
    tx = Transaction.query.filter_by(id=tx_id, user_id=current_user.id).first_or_404()
    db.session.delete(tx)
    db.session.commit()
    flash('Transaction deleted successfully!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/archive_transaction/<int:tx_id>', methods=['POST'])
@login_required
def archive_transaction(tx_id):
    tx = Transaction.query.filter_by(id=tx_id, user_id=current_user.id).first_or_404()
    # Toggle the archived flag
    tx.archived = not tx.archived
    db.session.commit()
    flash('Transaction {} successfully!'.format('archived' if tx.archived else 'unarchived'), 'success')
    return redirect(url_for('dashboard'))


@app.route('/transaction_details/<int:tx_id>')
@login_required
def transaction_details(tx_id):
    tx = Transaction.query.filter_by(id=tx_id, user_id=current_user.id).first_or_404()
    details = {
        'id': tx.id,
        'date': tx.date.strftime('%Y-%m-%d'),
        'type': tx.type,
        'category': tx.category,
        'amount': tx.amount,
        'description': tx.description,
        'recurring': tx.recurring,
        'receipt': tx.receipt
    }
    return jsonify(details)


@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        email = request.form.get('email')
        dark_mode = (request.form.get('dark_mode') == 'on')
        if email != current_user.email and User.query.filter_by(email=email).first():
            flash('Email already in use', 'danger')
            return redirect(url_for('profile'))
        current_user.email = email
        current_user.dark_mode = dark_mode
        db.session.commit()
        flash('Profile updated!', 'success')
        return redirect(url_for('profile'))
    return render_template('profile.html')

@app.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_pwd = request.form.get('current_password')
        new_pwd = request.form.get('new_password')
        confirm_pwd = request.form.get('confirm_password')
        
        if not check_password_hash(current_user.password, current_pwd):
            flash('Current password is incorrect.', 'danger')
            return redirect(url_for('change_password'))
        
        if new_pwd != confirm_pwd:
            flash('New password and confirmation do not match.', 'danger')
            return redirect(url_for('change_password'))
        
        current_user.password = generate_password_hash(new_pwd)
        db.session.commit()
        flash('Password changed successfully!', 'success')
        return redirect(url_for('profile'))
    
    return render_template('change_password.html')

@app.route('/categories', methods=['GET', 'POST'])
@login_required
def manage_categories():
    if request.method == 'POST':
        new_cat = request.form.get('category')
        if new_cat:
            if Category.query.filter_by(name=new_cat, user_id=current_user.id).first():
                flash('Category already exists.', 'danger')
            else:
                cat = Category(name=new_cat, user_id=current_user.id)
                db.session.add(cat)
                db.session.commit()
                flash('Category added successfully!', 'success')
        return redirect(url_for('manage_categories'))
    categories = Category.query.filter_by(user_id=current_user.id).all()
    return render_template('categories.html', categories=categories)

@app.route('/delete_category/<int:cat_id>', methods=['POST'])
@login_required
def delete_category(cat_id):
    cat = Category.query.filter_by(id=cat_id, user_id=current_user.id).first_or_404()
    db.session.delete(cat)
    db.session.commit()
    flash('Category deleted successfully.', 'success')
    return redirect(url_for('manage_categories'))

@app.route('/reports')
@login_required
def reports():
    transactions = Transaction.query.filter_by(user_id=current_user.id).all()
    monthly = {}
    for tx in transactions:
        key = tx.date.strftime('%Y-%m')
        monthly.setdefault(key, {'income': 0, 'expense': 0})
        if tx.type == 'income':
            monthly[key]['income'] += tx.amount
        else:
            monthly[key]['expense'] += tx.amount
    months = sorted(monthly.keys())
    income_data = [monthly[m]['income'] for m in months]
    expense_data = [monthly[m]['expense'] for m in months]
    return render_template('reports.html', months=months, income_data=income_data, expense_data=expense_data)

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def user_settings():
    if request.method == 'POST':
        # For example, update a setting such as currency symbol (stub)
        currency = request.form.get('currency')
        flash('Settings updated! (Stub: Currency set to {})'.format(currency), 'success')
        return redirect(url_for('user_settings'))
    return render_template('settings.html')

@app.route('/export_csv')
@login_required
def export_csv():
    transactions = Transaction.query.filter_by(user_id=current_user.id).order_by(Transaction.date.desc()).all()
    proxy = StringIO()
    writer = csv.writer(proxy)
    writer.writerow(['ID', 'Date', 'Type', 'Category', 'Amount', 'Description'])
    for tx in transactions:
        writer.writerow([tx.id, tx.date.strftime('%Y-%m-%d'), tx.type, tx.category, tx.amount, tx.description])
    mem = proxy.getvalue()
    proxy.close()
    response = make_response(mem)
    response.headers["Content-Disposition"] = "attachment; filename=transactions.csv"
    response.headers["Content-type"] = "text/csv"
    return response

@app.route('/backup')
@login_required
def backup():
    transactions = Transaction.query.filter_by(user_id=current_user.id).order_by(Transaction.date.desc()).all()
    backup_data = []
    for tx in transactions:
        backup_data.append({
            'id': tx.id,
            'date': tx.date.strftime('%Y-%m-%d'),
            'type': tx.type,
            'category': tx.category,
            'amount': tx.amount,
            'description': tx.description
        })
    response = make_response(json.dumps(backup_data, indent=4))
    response.headers["Content-Disposition"] = "attachment; filename=backup.json"
    response.headers["Content-type"] = "application/json"
    return response

@app.route('/api/transactions')
@login_required
def api_transactions():
    transactions = Transaction.query.filter_by(user_id=current_user.id).order_by(Transaction.date.desc()).all()
    tx_list = []
    for tx in transactions:
        tx_list.append({
            'id': tx.id,
            'date': tx.date.strftime('%Y-%m-%d'),
            'type': tx.type,
            'category': tx.category,
            'amount': tx.amount,
            'description': tx.description
        })
    return jsonify(tx_list)

@app.route('/reset-password')
def reset_password():
    flash('Password reset feature coming soon!', 'info')
    return redirect(url_for('login'))

# ----------------------
# Error Handlers
# ----------------------
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(e):
    return render_template('500.html'), 500

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/')
def home():
    return "HisabKitab is successfully running on Railway!"


# ----------------------
# Run the Application
# ----------------------
if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Create tables if they don't exist
    app.run(debug=True)
