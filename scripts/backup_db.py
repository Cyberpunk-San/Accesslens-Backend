import argparse
import shutil
from datetime import datetime
from pathlib import Path
import sys

def main():
    parser = argparse.ArgumentParser(description="Backup AccessLens SQLite database")
    parser.add_argument("--db-path", default="./accesslens.db", help="Path to the database file")
    parser.add_argument("--output", default="./backups", help="Output directory for backup")

    args = parser.parse_args()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    db_path = Path(args.db_path)
    output_dir = Path(args.output)
    
    if not db_path.exists():
        print(f" Error: Database file not found at {db_path}")
        return 1

    output_dir.mkdir(parents=True, exist_ok=True)
    backup_file = f"accesslens_backup_{timestamp}.db"
    backup_path = output_dir / backup_file

    try:
        print(f"Creating backup: {backup_path}")
        shutil.copy2(db_path, backup_path)
        print(f" Backup created successfully: {backup_path}")
        print(f"Size: {backup_path.stat().st_size / 1024 / 1024:.2f} MB")
        return 0
    except Exception as e:
        print(f" Backup failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())