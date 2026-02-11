#!/usr/bin/env python3
"""
Safe migration: create inventory and inventory_tx tables if they don't exist.
Usage:
  python migrate_inventory.py            # auto-detect DB from common locations
  python migrate_inventory.py path/to/db # explicit DB path

Back up your DB before running.
"""
import sqlite3
import os
import sys

DB_PATHS_TO_TRY = [
    "app.db",
    "instance/app.db",
    "database.db",
    "data.db",
    "dl-farm.db",
]

def find_db(explicit=None):
    if explicit:
        if os.path.exists(explicit):
            return explicit
        raise FileNotFoundError(f"Explicit DB path not found: {explicit}")
    for p in DB_PATHS_TO_TRY:
        if os.path.exists(p):
            return p
    # fallback: return first *.db in cwd
    for f in os.listdir('.'):
        if f.endswith('.db') or f.endswith('.sqlite') or f.endswith('.sqlite3'):
            return f
    return None

def create_tables(conn):
    cur = conn.cursor()
    # inventory table - include received / delivered / dispatched fields
    cur.execute("""
    CREATE TABLE IF NOT EXISTS inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_name TEXT NOT NULL,
        sku TEXT,
        quantity_on_hand INTEGER DEFAULT 0,
        location TEXT,
        notes TEXT,
        supplier_reference TEXT,
        received_date TEXT,
        received_by TEXT,
        delivered_by TEXT,
        delivered_date TEXT,
        dispatched_date TEXT,
        dispatched_by TEXT,
        dispatched_to TEXT,
        created_at TEXT,
        updated_at TEXT
    );
    """)
    # inventory transactions table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS inventory_tx (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        inventory_id INTEGER NOT NULL,
        tx_type TEXT NOT NULL,   -- 'in' or 'out'
        quantity INTEGER NOT NULL,
        reference TEXT,
        notes TEXT,
        performed_by TEXT,
        tx_date TEXT,
        FOREIGN KEY (inventory_id) REFERENCES inventory(id) ON DELETE CASCADE
    );
    """)
    conn.commit()

def main():
    explicit = sys.argv[1] if len(sys.argv) > 1 else None
    try:
        dbpath = find_db(explicit)
    except FileNotFoundError as e:
        print("Error:", e)
        sys.exit(1)

    if not dbpath:
        print("No sqlite DB file found in common locations. Provide path as argument:")
        print("  python migrate_inventory.py path/to/your.db")
        sys.exit(1)

    print("Using DB:", dbpath)
    ans = input("Proceed to create tables if missing in this DB? [y/N]: ").strip().lower()
    if ans not in ('y', 'yes'):
        print("Aborted.")
        sys.exit(0)

    conn = sqlite3.connect(dbpath)
    try:
        create_tables(conn)
        print("Ensured tables: inventory, inventory_tx")
        cur = conn.cursor()
        cur.execute("PRAGMA table_info('inventory')")
        print("inventory columns:", [r[1] for r in cur.fetchall()])
        cur.execute("PRAGMA table_info('inventory_tx')")
        print("inventory_tx columns:", [r[1] for r in cur.fetchall()])
    finally:
        conn.close()
        print("Migration finished.")

if __name__ == '__main__':
    main()
