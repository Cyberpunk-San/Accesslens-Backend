#!/bin/bash
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN} Starting AccessLens Development Environment${NC}"
echo "========================================"

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

echo -e "\n${YELLOW}Checking prerequisites...${NC}"

if ! command_exists python3; then
    echo -e "${RED} Python 3 not found${NC}"
    exit 1
fi

if ! command_exists npm; then
    echo -e "${RED} npm not found${NC}"
    exit 1
fi

# Start Redis for caching if needed
echo -e "\n${YELLOW}Redis is used for caching only.${NC}"
read -p " Start Redis container? [y/N] " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Starting Redis...${NC}"
    docker-compose up -d redis
    echo -e "${GREEN} Redis started${NC}"
fi

echo -e "${GREEN} All prerequisites satisfied${NC}"

# Activate virtual environment
echo -e "\n${YELLOW}Activating virtual environment...${NC}"
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
    echo -e "${GREEN} Virtual environment activated${NC}"
else
    echo -e "${RED} Virtual environment not found. Run setup.sh first${NC}"
    exit 1
fi

# Check if .env exists
if [ ! -f ".env" ]; then
    echo -e "${RED} .env file not found. Run setup.sh first${NC}"
    exit 1
fi

# Load environment variables
export $(grep -v '^#' .env | xargs)

# Start backend
echo -e "\n${YELLOW}Starting backend server...${NC}"
uvicorn app.main:app --reload --reload-dir app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
echo -e "${GREEN} Backend started (PID: $BACKEND_PID)${NC}"

# Wait for backend
sleep 3

# Start frontend
echo -e "\n${YELLOW}Starting frontend...${NC}"
cd ../frontend
npm run dev &
FRONTEND_PID=$!
cd ../backend
echo -e "${GREEN} Frontend started (PID: $FRONTEND_PID)${NC}"

echo -e "\n${GREEN} All services started!${NC}"
echo -e " Frontend: ${GREEN}http://localhost:3000${NC}"
echo -e " Backend API: ${GREEN}http://localhost:8000${NC}"

trap 'echo -e "\n${YELLOW}Stopping services...${NC}"; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0' INT TERM

wait