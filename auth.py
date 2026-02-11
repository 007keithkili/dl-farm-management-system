# auth.py
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User

# for safe redirect check
from urllib.parse import urlparse, urljoin

auth = Blueprint('auth', __name__)

# allowlist of roles that may be assigned via the registration form (for safety)
ALLOWED_ROLES = {'admin', 'manager', 'storekeeper', 'accountant', 'user'}


def is_safe_url(target):
    """
    Prevent open redirects — only allow redirects to same host.
    """
    host_url = request.host_url
    try:
        ref_url = urlparse(host_url)
        test_url = urlparse(urljoin(host_url, target))
        return (test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc)
    except Exception:
        return False


@auth.route('/login', methods=['GET', 'POST'])
def login():
    """
    Login user. Supports optional 'next' parameter (safely validated).
    After successful login, redirects based on role:
      - storekeeper -> inventory_list
      - admin / manager -> dashboard
      - accountant -> financial (if route exists in your app; fallback to dashboard)
      - others -> dashboard
    """
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = bool(request.form.get('remember'))

        if not username or not password:
            flash('Please enter both username and password', 'error')
            return render_template('login.html')

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            login_user(user, remember=remember)
            flash('Logged in successfully!', 'success')

            # Respect safe next param if provided
            next_url = request.args.get('next') or request.form.get('next')
            if next_url and is_safe_url(next_url):
                return redirect(next_url)

            # Role-based redirect targets
            role = (getattr(user, 'role', '') or '').lower()

            if role == 'storekeeper':
                try:
                    return redirect(url_for('inventory_list'))
                except Exception:
                    # fallback
                    return redirect(url_for('dashboard'))

            if role in ('admin', 'manager'):
                return redirect(url_for('dashboard'))

            if role == 'accountant':
                # prefer financial route if it exists in your app; fallback to dashboard
                try:
                    return redirect(url_for('financial'))
                except Exception:
                    return redirect(url_for('dashboard'))

            # default fallback
            return redirect(url_for('dashboard'))

        flash('Invalid username or password', 'error')

    # If GET or login failed, render login
    return render_template('login.html')


@auth.route('/register', methods=['GET', 'POST'])
def register():
    """
    Create a new user. Registration may accept 'role' but only from ALLOWED_ROLES.
    If 'role' is missing or invalid it defaults to 'user'.
    """
    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        email = (request.form.get('email') or '').strip()
        password = request.form.get('password') or ''
        role = (request.form.get('role') or '').strip().lower()

        # Basic validation
        if not username or not email or not password:
            flash('Please provide username, email and password', 'error')
            return redirect(url_for('auth.register'))

        # Normalize role
        if role not in ALLOWED_ROLES:
            role = 'user'

        # Check username uniqueness
        user = User.query.filter_by(username=username).first()
        if user:
            flash('Username already exists', 'error')
            return redirect(url_for('auth.register'))

        # Create user
        new_user = User(
            username=username,
            email=email,
            password=generate_password_hash(password, method='sha256'),
            role=role
        )

        try:
            db.session.add(new_user)
            db.session.commit()
        except Exception as e:
            current_app.logger.exception("User registration failed")
            flash('Failed to create account. Please try again.', 'error')
            return redirect(url_for('auth.register'))

        flash('Account created successfully! You may now login.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('register.html')


@auth.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out', 'info')
    return redirect(url_for('auth.login'))
