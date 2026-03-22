#!/bin/bash

# AccessLens Setup Script
set -e

echo " Setting up AccessLens..."
echo "==========================="

# Create directory structure
echo " Creating directories..."
mkdir -p models/llava
mkdir -p models/mistral-7b
mkdir -p data/reports
mkdir -p data/screenshots
mkdir -p data/cache
mkdir -p logs

# Set permissions
chmod -R 755 models
chmod -R 755 data
chmod -R 755 logs

# Check Python version
echo " Checking Python version..."
# Accepting 3.10 or higher for broader compatibility
python_version=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
required_version="3.10"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" = "$required_version" ]; then 
    echo " Python $python_version detected"
else
    echo " Python $required_version or higher required (detected: $python_version)"
    exit 1
fi

# Create virtual environment
echo " Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install dependencies
echo " Installing Python dependencies..."
pip install --upgrade pip
# Note: requirements.txt is optimized for fast builds
pip install --default-timeout=1000 -r requirements.txt

# Install Playwright browsers
echo " Installing Playwright browsers..."
playwright install chromium
playwright install-deps

# Copy environment file
if [ ! -f .env ]; then
    echo " Creating .env file..."
    cp .env.example .env
    echo " Please edit .env with your configuration"
fi

# Ask about model download (Optional)
echo ""
echo "AI models are ~30GB. You can skip this and use API endpoints instead."
read -p " Download AI models now? [y/N] " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Downloading models..."
    python scripts/download_models.py --path ./models --all
fi

# Setup database (SQLite)
echo ""
read -p " Initialize SQLite database? [y/N] " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    python scripts/setup_db.py
fi

echo ""
echo " Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env file with your configuration"
echo "2. Start the backend: uvicorn app.main:app --reload"
echo "3. Start the frontend: cd ../frontend && npm run dev"
echo ""
echo " Documentation: http://localhost:8000/docs"