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
    # app.py (add once, near app creation / imports)
from flask import url_for
from werkzeug.routing import BuildError

def endpoint_exists(endpoint_name):
    """Return True if `url_for(endpoint_name)` can be built (endpoint registered)."""
    try:
        url_for(endpoint_name)
        return True
    except BuildError:
        return False

# make it available in all templates
app.jinja_env.globals['endpoint_exists'] = endpoint_exists



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

# --- Replace your previous generate_report route with this conditional registration block ---

# --- BEGIN fixed single safe generate_report implementation (paste into app.py routes area) ---
import os
import csv
import datetime as _dt
from werkzeug.utils import secure_filename
from flask import request, redirect, url_for, flash
from flask_login import current_user, login_required

REPORTS_DIR = os.path.join(os.path.dirname(__file__), 'static', 'reports')
os.makedirs(REPORTS_DIR, exist_ok=True)

# --- add this single generate_report route to app.py (remove other duplicates) ---
# -> paste this into app.py (ONLY ONCE). Remove any duplicate generate_report routes first.
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required
import sqlite3
from flask import request, redirect, url_for, render_template, flash
import sqlite3, os
from datetime import date

def get_db_path():
    dburl = os.environ.get('DATABASE_URL','sqlite:////home/iqfrizqe/public_html/data.db')
    if dburl.startswith('sqlite:///'):
        return dburl.split('sqlite:///',1)[1]
    return dburl

# --- BEGIN: Production routes (ADD THIS BLOCK) ---
from flask import request, redirect, url_for, render_template, abort, jsonify, flash

from flask import Response, jsonify, request, flash, redirect, url_for, render_template, abort
from flask_login import login_required

@app.route('/production')
@login_required
def production_list():
    """List production records"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        # include production_type, health_status and an explicit animal_name fallback
        cur.execute("""
            SELECT p.id, p.record_date, p.animal_id, p.animal_name, p.production_type, p.health_status,
                   p.quantity, p.unit, p.notes, p.recorded_by, p.created_at, p.updated_at,
                   a.id AS a_id, a.breed AS a_breed, a.tag_number AS a_tag
              FROM production p
              LEFT JOIN animals a ON a.id = p.animal_id
             ORDER BY p.record_date DESC, p.id DESC
        """)
        rows = cur.fetchall()
        records = rows_to_objs(rows, cur)

        # total count (fixed)
        cur.execute("SELECT COUNT(*) FROM production")
        production_total = cur.fetchone()[0]
    except Exception:
        try:
            app.logger.exception("production_list error")
        except Exception:
            pass
        records = []
        production_total = 0
    finally:
        if conn:
            conn.close()

    # keep template context minimal and safe
    return render_template('production_list.html',
                           records=records,
                           production_total=production_total)


@app.route('/production/add', methods=['GET', 'POST'])
@login_required
def production_create():
    """Create a new production record (form GET or create POST)"""
    conn = None
    if request.method == 'GET':
        # need animals list for the select
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT id, breed, tag_number FROM animals ORDER BY id")
            animals = rows_to_objs(cur.fetchall(), cur)
        except Exception:
            animals = []
        finally:
            if conn:
                conn.close()
        return render_template('edit_production.html', record=None, animals=animals, creating=True)

    # POST - insert
    form = request.form
    record_date = form.get('record_date') or None
    # accept both animal_id (preferred) and animal_name (fallback from your modal)
    animal_id = form.get('animal_id') or None
    animal_name = form.get('animal_name') or None
    production_type = form.get('production_type') or None
    health_status = form.get('health_status') or None
    quantity = form.get('quantity') or None
    unit = form.get('unit') or None
    notes = form.get('notes') or None
    recorded_by = form.get('recorded_by') or None

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # If only animal_name provided, try to resolve to an animals.id (breed or tag_number)
        if not animal_id and animal_name:
            try:
                cur.execute("SELECT id FROM animals WHERE breed = ? OR tag_number = ? LIMIT 1", (animal_name, animal_name))
                arow = cur.fetchone()
                if arow:
                    animal_id = arow[0]
            except Exception:
                # ignore lookup failures — we'll store the animal_name into the production record (if column exists)
                animal_id = None

        # Insert with production_type and health_status, and also save animal_name for fallbacks
        cur.execute("""
            INSERT INTO production (record_date, animal_id, animal_name, production_type, health_status,
                                    quantity, unit, notes, recorded_by, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """, (
                record_date,
                animal_id or None,
                animal_name or None,
                production_type or None,
                health_status or None,
                quantity or None,
                unit or None,
                notes or None,
                recorded_by or None
            ))
        conn.commit()
    except Exception as e:
        app.logger.exception("production_create error")
        try:
            flash('Failed to create record: {}'.format(str(e)), 'danger')
        except Exception:
            pass
        return redirect(url_for('production_list'))
    finally:
        if conn:
            conn.close()

    return redirect(url_for('production_list'))


@app.route('/production/<int:record_id>')
@login_required
def view_production(record_id):
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        # p.* includes the fields we inserted (animal_name, production_type, health_status, etc.)
        cur.execute("""
            SELECT p.*, a.id AS a_id, a.breed AS a_breed, a.tag_number AS a_tag
              FROM production p
              LEFT JOIN animals a ON a.id = p.animal_id
             WHERE p.id = ?
            """, (record_id,))
        row = cur.fetchone()
        if not row:
            abort(404)
        record = rows_to_objs([row], cur)[0]
    except Exception:
        app.logger.exception("view_production error")
        abort(500)
    finally:
        if conn:
            conn.close()
    return render_template('view_production.html', record=record)


@app.route('/production/<int:record_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_production(record_id):
    conn = None
    if request.method == 'GET':
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT id, breed, tag_number FROM animals ORDER BY id")
            animals = rows_to_objs(cur.fetchall(), cur)
            cur.execute("SELECT * FROM production WHERE id = ?", (record_id,))
            row = cur.fetchone()
            if not row:
                abort(404)
            record = rows_to_objs([row], cur)[0]
        except Exception:
            app.logger.exception("edit_production GET error")
            abort(500)
        finally:
            if conn:
                conn.close()
        return render_template('edit_production.html', record=record, animals=animals, creating=False)

    # POST -> update
    form = request.form
    record_date = form.get('record_date') or None
    animal_id = form.get('animal_id') or None
    animal_name = form.get('animal_name') or None
    production_type = form.get('production_type') or None
    health_status = form.get('health_status') or None
    quantity = form.get('quantity') or None
    unit = form.get('unit') or None
    notes = form.get('notes') or None
    recorded_by = form.get('recorded_by') or None

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # If only animal_name provided, try to resolve to animals.id
        if not animal_id and animal_name:
            try:
                cur.execute("SELECT id FROM animals WHERE breed = ? OR tag_number = ? LIMIT 1", (animal_name, animal_name))
                arow = cur.fetchone()
                if arow:
                    animal_id = arow[0]
            except Exception:
                animal_id = None

        # Update record, set updated_at
        cur.execute("""
            UPDATE production
               SET record_date = ?, animal_id = ?, animal_name = ?, production_type = ?, health_status = ?,
                   quantity = ?, unit = ?, notes = ?, recorded_by = ?, updated_at = datetime('now')
             WHERE id = ?
            """, (
                record_date,
                animal_id or None,
                animal_name or None,
                production_type or None,
                health_status or None,
                quantity or None,
                unit or None,
                notes or None,
                recorded_by or None,
                record_id
            ))
        conn.commit()
    except Exception:
        app.logger.exception("edit_production POST error")
        try:
            flash('Failed to update record', 'danger')
        except Exception:
            pass
        return redirect(url_for('production_list'))
    finally:
        if conn:
            conn.close()

    return redirect(url_for('view_production', record_id=record_id))


@app.route('/production/<int:record_id>/delete', methods=['POST'])
@login_required
def delete_production(record_id):
    # conservative delete with confirm token optional
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM production WHERE id = ?", (record_id,))
        conn.commit()
        # If the request appears to be an AJAX/fetch call, return JSON ok for the front-end JS
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.headers.get('Accept', '').find('application/json') != -1:
            return jsonify({'ok': True}), 200
    except Exception:
        app.logger.exception("delete_production error")
        # still attempt to return something meaningful for AJAX callers
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.headers.get('Accept', '').find('application/json') != -1:
            return jsonify({'ok': False}), 500
    finally:
        try:
            if conn:
                conn.close()
        except Exception:
            pass
    # fallback for non-AJAX callers (forms) - redirect to list
    return redirect(url_for('production_list'))


# --- END: Production routes (ADD THIS BLOCK) ---
# ---------------- Inventory routes ----------------
@app.route('/inventory')
@login_required
def inventory_list():
    """List inventory items and quick actions for check in/out"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT i.id, i.item_name, i.sku, i.quantity_on_hand, i.location, i.notes,
                   i.created_at, i.updated_at,
                   (SELECT COUNT(*) FROM inventory_tx tx WHERE tx.inventory_id = i.id AND tx.tx_type = 'in') as total_in,
                   (SELECT COUNT(*) FROM inventory_tx tx WHERE tx.inventory_id = i.id AND tx.tx_type = 'out') as total_out
            FROM inventory i
            ORDER BY i.item_name COLLATE NOCASE
        """)
        rows = cur.fetchall()
        items = rows_to_objs(rows, cur)
    except Exception:
        try:
            app.logger.exception("inventory_list error")
        except Exception:
            pass
        items = []
    finally:
        if conn:
            conn.close()

    return render_template('inventory_list.html', items=items)


@app.route('/inventory/add', methods=['GET', 'POST'])
@login_required
def inventory_create():
    if request.method == 'GET':
        return render_template('edit_inventory.html', item=None, creating=True)
    # POST -> insert
    form = request.form
    item_name = form.get('item_name') or None
    sku = form.get('sku') or None
    quantity = form.get('quantity') or 0
    location = form.get('location') or None
    notes = form.get('notes') or None

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO inventory (item_name, sku, quantity_on_hand, location, notes, created_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
        """, (item_name, sku, int(quantity or 0), location, notes))
        conn.commit()
    except Exception as e:
        app.logger.exception("inventory_create error")
        try:
            flash('Failed to create inventory item: {}'.format(str(e)), 'danger')
        except Exception:
            pass
        return redirect(url_for('inventory_list'))
    finally:
        if conn:
            conn.close()
    return redirect(url_for('inventory_list'))


@app.route('/inventory/<int:item_id>')
@login_required
def view_inventory(item_id):
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM inventory WHERE id = ?", (item_id,))
        row = cur.fetchone()
        if not row:
            abort(404)
        item = rows_to_objs([row], cur)[0]

        # fetch recent transactions
        cur.execute("""
            SELECT id, inventory_id, tx_type, quantity, reference, notes, performed_by, tx_date
              FROM inventory_tx
             WHERE inventory_id = ?
             ORDER BY tx_date DESC, id DESC
             LIMIT 100
        """, (item_id,))
        tx_rows = cur.fetchall()
        txs = rows_to_objs(tx_rows, cur)
    except Exception:
        app.logger.exception("view_inventory error")
        abort(500)
    finally:
        if conn:
            conn.close()
    return render_template('view_inventory.html', item=item, txs=txs)


@app.route('/inventory/<int:item_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_inventory(item_id):
    conn = None
    if request.method == 'GET':
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT * FROM inventory WHERE id = ?", (item_id,))
            row = cur.fetchone()
            if not row:
                abort(404)
            item = rows_to_objs([row], cur)[0]
        except Exception:
            app.logger.exception("edit_inventory GET error")
            abort(500)
        finally:
            if conn:
                conn.close()
        return render_template('edit_inventory.html', item=item, creating=False)

    # POST -> update
    form = request.form
    item_name = form.get('item_name') or None
    sku = form.get('sku') or None
    quantity = form.get('quantity') or None
    location = form.get('location') or None
    notes = form.get('notes') or None

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE inventory
               SET item_name = ?, sku = ?, quantity_on_hand = ?, location = ?, notes = ?, updated_at = datetime('now')
             WHERE id = ?
        """, (item_name, sku, int(quantity or 0), location, notes, item_id))
        conn.commit()
    except Exception:
        app.logger.exception("edit_inventory POST error")
        try:
            flash('Failed to update item', 'danger')
        except Exception:
            pass
        return redirect(url_for('inventory_list'))
    finally:
        if conn:
            conn.close()
    return redirect(url_for('view_inventory', item_id=item_id))


@app.route('/inventory/<int:item_id>/delete', methods=['POST'])
@login_required
def delete_inventory(item_id):
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM inventory WHERE id = ?", (item_id,))
        conn.commit()
        # respond JSON for AJAX calls
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'ok': True})
    except Exception:
        app.logger.exception("delete_inventory error")
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'ok': False}), 500
    finally:
        if conn:
            conn.close()
    return redirect(url_for('inventory_list'))


@app.route('/inventory/<int:item_id>/tx', methods=['POST'])
@login_required
def inventory_tx(item_id):
    """
    Process a check-in (tx_type='in') or check-out (tx_type='out').
    Accepts JSON or form POST:
      - tx_type: 'in' or 'out'
      - quantity: integer (>0)
      - reference: optional string (delivery note, PO, etc.)
      - notes, performed_by (optional)
    Returns JSON for AJAX callers and redirects for form callers.
    """
    data = request.get_json(silent=True) or request.form
    tx_type = (data.get('tx_type') or '').lower()
    try:
        qty = int(data.get('quantity') or 0)
    except Exception:
        qty = 0
    reference = data.get('reference') or None
    notes = data.get('notes') or None
    performed_by = data.get('performed_by') or (getattr(current_user, 'name', None) or None)
    tx_date = datetime.datetime.utcnow().isoformat(sep=' ')

    if tx_type not in ('in', 'out') or qty <= 0:
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'ok': False, 'error': 'invalid payload'}), 400
        flash('Invalid transaction', 'danger')
        return redirect(url_for('view_inventory', item_id=item_id))

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        # Insert transaction
        cur.execute("""
            INSERT INTO inventory_tx (inventory_id, tx_type, quantity, reference, notes, performed_by, tx_date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (item_id, tx_type, qty, reference, notes, performed_by, tx_date))

        # Update quantity_on_hand
        if tx_type == 'in':
            cur.execute("UPDATE inventory SET quantity_on_hand = COALESCE(quantity_on_hand,0) + ?, updated_at = datetime('now') WHERE id = ?", (qty, item_id))
        else:
            # prevent negative quantities: subtract but floor at 0
            cur.execute("SELECT COALESCE(quantity_on_hand,0) FROM inventory WHERE id = ?", (item_id,))
            current_qty = cur.fetchone()[0] or 0
            new_qty = max(0, current_qty - qty)
            cur.execute("UPDATE inventory SET quantity_on_hand = ?, updated_at = datetime('now') WHERE id = ?", (new_qty, item_id))

        conn.commit()

        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'ok': True}), 200
    except Exception:
        app.logger.exception("inventory_tx error")
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'ok': False}), 500
        try:
            flash('Failed to record transaction', 'danger')
        except Exception:
            pass
        return redirect(url_for('view_inventory', item_id=item_id))
    finally:
        if conn:
            conn.close()

    return redirect(url_for('view_inventory', item_id=item_id))


@app.route('/inventory/export')
@login_required
def inventory_export():
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, item_name, sku, quantity_on_hand, location, notes, created_at, updated_at FROM inventory ORDER BY item_name")
        rows = cur.fetchall()
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(['id','item_name','sku','quantity_on_hand','location','notes','created_at','updated_at'])
        for r in rows:
            writer.writerow([r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7]])
        csv_data = buf.getvalue()
        buf.close()
        return Response(csv_data, mimetype="text/csv", headers={"Content-disposition":"attachment; filename=inventory_export.csv"})
    except Exception:
        app.logger.exception("inventory_export error")
        try:
            flash("Export failed", "danger")
        except Exception:
            pass
        return redirect(url_for('inventory_list'))
    finally:
        if conn:
            conn.close()


@app.route('/production/export')
@login_required
def production_export():
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT p.id, p.record_date, p.animal_id, p.animal_name, p.production_type, p.health_status,
                   p.quantity, p.unit, p.notes, p.recorded_by,
                   a.id AS a_id, a.breed AS a_breed, a.tag_number AS a_tag
              FROM production p
              LEFT JOIN animals a ON a.id = p.animal_id
             ORDER BY p.record_date DESC, p.id DESC
        """)
        rows = cur.fetchall()

        # Build CSV in memory using cursor.description for robust column mapping
        import csv, io
        buf = io.StringIO()
        writer = csv.writer(buf)
        headers = ['id', 'record_date', 'animal_id', 'animal_name', 'production_type', 'health_status',
                   'quantity', 'unit', 'notes', 'recorded_by', 'animal_breed', 'animal_tag']
        writer.writerow(headers)

        # If rows are tuples, map by index relying on SELECT order above
        for row in rows:
            # defensive extraction: attempt to index by known positions
            writer.writerow([
                row[0],  # p.id
                row[1],  # record_date
                row[2],  # animal_id
                row[3],  # animal_name
                row[4],  # production_type
                row[5],  # health_status
                row[6],  # quantity
                row[7],  # unit
                row[8],  # notes
                row[9],  # recorded_by
                row[11], # a_breed (note SELECT order: a.id AS a_id is at index 10, a.breed at 11)
                row[12]  # a_tag
            ])

        csv_data = buf.getvalue()
        buf.close()
        return Response(
            csv_data,
            mimetype="text/csv",
            headers={"Content-disposition": "attachment; filename=production_export.csv"}
        )
    except Exception:
        app.logger.exception("production_export error")
        try:
            flash("Export failed", "danger")
        except Exception:
            pass
        return redirect(url_for('production_list'))
    finally:
        if conn:
            conn.close()


@app.route('/generate-report', methods=['POST'])
@login_required
def generate_report():
    """
    Accepts the POST from the reports forms and redirects to /print-report
    with safe query params. This centralizes printing and avoids endpoint collisions.
    """
    try:
        # Normalize inputs from different form names
        report_type = (request.form.get('report_type') or request.form.get('type') or 'custom').strip().lower()
        period = (request.form.get('period') or '').strip()
        start_date = (request.form.get('start_date') or request.form.get('startDate') or '').strip()
        end_date = (request.form.get('end_date') or request.form.get('endDate') or '').strip()
        fmt = (request.form.get('format') or 'html').strip().lower()

        # extras
        extras = {}
        if request.form.get('include_income'):
            extras['include_income'] = '1'
        if request.form.get('include_expenses'):
            extras['include_expenses'] = '1'
        if request.form.get('include_charts'):
            extras['include_charts'] = '1'

        # Build query string parameters
        qs = {
            'report_type': report_type,
            'period': period,
            'start_date': start_date,
            'end_date': end_date,
            'format': fmt,
            'print': '1'   # instruct print mode
        }
        qs.update(extras)

        return redirect(url_for('print_report', **qs))
    except Exception as e:
        app.logger.exception("generate_report failed")
        flash('Could not prepare print request: {}'.format(e), 'error')
        return redirect(url_for('reports'))


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
# --- Delete animal route (add to app.py) ---
@app.route('/animal/delete/<int:animal_id>', methods=['POST'])
@login_required
def delete_animal(animal_id):
    # optional: restrict to roles that are allowed to delete
    # if current_user.role not in ('admin','manager'):
    #     flash('Not authorized to delete animals', 'error')
    #     return redirect(url_for('animals'))

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Optionally check if animal exists before attempting delete
        cur.execute("SELECT id, tag_number FROM animal WHERE id = ?", (animal_id,))
        row = cur.fetchone()
        if not row:
            flash('Animal not found', 'error')
            return redirect(url_for('animals'))

        # If there are related records (sales, medical etc.) you may want to
        # check or cascade; here we simply attempt the delete
        cur.execute("DELETE FROM animal WHERE id = ?", (animal_id,))
        conn.commit()
        flash(f'Animal A-{animal_id} deleted successfully', 'success')
        app.logger.info("Deleted animal id=%s by user=%s", animal_id, current_user.username)
    except Exception as e:
        conn.rollback()
        app.logger.exception("Failed to delete animal id=%s", animal_id)
        flash('Failed to delete animal (check related records)', 'error')
    finally:
        conn.close()

    return redirect(url_for('animals'))


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
from datetime import datetime  # add at top if not present

# add this to app.py near your sales routes (after add_sale is a good spot)
from sqlite3 import OperationalError
# put this near your other sales routes (e.g. after add_sale/edit_sale)
from sqlite3 import OperationalError
from datetime import datetime

@app.route('/delete_sale/<int:sale_id>', methods=['POST'])
@login_required
def delete_sale(sale_id):
    # only allow permitted roles
    if getattr(current_user, 'role', None) not in ['admin', 'manager', 'accountant']:
        flash('Access denied.', 'error')
        return redirect(url_for('sales'))

    conn = None
    try:
        # open DB using your helper if available
        try:
            conn = get_db_connection()
        except NameError:
            import sqlite3, os
            db_path = os.path.join(os.path.dirname(__file__), 'database', 'farm.db')
            conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        # detect which sale table exists
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND (name='sale' OR name='sales')")
        row = cur.fetchone()
        if not row:
            flash('Sale table does not exist.', 'error')
            return redirect(url_for('sales'))

        table_name = row[0]  # 'sale' or 'sales'

        # fetch the row to give a friendly message
        cur.execute(f"SELECT id, customer_name, product, total_amount FROM {table_name} WHERE id = ?", (sale_id,))
        r = cur.fetchone()
        if not r:
            flash('Sale record not found.', 'error')
            return redirect(url_for('sales'))

        customer = r[1] or ''
        product = r[2] or ''
        total_amount = r[3] or 0

        # delete the sale
        cur.execute(f"DELETE FROM {table_name} WHERE id = ?", (sale_id,))
        conn.commit()

        # ensure deletion_logs and insert audit row
        try:
            cur.execute('''
                CREATE TABLE IF NOT EXISTS deletion_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    table_name TEXT,
                    record_id INTEGER,
                    record_repr TEXT,
                    deleted_by TEXT,
                    deleted_by_id INTEGER,
                    timestamp TEXT
                )
            ''')
            conn.commit()

            deleter_id = getattr(current_user, 'id', None)
            deleter_ident = getattr(current_user, 'username', None) or getattr(current_user, 'email', None) or str(deleter_id)
            timestamp = datetime.utcnow().isoformat() + 'Z'
            record_repr = f"{customer} — {product} ({total_amount})".strip()

            cur.execute('''
                INSERT INTO deletion_logs (table_name, record_id, record_repr, deleted_by, deleted_by_id, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (table_name, sale_id, record_repr, str(deleter_ident), deleter_id, timestamp))
            conn.commit()
        except Exception:
            current_app.logger.exception('Failed to write deletion log for sale %s', sale_id)

        flash(f'Sale S-{sale_id} deleted: {customer} — {product} (Ksh {total_amount})', 'success')

    except OperationalError as oe:
        current_app.logger.exception('OperationalError deleting sale: %s', oe)
        flash('Database error while deleting sale: ' + str(oe), 'error')
    except Exception as e:
        current_app.logger.exception('Error deleting sale: %s', e)
        flash('Error deleting sale: ' + str(e), 'error')
    finally:
        if conn:
            conn.close()

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
@app.route('/delete_breeding/<int:breeding_id>', methods=['POST'])
@login_required
def delete_breeding(breeding_id):
    # same role check as your /breeding view
    if current_user.role not in ['admin', 'manager']:
        flash('Access denied.', 'error')
        return redirect(url_for('breeding'))

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # confirm record exists
        cur.execute('SELECT id FROM breeding WHERE id = ?', (breeding_id,))
        row = cur.fetchone()
        if not row:
            flash('Breeding record not found.', 'error')
            return redirect(url_for('breeding'))

        # perform delete
        cur.execute('DELETE FROM breeding WHERE id = ?', (breeding_id,))
        conn.commit()

        flash(f'Breeding record BP-{breeding_id} deleted.', 'success')
    except Exception as e:
        # log error on server and show friendly message
        try:
            current_app.logger.exception('Error deleting breeding record %s', breeding_id)
        except Exception:
            pass
        flash('Could not delete the breeding record. See server logs.', 'error')
    finally:
        try:
            if conn:
                conn.close()
        except Exception:
            pass

    return redirect(url_for('breeding'))



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
# --- routes (paste/replace existing versions) ---

@app.route('/medical')
@login_required
def medical_records():
    # Authorization
    if current_user.role not in ['admin', 'manager']:
        flash('Access denied.', 'error')
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM medical ORDER BY created_at DESC')
    medical_records = cur.fetchall()
    cur.execute('SELECT COUNT(*) FROM medical')
    total_medical = cur.fetchone()[0] or 0
    conn.close()

    return render_template('medical.html', medical_records=medical_records, total_medical=total_medical)


@app.route('/delete_medical/<int:medical_id>', methods=['POST'])
@login_required
def delete_medical(medical_id):
    # Optional: restrict to admin/manager
    if current_user.role not in ['admin', 'manager']:
        flash('Access denied.', 'error')
        return redirect(url_for('medical_records'))

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('DELETE FROM medical WHERE id = ?', (medical_id,))
        conn.commit()
        conn.close()
        flash('Medical record deleted successfully!', 'success')
    except Exception as e:
        flash(f'Error deleting record: {e}', 'error')

    # Redirect to the list page (use correct endpoint name)
    return redirect(url_for('medical_records'))


@app.route('/medical/<int:medical_id>')
@login_required
def view_medical(medical_id):
    if current_user.role not in ['admin', 'manager']:
        flash('Access denied.', 'error')
        return redirect(url_for('medical_records'))

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM medical WHERE id = ?', (medical_id,))
    rec = cur.fetchone()
    conn.close()

    if not rec:
        flash('Medical record not found.', 'error')
        return redirect(url_for('medical_records'))

    return render_template('medical_view.html', record=rec)


@app.route('/medical/<int:medical_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_medical(medical_id):
    if current_user.role not in ['admin', 'manager']:
        flash('Access denied.', 'error')
        return redirect(url_for('medical_records'))

    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == 'POST':
        # optionally debug incoming form
        # debug_form('edit_medical', request.form)
        try:
            cur.execute(
                'UPDATE medical SET animal_id=?, treatment_date=?, condition=?, treatment=?, veterinarian=?, next_checkup=?, notes=? WHERE id=?',
                (
                    request.form.get('animal_id', '').strip(),
                    request.form.get('treatment_date'),
                    request.form.get('condition', '').strip(),
                    request.form.get('treatment', '').strip(),
                    request.form.get('veterinarian', '').strip(),
                    request.form.get('next_checkup'),
                    request.form.get('notes', '').strip(),
                    medical_id
                )
            )
            conn.commit()
            flash('Medical record updated!', 'success')
        except Exception as e:
            flash(f'Error: {e}', 'error')
        finally:
            conn.close()

        return redirect(url_for('medical_records'))

    cur.execute('SELECT * FROM medical WHERE id = ?', (medical_id,))
    rec = cur.fetchone()
    conn.close()

    if not rec:
        flash('Medical record not found.', 'error')
        return redirect(url_for('medical_records'))

    return render_template('medical_edit.html', record=rec)


@app.route('/add_medical', methods=['POST'])
@login_required
def add_medical():
    # debug_form('add_medical', request.form)
    if current_user.role not in ['admin', 'manager']:
        flash('Access denied.', 'error')
        return redirect(url_for('medical_records'))

    try:
        aid = request.form.get('animal_id', '').strip()
        tdate = request.form.get('treatment_date')
        cond = request.form.get('condition', '').strip()
        treat = request.form.get('treatment', '').strip()

        if not aid or not tdate or not cond or not treat:
            flash('Required fields missing.', 'error')
            return redirect(url_for('medical_records'))

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            'INSERT INTO medical (animal_id, treatment_date, condition, treatment, veterinarian, next_checkup, notes) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (
                aid,
                tdate,
                cond,
                treat,
                request.form.get('veterinarian', '').strip(),
                request.form.get('next_checkup'),
                request.form.get('notes', '').strip()
            )
        )
        conn.commit()
        conn.close()
        flash('Medical record added!', 'success')
    except Exception as e:
        flash(f'Error adding medical record: {e}', 'error')

    return redirect(url_for('medical_records'))



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
# add near your other feed routes (imports assumed already present)
from flask import current_app

@app.route('/delete_feed/<int:feed_id>', methods=['POST'])
@login_required
def delete_feed(feed_id):
    # Only allow admins/managers (same pattern as your other routes)
    if current_user.role not in ['admin', 'manager']:
        flash('Access denied.', 'error')
        return redirect(url_for('feed'))

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Optional: check record exists
        cur.execute('SELECT id FROM feed WHERE id = ?', (feed_id,))
        rec = cur.fetchone()
        if not rec:
            flash('Feed record not found.', 'error')
            conn.close()
            return redirect(url_for('feed'))

        # Delete
        cur.execute('DELETE FROM feed WHERE id = ?', (feed_id,))
        conn.commit()
        conn.close()

        flash('Feed record deleted successfully.', 'success')
    except Exception as e:
        # Keep the error message concise for UI; log details server-side if needed
        current_app.logger.exception("Failed to delete feed record %s", feed_id)
        flash(f'Error deleting feed record: {e}', 'error')

    return redirect(url_for('feed'))


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

from sqlite3 import IntegrityError

@app.route('/supplier/<int:supplier_id>/delete', methods=['POST'])
@app.route('/suppliers/<int:supplier_id>/delete', methods=['POST'])
@login_required
def delete_supplier(supplier_id):
    # only admins may delete suppliers
    if current_user.role != 'admin':
        flash('Access denied.', 'error'); return redirect(url_for('suppliers'))

    conn = None
    try:
        conn = get_db_connection(); cur = conn.cursor()
        # confirm exists
        cur.execute('SELECT id, company_name FROM supplier WHERE id = ?', (supplier_id,))
        rec = cur.fetchone()
        if not rec:
            flash('Supplier not found.', 'error'); return redirect(url_for('suppliers'))

        # delete
        cur.execute('DELETE FROM supplier WHERE id = ?', (supplier_id,))
        conn.commit()
        flash(f"Supplier '{rec['company_name']}' deleted.", 'success')
    except IntegrityError as ie:
        # likely referenced by other tables (FK constraint)
        flash('Cannot delete supplier: it is referenced by other records.', 'error')
    except Exception as e:
        flash(f'Error deleting supplier: {e}', 'error')
    finally:
        if conn:
            conn.close()
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
# --- paste into app.py after your add_customer route ---
from datetime import datetime
from sqlite3 import OperationalError

@app.route('/customers/<int:customer_id>/delete', methods=['POST'])
@login_required
def delete_customer(customer_id):
    """Delete a customer row. Only admin/manager allowed to delete."""
    if getattr(current_user, 'role', None) not in ['admin', 'manager']:
        flash('Access denied.', 'error')
        return redirect(url_for('customers'))

    conn = None
    try:
        # use existing helper
        conn = get_db_connection()
        cur = conn.cursor()

        # ensure table exists
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='customer' LIMIT 1")
        if not cur.fetchone():
            flash('Customer table does not exist.', 'error')
            return redirect(url_for('customers'))

        # ensure record exists
        cur.execute('SELECT id, customer_name, company, phone FROM customer WHERE id = ?', (customer_id,))
        row = cur.fetchone()
        if not row:
            flash('Customer not found.', 'error')
            return redirect(url_for('customers'))

        # delete
        cur.execute('DELETE FROM customer WHERE id = ?', (customer_id,))
        conn.commit()

        # optional audit log (will create table if missing)
        try:
            cur.execute('''
                CREATE TABLE IF NOT EXISTS deletion_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    table_name TEXT,
                    record_id INTEGER,
                    record_repr TEXT,
                    deleted_by TEXT,
                    deleted_by_id INTEGER,
                    timestamp TEXT
                )
            ''')
            conn.commit()

            deleter_id = getattr(current_user, 'id', None)
            deleter_ident = getattr(current_user, 'username', None) or getattr(current_user, 'email', None) or str(deleter_id)
            timestamp = datetime.utcnow().isoformat() + 'Z'
            record_repr = f"{row['customer_name']} — {row['company'] or ''} ({row['phone'] or ''})".strip()

            cur.execute('''
                INSERT INTO deletion_logs (table_name, record_id, record_repr, deleted_by, deleted_by_id, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', ('customer', customer_id, record_repr, str(deleter_ident), deleter_id, timestamp))
            conn.commit()
        except Exception:
            current_app.logger.exception('Failed to insert deletion log for customer %s', customer_id)

        flash(f'Customer C-{customer_id} deleted: {row["customer_name"]}', 'success')

    except OperationalError as oe:
        current_app.logger.exception('OperationalError deleting customer: %s', oe)
        flash('Database error while deleting customer: ' + str(oe), 'error')
    except Exception as e:
        current_app.logger.exception('Error deleting customer: %s', e)
        flash('Error deleting customer: ' + str(e), 'error')
    finally:
        if conn:
            conn.close()

    return redirect(url_for('customers'))
# --- end route ---


# ----- Financial -----
@app.route('/financial')
@login_required
def financial():
    if current_user.role not in ['admin', 'accountant']:
        flash('Access denied.', 'error'); return redirect(url_for('dashboard'))
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute('SELECT * FROM financial ORDER BY created_at DESC'); financial_records = cur.fetchall()
    cur.execute('SELECT SUM(amount) FROM financial WHERE transaction_type = ?', ('income',)); total_income = cur.fetchone()[0] or 0
    cur.execute('SELECT SUM(amount) FROM financial WHERE transaction_type = ?', ('expense',)); total_expense = cur.fetchone()[0] or 0
    net_profit = total_income - total_expense
    cur.execute('SELECT COUNT(*) FROM financial'); total_financial_records = cur.fetchone()[0] or 0
    conn.close()
    return render_template('financial.html', financial_records=financial_records, total_income=total_income, total_expense=total_expense, net_profit=net_profit, total_financial_records=total_financial_records)


@app.route('/financial/<int:record_id>')
@login_required
def view_financial(record_id):
    if current_user.role not in ['admin', 'accountant']:
        flash('Access denied.', 'error'); return redirect(url_for('financial'))
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute('SELECT * FROM financial WHERE id = ?', (record_id,)); rec = cur.fetchone(); conn.close()
    if not rec:
        flash('Financial record not found.', 'error'); return redirect(url_for('financial'))
    return render_template('financial_view.html', record=rec)

@app.route('/financial/<int:record_id>/delete', methods=['POST'])
@login_required
def delete_financial(record_id):
    # only allow admin/manager to delete (adjust roles as needed)
    if getattr(current_user, 'role', None) not in ['admin', 'manager']:
        flash('Access denied.', 'error')
        return redirect(url_for('financial'))

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute('SELECT * FROM financial WHERE id = ?', (record_id,))
        rec = cur.fetchone()
        if not rec:
            flash('Record not found.', 'error')
            return redirect(url_for('financial'))

        # optional: copy rec contents to a deletion log table (audit)
        cur.execute('DELETE FROM financial WHERE id = ?', (record_id,))
        conn.commit()
        flash(f'Financial record F-{record_id} deleted.', 'success')
    except Exception as e:
        current_app.logger.exception('Error deleting financial record: %s', e)
        flash(f'Error deleting record: {e}', 'error')
    finally:
        conn.close()

    return redirect(url_for('financial'))

@app.route('/financial/<int:record_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_financial(record_id):
    if current_user.role not in ['admin', 'accountant']:
        flash('Access denied.', 'error'); return redirect(url_for('financial'))
    conn = get_db_connection(); cur = conn.cursor()
    if request.method == 'POST':
        debug_form('edit_financial', request.form)
        try:
            cur.execute('UPDATE financial SET transaction_type=?, amount=?, category=?, description=?, transaction_date=?, reference=? WHERE id=?',
                        (request.form.get('transaction_type', '').strip(), float(request.form.get('amount', '0') or 0), request.form.get('category', '').strip(), request.form.get('description', '').strip(), request.form.get('transaction_date'), request.form.get('reference', '').strip(), record_id))
            conn.commit(); flash('Financial record updated!', 'success')
        except Exception as e:
            flash(f'Error: {e}', 'error')
        finally:
            conn.close()
        return redirect(url_for('financial'))
    cur.execute('SELECT * FROM financial WHERE id = ?', (record_id,)); rec = cur.fetchone(); conn.close()
    if not rec:
        flash('Financial record not found.', 'error'); return redirect(url_for('financial'))
    return render_template('financial_edit.html', record=rec)


@app.route('/add_financial', methods=['POST'])
@login_required
def add_financial():
    debug_form('add_financial', request.form)
    if current_user.role not in ['admin', 'accountant']:
        flash('Access denied.', 'error'); return redirect(url_for('financial'))
    try:
        ttype = request.form.get('type', '').strip(); amount = float(request.form.get('amount', '0') or 0)
        if not ttype or amount <= 0 or not request.form.get('category') or not request.form.get('description'):
            flash('Required fields missing.', 'error'); return redirect(url_for('financial'))
        conn = get_db_connection(); cur = conn.cursor()
        cur.execute('INSERT INTO financial (transaction_type, amount, category, description, transaction_date, reference) VALUES (?, ?, ?, ?, ?, ?)',
                    (ttype, amount, request.form.get('category', '').strip(), request.form.get('description', '').strip(), request.form.get('transaction_date'), request.form.get('reference', '')))
        conn.commit(); conn.close(); flash('Financial transaction added!', 'success')
    except Exception as e:
        flash(f'Error: {e}', 'error')
    return redirect(url_for('financial'))


# ----- Staff (list/view/edit/add) -----
# ---------- STAFF LIST ----------
@app.route('/staff')
@login_required
def staff():
    if current_user.role != 'admin':
        flash('Access denied.', 'error')
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute('SELECT * FROM staff ORDER BY created_at DESC')
        staff_members = cur.fetchall()

        cur.execute("SELECT COUNT(*) FROM staff")
        total_staff = cur.fetchone()[0] or 0

        cur.execute("SELECT COUNT(*) FROM staff WHERE status = 'Active'")
        active_today = cur.fetchone()[0] or 0

        cur.execute("SELECT COUNT(*) FROM staff WHERE status IN ('On Leave','Leave')")
        on_leave = cur.fetchone()[0] or 0

        cur.execute("SELECT COUNT(*) FROM task WHERE status IN ('Pending','In Progress')")
        active_tasks = cur.fetchone()[0] or 0
    finally:
        conn.close()

    return render_template(
        'staff.html',
        staff_members=staff_members,
        total_staff=total_staff,
        active_today=active_today,
        on_leave=on_leave,
        active_tasks=active_tasks
    )


# ---------- DELETE STAFF ----------
@app.route('/delete_staff/<int:staff_id>', methods=['POST'])
@login_required
def delete_staff(staff_id):
    # Only admin/manager allowed to delete
    if getattr(current_user, 'role', None) not in ['admin', 'manager']:
        flash('Access denied.', 'error')
        return redirect(url_for('staff'))

    # Server-side self-delete protection
    try:
        if getattr(current_user, 'id', None) is not None and int(current_user.id) == int(staff_id):
            flash('You cannot delete your own account.', 'error')
            return redirect(url_for('staff'))
    except Exception:
        # continue with caution
        pass

    # local import so you don't have to add it at top if you prefer
    from datetime import datetime

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # fetch the record to get name
        cur.execute('SELECT id, first_name, last_name FROM staff WHERE id = ?', (staff_id,))
        row = cur.fetchone()
        if not row:
            flash('Staff member not found.', 'error')
            return redirect(url_for('staff'))

        # row may be tuple or dict-like
        try:
            if isinstance(row, dict):
                fname = row.get('first_name', '')
                lname = row.get('last_name', '')
            else:
                fname = row[1] if len(row) > 1 else ''
                lname = row[2] if len(row) > 2 else ''
        except Exception:
            fname, lname = '', ''
        record_repr = f"{fname} {lname}".strip()

        # perform delete
        cur.execute('DELETE FROM staff WHERE id = ?', (staff_id,))
        conn.commit()

        # ensure deletion_logs table exists and insert audit row
        try:
            cur.execute('''
                CREATE TABLE IF NOT EXISTS deletion_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    table_name TEXT,
                    record_id INTEGER,
                    record_repr TEXT,
                    deleted_by TEXT,
                    deleted_by_id INTEGER,
                    timestamp TEXT
                )
            ''')
            conn.commit()

            deleter_id = getattr(current_user, 'id', None)
            deleter_ident = getattr(current_user, 'username', None) or getattr(current_user, 'email', None) or str(deleter_id)
            timestamp = datetime.utcnow().isoformat() + 'Z'

            cur.execute('''
                INSERT INTO deletion_logs (table_name, record_id, record_repr, deleted_by, deleted_by_id, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', ('staff', staff_id, record_repr, str(deleter_ident), deleter_id, timestamp))
            conn.commit()
        except Exception as log_exc:
            current_app.logger.exception('Failed to write deletion log: %s', log_exc)

        current_app.logger.info(
            'User %s (id=%s) deleted staff id=%s (%s) at %s',
            getattr(current_user, 'username', 'unknown'),
            getattr(current_user, 'id', 'unknown'),
            staff_id,
            record_repr,
            timestamp if 'timestamp' in locals() else ''
        )

        flash(f'Staff member {record_repr} (STF-{staff_id}) deleted successfully.', 'success')

    except Exception as e:
        current_app.logger.exception('Error deleting staff member: %s', e)
        flash(f'Error deleting staff member: {e}', 'error')
    finally:
        if conn:
            conn.close()

    return redirect(url_for('staff'))


# ---------- VIEW STAFF ----------
@app.route('/staff/<int:staff_id>')
@login_required
def view_staff(staff_id):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute('SELECT * FROM staff WHERE id = ?', (staff_id,))
        s = cur.fetchone()
    finally:
        conn.close()

    if not s:
        flash('Staff member not found.', 'error')
        return redirect(url_for('staff'))

    return render_template('staff_view.html', staff=s)


# ---------- EDIT STAFF ----------
@app.route('/staff/<int:staff_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_staff(staff_id):
    if current_user.role != 'admin':
        flash('Access denied.', 'error')
        return redirect(url_for('staff'))

    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == 'POST':
        debug_form('edit_staff', request.form)
        try:
            first_name = request.form.get('first_name', '').strip()
            last_name = request.form.get('last_name', '').strip()
            position = request.form.get('position', '').strip()
            department = request.form.get('department', '').strip()
            email = request.form.get('email', '').strip()
            phone = request.form.get('phone', '').strip()
            status = request.form.get('status', 'Active').strip()
            id_number = request.form.get('id_number', '').strip()

            cur.execute(
                'UPDATE staff SET first_name=?, last_name=?, position=?, department=?, email=?, phone=?, status=?, id_number=? WHERE id=?',
                (first_name, last_name, position, department, email, phone, status, id_number, staff_id)
            )
            conn.commit()
            flash('Staff updated!', 'success')
        except Exception as e:
            current_app.logger.exception('Error updating staff: %s', e)
            flash(f'Error: {e}', 'error')
        finally:
            conn.close()
        return redirect(url_for('staff'))

    # GET
    try:
        cur.execute('SELECT * FROM staff WHERE id = ?', (staff_id,))
        s = cur.fetchone()
    finally:
        conn.close()

    if not s:
        flash('Staff member not found.', 'error')
        return redirect(url_for('staff'))
    return render_template('staff_edit.html', staff=s)


# ---------- ADD STAFF ----------
@app.route('/add_staff', methods=['POST'])
@login_required
def add_staff():
    debug_form('add_staff', request.form)
    if current_user.role != 'admin':
        flash('Access denied.', 'error')
        return redirect(url_for('staff'))

    try:
        fn = request.form.get('first_name', '').strip()
        ln = request.form.get('last_name', '').strip()
        pos = request.form.get('position', '').strip()
        phone = request.form.get('phone', '').strip()

        if not fn or not ln or not pos or not phone:
            flash('Required fields missing.', 'error')
            return redirect(url_for('staff'))

        department = request.form.get('department', '').strip()
        email = request.form.get('email', '').strip()
        address = request.form.get('address', '').strip()
        dob = request.form.get('dob') or None
        date_employed = request.form.get('date_employed') or None
        id_number = request.form.get('id_number', '').strip()
        status = request.form.get('status', 'active').strip()

        conn = get_db_connection()
        cur = conn.cursor()

        # IMPORTANT: make sure your staff table has the columns below (id_number, status)
        cur.execute(
            'INSERT INTO staff (first_name, last_name, position, department, email, phone, address, dob, date_employed, id_number, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (fn, ln, pos, department, email, phone, address, dob, date_employed, id_number, status)
        )
        conn.commit()
        conn.close()
        flash('Staff member added!', 'success')
    except Exception as e:
        current_app.logger.exception('Error adding staff: %s', e)
        flash(f'Error: {e}', 'error')

    return redirect(url_for('staff'))

# ----- NEW: task view & edit routes (added to resolve BuildError for view/edit links) -----
@app.route('/tasks/<int:task_id>')
@login_required
def view_task(task_id):
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute('SELECT * FROM task WHERE id = ?', (task_id,))
    task = cur.fetchone()
    conn.close()
    if not task:
        flash('Task not found.', 'error')
        return redirect(url_for('tasks'))
    return render_template('task_view.html', task=task)

# --- Task list and add_task handlers (paste into app.py) ---
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required
import sqlite3

# helper: convert sqlite rows to simple objects with attribute access
def rows_to_objs(rows, cursor):
    cols = []
    try:
        cols = [c[0] for c in cursor.description]
    except Exception:
        cols = []
    objs = []
    for r in rows:
        # r might be sqlite3.Row, dict, or tuple
        if hasattr(r, "keys"):
            d = {k: r[k] for k in r.keys()}
        elif isinstance(r, dict):
            d = r
        else:
            d = {}
            for i, col in enumerate(cols):
                d[col] = r[i] if i < len(r) else None
        class Obj: pass
        o = Obj()
        o.__dict__.update(d)
        objs.append(o)
    return objs

import datetime   # put near top of app.py if not already present

def _convert_value_for_json(v):
    """Make values JSON serializable (dates -> iso string, bytes -> str, primitives pass)."""
    if v is None:
        return None
    if isinstance(v, (datetime.date, datetime.datetime)):
        return v.isoformat()
    if isinstance(v, (bytes, bytearray)):
        try:
            return v.decode('utf-8', errors='ignore')
        except Exception:
            return str(v)
    # primitives (int, float, str, bool) are left as-is
    return v

def _obj_to_plain_dict(o):
    """Turn attribute-access object (rows_to_objs/Obj) into a plain dict safe for JSON."""
    if hasattr(o, '__dict__'):
        d = {}
        for k, v in o.__dict__.items():
            if k.startswith('_'):
                continue
            d[k] = _convert_value_for_json(v)
        return d
    # fallback: try mapping
    try:
        return {k: _convert_value_for_json(v) for k, v in dict(o).items()}
    except Exception:
        return {"id": getattr(o, "id", None), "repr": str(o)}

@app.route('/tasks')
@login_required
def tasks():
    """
    Render task list page and supply tasks_json (list of plain dicts) for client JS.
    """
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # staff members (for the create modal)
        cur.execute("SELECT id, first_name, last_name FROM staff ORDER BY id")
        staff_rows = cur.fetchall()
        staff_members = rows_to_objs(staff_rows, cur)

        # tasks list (attribute-access objects for template loops)
        cur.execute("SELECT * FROM task ORDER BY id DESC")
        task_rows = cur.fetchall()
        tasks_list = rows_to_objs(task_rows, cur)

        # counts
        cur.execute("SELECT COUNT(*) FROM task WHERE status = ?", ('Pending',))
        pending_count = cur.fetchone()[0] or 0
        cur.execute("SELECT COUNT(*) FROM task WHERE status = ?", ('In Progress',))
        inprogress_count = cur.fetchone()[0] or 0
        cur.execute("SELECT COUNT(*) FROM task WHERE status = ?", ('Completed',))
        completed_count = cur.fetchone()[0] or 0

        # overdue (uses sqlite date() comparison)
        try:
            cur.execute("SELECT COUNT(*) FROM task WHERE due_date IS NOT NULL AND due_date < date('now')")
            overdue_count = cur.fetchone()[0] or 0
        except Exception:
            overdue_count = 0

        # staff_map for resolving assigned_to
        staff_map = {}
        for s in staff_members:
            sid = getattr(s, 'id', None)
            name = f"{getattr(s,'first_name','') or ''} {getattr(s,'last_name','') or ''}".strip()
            staff_map[sid] = name
            staff_map[str(sid)] = name

    except Exception as e:
        # On error, fallback to demo data so page still renders
        flash(f"Could not load tasks (fallback demo): {e}", "warning")
        class D:
            def __init__(self, d): self.__dict__.update(d)
        tasks_list = [
            D({"id": 1, "title": "Demo task", "description": "Demo", "assigned_to": None,
               "due_date": None, "priority": "Normal", "category": "general", "status": "Pending"})
        ]
        staff_members = []
        pending_count = inprogress_count = completed_count = overdue_count = 0
        staff_map = {}
    finally:
        if conn:
            conn.close()

    # Build JSON-serializable list for client JS (plain dicts)
    tasks_json = [_obj_to_plain_dict(t) for t in tasks_list]

    return render_template('task_management.html',
                           tasks=tasks_list,
                           tasks_json=tasks_json,
                           staff_members=staff_members,
                           pending_count=pending_count,
                           inprogress_count=inprogress_count,
                           completed_count=completed_count,
                           overdue_count=overdue_count,
                           staff_map=staff_map)

# ----- Reports ----

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
@app.route('/delete_task', methods=['POST'])
@login_required
def delete_task():
    try:
        # accept either form-encoded or JSON body
        task_id = request.form.get('task_id') or (request.get_json(silent=True) or {}).get('task_id')
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