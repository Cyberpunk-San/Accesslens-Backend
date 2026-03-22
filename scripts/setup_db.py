import asyncio
import os
import logging
from pathlib import Path
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def setup_database():
    """
    Minimal database setup script.
    Ensures the data directory exists and the database file can be created.
    Schema management is handled automatically by the application on startup.
    """
    try:
        # Import settings from app core
        from app.core.config import settings
        
        db_url = settings.database_url
        if not db_url or not db_url.startswith("sqlite:///"):
            # Fallback for unexpected configurations
            db_path = Path("accesslens.db")
        else:
            db_path = Path(db_url.replace("sqlite:///", ""))

        logger.info(f"Ensuring database directory exists for: {db_path}")
        
        # Create directory if it doesn't exist
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # We don't execute SQL here to avoid syntax conflicts with migrations.
        # The application (report_storage.py) handles its own table creation.
        logger.info("Database directory preparation complete.")
        return True

    except Exception as e:
        logger.error(f"Error during database directory setup: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(setup_database())
    sys.exit(0 if success else 1)