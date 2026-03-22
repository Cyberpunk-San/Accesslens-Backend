# backend/scripts/cleanup.sh
#!/bin/bash

set -e

echo " AccessLens Cleanup Utility"
echo "============================="

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Function to ask for confirmation
confirm() {
    echo -e "${YELLOW}$1${NC}"
    read -p "Are you sure? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        return 1
    fi
    return 0
}

# Clean old reports
clean_reports() {
    echo -e "\n${YELLOW}Cleaning old reports...${NC}"
    
    # Default to 30 days
    DAYS=${1:-30}
    
    if confirm "Delete reports older than $DAYS days?"; then
        python scripts/cleanup_reports.py --days "$DAYS"
        echo -e "${GREEN} Old reports cleaned${NC}"
    fi
}

# Clean logs
clean_logs() {
    echo -e "\n${YELLOW}Cleaning log files...${NC}"
    
    # Log directory
    LOG_DIR="./logs"
    
    if [ -d "$LOG_DIR" ]; then
        # Show log sizes
        echo "Current log files:"
        ls -lh "$LOG_DIR"
        
        if confirm "Delete all log files?"; then
            rm -f "$LOG_DIR"/*.log
            echo -e "${GREEN} Logs cleaned${NC}"
        fi
    else
        echo "No log directory found"
    fi
}

# Clean cache
clean_cache() {
    echo -e "\n${YELLOW}Cleaning cache...${NC}"
    
    CACHE_DIR="./data/cache"
    
    if [ -d "$CACHE_DIR" ]; then
        # Show cache size
        CACHE_SIZE=$(du -sh "$CACHE_DIR" | cut -f1)
        echo "Cache size: $CACHE_SIZE"
        
        if confirm "Delete cache?"; then
            rm -rf "$CACHE_DIR"/*
            echo -e "${GREEN} Cache cleaned${NC}"
        fi
    else
        echo "No cache directory found"
    fi
}

# Clean screenshots
clean_screenshots() {
    echo -e "\n${YELLOW}Cleaning screenshots...${NC}"
    
    SCREENSHOT_DIR="./data/screenshots"
    
    if [ -d "$SCREENSHOT_DIR" ]; then
        # Show screenshot count
        COUNT=$(find "$SCREENSHOT_DIR" -type f -name "*.jpg" | wc -l)
        SIZE=$(du -sh "$SCREENSHOT_DIR" | cut -f1)
        echo "Screenshots: $COUNT files, $SIZE"
        
        if confirm "Delete all screenshots?"; then
            rm -f "$SCREENSHOT_DIR"/*.jpg
            echo -e "${GREEN} Screenshots cleaned${NC}"
        fi
    else
        echo "No screenshots directory found"
    fi
}

# Clean virtual environment
clean_venv() {
    echo -e "\n${YELLOW}Cleaning virtual environment...${NC}"
    
    if [ -d "venv" ]; then
        VENV_SIZE=$(du -sh "venv" | cut -f1)
        echo "Virtual environment size: $VENV_SIZE"
        
        if confirm "Delete virtual environment?"; then
            rm -rf venv
            echo -e "${GREEN} Virtual environment cleaned${NC}"
        fi
    else
        echo "No virtual environment found"
    fi
}

# Main menu
show_menu() {
    echo -e "\n${GREEN}What would you like to clean?${NC}"
    echo "1) Old reports (older than 30 days)"
    echo "2) Log files"
    echo "3) Cache"
    echo "4) Screenshots"
    echo "5) Virtual environment"
    echo "6) All"
    echo "0) Exit"
    
    read -p "Select option: " OPTION
    
    case $OPTION in
        1) clean_reports 30 ;;
        2) clean_logs ;;
        3) clean_cache ;;
        4) clean_screenshots ;;
        5) clean_venv ;;
        6)
            clean_reports 30
            clean_logs
            clean_cache
            clean_screenshots
            clean_redis
            ;;
        0) exit 0 ;;
        *) echo -e "${RED}Invalid option${NC}" ;;
    esac
}

# Parse command line arguments for non-interactive mode
if [ "$1" == "--all" ]; then
    clean_reports 30 <<< "y"
    clean_logs <<< "y"
    clean_cache <<< "y"
    clean_screenshots <<< "y"
    exit 0
elif [ "$1" == "--cache" ]; then
    clean_cache <<< "y"
    exit 0
elif [ "$1" == "--reports" ]; then
    clean_reports 30 <<< "y"
    exit 0
elif [ "$1" == "--db" ]; then
    clean_reports 0 <<< "y"
    exit 0
fi

# Parse CLI arguments for headless CI execution
if [ "$1" == "--all" ]; then
    clean_reports 30 <<< "y"
    clean_logs <<< "y"
    clean_cache <<< "y"
    clean_screenshots <<< "y"
    exit 0
elif [ "$1" == "--cache" ]; then
    clean_cache <<< "y"
    exit 0
elif [ "$1" == "--reports" ]; then
    clean_reports 30 <<< "y"
    exit 0
elif [ "$1" == "--db" ]; then
    clean_reports 0 <<< "y"
    exit 0
fi

# Main loop
while true; do
    show_menu
done