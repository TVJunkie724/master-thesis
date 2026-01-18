"""
Migration: Add L4/L5 columns to deployer_configurations table.

Run this script to add the new columns for Layer 4/5 support.
This is needed because SQLAlchemy's create_all() doesn't add columns to existing tables.

Usage:
    python -m migrations.add_l4_l5_columns
    
Or manually run the SQL:
    ALTER TABLE deployer_configurations ADD COLUMN hierarchy_content TEXT;
    ALTER TABLE deployer_configurations ADD COLUMN hierarchy_validated BOOLEAN DEFAULT 0;
    ALTER TABLE deployer_configurations ADD COLUMN scene_glb_uploaded BOOLEAN DEFAULT 0;
    ALTER TABLE deployer_configurations ADD COLUMN scene_config_content TEXT;
    ALTER TABLE deployer_configurations ADD COLUMN scene_config_validated BOOLEAN DEFAULT 0;
    ALTER TABLE deployer_configurations ADD COLUMN user_config_content TEXT;
    ALTER TABLE deployer_configurations ADD COLUMN user_config_validated BOOLEAN DEFAULT 0;
"""

import sqlite3
import os

def migrate():
    # Default path for development
    db_path = os.environ.get('DATABASE_URL', 'sqlite:///./data/app.db')
    
    # Handle SQLite URL format
    if db_path.startswith('sqlite:///'):
        db_path = db_path.replace('sqlite:///', '')
    
    print(f"Migrating database: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    columns_to_add = [
        # Section 2: L4 Config (Hierarchy)
        ('hierarchy_content', 'TEXT'),
        ('hierarchy_validated', 'BOOLEAN DEFAULT 0'),
        # Section 3: L4 (Digital Twin / Visualization)
        ('scene_glb_uploaded', 'BOOLEAN DEFAULT 0'),
        ('scene_config_content', 'TEXT'),
        ('scene_config_validated', 'BOOLEAN DEFAULT 0'),
        # Section 3: L4/L5 Shared (Platform User)
        ('user_config_content', 'TEXT'),
        ('user_config_validated', 'BOOLEAN DEFAULT 0'),
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
