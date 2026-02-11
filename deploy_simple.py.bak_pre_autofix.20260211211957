# deploy_simple.py - SIMPLE DEPLOYMENT
import os
import sys
import subprocess
import webbrowser
from pathlib import Path

def print_header():
    print("=" * 60)
    print("DL FARM MANAGEMENT SYSTEM - DEPLOYMENT")
    print("=" * 60)

def check_requirements():
    """Check and install requirements"""
    print("\n1. Checking requirements...")
    
    requirements = [
        'Flask==2.3.3',
        'Flask-SQLAlchemy==3.0.5',
        'Flask-Login==0.6.2',
        'Werkzeug==2.3.7'
    ]
    
    try:
        import flask
        print("✓ Flask is already installed")
    except ImportError:
        print("Installing Flask...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "flask"])
    
    try:
        import flask_sqlalchemy
        print("✓ Flask-SQLAlchemy is already installed")
    except ImportError:
        print("Installing Flask-SQLAlchemy...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "Flask-SQLAlchemy"])
    
    try:
        import flask_login
        print("✓ Flask-Login is already installed")
    except ImportError:
        print("Installing Flask-Login...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "Flask-Login"])
    
    print("✓ All requirements checked")

def setup_database():
    """Setup database folder"""
    print("\n2. Setting up database...")
    
    db_path = Path('database/farm.db')
    db_path.parent.mkdir(exist_ok=True)
    
    if db_path.exists():
        print("✓ Database file already exists")
    else:
        db_path.touch()
        print("✓ Created new database file")
    
    return True

def create_default_data():
    """Create default users"""
    print("\n3. Creating default users...")
    
    try:
        # Import after ensuring dependencies are installed
        from app import app, db
        from models import User
        from werkzeug.security import generate_password_hash
        
        with app.app_context():
            # Create tables
            db.create_all()
            
            # Default users
            users = [
                {
                    'username': 'admin',
                    'email': 'admin@dlfarm.com',
                    'password': 'admin123',
                    'role': 'admin'
                },
                {
                    'username': 'manager', 
                    'email': 'manager@dlfarm.com',
                    'password': 'manager123',
                    'role': 'manager'
                },
                {
                    'username': 'accountant',
                    'email': 'accountant@dlfarm.com',
                    'password': 'accountant123',
                    'role': 'accountant'
                }
            ]
            
            for user_data in users:
                if not User.query.filter_by(username=user_data['username']).first():
                    user = User(
                        username=user_data['username'],
                        email=user_data['email'],
                        password=generate_password_hash(user_data['password'], method='sha256'),
                        role=user_data['role']
                    )
                    db.session.add(user)
                    print(f"✓ Created {user_data['role']} user: {user_data['username']}")
            
            db.session.commit()
            print("✓ Database setup complete")
            
    except Exception as e:
        print(f"✗ Error setting up database: {e}")
        return False
    
    return True

def start_application():
    """Start the Flask application"""
    print("\n4. Starting DL Farm Management System...")
    print("=" * 60)
    print("\n✅ SYSTEM IS NOW RUNNING!")
    print("\nOpen your browser and go to: http://localhost:5000")
    print("\n📋 LOGIN CREDENTIALS:")
    print("   Admin:     admin / admin123")
    print("   Manager:   manager / manager123")
    print("   Accountant: accountant / accountant123")
    print("\n⚠️  Press Ctrl+C to stop the server")
    print("=" * 60)
    
    # Open browser automatically
    try:
        webbrowser.open('http://localhost:5000')
    except:
        pass
    
    # Start Flask application
    os.system(f'"{sys.executable}" app.py')

def main():
    """Main deployment function"""
    print_header()
    
    try:
        check_requirements()
        setup_database()
        create_default_data()
        start_application()
    except KeyboardInterrupt:
        print("\n\n⚠️  Deployment cancelled by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        print("\nTry these solutions:")
        print("1. Make sure Python 3.8+ is installed")
        print("2. Run as administrator if on Windows")
        print("3. Check your internet connection")
        input("\nPress Enter to exit...")
        sys.exit(1)

if __name__ == "__main__":
    main()