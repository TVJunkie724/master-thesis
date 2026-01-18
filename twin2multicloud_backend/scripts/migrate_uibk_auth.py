"""
Migration script to add UIBK authentication fields to the users table.

This script adds the following columns to the 'users' table:
- uibk_id: Stores the eduPersonPrincipalName from SAML assertion
- auth_provider: Tracks which provider was used for initial login ("google" | "uibk")
- last_login_at: Tracks the last login timestamp

Run this script once to migrate existing databases.

Usage:
    docker exec -it master-thesis-management-backend-1 python -m scripts.migrate_uibk_auth

Or manually:
    cd twin2multicloud_backend
    PYTHONPATH=/app python -c "from scripts.migrate_uibk_auth import migrate; migrate()"
"""

import sqlite3
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import settings


def migrate():
    """Add UIBK authentication columns to users table."""
    
    # Extract database path from URL
    db_url = settings.DATABASE_URL
    if db_url.startswith("sqlite:///"):
        db_path = db_url.replace("sqlite:///", "")
        # Handle relative paths
        if db_path.startswith("./"):
            db_path = db_path[2:]
    else:
        print(f"This script only supports SQLite. Current DB: {db_url}")
        return False
    
    print(f"Migrating database: {db_path}")
    
    if not os.path.exists(db_path):
        print(f"Database file not found: {db_path}")
        print("The database will be created with the new schema when the application starts.")
        return True
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(users)")
        columns = {row[1] for row in cursor.fetchall()}
        
        migrations_applied = []
        
        # Add uibk_id column (SQLite doesn't support UNIQUE in ALTER TABLE, so add column first, index later)
        if 'uibk_id' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN uibk_id TEXT")
            migrations_applied.append("uibk_id")
            print("  ✓ Added column: uibk_id")
        else:
            print("  - Column uibk_id already exists")
        
        # Add auth_provider column with default
        if 'auth_provider' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN auth_provider TEXT NOT NULL DEFAULT 'google'")
            migrations_applied.append("auth_provider")
            print("  ✓ Added column: auth_provider (default: 'google')")
        else:
            print("  - Column auth_provider already exists")
        
        # Add last_login_at column
        if 'last_login_at' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN last_login_at DATETIME")
            migrations_applied.append("last_login_at")
            print("  ✓ Added column: last_login_at")
        else:
            print("  - Column last_login_at already exists")
        
        # Create index on uibk_id if not exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='index' AND name='ix_users_uibk_id'
        """)
        if not cursor.fetchone():
            cursor.execute("CREATE UNIQUE INDEX ix_users_uibk_id ON users(uibk_id)")
            migrations_applied.append("ix_users_uibk_id")
            print("  ✓ Created index: ix_users_uibk_id")
        else:
            print("  - Index ix_users_uibk_id already exists")
        
        conn.commit()
        conn.close()
        
        if migrations_applied:
            print(f"\n✅ Migration complete! Applied: {', '.join(migrations_applied)}")
        else:
            print("\n✅ Database already up to date.")
        
        return True
        
    except sqlite3.Error as e:
        print(f"❌ Migration failed: {e}")
        return False


if __name__ == "__main__":
    success = migrate()
    sys.exit(0 if success else 1)
