# seed_data.py
from app import app, db
from models import User, Animal, Feed, Staff, Task
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta

def seed_database():
    with app.app_context():
        # Clear existing data
        db.drop_all()
        db.create_all()
        
        # Create users
        users = [
            User(
                username='admin',
                email='admin@dlfarm.com',
                password=generate_password_hash('admin123', method='sha256'),
                role='admin'
            ),
            User(
                username='manager',
                email='manager@dlfarm.com',
                password=generate_password_hash('manager123', method='sha256'),
                role='manager'
            ),
            User(
                username='accountant',
                email='accountant@dlfarm.com',
                password=generate_password_hash('accountant123', method='sha256'),
                role='accountant'
            )
        ]
        
        for user in users:
            db.session.add(user)
        
        # Create sample animals
        animals = [
            Animal(
                tag_number='AN-001',
                breed='Large White',
                birth_date=datetime(2025, 1, 15),
                weight=45.5,
                status='Active',
                pen_number='PEN-001',
                health_status='Good'
            ),
            Animal(
                tag_number='AN-002',
                breed='Duroc',
                birth_date=datetime(2025, 2, 20),
                weight=38.2,
                status='Active',
                pen_number='PEN-002',
                health_status='Good'
            ),
            Animal(
                tag_number='AN-003',
                breed='Landrace',
                birth_date=datetime(2025, 3, 10),
                weight=42.1,
                status='Sick',
                pen_number='PEN-003',
                health_status='Poor'
            )
        ]
        
        for animal in animals:
            db.session.add(animal)
        
        # Create sample feed inventory
        feeds = [
            Feed(
                feed_type='Pig Finisher Feed',
                quantity_kg=800,
                unit_price=50,
                supplier='United Feed',
                purchase_date=datetime(2025, 10, 1),
                expiry_date=datetime(2026, 4, 1)
            ),
            Feed(
                feed_type='Pig Starter Feed',
                quantity_kg=1500,
                unit_price=45,
                supplier='Animal Feed Co.',
                purchase_date=datetime(2025, 9, 15),
                expiry_date=datetime(2026, 3, 15)
            )
        ]
        
        for feed in feeds:
            db.session.add(feed)
        
        # Create sample staff
        staff_members = [
            Staff(
                name='Stephen Njoroge',
                role='Farm Manager',
                department='Livestock',
                salary=42000,
                contact='0719287124',
                hire_date=datetime(2024, 1, 15)
            ),
            Staff(
                name='John Mwangi',
                role='Assistant',
                department='Breeding',
                salary=25000,
                contact='0723456789',
                hire_date=datetime(2024, 3, 20)
            )
        ]
        
        for staff in staff_members:
            db.session.add(staff)
        
        # Create sample tasks
        tasks = [
            Task(
                title='Health Check',
                description='Routine health inspection',
                assigned_to=1,
                due_date=datetime.now() + timedelta(days=2),
                status='Pending',
                priority='High'
            ),
            Task(
                title='Feed Animals',
                description='Morning feeding',
                assigned_to=2,
                due_date=datetime.now() - timedelta(days=1),
                status='Overdue',
                priority='Medium'
            )
        ]
        
        for task in tasks:
            db.session.add(task)
        
        # Commit all changes
        db.session.commit()
        print("Database seeded successfully!")
        print("Test credentials:")
        print("Admin: admin / admin123")
        print("Manager: manager / manager123")
        print("Accountant: accountant / accountant123")

if __name__ == '__main__':
    seed_database()