"""
Slovoyad — Database Migration Runner

Usage:
    python migrate.py              # Apply all pending migrations
    python migrate.py status       # Show migration status
    python migrate.py create "description"  # Create new migration file

Migrations are .sql files in the migrations/ directory.
A _migrations table tracks which have been applied.
"""

import os
import sys
import glob
import datetime
import pymysql
from dotenv import load_dotenv

load_dotenv()

# --- Configuration ---

def get_db_config():
    return {
        "host": os.getenv("DB_HOST", "127.0.0.1"),
        "port": int(os.getenv("DB_PORT", 3306)),
        "user": os.getenv("DB_USERNAME", "root"),
        "password": os.getenv("DB_PASSWORD", ""),
        "database": os.getenv("DB_DATABASE", "slovoyad"),
        "charset": "utf8mb4",
    }

MIGRATIONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "migrations")

# --- Database Helpers ---

def get_connection():
    config = get_db_config()
    return pymysql.connect(**config)

def ensure_migrations_table(conn):
    """Create the _migrations tracking table if it doesn't exist."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS _migrations (
                id INT AUTO_INCREMENT PRIMARY KEY,
                filename VARCHAR(255) NOT NULL UNIQUE,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)
    conn.commit()

def get_applied_migrations(conn):
    """Return set of already-applied migration filenames."""
    with conn.cursor() as cur:
        cur.execute("SELECT filename FROM _migrations ORDER BY filename")
        return {row[0] for row in cur.fetchall()}

def get_migration_files():
    """Return sorted list of .sql files in the migrations directory."""
    if not os.path.isdir(MIGRATIONS_DIR):
        os.makedirs(MIGRATIONS_DIR, exist_ok=True)
        return []
    files = glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql"))
    return sorted([os.path.basename(f) for f in files])

# --- Commands ---

def cmd_migrate():
    """Apply all pending migrations in order."""
    conn = get_connection()
    try:
        ensure_migrations_table(conn)
        applied = get_applied_migrations(conn)
        all_files = get_migration_files()
        pending = [f for f in all_files if f not in applied]

        if not pending:
            print("✅ No pending migrations.")
            return

        print(f"📦 {len(pending)} pending migration(s):\n")

        for filename in pending:
            filepath = os.path.join(MIGRATIONS_DIR, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                sql = f.read().strip()

            if not sql:
                print(f"  ⚠️  {filename} — empty, skipping")
                continue

            print(f"  ▶ Applying: {filename} ... ", end="", flush=True)
            try:
                with conn.cursor() as cur:
                    # Execute multi-statement SQL
                    for statement in sql.split(";"):
                        statement = statement.strip()
                        if statement:
                            cur.execute(statement)
                    # Record the migration
                    cur.execute(
                        "INSERT INTO _migrations (filename) VALUES (%s)",
                        (filename,)
                    )
                conn.commit()
                print("✅")
            except Exception as e:
                conn.rollback()
                print(f"❌ FAILED")
                print(f"     Error: {e}")
                print(f"\n⛔ Migration aborted. Fix the issue and re-run.")
                sys.exit(1)

        print(f"\n✅ All {len(pending)} migration(s) applied successfully.")

    finally:
        conn.close()

def cmd_status():
    """Show which migrations have been applied and which are pending."""
    conn = get_connection()
    try:
        ensure_migrations_table(conn)
        applied = get_applied_migrations(conn)
        all_files = get_migration_files()

        if not all_files:
            print("📂 No migration files found in migrations/")
            return

        print(f"📋 Migration status ({len(all_files)} total):\n")
        for f in all_files:
            status = "✅ Applied" if f in applied else "⏳ Pending"
            print(f"  {status}  {f}")

        pending_count = len([f for f in all_files if f not in applied])
        print(f"\n  {len(applied)} applied, {pending_count} pending.")

    finally:
        conn.close()

def cmd_create(description):
    """Create a new empty migration file with timestamp prefix."""
    os.makedirs(MIGRATIONS_DIR, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_desc = description.lower().replace(" ", "_").replace("-", "_")
    # Remove non-alphanumeric chars except underscores
    safe_desc = "".join(c for c in safe_desc if c.isalnum() or c == "_")
    filename = f"{timestamp}_{safe_desc}.sql"
    filepath = os.path.join(MIGRATIONS_DIR, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"-- Migration: {description}\n")
        f.write(f"-- Created: {datetime.datetime.now().isoformat()}\n\n")

    print(f"✅ Created: migrations/{filename}")
    return filename

# --- Entry Point ---

def main():
    args = sys.argv[1:]

    if not args:
        cmd_migrate()
    elif args[0] == "status":
        cmd_status()
    elif args[0] == "create":
        if len(args) < 2:
            print("Usage: python migrate.py create \"description\"")
            sys.exit(1)
        cmd_create(" ".join(args[1:]))
    else:
        print(f"Unknown command: {args[0]}")
        print("Usage:")
        print("  python migrate.py              # Apply pending migrations")
        print("  python migrate.py status       # Show status")
        print('  python migrate.py create "desc" # Create new migration')
        sys.exit(1)

if __name__ == "__main__":
    main()
