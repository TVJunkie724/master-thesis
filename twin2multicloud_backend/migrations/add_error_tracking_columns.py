"""
Migration: Add last_error and transient state columns to digital_twins table.

Adds last_error column for storing deployment/destroy error messages.
Also updates the twin_state enum to include DEPLOYING and DESTROYING states.

Usage:
    python -m migrations.add_error_tracking_columns
    
Or manually run the SQL:
    ALTER TABLE digital_twins ADD COLUMN last_error TEXT;
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
        ('last_error', 'TEXT'),
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
    
    # Note: SQLite doesn't support altering ENUM types directly.
    # The new DEPLOYING and DESTROYING states are handled at the application level.
    # SQLAlchemy Enum validation happens in Python, not in SQLite.
    print("✓ Note: DEPLOYING/DESTROYING states are handled at application level (SQLAlchemy Enum)")
    
    conn.commit()
    conn.close()
    print("\n✓ Migration complete!")

if __name__ == "__main__":
    migrate()
