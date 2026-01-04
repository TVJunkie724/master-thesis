"""
Migration: Add requirements columns to deployer_configurations table.

Run this script to add the new columns for requirements.txt support.
This is needed because SQLAlchemy's create_all() doesn't add columns to existing tables.

Usage:
    python -m migrations.add_requirements_columns
    
Or manually run the SQL:
    ALTER TABLE deployer_configurations ADD COLUMN processor_requirements TEXT;
    ALTER TABLE deployer_configurations ADD COLUMN event_feedback_requirements TEXT;
    ALTER TABLE deployer_configurations ADD COLUMN event_action_requirements TEXT;
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
        ('processor_requirements', 'TEXT'),
        ('event_feedback_requirements', 'TEXT'),
        ('event_action_requirements', 'TEXT'),
    ]
    
    for column_name, column_type in columns_to_add:
        try:
            cursor.execute(f"ALTER TABLE deployer_configurations ADD COLUMN {column_name} {column_type}")
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
