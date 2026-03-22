#!/bin/bash

# AccessLens Model Download Script
# Downloads AI models for accessibility analysis

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
MODELS_DIR="${1:-./models}"
LOG_FILE="download_models.log"

# Print banner
echo -e "${BLUE}"
echo ""
echo "           AccessLens AI Model Downloader                "
echo ""
echo -e "${NC}"

# Function to log messages
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
}

warn() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$LOG_FILE"
}

# Check for required tools
check_requirements() {
    log "Checking system requirements..."
    
    # Check for curl/wget
    if command -v curl &> /dev/null; then
        DOWNLOAD_CMD="curl -L -O"
        log " curl found"
    elif command -v wget &> /dev/null; then
        DOWNLOAD_CMD="wget"
        log " wget found"
    else
        error "Neither curl nor wget found. Please install one of them."
        exit 1
    fi
    
    # Check for available disk space
    if command -v df &> /dev/null; then
        AVAILABLE_SPACE=$(df -BG "$MODELS_DIR" 2>/dev/null | awk 'NR==2 {print $4}' | sed 's/G//')
        if [ -z "$AVAILABLE_SPACE" ]; then
            AVAILABLE_SPACE=$(df -BG . | awk 'NR==2 {print $4}' | sed 's/G//')
        fi
        
        log "Available disk space: ${AVAILABLE_SPACE}GB"
        
        if [ "$AVAILABLE_SPACE" -lt 30 ]; then
            warn "Low disk space! Need at least 30GB for both models."
            read -p "Continue anyway? (y/N) " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                exit 1
            fi
        fi
    fi
    
    # Check Python
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version)
        log " $PYTHON_VERSION found"
    else
        error "Python 3 not found"
        exit 1
    fi
}

# Create directory structure
create_directories() {
    log "Creating model directories..."
    mkdir -p "$MODELS_DIR"/{llava,mistral-7b}
    log " Directories created at $MODELS_DIR"
}

# Download LLaVA model
download_llava() {
    log " Downloading LLaVA model (13.5GB)..."
    
    cd "$MODELS_DIR/llava"
    
    FILES=(
        "pytorch_model.bin"
        "config.json"
        "tokenizer.model"
        "tokenizer_config.json"
        "special_tokens_map.json"
        "preprocessor_config.json"
    )
    
    BASE_URL="https://huggingface.co/liuhaotian/llava-v1.5-7b/resolve/main"
    
    for file in "${FILES[@]}"; do
        if [ -f "$file" ]; then
            log "   $file already exists"
        else
            log "  Downloading $file..."
            if [ "$DOWNLOAD_CMD" = "curl -L -O" ]; then
                curl -L -O "$BASE_URL/$file" || {
                    error "Failed to download $file"
                    return 1
                }
            else
                wget "$BASE_URL/$file" || {
                    error "Failed to download $file"
                    return 1
                }
            fi
        fi
    done
    
    # Create marker file
    echo "Downloaded on $(date)" > .downloaded
    
    log " LLaVA model downloaded successfully"
    cd - > /dev/null
}

# Download Mistral 7B model
download_mistral() {
    log " Downloading Mistral 7B model (14GB)..."
    
    cd "$MODELS_DIR/mistral-7b"
    
    FILES=(
        "pytorch_model-00001-of-00003.bin"
        "pytorch_model-00002-of-00003.bin"
        "pytorch_model-00003-of-00003.bin"
        "config.json"
        "tokenizer.model"
        "tokenizer_config.json"
        "special_tokens_map.json"
        "generation_config.json"
    )
    
    BASE_URL="https://huggingface.co/mistralai/Mistral-7B-v0.1/resolve/main"
    
    for file in "${FILES[@]}"; do
        if [ -f "$file" ]; then
            log "   $file already exists"
        else
            log "  Downloading $file..."
            if [ "$DOWNLOAD_CMD" = "curl -L -O" ]; then
                curl -L -O "$BASE_URL/$file" || {
                    error "Failed to download $file"
                    return 1
                }
            else
                wget "$BASE_URL/$file" || {
                    error "Failed to download $file"
                    return 1
                }
            fi
        fi
    done
    
    # Create marker file
    echo "Downloaded on $(date)" > .downloaded
    
    log " Mistral 7B model downloaded successfully"
    cd - > /dev/null
}

# Verify downloads
verify_downloads() {
    log " Verifying downloads..."
    
    # Check LLaVA
    if [ -f "$MODELS_DIR/llava/.downloaded" ]; then
        LLAVA_SIZE=$(du -sh "$MODELS_DIR/llava" 2>/dev/null | cut -f1)
        log " LLaVA: $LLAVA_SIZE"
    else
        warn " LLaVA download incomplete"
    fi
    
    # Check Mistral
    if [ -f "$MODELS_DIR/mistral-7b/.downloaded" ]; then
        MISTRAL_SIZE=$(du -sh "$MODELS_DIR/mistral-7b" 2>/dev/null | cut -f1)
        log " Mistral: $MISTRAL_SIZE"
    else
        warn " Mistral download incomplete"
    fi
}

# Show help
show_help() {
    echo "Usage: $0 [OPTIONS]"
    echo
    echo "Options:"
    echo "  --help          Show this help message"
    echo "  --path DIR      Download models to DIR (default: ./models)"
    echo "  --llava-only    Download only LLaVA model"
    echo "  --mistral-only  Download only Mistral model"
    echo "  --verify        Verify existing downloads only"
    echo
    echo "Examples:"
    echo "  $0 --path /data/models"
    echo "  $0 --llava-only"
    echo "  $0 --verify"
}

# Main function
main() {
    local DOWNLOAD_LLAVA=true
    local DOWNLOAD_MISTRAL=true
    local VERIFY_ONLY=false
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --help)
                show_help
                exit 0
                ;;
            --path)
                MODELS_DIR="$2"
                shift 2
                ;;
            --llava-only)
                DOWNLOAD_MISTRAL=false
                shift
                ;;
            --mistral-only)
                DOWNLOAD_LLAVA=false
                shift
                ;;
            --verify)
                VERIFY_ONLY=true
                shift
                ;;
            *)
                error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    # Check requirements
    check_requirements
    
    if [ "$VERIFY_ONLY" = true ]; then
        verify_downloads
        exit 0
    fi
    
    # Create directories
    create_directories
    
    # Show download summary
    echo
    log "Download Summary:"
    if [ "$DOWNLOAD_LLAVA" = true ]; then
        log "  - LLaVA (13.5GB)"
    fi
    if [ "$DOWNLOAD_MISTRAL" = true ]; then
        log "  - Mistral 7B (14GB)"
    fi
    echo
    
    # Confirm download
    read -p "Start download? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log "Download cancelled"
        exit 0
    fi
    
    # Download models
    if [ "$DOWNLOAD_LLAVA" = true ]; then
        download_llava || warn "LLaVA download had issues"
    fi
    
    if [ "$DOWNLOAD_MISTRAL" = true ]; then
        download_mistral || warn "Mistral download had issues"
    fi
    
    # Final verification
    verify_downloads
    
    echo
    log " Download process completed!"
    log "Models saved to: $MODELS_DIR"
    log "Check $LOG_FILE for detailed log"
}

# Run main function
main "$@"