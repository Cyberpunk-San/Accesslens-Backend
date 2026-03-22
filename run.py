#!/usr/bin/env python3
"""
AccessLens - Main entry point for running the API server
"""

import os
import sys
import uvicorn
import argparse
import logging
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from app.core.config import settings

def setup_environment():
    """Setup environment variables and paths"""
    # Create necessary directories
    directories = [
        settings.storage_path,
        settings.storage_path / "reports",
        settings.storage_path / "screenshots",
        settings.storage_path / "cache",
        Path("logs"),
        Path("models")
    ]
    
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
        print(f"✅ Created directory: {directory}")

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="AccessLens API Server")
    parser.add_argument("--host", type=str, default=settings.api_host, 
                       help=f"Host to bind to (default: {settings.api_host})")
    parser.add_argument("--port", type=int, default=settings.api_port, 
                       help=f"Port to bind to (default: {settings.api_port})")
    parser.add_argument("--reload", action="store_true", 
                       help="Enable auto-reload for development")
    parser.add_argument("--log-level", type=str, default=settings.log_level.lower(),
                       choices=["debug", "info", "warning", "error", "critical"],
                       help="Logging level")
    parser.add_argument("--setup", action="store_true",
                       help="Setup directories and exit")
    parser.add_argument("--version", action="store_true",
                       help="Show version and exit")
    
    args = parser.parse_args()
    
    if args.version:
        print("AccessLens v1.0.0")
        print("Layered Accessibility Auditing Framework")
        return 0
    
    if args.setup:
        setup_environment()
        print("✅ Setup complete!")
        return 0
    
    # Print banner (commented out due to potential encoding issues in Windows)
    # print("""
    # ╔══════════════════════════════════════════════════════════╗
    # ║                     AccessLens v1.0.0                    ║
    # ║           Layered Accessibility Auditing Framework        ║
    # ╚══════════════════════════════════════════════════════════╝
    # """)
    
    print(f"🚀 Starting server at http://{args.host}:{args.port}")
    print(f"📚 API Documentation: http://{args.host}:{args.port}/docs")
    print(f"🔧 Debug mode: {args.reload}")
    print(f"📝 Log level: {args.log_level}")
    print()
    
    # Run server
    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level,
        access_log=True,
        proxy_headers=True,
        forwarded_allow_ips="*"
    )
    
    return 0

if __name__ == "__main__":
    sys.exit(main())