"""
Quick migration to add theme_preference column to users table.
Run this once to fix the database schema.
"""
import sqlite3
import os

def migrate():
    db_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'app.db')
    
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if column already exists
    cursor.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'theme_preference' in columns:
        print("Column 'theme_preference' already exists. Nothing to do.")
    else:
        print("Adding 'theme_preference' column to users table...")
        cursor.execute("ALTER TABLE users ADD COLUMN theme_preference TEXT DEFAULT 'dark'")
        conn.commit()
        print("Migration complete!")
    
    conn.close()

if __name__ == "__main__":
    migrate()
