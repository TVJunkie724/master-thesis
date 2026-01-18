"""
Migration: Add deployment lifecycle columns to digital_twins table.

Adds deployed_at and destroyed_at timestamp columns for cooldown tracking
(GCP Firestore requires 5-min wait after deletion before same name can be reused).

Usage:
    python -m migrations.add_deployment_lifecycle_columns
    
Or manually run the SQL:
    ALTER TABLE digital_twins ADD COLUMN deployed_at DATETIME;
    ALTER TABLE digital_twins ADD COLUMN destroyed_at DATETIME;
"""

import sqlite3
import os

def migrate():
    # Default path for development
    db_path = os.environ.get('DATABASE_URL', 'sqlite:///./management.db')
    
    # Handle SQLite URL format
    if db_path.startswith('sqlite:///'):
        db_path = db_path.replace('sqlite:///', '')
    
    print(f"Migrating database: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    columns_to_add = [
        ('deployed_at', 'DATETIME'),
        ('destroyed_at', 'DATETIME'),
    ]
    
    for column_name, column_type in columns_to_add:
        try:
            cursor.execute(f"ALTER TABLE digital_twins ADD COLUMN {column_name} {column_type}")
            print(f"✓ Added column: {column_name}")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                print(f"✓ Column already exists: {column_name}")
            else:
                raise
    
    conn.commit()
    conn.close()
    print("\n✓ Migration complete!")

if __name__ == "__main__":
    migrate()
