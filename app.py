# app.py - COMPLETE FIXED VERSION (replace your current file with this)
from flask import Flask, render_template, request, jsonify, flash, redirect, url_for, make_response
from flask_login import LoginManager, login_required, current_user, login_user, logout_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date, timedelta

import sqlite3
from pathlib import Path
import io
import csv
import sys
import traceback

# ----- Config -----
app = Flask(__name__)
app.secret_key = 'dl-farm-secret-key-2025-change-in-production'

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / 'database' / 'farm.db'
DB_PATH.parent.mkdir(exist_ok=True)

# ----- Login setup -----
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'


class User(UserMixin):
    def __init__(self, id, username, email, role):
        self.id = id
        self.username = username
        self.email = email
        self.role = role

    def get_role(self):
        return self.role


@login_manager.user_loader
def load_user(user_id):
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        cursor.execute('SELECT id, username, email, role FROM user WHERE id = ?', (int(user_id),))
        row = cursor.fetchone()
        conn.close()
        if row:
            return User(row[0], row[1], row[2], row[3])
        return None
    except Exception:
        return None


def get_db_connection():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


# ----- DB init + migration helper -----
def ensure_task_columns(conn):
    """If older DB lacked priority/category columns, add them safely."""
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(task)")
        cols = {r[1] for r in cur.fetchall()}
        changed = False
        if 'priority' not in cols:
            cur.execute("ALTER TABLE task ADD COLUMN priority TEXT DEFAULT 'Normal'")
            changed = True
            print("✓ Added 'priority' column to task")
        if 'category' not in cols:
            cur.execute("ALTER TABLE task ADD COLUMN category TEXT DEFAULT 'general'")
            changed = True
            print("✓ Added 'category' column to task")
        if changed:
            conn.commit()
    except Exception as e:
        print("Warning (ensure_task_columns):", e)


def ensure_reports_table(conn):
    """
    Ensure the reports metadata table exists.
    Fields: id, report_name, report_type, format, filepath, period_start, period_end,
            generated_by, notes, created_at
    """
    try:
        cur = conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_name TEXT,
            report_type TEXT,
            format TEXT,
            filepath TEXT,
            period_start DATE,
            period_end DATE,
            generated_by TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        conn.commit()
    except Exception as e:
        # Log but do not interrupt initialization
        print("Warning creating reports table:", e)


def init_database():
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute('SELECT id, first_name, last_name FROM staff ORDER BY first_name')
        staff_list = cur.fetchall()
    except:
        staff_list = []


    # create core tables (idempotent)
    cur.execute('''
        CREATE TABLE IF NOT EXISTS user (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS task (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            assigned_to TEXT,
            status TEXT DEFAULT 'Pending',
            priority TEXT DEFAULT 'Normal',
            due_date DATE,
            category TEXT DEFAULT 'general',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    ensure_task_columns(conn)
    cur.execute('''
        CREATE TABLE IF NOT EXISTS animal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tag_number TEXT UNIQUE NOT NULL,
            breed TEXT NOT NULL,
            birth_date DATE,
            weight REAL,
            status TEXT DEFAULT 'Active',
            pen_number TEXT,
            health_status TEXT DEFAULT 'Good',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS sale (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT NOT NULL,
            product TEXT NOT NULL,
            quantity INTEGER DEFAULT 1,
            price_per_unit REAL NOT NULL,
            total_amount REAL NOT NULL,
            sale_date DATE DEFAULT CURRENT_DATE,
            payment_status TEXT DEFAULT 'Pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS breeding (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            male_id TEXT NOT NULL,
            female_id TEXT NOT NULL,
            breeding_date DATE NOT NULL,
            expected_birth DATE,
            notes TEXT,
            status TEXT DEFAULT 'Pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS medical (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            animal_id TEXT NOT NULL,
            treatment_date DATE NOT NULL,
            condition TEXT NOT NULL,
            treatment TEXT NOT NULL,
            veterinarian TEXT,
            next_checkup DATE,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS feed (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            feed_type TEXT NOT NULL,
            quantity REAL NOT NULL,
            animal_group TEXT,
            feeding_time TIME,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS staff (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            position TEXT NOT NULL,
            department TEXT,
            email TEXT,
            phone TEXT NOT NULL,
            address TEXT,
            dob DATE,
            date_employed DATE,
            status TEXT DEFAULT 'Active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS customer (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT NOT NULL,
            company TEXT,
            phone TEXT NOT NULL,
            email TEXT,
            address TEXT,
            customer_type TEXT DEFAULT 'retail',
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS financial (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_type TEXT NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            description TEXT NOT NULL,
            transaction_date DATE,
            reference TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS supplier (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT NOT NULL,
            contact_person TEXT NOT NULL,
            phone TEXT NOT NULL,
            email TEXT,
            products TEXT NOT NULL,
            address TEXT,
            payment_terms TEXT DEFAULT 'cod',
            rating INTEGER DEFAULT 3,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # ensure reports table exists
    ensure_reports_table(conn)

    # add default users if none
    cur.execute('SELECT COUNT(*) FROM user')
    if cur.fetchone()[0] == 0:
        defaults = [
            ('admin', 'admin@dlfarm.com', generate_password_hash('admin123'), 'admin'),
            ('manager', 'manager@dlfarm.com', generate_password_hash('manager123'), 'manager'),
            ('accountant', 'accountant@dlfarm.com', generate_password_hash('accountant123'), 'accountant'),
        ]
        for u, e, p, r in defaults:
            cur.execute('INSERT OR IGNORE INTO user (username, email, password, role) VALUES (?, ?, ?, ?)', (u, e, p, r))
        print("✓ Created default users: admin/manager/accountant")

    # sample tasks if empty
    cur.execute('SELECT COUNT(*) FROM task')
    if cur.fetchone()[0] == 0:
        cur.execute('INSERT INTO task (title, description, assigned_to, status, due_date) VALUES (?, ?, ?, ?, ?)',
                    ('Check animal health', 'Daily health check', 'manager', 'Pending', datetime.now().date()))
        cur.execute('INSERT INTO task (title, description, assigned_to, status, due_date) VALUES (?, ?, ?, ?, ?)',
                    ('Feed animals', 'Morning feeding', 'staff', 'Completed', datetime.now().date()))
    conn.commit()
    conn.close()
    print("✓ Database initialized (or verified)")


init_database()


# ----- helper debug for form submissions -----
def debug_form(name, form):
    print(f"DEBUG FORM: {name} -> {dict(form)}", file=sys.stdout)


# ----- Routes -----
@app.route('/')
def index():
    if getattr(current_user, 'is_authenticated', False):
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if getattr(current_user, 'is_authenticated', False):
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        conn = get_db_connection(); cur = conn.cursor()
        cur.execute('SELECT id, username, email, password, role FROM user WHERE username = ?', (username,))
        row = cur.fetchone(); conn.close()
        if not row:
            flash('Invalid username or password', 'error'); return render_template('login.html')
        if check_password_hash(row[3], password):
            user = User(row[0], row[1], row[2], row[4])
            login_user(user, remember=True)
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'error')
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully', 'success')
    return redirect(url_for('login'))


# ----- Dashboard -----
@app.route('/dashboard')
@login_required
def dashboard():
    """
    Dashboard route: computes KPIs and time-series used by dashboard.html:
    - days: list of YYYY-MM-DD strings for the selected range (default last 30 days)
    - income_series, expense_series: lists of sums aligned to days
    - feed_series: daily feed quantity sums
    - avg_weight_series: daily average animal weight
    - task_counts: dict with Pending / In Progress / Completed counts
    - medical_count: total medical records count
    Also retains previous simple KPIs.
    """
    conn = get_db_connection()
    cur = conn.cursor()

    # Basic totals (keep existing behaviour)
    try:
        cur.execute('SELECT COUNT(*) FROM animal'); total_animals = cur.fetchone()[0] or 0
    except:
        total_animals = 0
    try:
        cur.execute('SELECT COUNT(*) FROM sale'); total_sales = cur.fetchone()[0] or 0
    except:
        total_sales = 0
    try:
        cur.execute("SELECT COUNT(*) FROM task WHERE status = 'Pending'"); pending_tasks = cur.fetchone()[0] or 0
    except:
        pending_tasks = 0
    try:
        cur.execute("SELECT COUNT(*) FROM staff"); total_staff = cur.fetchone()[0] or 0
    except:
        total_staff = 0

    # Date range: allow ?start=YYYY-MM-DD&end=YYYY-MM-DD else default last 30 days
    start_q = request.args.get('start', '').strip()
    end_q = request.args.get('end', '').strip()
    try:
        if start_q:
            start_dt = datetime.strptime(start_q, '%Y-%m-%d').date()
        else:
            start_dt = date.today() - timedelta(days=29)
        if end_q:
            end_dt = datetime.strptime(end_q, '%Y-%m-%d').date()
        else:
            end_dt = date.today()
    except Exception:
        # fallback in case of invalid inputs
        start_dt = date.today() - timedelta(days=29)
        end_dt = date.today()

    # ensure start <= end
    if start_dt > end_dt:
        start_dt, end_dt = end_dt, start_dt

    # list of day labels (ISO yyyy-mm-dd)
    days = []
    cur_day = start_dt
    while cur_day <= end_dt:
        days.append(cur_day.isoformat())
        cur_day = cur_day + timedelta(days=1)

    # Helper: build mapping from SQL aggregate queries (date -> value)
    def query_date_sum(table, date_col, value_expr, extra_where='', params=()):
        """
        returns dict { 'YYYY-MM-DD': value }
        table: table name
        date_col: column to apply DATE() on (e.g. created_at or transaction_date)
        value_expr: expression to SUM (e.g. 'amount' or 'quantity')
        extra_where: additional WHERE clause fragment (without 'AND')
        params: tuple for query params (not start/end)
        """
        q = f"""
            SELECT DATE({date_col}) as d, COALESCE(SUM({value_expr}),0) as val
            FROM {table}
            WHERE DATE({date_col}) BETWEEN ? AND ?
            {('AND ' + extra_where) if extra_where else ''}
            GROUP BY d
            ORDER BY d
        """
        cur.execute(q, (start_dt.isoformat(), end_dt.isoformat(),) + tuple(params))
        rows = cur.fetchall()
        return {r[0]: (r[1] or 0) for r in rows}

    # Income / Expense series from financial.transaction_date
    try:
        income_map = query_date_sum('financial', 'transaction_date', 'amount', "transaction_type = 'income'")
        expense_map = query_date_sum('financial', 'transaction_date', 'amount', "transaction_type = 'expense'")
    except Exception:
        income_map = {}
        expense_map = {}

    # Feed series (sum quantity by created_at date)
    try:
        feed_map = query_date_sum('feed', 'created_at', 'quantity')
    except Exception:
        feed_map = {}

    # Average weight series - average weight of animals by created_at date
    try:
        # query returns date->avg
        q = """
            SELECT DATE(created_at) as d, COALESCE(AVG(weight),0) as val
            FROM animal
            WHERE DATE(created_at) BETWEEN ? AND ?
            GROUP BY d
            ORDER BY d
        """
        cur.execute(q, (start_dt.isoformat(), end_dt.isoformat()))
        rows = cur.fetchall()
        weight_map = {r[0]: (r[1] or 0) for r in rows}
    except Exception:
        weight_map = {}

    # Build aligned lists for charts
    income_series = [float(income_map.get(d, 0)) for d in days]
    expense_series = [float(expense_map.get(d, 0)) for d in days]
    feed_series = [float(feed_map.get(d, 0)) for d in days]
    avg_weight_series = [float(weight_map.get(d, 0)) for d in days]

    # task counts by status (global)
    try:
        cur.execute("SELECT status, COUNT(*) FROM task GROUP BY status")
        task_rows = cur.fetchall()
        task_counts = {'Pending': 0, 'In Progress': 0, 'Completed': 0}
        for r in task_rows:
            st = (r[0] or '').strip()
            cnt = r[1] or 0
            if st.lower() == 'pending':
                task_counts['Pending'] = cnt
            elif st.lower() in ('in progress', 'in_progress', 'inprogress'):
                task_counts['In Progress'] = cnt
            elif st.lower() == 'completed':
                task_counts['Completed'] = cnt
            else:
                # keep other statuses ignored for chart
                pass
    except:
        task_counts = {'Pending': 0, 'In Progress': 0, 'Completed': 0}

    # medical records count
    try:
        cur.execute('SELECT COUNT(*) FROM medical'); medical_count = cur.fetchone()[0] or 0
    except:
        medical_count = 0

    # net profit for the selected range
    try:
        total_income = sum(income_series)
        total_expense = sum(expense_series)
        net_profit = total_income - total_expense
    except:
        net_profit = 0.0

    conn.close()

    return render_template('dashboard.html',
                           # existing KPIs
                           total_animals=total_animals,
                           total_sales=total_sales,
                           pending_tasks=pending_tasks,
                           total_staff=total_staff,
                           # new series/counts for charts
                           days=days,
                           income_series=income_series,
                           expense_series=expense_series,
                           feed_series=feed_series,
                           avg_weight_series=avg_weight_series,
                           task_counts=task_counts,
                           medical_count=medical_count,
                           net_profit=net_profit,
                           # convenient aliases for template
                           start_date=start_dt.isoformat(),
                           end_date=end_dt.isoformat(),
                           # keep user info
                           user_role=current_user.role,
                           username=current_user.username)


# ----- Animals -----
@app.route('/animals')
@login_required
def animals():
    if current_user.role not in ['admin', 'manager']:
        flash('Access denied. Manager role required.', 'error'); return redirect(url_for('dashboard'))
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute('SELECT * FROM animal ORDER BY created_at DESC'); animals = cur.fetchall()
    cur.execute('SELECT COUNT(*) FROM animal'); total_animals = cur.fetchone()[0] or 0
    conn.close()
    return render_template('animals.html', animals=animals, total_animals=total_animals)


@app.route('/animals/<int:animal_id>')
@login_required
def view_animal(animal_id):
    if current_user.role not in ['admin', 'manager']:
        flash('Access denied.', 'error'); return redirect(url_for('animals'))
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute('SELECT * FROM animal WHERE id = ?', (animal_id,)); animal = cur.fetchone(); conn.close()
    if not animal:
        flash('Animal not found.', 'error'); return redirect(url_for('animals'))
    return render_template('animal_view.html', animal=animal)


@app.route('/animals/<int:animal_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_animal(animal_id):
    if current_user.role not in ['admin', 'manager']:
        flash('Access denied.', 'error'); return redirect(url_for('animals'))
    conn = get_db_connection(); cur = conn.cursor()
    if request.method == 'POST':
        debug_form('edit_animal', request.form)
        try:
            cur.execute('UPDATE animal SET tag_number=?, breed=?, birth_date=?, weight=?, status=?, pen_number=?, health_status=? WHERE id=?',
                        (request.form.get('tag_number', '').strip(), request.form.get('breed', '').strip(), request.form.get('birth_date'),
                         float(request.form.get('weight') or 0), request.form.get('status', 'Active'), request.form.get('pen_number', ''), request.form.get('health_status', 'Good'), animal_id))
            conn.commit(); flash('Animal updated!', 'success')
        except Exception as e:
            flash(f'Error updating animal: {e}', 'error')
        finally:
            conn.close()
        return redirect(url_for('animals'))
    cur.execute('SELECT * FROM animal WHERE id = ?', (animal_id,)); animal = cur.fetchone(); conn.close()
    if not animal:
        flash('Animal not found.', 'error'); return redirect(url_for('animals'))
    return render_template('animal_edit.html', animal=animal)


@app.route('/add_animal', methods=['POST'])
@login_required
def add_animal():
    debug_form('add_animal', request.form)
    if current_user.role not in ['admin', 'manager']:
        flash('Access denied.', 'error'); return redirect(url_for('animals'))
    try:
        tag = request.form.get('tag_number', '').strip(); breed = request.form.get('breed', '').strip()
        if not tag or not breed:
            flash('Tag and breed are required.', 'error'); return redirect(url_for('animals'))
        conn = get_db_connection(); cur = conn.cursor()
        cur.execute('SELECT id FROM animal WHERE tag_number = ?', (tag,))
        if cur.fetchone():
            flash('Tag already exists.', 'error'); conn.close(); return redirect(url_for('animals'))
        cur.execute('INSERT INTO animal (tag_number, breed, birth_date, weight, status, pen_number, health_status) VALUES (?, ?, ?, ?, ?, ?, ?)',
                    (tag, breed, request.form.get('birth_date'), float(request.form.get('weight') or 0), request.form.get('status', 'Active'), request.form.get('pen_number', ''), request.form.get('health_status', 'Good')))
        conn.commit(); conn.close(); flash('Animal added!', 'success')
    except Exception as e:
        flash(f'Error adding animal: {e}', 'error')
    return redirect(url_for('animals'))


# ----- Sales -----
@app.route('/sales')
@login_required
def sales():
    if current_user.role not in ['admin', 'accountant']:
        flash('Access denied.', 'error'); return redirect(url_for('dashboard'))
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute('SELECT * FROM sale ORDER BY sale_date DESC'); sales = cur.fetchall()
    cur.execute('SELECT SUM(total_amount) FROM sale'); total_revenue = cur.fetchone()[0] or 0
    cur.execute('SELECT COUNT(*) FROM sale'); total_sales = cur.fetchone()[0] or 0
    conn.close()
    return render_template('sales.html', sales=sales, total_revenue=total_revenue, total_sales=total_sales)


@app.route('/sales/<int:sale_id>')
@login_required
def view_sale(sale_id):
    if current_user.role not in ['admin', 'accountant']:
        flash('Access denied.', 'error'); return redirect(url_for('sales'))
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute('SELECT * FROM sale WHERE id = ?', (sale_id,)); sale = cur.fetchone(); conn.close()
    if not sale:
        flash('Sale not found.', 'error'); return redirect(url_for('sales'))
    return render_template('sale_view.html', sale=sale)


@app.route('/sales/<int:sale_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_sale(sale_id):
    if current_user.role not in ['admin', 'accountant']:
        flash('Access denied.', 'error'); return redirect(url_for('sales'))
    conn = get_db_connection(); cur = conn.cursor()
    if request.method == 'POST':
        debug_form('edit_sale', request.form)
        try:
            qty = int(request.form.get('quantity', '1') or 1)
            price = float(request.form.get('price_per_unit', '0') or 0)
            total = qty * price
            cur.execute('UPDATE sale SET customer_name=?, product=?, quantity=?, price_per_unit=?, total_amount=?, sale_date=? WHERE id=?',
                        (request.form.get('customer_name', '').strip(), request.form.get('product', '').strip(), qty, price, total, request.form.get('sale_date'), sale_id))
            conn.commit(); flash('Sale updated!', 'success')
        except Exception as e:
            flash(f'Error updating sale: {e}', 'error')
        finally:
            conn.close()
        return redirect(url_for('sales'))
    cur.execute('SELECT * FROM sale WHERE id = ?', (sale_id,)); sale = cur.fetchone(); conn.close()
    if not sale:
        flash('Sale not found.', 'error'); return redirect(url_for('sales'))
    return render_template('sale_edit.html', sale=sale)


@app.route('/add_sale', methods=['POST'])
@login_required
def add_sale():
    debug_form('add_sale', request.form)
    if current_user.role not in ['admin', 'accountant']:
        flash('Access denied.', 'error'); return redirect(url_for('sales'))
    try:
        customer = request.form.get('customer_name', '').strip(); product = request.form.get('product', '').strip()
        qty = int(request.form.get('quantity', '1') or 1); price = float(request.form.get('price_per_unit', '0') or 0)
        total = qty * price
        if not customer or not product:
            flash('Customer and product are required.', 'error'); return redirect(url_for('sales'))
        conn = get_db_connection(); cur = conn.cursor()
        cur.execute('INSERT INTO sale (customer_name, product, quantity, price_per_unit, total_amount, sale_date) VALUES (?, ?, ?, ?, ?, ?)',
                    (customer, product, qty, price, total, request.form.get('sale_date')))
        conn.commit(); conn.close(); flash('Sale recorded!', 'success')
    except Exception as e:
        flash(f'Error recording sale: {e}', 'error')
    return redirect(url_for('sales'))


# ----- Breeding -----
@app.route('/breeding')
@login_required
def breeding():
    if current_user.role not in ['admin', 'manager']:
        flash('Access denied.', 'error'); return redirect(url_for('dashboard'))
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute('SELECT * FROM breeding ORDER BY created_at DESC'); breeding_records = cur.fetchall()
    cur.execute('SELECT COUNT(*) FROM breeding'); total_breeding = cur.fetchone()[0] or 0
    try:
        cur.execute("SELECT COUNT(*) FROM breeding WHERE status IN ('Pending','In Progress')"); active_pairs = cur.fetchone()[0] or 0
    except:
        active_pairs = 0
    try:
        today_str = date.today().isoformat()
        cur.execute("SELECT COUNT(*) FROM breeding WHERE expected_birth IS NOT NULL AND expected_birth >= ?", (today_str,))
        expected_births = cur.fetchone()[0] or 0
    except:
        expected_births = 0
    try:
        cur.execute("SELECT COUNT(*) FROM breeding WHERE status = 'Completed'"); completed = cur.fetchone()[0] or 0
        success_rate = int((completed / (total_breeding or 1)) * 100)
    except:
        success_rate = 0
    conn.close()
    return render_template('breeding.html', breeding_records=breeding_records, total_breeding=total_breeding, active_pairs=active_pairs, expected_births=expected_births, total_offspring=0, success_rate=success_rate)


@app.route('/breeding/<int:breeding_id>')
@login_required
def view_breeding(breeding_id):
    if current_user.role not in ['admin', 'manager']:
        flash('Access denied.', 'error'); return redirect(url_for('breeding'))
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute('SELECT * FROM breeding WHERE id = ?', (breeding_id,)); rec = cur.fetchone(); conn.close()
    if not rec:
        flash('Breeding record not found.', 'error'); return redirect(url_for('breeding'))
    return render_template('breeding_view.html', record=rec)


@app.route('/breeding/<int:breeding_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_breeding(breeding_id):
    if current_user.role not in ['admin', 'manager']:
        flash('Access denied.', 'error'); return redirect(url_for('breeding'))
    conn = get_db_connection(); cur = conn.cursor()
    if request.method == 'POST':
        debug_form('edit_breeding', request.form)
        try:
            cur.execute('UPDATE breeding SET male_id=?, female_id=?, breeding_date=?, expected_birth=?, status=?, notes=? WHERE id=?',
                        (request.form.get('male_id', '').strip(), request.form.get('female_id', '').strip(), request.form.get('breeding_date'), request.form.get('expected_birth'), request.form.get('status', 'Pending'), request.form.get('notes', '').strip(), breeding_id))
            conn.commit(); flash('Breeding record updated!', 'success')
        except Exception as e:
            flash(f'Error updating breeding record: {e}', 'error')
        finally:
            conn.close()
        return redirect(url_for('breeding'))
    cur.execute('SELECT * FROM breeding WHERE id = ?', (breeding_id,)); rec = cur.fetchone(); conn.close()
    if not rec:
        flash('Breeding record not found.', 'error'); return redirect(url_for('breeding'))
    return render_template('breeding_edit.html', record=rec)


@app.route('/add_breeding', methods=['POST'])
@login_required
def add_breeding():
    debug_form('add_breeding', request.form)
    if current_user.role not in ['admin', 'manager']:
        flash('Access denied.', 'error'); return redirect(url_for('breeding'))
    try:
        male = request.form.get('male_id', '').strip(); female = request.form.get('female_id', '').strip(); bdate = request.form.get('breeding_date')
        if not male or not female or not bdate:
            flash('Male, female and breeding date required.', 'error'); return redirect(url_for('breeding'))
        conn = get_db_connection(); cur = conn.cursor()
        cur.execute('INSERT INTO breeding (male_id, female_id, breeding_date, expected_birth, notes) VALUES (?, ?, ?, ?, ?)', (male, female, bdate, request.form.get('expected_birth'), request.form.get('notes', '')))
        conn.commit(); conn.close(); flash('Breeding record added!', 'success')
    except Exception as e:
        flash(f'Error adding breeding record: {e}', 'error')
    return redirect(url_for('breeding'))


# ----- Medical -----
@app.route('/medical')
@login_required
def medical():
    if current_user.role not in ['admin', 'manager']:
        flash('Access denied.', 'error'); return redirect(url_for('dashboard'))
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute('SELECT * FROM medical ORDER BY created_at DESC'); medical_records = cur.fetchall()
    cur.execute('SELECT COUNT(*) FROM medical'); total_medical = cur.fetchone()[0] or 0
    conn.close()
    return render_template('medical.html', medical_records=medical_records, total_medical=total_medical)


@app.route('/medical/<int:medical_id>')
@login_required
def view_medical(medical_id):
    if current_user.role not in ['admin', 'manager']:
        flash('Access denied.', 'error'); return redirect(url_for('medical'))
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute('SELECT * FROM medical WHERE id = ?', (medical_id,)); rec = cur.fetchone(); conn.close()
    if not rec:
        flash('Medical record not found.', 'error'); return redirect(url_for('medical'))
    return render_template('medical_view.html', record=rec)


@app.route('/medical/<int:medical_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_medical(medical_id):
    if current_user.role not in ['admin', 'manager']:
        flash('Access denied.', 'error'); return redirect(url_for('medical'))
    conn = get_db_connection(); cur = conn.cursor()
    if request.method == 'POST':
        debug_form('edit_medical', request.form)
        try:
            cur.execute('UPDATE medical SET animal_id=?, treatment_date=?, condition=?, treatment=?, veterinarian=?, next_checkup=?, notes=? WHERE id=?',
                        (request.form.get('animal_id', '').strip(), request.form.get('treatment_date'), request.form.get('condition', '').strip(), request.form.get('treatment', '').strip(), request.form.get('veterinarian', '').strip(), request.form.get('next_checkup'), request.form.get('notes', '').strip(), medical_id))
            conn.commit(); flash('Medical record updated!', 'success')
        except Exception as e:
            flash(f'Error: {e}', 'error')
        finally:
            conn.close()
        return redirect(url_for('medical'))
    cur.execute('SELECT * FROM medical WHERE id = ?', (medical_id,)); rec = cur.fetchone(); conn.close()
    if not rec:
        flash('Medical record not found.', 'error'); return redirect(url_for('medical'))
    return render_template('medical_edit.html', record=rec)


@app.route('/add_medical', methods=['POST'])
@login_required
def add_medical():
    debug_form('add_medical', request.form)
    if current_user.role not in ['admin', 'manager']:
        flash('Access denied.', 'error'); return redirect(url_for('medical'))
    try:
        aid = request.form.get('animal_id', '').strip(); tdate = request.form.get('treatment_date'); cond = request.form.get('condition', '').strip(); treat = request.form.get('treatment', '').strip()
        if not aid or not tdate or not cond or not treat:
            flash('Required fields missing.', 'error'); return redirect(url_for('medical'))
        conn = get_db_connection(); cur = conn.cursor()
        cur.execute('INSERT INTO medical (animal_id, treatment_date, condition, treatment, veterinarian, next_checkup, notes) VALUES (?, ?, ?, ?, ?, ?, ?)',
                    (aid, tdate, cond, treat, request.form.get('veterinarian', ''), request.form.get('next_checkup'), request.form.get('notes', '')))
        conn.commit(); conn.close(); flash('Medical record added!', 'success')
    except Exception as e:
        flash(f'Error adding medical record: {e}', 'error')
    return redirect(url_for('medical'))


# ----- Feed -----
@app.route('/feed')
@login_required
def feed():
    if current_user.role not in ['admin', 'manager']:
        flash('Access denied.', 'error'); return redirect(url_for('dashboard'))
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute('SELECT * FROM feed ORDER BY created_at DESC'); feed_records = cur.fetchall()
    cur.execute('SELECT COUNT(*) FROM feed'); total_feed = cur.fetchone()[0] or 0
    conn.close()
    return render_template('feed.html', feed_records=feed_records, total_feed=total_feed)


@app.route('/feed/<int:feed_id>')
@login_required
def view_feed(feed_id):
    if current_user.role not in ['admin', 'manager']:
        flash('Access denied.', 'error'); return redirect(url_for('feed'))
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute('SELECT * FROM feed WHERE id = ?', (feed_id,)); rec = cur.fetchone(); conn.close()
    if not rec:
        flash('Feed record not found.', 'error'); return redirect(url_for('feed'))
    return render_template('feed_view.html', record=rec)


@app.route('/feed/<int:feed_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_feed(feed_id):
    if current_user.role not in ['admin', 'manager']:
        flash('Access denied.', 'error'); return redirect(url_for('feed'))
    conn = get_db_connection(); cur = conn.cursor()
    if request.method == 'POST':
        debug_form('edit_feed', request.form)
        try:
            cur.execute('UPDATE feed SET feed_type=?, quantity=?, animal_group=?, feeding_time=?, notes=? WHERE id=?',
                        (request.form.get('feed_type', '').strip(), float(request.form.get('quantity', '0') or 0), request.form.get('animal_group', '').strip(), request.form.get('feeding_time'), request.form.get('notes', '').strip(), feed_id))
            conn.commit(); flash('Feed record updated!', 'success')
        except Exception as e:
            flash(f'Error: {e}', 'error')
        finally:
            conn.close()
        return redirect(url_for('feed'))
    cur.execute('SELECT * FROM feed WHERE id = ?', (feed_id,)); rec = cur.fetchone(); conn.close()
    if not rec:
        flash('Feed record not found.', 'error'); return redirect(url_for('feed'))
    return render_template('feed_edit.html', record=rec)


@app.route('/add_feed', methods=['POST'])
@login_required
def add_feed():
    debug_form('add_feed', request.form)
    if current_user.role not in ['admin', 'manager']:
        flash('Access denied.', 'error'); return redirect(url_for('feed'))
    try:
        ft = request.form.get('feed_type', '').strip(); qty = float(request.form.get('quantity', '0') or 0)
        if not ft or qty <= 0:
            flash('Feed type and positive quantity required.', 'error'); return redirect(url_for('feed'))
        conn = get_db_connection(); cur = conn.cursor()
        cur.execute('INSERT INTO feed (feed_type, quantity, animal_group, feeding_time, notes) VALUES (?, ?, ?, ?, ?)',
                    (ft, qty, request.form.get('animal_group', ''), request.form.get('feeding_time'), request.form.get('notes', '')))
        conn.commit(); conn.close(); flash('Feed record added!', 'success')
    except Exception as e:
        flash(f'Error adding feed: {e}', 'error')
    return redirect(url_for('feed'))


# ----- Suppliers -----
@app.route('/suppliers')
@login_required
def suppliers():
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute('SELECT * FROM supplier ORDER BY created_at DESC'); suppliers = cur.fetchall()
    cur.execute('SELECT COUNT(*) FROM supplier'); total_suppliers = cur.fetchone()[0] or 0
    conn.close()
    return render_template('suppliers.html', suppliers=suppliers, total_suppliers=total_suppliers)


@app.route('/suppliers/<int:supplier_id>')
@login_required
def view_supplier(supplier_id):
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute('SELECT * FROM supplier WHERE id = ?', (supplier_id,)); rec = cur.fetchone(); conn.close()
    if not rec:
        flash('Supplier not found.', 'error'); return redirect(url_for('suppliers'))
    return render_template('supplier_view.html', supplier=rec)


@app.route('/suppliers/<int:supplier_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_supplier(supplier_id):
    if current_user.role != 'admin':
        flash('Access denied.', 'error'); return redirect(url_for('suppliers'))
    conn = get_db_connection(); cur = conn.cursor()
    if request.method == 'POST':
        debug_form('edit_supplier', request.form)
        try:
            cur.execute('UPDATE supplier SET company_name=?, contact_person=?, phone=?, email=?, products=?, address=?, payment_terms=?, rating=?, notes=? WHERE id=?',
                        (request.form.get('company_name', '').strip(), request.form.get('contact_person', '').strip(), request.form.get('phone', '').strip(), request.form.get('email', '').strip(), request.form.get('products', '').strip(), request.form.get('address', '').strip(), request.form.get('payment_terms', 'cod').strip(), int(request.form.get('rating', '3') or 3), request.form.get('notes', '').strip(), supplier_id))
            conn.commit(); flash('Supplier updated!', 'success')
        except Exception as e:
            flash(f'Error: {e}', 'error')
        finally:
            conn.close()
        return redirect(url_for('suppliers'))
    cur.execute('SELECT * FROM supplier WHERE id = ?', (supplier_id,)); rec = cur.fetchone(); conn.close()
    if not rec:
        flash('Supplier not found.', 'error'); return redirect(url_for('suppliers'))
    return render_template('supplier_edit.html', supplier=rec)


@app.route('/add_supplier', methods=['POST'])
@login_required
def add_supplier():
    debug_form('add_supplier', request.form)
    try:
        company = request.form.get('company_name', '').strip(); contact = request.form.get('contact_person', '').strip(); phone = request.form.get('phone', '').strip(); products = request.form.get('products', '').strip()
        if not company or not contact or not phone or not products:
            flash('Required fields missing.', 'error'); return redirect(url_for('suppliers'))
        conn = get_db_connection(); cur = conn.cursor()
        cur.execute('INSERT INTO supplier (company_name, contact_person, phone, email, products, address, payment_terms, rating, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                    (company, contact, phone, request.form.get('email', ''), products, request.form.get('address', ''), request.form.get('payment_terms', 'cod'), int(request.form.get('rating', '3') or 3), request.form.get('notes', '')))
        conn.commit(); conn.close(); flash('Supplier added!', 'success')
    except Exception as e:
        flash(f'Error adding supplier: {e}', 'error')
    return redirect(url_for('suppliers'))


# ----- Customers -----
@app.route('/customers')
@login_required
def customers():
    if current_user.role not in ['admin', 'accountant']:
        flash('Access denied.', 'error'); return redirect(url_for('dashboard'))
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute('SELECT * FROM customer ORDER BY created_at DESC'); customers = cur.fetchall()
    cur.execute('SELECT COUNT(*) FROM customer'); total_customers = cur.fetchone()[0] or 0
    conn.close()
    return render_template('customers.html', customers=customers, total_customers=total_customers)


@app.route('/customers/<int:customer_id>')
@login_required
def view_customer(customer_id):
    if current_user.role not in ['admin', 'accountant']:
        flash('Access denied.', 'error'); return redirect(url_for('customers'))
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute('SELECT * FROM customer WHERE id = ?', (customer_id,)); rec = cur.fetchone(); conn.close()
    if not rec:
        flash('Customer not found.', 'error'); return redirect(url_for('customers'))
    return render_template('customer_view.html', customer=rec)


@app.route('/customers/<int:customer_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_customer(customer_id):
    if current_user.role not in ['admin', 'accountant']:
        flash('Access denied.', 'error'); return redirect(url_for('customers'))
    conn = get_db_connection(); cur = conn.cursor()
    if request.method == 'POST':
        debug_form('edit_customer', request.form)
        try:
            cur.execute('UPDATE customer SET customer_name=?, company=?, phone=?, email=?, address=?, customer_type=?, notes=? WHERE id=?',
                        (request.form.get('customer_name', '').strip(), request.form.get('company', '').strip(), request.form.get('phone', '').strip(), request.form.get('email', '').strip(), request.form.get('address', '').strip(), request.form.get('customer_type', 'retail').strip(), request.form.get('notes', '').strip(), customer_id))
            conn.commit(); flash('Customer updated!', 'success')
        except Exception as e:
            flash(f'Error: {e}', 'error')
        finally:
            conn.close()
        return redirect(url_for('customers'))
    cur.execute('SELECT * FROM customer WHERE id = ?', (customer_id,)); rec = cur.fetchone(); conn.close()
    if not rec:
        flash('Customer not found.', 'error'); return redirect(url_for('customers'))
    return render_template('customer_edit.html', customer=rec)


@app.route('/add_customer', methods=['POST'])
@login_required
def add_customer():
    debug_form('add_customer', request.form)
    try:
        cname = request.form.get('customer_name', '').strip(); phone = request.form.get('phone', '').strip()
        if not cname or not phone:
            flash('Required fields missing.', 'error'); return redirect(url_for('customers'))
        conn = get_db_connection(); cur = conn.cursor()
        cur.execute('INSERT INTO customer (customer_name, company, phone, email, address, customer_type, notes) VALUES (?, ?, ?, ?, ?, ?, ?)',
                    (cname, request.form.get('company', ''), phone, request.form.get('email', ''), request.form.get('address', ''), request.form.get('customer_type', 'retail'), request.form.get('notes', '')))
        conn.commit(); conn.close(); flash('Customer added!', 'success')
    except Exception as e:
        flash(f'Error: {e}', 'error')
    return redirect(url_for('customers'))


# ----- Financial -----@app.route('/financial')
# ----- Financial -----
@app.route('/financial', endpoint='financial')
@login_required
def financial():
    if current_user.role not in ['admin', 'accountant']:
        flash('Access denied.', 'error')
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute('SELECT * FROM financial ORDER BY created_at DESC')
        financial_records = cur.fetchall()

        cur.execute('SELECT SUM(amount) FROM financial WHERE transaction_type = ?', ('income',))
        total_income = cur.fetchone()[0] or 0

        cur.execute('SELECT SUM(amount) FROM financial WHERE transaction_type = ?', ('expense',))
        total_expense = cur.fetchone()[0] or 0

        net_profit = total_income - total_expense

        cur.execute('SELECT COUNT(*) FROM financial')
        total_financial_records = cur.fetchone()[0] or 0
    except Exception:
        # If any DB error, present empty/defaults but allow page to render
        financial_records = []
        total_income = 0
        total_expense = 0
        net_profit = 0
        total_financial_records = 0
    finally:
        conn.close()

    return render_template(
        'financial.html',
        financial_records=financial_records,
        total_income=total_income,
        total_expense=total_expense,
        net_profit=net_profit,
        total_financial_records=total_financial_records
    )


@app.route('/financial/<int:record_id>', endpoint='view_financial')
@login_required
def view_financial(record_id):
    if current_user.role not in ['admin', 'accountant']:
        flash('Access denied.', 'error')
        return redirect(url_for('financial'))

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute('SELECT * FROM financial WHERE id = ?', (record_id,))
        rec = cur.fetchone()
    finally:
        conn.close()

    if not rec:
        flash('Financial record not found.', 'error')
        return redirect(url_for('financial'))

    return render_template('financial_view.html', record=rec)


@app.route('/financial/<int:record_id>/edit', methods=['GET', 'POST'], endpoint='edit_financial')
@login_required
def edit_financial(record_id):
    if current_user.role not in ['admin', 'accountant']:
        flash('Access denied.', 'error')
        return redirect(url_for('financial'))

    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == 'POST':
        debug_form('edit_financial', request.form)
        try:
            cur.execute(
                'UPDATE financial SET transaction_type=?, amount=?, category=?, description=?, transaction_date=?, reference=? WHERE id=?',
                (
                    request.form.get('transaction_type', '').strip(),
                    float(request.form.get('amount', '0') or 0),
                    request.form.get('category', '').strip(),
                    request.form.get('description', '').strip(),
                    request.form.get('transaction_date'),
                    request.form.get('reference', '').strip(),
                    record_id
                )
            )
            conn.commit()
            flash('Financial record updated!', 'success')
        except Exception as e:
            flash(f'Error: {e}', 'error')
        finally:
            conn.close()
        return redirect(url_for('financial'))

    # GET
    try:
        cur = conn.cursor()
        cur.execute('SELECT * FROM financial WHERE id = ?', (record_id,))
        rec = cur.fetchone()
    finally:
        conn.close()

    if not rec:
        flash('Financial record not found.', 'error')
        return redirect(url_for('financial'))

    return render_template('financial_edit.html', record=rec)


@app.route('/add_financial', methods=['POST'], endpoint='add_financial')
@login_required
def add_financial():
    debug_form('add_financial', request.form)
    if current_user.role not in ['admin', 'accountant']:
        flash('Access denied.', 'error')
        return redirect(url_for('financial'))

    try:
        ttype = request.form.get('type', '').strip()
        amount = float(request.form.get('amount', '0') or 0)
        if not ttype or amount <= 0 or not request.form.get('category') or not request.form.get('description'):
            flash('Required fields missing.', 'error')
            return redirect(url_for('financial'))

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            'INSERT INTO financial (transaction_type, amount, category, description, transaction_date, reference) VALUES (?, ?, ?, ?, ?, ?)',
            (
                ttype,
                amount,
                request.form.get('category', '').strip(),
                request.form.get('description', '').strip(),
                request.form.get('transaction_date'),
                request.form.get('reference', '')
            )
        )
        conn.commit()
        conn.close()
        flash('Financial transaction added!', 'success')
    except Exception as e:
        flash(f'Error: {e}', 'error')

    return redirect(url_for('financial'))



# ----- Staff (list/view/edit/add) -----
@app.route('/staff')
@login_required
def staff():
    if current_user.role != 'admin':
        flash('Access denied.', 'error'); return redirect(url_for('dashboard'))
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute('SELECT * FROM staff ORDER BY created_at DESC'); staff_members = cur.fetchall()
    cur.execute("SELECT COUNT(*) FROM staff"); total_staff = cur.fetchone()[0] or 0
    cur.execute("SELECT COUNT(*) FROM staff WHERE status = 'Active'"); active_today = cur.fetchone()[0] or 0
    cur.execute("SELECT COUNT(*) FROM staff WHERE status IN ('On Leave','Leave')"); on_leave = cur.fetchone()[0] or 0
    cur.execute("SELECT COUNT(*) FROM task WHERE status IN ('Pending','In Progress')"); active_tasks = cur.fetchone()[0] or 0
    conn.close()
    return render_template('staff.html', staff_members=staff_members, total_staff=total_staff, active_today=active_today, on_leave=on_leave, active_tasks=active_tasks)


@app.route('/staff/<int:staff_id>')
@login_required
def view_staff(staff_id):
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute('SELECT * FROM staff WHERE id = ?', (staff_id,)); s = cur.fetchone(); conn.close()
    if not s:
        flash('Staff member not found.', 'error'); return redirect(url_for('staff'))
    return render_template('staff_view.html', staff=s)


@app.route('/staff/<int:staff_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_staff(staff_id):
    if current_user.role != 'admin':
        flash('Access denied.', 'error'); return redirect(url_for('staff'))
    conn = get_db_connection(); cur = conn.cursor()
    if request.method == 'POST':
        debug_form('edit_staff', request.form)
        try:
            cur.execute('UPDATE staff SET first_name=?, last_name=?, position=?, department=?, email=?, phone=?, status=?, id_number=? WHERE id=?',
                        (request.form.get('first_name', '').strip(), request.form.get('last_name', '').strip(), request.form.get('position', '').strip(), request.form.get('department', '').strip(), request.form.get('email', '').strip(), request.form.get('phone', '').strip(), request.form.get('status', 'Active').strip(), staff_id))
            conn.commit(); flash('Staff updated!', 'success')
        except Exception as e:
            flash(f'Error: {e}', 'error')
        finally:
            conn.close()
        return redirect(url_for('staff'))
    cur.execute('SELECT * FROM staff WHERE id = ?', (staff_id,)); s = cur.fetchone(); conn.close()
    if not s:
        flash('Staff member not found.', 'error'); return redirect(url_for('staff'))
    return render_template('staff_edit.html', staff=s)


@app.route('/add_staff', methods=['POST'])
@login_required
def add_staff():
    debug_form('add_staff', request.form)
    if current_user.role != 'admin':
        flash('Access denied.', 'error'); return redirect(url_for('staff'))
    try:
        fn = request.form.get('first_name', '').strip(); ln = request.form.get('last_name', '').strip(); pos = request.form.get('position', '').strip(); phone = request.form.get('phone', '').strip()
        if not fn or not ln or not pos or not phone:
            flash('Required fields missing.', 'error'); return redirect(url_for('staff'))
        conn = get_db_connection(); cur = conn.cursor()
        cur.execute('INSERT INTO staff (first_name, last_name, position, department, email, phone, address, dob, date_employed, id_number) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                    (fn, ln, pos, request.form.get('department', ''), request.form.get('email', ''), phone, request.form.get('address', ''), request.form.get('dob'), request.form.get('date_employed')))
        conn.commit(); conn.close(); flash('Staff member added!', 'success')
    except Exception as e:
        flash(f'Error: {e}', 'error')
    return redirect(url_for('staff'))


# ----- Tasks list/add + status update -----
# ----- Tasks list/add + status update -----
@app.route('/tasks')
@login_required
def tasks():
    conn = get_db_connection()
    cur = conn.cursor()

    # Fetch tasks
    try:
        cur.execute('SELECT * FROM task ORDER BY due_date')
        tasks = cur.fetchall()
    except Exception:
        tasks = []

    # Fetch staff members for the dropdown (convert rows -> dicts)
    try:
        cur.execute('SELECT id, first_name, last_name FROM staff ORDER BY first_name')
        rows = cur.fetchall()
        cols = [c[0] for c in cur.description] if cur.description else []
        staff_members = [dict(zip(cols, r)) for r in rows]
        # map of id -> "First Last" for display in the tasks table
        staff_map = { str(s['id']): f"{s['first_name']} {s['last_name']}" for s in staff_members }
    except Exception:
        staff_members = []
        staff_map = {}

    # Fetch task counts
    try:
        cur.execute("SELECT COUNT(*) FROM task WHERE status = 'Pending'")
        pending_count = cur.fetchone()[0] or 0
    except Exception:
        pending_count = 0

    try:
        cur.execute("SELECT COUNT(*) FROM task WHERE status = 'In Progress'")
        inprogress_count = cur.fetchone()[0] or 0
    except Exception:
        inprogress_count = 0

    try:
        cur.execute("SELECT COUNT(*) FROM task WHERE status = 'Completed'")
        completed_count = cur.fetchone()[0] or 0
    except Exception:
        completed_count = 0

    try:
        today_str = date.today().isoformat()
        cur.execute("SELECT COUNT(*) FROM task WHERE due_date IS NOT NULL AND due_date < ? AND status != 'Completed'", (today_str,))
        overdue_count = cur.fetchone()[0] or 0
    except Exception:
        overdue_count = 0

    conn.close()

    return render_template('tasks.html',
                          tasks=tasks,
                          pending_count=pending_count,
                          inprogress_count=inprogress_count,
                          completed_count=completed_count,
                          overdue_count=overdue_count,
                          staff_members=staff_members,
                          staff_map=staff_map)

@app.route('/add_task', methods=['POST'])
@login_required
def add_task():
    debug_form('add_task', request.form)
    try:
        title = request.form.get('title', '').strip()
        if not title:
            flash('Task title is required.', 'error')
            return redirect(url_for('tasks'))
        
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('INSERT INTO task (title, description, assigned_to, status, priority, due_date, category) VALUES (?, ?, ?, ?, ?, ?, ?)',
                    (title, 
                     request.form.get('description', ''), 
                     request.form.get('assigned_to', ''), 
                     'Pending', 
                     request.form.get('priority', 'Normal'), 
                     request.form.get('due_date'), 
                     request.form.get('category', 'general')))
        conn.commit()
        conn.close()
        flash('Task added!', 'success')
    except Exception as e:
        flash(f'Error adding task: {e}', 'error')
    return redirect(url_for('tasks'))


# ----- NEW: task view & edit routes (added to resolve BuildError for view/edit links) -----
@app.route('/tasks/<int:task_id>')
@login_required
def view_task(task_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM task WHERE id = ?', (task_id,))
    task = cur.fetchone()
    conn.close()
    if not task:
        flash('Task not found.', 'error')
        return redirect(url_for('tasks'))
    return render_template('task_view.html', task=task)


@app.route('/tasks/<int:task_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_task(task_id):
    # restrict edits to admin/manager to match your other patterns
    if current_user.role not in ['admin', 'manager']:
        flash('Access denied.', 'error')
        return redirect(url_for('tasks'))

    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == 'POST':
        debug_form('edit_task', request.form)
        try:
            cur.execute('UPDATE task SET title=?, description=?, assigned_to=?, status=?, priority=?, due_date=?, category=? WHERE id=?',
                        (request.form.get('title', '').strip(),
                         request.form.get('description', '').strip(),
                         request.form.get('assigned_to', '').strip(),
                         request.form.get('status', 'Pending'),
                         request.form.get('priority', 'Normal'),
                         request.form.get('due_date'),
                         request.form.get('category', 'general'),
                         task_id))
            conn.commit()
            flash('Task updated!', 'success')
        except Exception as e:
            flash(f'Error updating task: {e}', 'error')
        finally:
            conn.close()
        return redirect(url_for('tasks'))

    # GET: fetch the task
    cur.execute('SELECT * FROM task WHERE id = ?', (task_id,))
    task = cur.fetchone()
    conn.close()
    if not task:
        flash('Task not found.', 'error')
        return redirect(url_for('tasks'))

    # Also fetch staff list for the edit form dropdown (convert to dicts)
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute('SELECT id, first_name, last_name FROM staff ORDER BY first_name')
        rows = cur.fetchall()
        cols = [c[0] for c in cur.description] if cur.description else []
        staff_members = [dict(zip(cols, r)) for r in rows]
    except Exception:
        staff_members = []
    finally:
        conn.close()

    return render_template('task_edit.html', task=task, staff_members=staff_members)
@app.route('/tasks/<int:task_id>/delete', methods=['POST'])
@login_required
def delete_task(task_id):
    # permission guard (matches your edit pattern)
    if current_user.role not in ['admin', 'manager']:
        flash('Access denied.', 'error')
        return redirect(url_for('tasks'))

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Optionally: you could check the task exists first
        cur.execute('SELECT id, title FROM task WHERE id = ?', (task_id,))
        found = cur.fetchone()
        if not found:
            flash('Task not found.', 'error')
            return redirect(url_for('tasks'))

        cur.execute('DELETE FROM task WHERE id = ?', (task_id,))
        conn.commit()
        flash(f"Task T-{task_id} deleted.", 'success')
    except Exception as e:
        conn.rollback()
        flash(f"Error deleting task: {e}", 'error')
    finally:
        conn.close()

    return redirect(url_for('tasks'))


# ----- END new task view/edit routes -----


@app.route('/update_task_status', methods=['POST'])
@login_required
def update_task_status():
    try:
        data = request.get_json()
        task_id = data.get('task_id')
        status = data.get('status')
        if not task_id or not status:
            return jsonify({'success': False, 'message': 'Missing data'})
        
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('UPDATE task SET status = ? WHERE id = ?', (status, task_id))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Task status updated'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
# ----- Reports -----
@app.route('/reports')
@login_required
def reports():
    """
    Render reports page and pass recent_reports (most recent 50) from DB.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT id, report_name, report_type, format, filepath, period_start, period_end, generated_by, notes, created_at
            FROM reports
            ORDER BY created_at DESC
            LIMIT 50
        """)
        recent_reports = cur.fetchall()
    except Exception as e:
        print("Error fetching recent reports:", e)
        recent_reports = []
    finally:
        conn.close()
    return render_template('reports.html', recent_reports=recent_reports)


@app.route('/generate-report', methods=['POST'])
@login_required
def generate_report():
    """
    Generate a report. For CSV/Excel we produce a CSV file in static/exports,
    insert a metadata row into `reports`, and return the CSV for download.
    Other formats simply flash and redirect (can be extended later).
    """
    report_type = (request.form.get('report_type') or 'custom').strip().lower()
    report_format = (request.form.get('format') or 'pdf').strip().lower()
    start_date = request.form.get('start_date') or request.form.get('start') or ''
    end_date = request.form.get('end_date') or request.form.get('end') or ''
    period = (request.form.get('period') or '').strip()
    generated_by = getattr(current_user, 'username', 'system')

    print("GENERATE_REPORT called", {'user': generated_by, 'type': report_type, 'format': report_format})

    # Only CSV/Excel handled server-side here (safe, simple)
    if report_format in ('csv', 'excel'):
        try:
            conn = get_db_connection(); cur = conn.cursor()

            # Build rows and headers depending on report_type
            if report_type == 'staff':
                cur.execute("SELECT first_name, last_name, position, department, email, phone FROM staff ORDER BY created_at DESC")
                headers = ['first_name', 'last_name', 'position', 'department', 'email', 'phone']
            elif report_type == 'financial':
                cur.execute("SELECT transaction_date, transaction_type, category, amount, description FROM financial ORDER BY transaction_date DESC")
                headers = ['transaction_date', 'transaction_type', 'category', 'amount', 'description']
            elif report_type in ('livestock', 'breeding'):
                cur.execute("SELECT id, tag_number, breed, birth_date, weight, status FROM animal ORDER BY created_at DESC")
                headers = ['id', 'tag_number', 'breed', 'birth_date', 'weight', 'status']
            elif report_type == 'feed':
                cur.execute("SELECT created_at, feed_type, quantity, animal_group FROM feed ORDER BY created_at DESC")
                headers = ['created_at', 'feed_type', 'quantity', 'animal_group']
            else:
                # default to tasks
                cur.execute("SELECT id, title, status, due_date, created_at FROM task ORDER BY created_at DESC")
                headers = ['id', 'title', 'status', 'due_date', 'created_at']

            rows = cur.fetchall()
            conn.close()

            # prepare CSV text
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(headers)
            for r in rows:
                # sqlite3.Row -> allow index access matching headers where possible
                row_vals = []
                try:
                    # r.keys() exists because row_factory=sqlite3.Row
                    for h in headers:
                        if h in r.keys():
                            row_vals.append(r[h])
                        else:
                            # fallback to index by position
                            row_vals.append(list(r)[headers.index(h)] if headers.index(h) < len(list(r)) else '')
                except Exception:
                    row_vals = list(r)
                writer.writerow(row_vals)
            csv_data = output.getvalue()
            output.close()

            # ensure exports dir exists
            exports_dir = BASE_DIR / 'static' / 'exports'
            exports_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            ext = 'csv'
            filename = f"{report_type}_report_{timestamp}.{ext}"
            file_path = exports_dir / filename

            # write file to disk
            file_path.write_text(csv_data, encoding='utf-8')

            # insert metadata row into reports table (best-effort)
            try:
                conn = get_db_connection(); cur = conn.cursor()
                cur.execute("""
                    INSERT INTO reports (report_name, report_type, format, filepath, period_start, period_end, generated_by, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    f"{report_type.capitalize()} report {timestamp}",
                    report_type,
                    report_format,
                    f"exports/{filename}",
                    start_date or None,
                    end_date or None,
                    generated_by,
                    f"period={period}"
                ))
                conn.commit()
                conn.close()
            except Exception as me:
                print("Warning: could not save reports metadata:", me)

            # return CSV as attachment for immediate download
            response = make_response(csv_data)
            response.headers['Content-Disposition'] = f'attachment; filename={filename}'
            response.headers['Content-Type'] = 'text/csv; charset=utf-8'
            return response

        except Exception as e:
            print("Error generating report:", e)
            traceback.print_exc()
            flash(f"Error: {e}", "error")
            return redirect(url_for('reports'))

    # fallback for other formats
    flash(f"{report_type.capitalize()} report request received (format: {report_format}).", "success")
    return redirect(url_for('reports'))


# ----- Settings and user management -----
@app.route('/settings')
@login_required
def settings():
    if current_user.role != 'admin':
        flash('Access denied.', 'error'); return redirect(url_for('dashboard'))
    return render_template('settings.html')


@app.route('/update_settings', methods=['POST'])
@login_required
def update_settings():
    if current_user.role != 'admin':
        flash('Access denied.', 'error'); return redirect(url_for('settings'))
    try:
        flash('Settings updated successfully!', 'success')
    except Exception as e:
        flash(f'Error updating settings: {e}', 'error')
    return redirect(url_for('settings'))


@app.route('/add_user', methods=['POST'])
@login_required
def add_user():
    debug_form('add_user', request.form)
    if current_user.role != 'admin':
        flash('Access denied.', 'error'); return redirect(url_for('settings'))
    try:
        username = request.form.get('username', '').strip(); email = request.form.get('email', '').strip(); password = request.form.get('password', '')
        if not username or not email or not password:
            flash('All fields are required.', 'error'); return redirect(url_for('settings'))
        conn = get_db_connection(); cur = conn.cursor()
        cur.execute('SELECT id FROM user WHERE username = ? OR email = ?', (username, email))
        if cur.fetchone():
            flash('Username or email already exists.', 'error'); conn.close(); return redirect(url_for('settings'))
        cur.execute('INSERT INTO user (username, email, password, role) VALUES (?, ?, ?, ?)', (username, email, generate_password_hash(password), request.form.get('role', 'staff')))
        conn.commit(); conn.close(); flash('User added!', 'success')
    except Exception as e:
        flash(f'Error adding user: {e}', 'error')
    return redirect(url_for('settings'))


# ----- Run server -----

# --- API: delete task (AJAX) ---
# Renamed the function and endpoint to avoid endpoint-name collision with the
# /tasks/<int:task_id>/delete route which uses endpoint 'delete_task'.
@app.route('/delete_task', methods=['POST'], endpoint='delete_task_ajax')
@login_required
def delete_task_ajax():
    try:
        # accept either form-encoded or JSON body
        payload = request.get_json(silent=True)
        task_id = request.form.get('task_id') or (payload or {}).get('task_id')
        if not task_id:
            return jsonify({'success': False, 'message': 'Missing task_id'})
        conn = get_db_connection(); cur = conn.cursor()
        cur.execute('DELETE FROM task WHERE id = ?', (task_id,))
        conn.commit(); conn.close()
        return jsonify({'success': True, 'message': 'Task deleted'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


if __name__ == '__main__':
    print("=" * 60); print("DL FARM MANAGEMENT SYSTEM - COMPLETE"); print("=" * 60)
    try:
        conn = sqlite3.connect(str(DB_PATH)); cur = conn.cursor(); cur.execute('SELECT username, role FROM user'); users = cur.fetchall(); print("Existing users:");
        for u in users: print(f" - {u[0]} ({u[1]})")
        conn.close()
    except Exception as e:
        print("Error checking DB:", e)
    print("Starting server: http://localhost:5000"); print("=" * 60)
    app.run(debug=True, host='0.0.0.0', port=5000)

def init_database():
    conn = get_db_connection()
    cur = conn.cursor()
    
    # create core tables (idempotent)
    cur.execute('''
        CREATE TABLE IF NOT EXISTS user (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS staff (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            position TEXT NOT NULL,
            department TEXT,
            email TEXT,
            phone TEXT NOT NULL,
            address TEXT,
            dob DATE,
            date_employed DATE,
            status TEXT DEFAULT 'Active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # add default users if none
    cur.execute('SELECT COUNT(*) FROM user')
    if cur.fetchone()[0] == 0:
        defaults = [
            ('admin', 'admin@dlfarm.com', generate_password_hash('admin123'), 'admin'),
            ('manager', 'manager@dlfarm.com', generate_password_hash('manager123'), 'manager'),
            ('accountant', 'accountant@dlfarm.com', generate_password_hash('accountant123'), 'accountant'),
        ]
        for u, e, p, r in defaults:
            cur.execute(
                'INSERT OR IGNORE INTO user (username, email, password, role) VALUES (?, ?, ?, ?)',
                (u, e, p, r)
            )
        print("✓ Created default users")

    # sample staff
    cur.execute('SELECT COUNT(*) FROM staff')
    if cur.fetchone()[0] == 0:
        sample_staff = [
            ('James', 'Kipianui Rotich', 'Farm Manager', 'Management', 'james@dlfarm.com', '0721368651', 'Eldoret', '1985-03-15', '2020-01-10'),
            ('Michael', 'Kemboi', 'Mechanic', 'Maintenance', 'michael@dlfarm.com', '0720977192', 'Eldoret', '1990-07-22', '2021-03-05'),
            ('Nicholas', 'Yego', 'Accountant', 'Finance', 'nicholas@dlfarm.com', '0712441667', 'Eldoret', '1988-11-30', '2019-08-15'),
        ]

        for fn, ln, pos, dept, email, phone, addr, dob, emp_date in sample_staff:
            cur.execute(
                'INSERT INTO staff (first_name, last_name, position, department, email, phone, address, dob, date_employed) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (fn, ln, pos, dept, email, phone, addr, dob, emp_date)
            )
        print("✓ Created sample staff")

    conn.commit()
    conn.close()
    print("✓ Database initialized")

if __name__ == '__main__':
    init_database()
    app.run(debug=True)
