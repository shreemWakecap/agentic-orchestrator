#!/usr/bin/env python
"""
Database initialization script.

This script initializes the database schema. It can be run in two modes:
1. SQLAlchemy ORM mode (default): Uses SQLAlchemy to auto-create tables from models
2. SQL migration mode: Runs SQL migration files directly

Usage:
    python -m db.init_db              # Auto-create tables via SQLAlchemy
    python -m db.init_db --sql        # Run SQL migrations
    python -m db.init_db --drop       # Drop all tables first (DANGEROUS!)
    python -m db.init_db --check      # Check database connection only
"""
import argparse
import sys
from pathlib import Path

# Ensure orchestrator directory is in path
ORCHESTRATOR_DIR = Path(__file__).parent.parent
if str(ORCHESTRATOR_DIR) not in sys.path:
    sys.path.insert(0, str(ORCHESTRATOR_DIR))


def check_connection():
    """Test database connection."""
    print("Checking database connection...")
    try:
        from db.connection import Database
        db = Database()
        row = db.fetchone("SELECT 1 as test")
        if row and row.get('test') == 1:
            print("Database connection: OK")
            return True
        else:
            print("Database connection: FAILED (unexpected response)")
            return False
    except Exception as e:
        print(f"Database connection: FAILED ({e})")
        return False


def init_with_sqlalchemy(drop_first: bool = False):
    """Initialize database using SQLAlchemy ORM models."""
    print("Initializing database with SQLAlchemy ORM...")

    try:
        from sqlalchemy import create_engine
        from config import get_database_config
        from db.models import Base, create_all_tables, drop_all_tables

        db_config = get_database_config()
        engine = create_engine(db_config.sync_url, echo=False)

        if drop_first:
            print("  Dropping existing tables...")
            drop_all_tables(engine)
            print("  Tables dropped.")

        print("  Creating tables from ORM models...")
        create_all_tables(engine)
        print("  Tables created successfully.")

        # Verify tables exist
        from sqlalchemy import inspect
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        print(f"  Created {len(tables)} tables: {', '.join(sorted(tables))}")

        return True
    except Exception as e:
        print(f"  FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def init_with_sql(drop_first: bool = False):
    """Initialize database by running SQL migration files."""
    print("Initializing database with SQL migrations...")

    try:
        from sqlalchemy import create_engine, text
        from config import get_database_config

        db_config = get_database_config()
        engine = create_engine(db_config.sync_url, echo=False)

        migrations_dir = Path(__file__).parent / "migrations"

        if drop_first:
            print("  Dropping existing tables...")
            with engine.connect() as conn:
                # Get all tables and drop them
                result = conn.execute(text("""
                    SELECT tablename FROM pg_tables
                    WHERE schemaname = 'public'
                """))
                tables = [row[0] for row in result.fetchall()]
                for table in tables:
                    conn.execute(text(f'DROP TABLE IF EXISTS "{table}" CASCADE'))
                conn.commit()
            print(f"  Dropped {len(tables)} tables.")

        # Find and run migration files
        sql_files = sorted(migrations_dir.glob("*.sql"))

        if not sql_files:
            print("  No SQL migration files found.")
            return False

        for sql_file in sql_files:
            print(f"  Running migration: {sql_file.name}")
            sql_content = sql_file.read_text()

            with engine.connect() as conn:
                # Split by semicolon and execute each statement
                statements = [s.strip() for s in sql_content.split(';') if s.strip()]
                for stmt in statements:
                    if stmt and not stmt.startswith('--'):
                        try:
                            conn.execute(text(stmt))
                        except Exception as e:
                            # Ignore "already exists" errors for IF NOT EXISTS
                            if "already exists" not in str(e).lower():
                                print(f"    Warning: {e}")
                conn.commit()
            print(f"    Completed: {sql_file.name}")

        # Verify tables exist
        from sqlalchemy import inspect
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        print(f"  Created {len(tables)} tables: {', '.join(sorted(tables))}")

        return True
    except Exception as e:
        print(f"  FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(description="Initialize orchestrator database")
    parser.add_argument("--sql", action="store_true", help="Use SQL migrations instead of SQLAlchemy")
    parser.add_argument("--drop", action="store_true", help="Drop all tables first (DANGEROUS!)")
    parser.add_argument("--check", action="store_true", help="Only check database connection")
    args = parser.parse_args()

    if args.check:
        success = check_connection()
        sys.exit(0 if success else 1)

    if args.drop:
        response = input("WARNING: This will DROP ALL TABLES. Type 'yes' to confirm: ")
        if response.lower() != 'yes':
            print("Aborted.")
            sys.exit(1)

    if args.sql:
        success = init_with_sql(drop_first=args.drop)
    else:
        success = init_with_sqlalchemy(drop_first=args.drop)

    if success:
        print("\nDatabase initialization complete!")
    else:
        print("\nDatabase initialization FAILED!")
        sys.exit(1)


if __name__ == "__main__":
    main()
