import asyncio
import aiosqlite
import argparse
from datetime import datetime, timedelta
from pathlib import Path
import sys

async def cleanup_reports(days: int, db_path: str):
    path = Path(db_path)
    if not path.exists():
        print(f"Database file not found at {db_path}")
        return

    cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()

    try:
        async with aiosqlite.connect(db_path) as db:
            # Check count
            async with db.execute("SELECT COUNT(*) FROM reports WHERE timestamp < ?", (cutoff_date,)) as cursor:
                row = await cursor.fetchone()
                count = row[0] if row else 0

            if count == 0:
                print(f"No reports older than {days} days found")
                return

            print(f"Found {count} reports older than {days} days")

            # Delete
            await db.execute("DELETE FROM reports WHERE timestamp < ?", (cutoff_date,))
            await db.commit()
            print(f"Deleted {count} old reports from database")
            
    except Exception as e:
        print(f"Cleanup failed: {e}")

def main():
    parser = argparse.ArgumentParser(description="Clean up old reports from SQLite")
    parser.add_argument("--days", type=int, default=30, help="Delete reports older than DAYS")
    parser.add_argument("--db-path", default="./accesslens.db", help="Path to SQLite database")

    args = parser.parse_args()

    asyncio.run(cleanup_reports(days=args.days, db_path=args.db_path))

if __name__ == "__main__":
    main()