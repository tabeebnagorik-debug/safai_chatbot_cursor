"""
Script to initialize database tables.
Run this script to create all necessary tables in the database.
"""
from database import init_db
import sys

if __name__ == "__main__":
    try:
        print("Initializing database tables...")
        init_db()
        print("✓ Database tables initialized successfully!")
        sys.exit(0)
    except Exception as e:
        print(f"✗ Error initializing database tables: {e}")
        sys.exit(1)

