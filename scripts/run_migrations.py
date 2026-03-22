import asyncio
import aiosqlite
import argparse
from pathlib import Path
import logging
import sys

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def run_migrations(db_path: str):
    path = Path(db_path)
    if not path.exists():
        logger.error(f"Database file not found at {db_path}. Run setup_db.py first.")
        return

    try:
        async with aiosqlite.connect(db_path) as db:
            # 1. Create migration table if not exists
            await db.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 2. Get current version
            async with db.execute("SELECT MAX(version) FROM schema_migrations") as cursor:
                row = await cursor.fetchone()
                current = row[0] if row and row[0] is not None else 0

            # 3. Apply missing migrations
            migrations_dir = Path(__file__).parent.parent / "migrations"
            migration_files = sorted(migrations_dir.glob("*.sql"))

            for migration_file in migration_files:
                try:
                    version = int(migration_file.stem.split('_')[0])
                except (ValueError, IndexError):
                    logger.warning(f"Skipping invalid migration file: {migration_file.name}")
                    continue

                if version > current:
                    with open(migration_file, 'r') as f:
                        sql = f.read()

                    # SKIP if it's a PostgreSQL-only migration and we are on SQLite
                    if "POSTGRESQL-ONLY" in sql or "JSONB" in sql or "UUID" in sql:
                        logger.info(f"Skipping incompatible migration {migration_file.name} for SQLite")
                        continue

                    logger.info(f"Applying migration {migration_file.name}...")

                    # SQLite executescript allows multiple statements
                    await db.executescript(sql)
                    await db.execute(
                        "INSERT INTO schema_migrations (version, name) VALUES (?, ?)",
                        (version, migration_file.name)
                    )
                    await db.commit()
                    logger.info(f"Migration {migration_file.name} applied successfully")

        logger.info("All migrations completed")
        
    except Exception as e:
        logger.error(f"Migration process failed: {e}")
        raise

def main():
    parser = argparse.ArgumentParser(description="Run AccessLens SQLite migrations")
    parser.add_argument("--db-path", default="./accesslens.db", help="Path to SQLite database")

    args = parser.parse_args()

    asyncio.run(run_migrations(db_path=args.db_path))

if __name__ == "__main__":
    main()