import argparse
import shutil
from pathlib import Path
import sys

def main():
    parser = argparse.ArgumentParser(description="Restore AccessLens SQLite database")
    parser.add_argument("backup_file", help="The backup .db file to restore")
    parser.add_argument("--dest", default="./accesslens.db", help="Destination database path (default: ./accesslens.db)")

    args = parser.parse_args()

    backup_path = Path(args.backup_file)
    dest_path = Path(args.dest)

    if not backup_path.exists():
        print(f" Error: Backup file not found: {backup_path}")
        return 1

    print(f" Warning: This will overwrite your current database at {dest_path}")
    response = input("Are you sure you want to continue? [y/N]: ")

    if response.lower() != 'y':
        print("Restore cancelled")
        return 0

    try:
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        
        print(f"Restoring {backup_path} to {dest_path}...")
        shutil.copy2(backup_path, dest_path)
        
        print(" Database restored successfully!")
        return 0
        
    except Exception as e:
        print(f" Restore failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())