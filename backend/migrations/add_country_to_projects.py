"""
Migration: Add country column to projects table
Run this script to add the country column to existing projects.

Usage:
    python migrations/add_country_to_projects.py
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from urllib.parse import urlparse


def run_migration():
    # Get database URL from environment or .env file
    database_url = os.environ.get("DATABASE_URL")

    if not database_url:
        # Try to load from .env file
        env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("DATABASE_URL="):
                        database_url = line.split("=", 1)[1].strip()
                        break

    if not database_url:
        print("ERROR: DATABASE_URL not configured")
        return False

    print(f"Connecting to database...")

    # Parse the database URL
    parsed = urlparse(database_url)

    # Connect to database
    conn = psycopg2.connect(
        host=parsed.hostname,
        port=parsed.port or 5432,
        user=parsed.username,
        password=parsed.password,
        dbname=parsed.path.lstrip("/").split("?")[0],
        sslmode="require"
    )

    try:
        cursor = conn.cursor()

        # Check if column already exists
        cursor.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'projects' AND column_name = 'country'
        """)
        exists = cursor.fetchone()

        if exists:
            print("Column 'country' already exists in 'projects' table. Skipping migration.")
            return True

        # Add the column
        print("Adding 'country' column to 'projects' table...")
        cursor.execute("""
            ALTER TABLE projects
            ADD COLUMN country VARCHAR(10) DEFAULT 'in'
        """)

        conn.commit()
        print("Migration completed successfully!")
        print("All existing projects now have country='in' (India) as default.")
        return True

    except Exception as e:
        print(f"ERROR: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
