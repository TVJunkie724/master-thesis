"""
Migration: Add session_id and operation_type to deployments table.

Adds columns needed for proper deployment tracking and linking to DeploymentLog.

Usage:
    python -m migrations.add_deployment_session_columns
    
Or manually run the SQL:
    ALTER TABLE deployments ADD COLUMN session_id VARCHAR UNIQUE;
    ALTER TABLE deployments ADD COLUMN operation_type VARCHAR DEFAULT 'deploy';
    ALTER TABLE deployments ADD COLUMN error_message TEXT;
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
        ('session_id', 'VARCHAR'),
        ('operation_type', 'VARCHAR DEFAULT "deploy"'),
        ('error_message', 'TEXT'),
    ]
    
    for column_name, column_type in columns_to_add:
        try:
            cursor.execute(f"ALTER TABLE deployments ADD COLUMN {column_name} {column_type}")
            print(f"✓ Added column: {column_name}")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                print(f"✓ Column already exists: {column_name}")
            else:
                raise
    
    # Update status default from 'pending' to 'running'
    # (This is a cosmetic change, existing data can keep their values)
    
    conn.commit()
    conn.close()
    print("\n✓ Migration complete!")

if __name__ == "__main__":
    migrate()
