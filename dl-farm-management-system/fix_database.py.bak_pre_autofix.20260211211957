# fix_database.py - DATABASE FIX FOR WINDOWS
import os
import sys
from pathlib import Path
import sqlite3

def fix_database():
    print("=" * 60)
    print("DATABASE FIX FOR DL FARM SYSTEM")
    print("=" * 60)
    
    # Get current directory
    current_dir = Path.cwd()
    print(f"Current directory: {current_dir}")
    
    # Database path
    db_path = current_dir / 'database' / 'farm.db'
    print(f"Database path: {db_path}")
    
    # Ensure database directory exists
    db_path.parent.mkdir(exist_ok=True)
    print("✓ Database directory checked")
    
    # Check if file exists and has content
    if db_path.exists():
        size = db_path.stat().st_size
        print(f"Database file size: {size} bytes")
        
        if size == 0:
            print("❌ Database file is EMPTY (0 bytes)")
            print("Deleting empty file...")
            db_path.unlink()
            print("✓ Empty file deleted")
    
    # Create fresh database
    print("\nCreating new database...")
    
    # Connect and create tables using SQLite directly
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        print("✓ Database connection established")
        
        # Create users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP
            )
        ''')
        print("✓ Users table created")
        
        # Create animals table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS animal (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tag_number TEXT UNIQUE NOT NULL,
                breed TEXT NOT NULL,
                birth_date DATE,
                weight REAL,
                status TEXT DEFAULT 'Active',
                pen_number TEXT,
                health_status TEXT DEFAULT 'Good',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        print("✓ Animals table created")
        
        # Create default users
        import hashlib
        def hash_password(password):
            return hashlib.sha256(password.encode()).hexdigest()
        
        users = [
            ('admin', 'admin@dlfarm.com', hash_password('admin123'), 'admin'),
            ('manager', 'manager@dlfarm.com', hash_password('manager123'), 'manager'),
            ('accountant', 'accountant@dlfarm.com', hash_password('accountant123'), 'accountant')
        ]
        
        for username, email, password, role in users:
            cursor.execute(
                'INSERT OR IGNORE INTO user (username, email, password, role) VALUES (?, ?, ?, ?)',
                (username, email, password, role)
            )
            print(f"✓ Created user: {username} ({role})")
        
        # Commit changes
        conn.commit()
        conn.close()
        
        print("\n✅ DATABASE CREATED SUCCESSFULLY!")
        print(f"Location: {db_path}")
        
        # Show file info
        size = db_path.stat().st_size
        print(f"File size: {size} bytes")
        
        if size > 0:
            print("✓ Database is NOT empty - Ready to use!")
        else:
            print("❌ Database is still empty - Something went wrong")
            
    except Exception as e:
        print(f"❌ Error creating database: {e}")
        return False
    
    return True

def run_application():
    print("\n" + "=" * 60)
    print("STARTING DL FARM MANAGEMENT SYSTEM")
    print("=" * 60)
    
    try:
        # Import and run the Flask app
        import app
        print("✓ Flask app imported successfully")
        
        # Run the app
        print("\n✅ SYSTEM IS NOW RUNNING!")
        print("\nOpen your browser and go to: http://localhost:5000")
        print("\n📋 LOGIN CREDENTIALS:")
        print("   Admin:     admin / admin123")
        print("   Manager:   manager / manager123")
        print("   Accountant: accountant / accountant123")
        print("\n⚠️  Press Ctrl+C to stop the server")
        print("=" * 60)
        
        # Run the app
        app.app.run(debug=True, host='0.0.0.0', port=5000)
        
    except Exception as e:
        print(f"❌ Error running application: {e}")
        return False

def main():
    print("DL FARM SYSTEM - WINDOWS FIX")
    print("=" * 60)
    
    # Step 1: Fix database
    if not fix_database():
        print("\n❌ Database fix failed!")
        input("Press Enter to exit...")
        return
    
    # Step 2: Run application
    run_application()

if __name__ == '__main__':
    main()