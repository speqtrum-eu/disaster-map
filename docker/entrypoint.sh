#!/bin/bash
# Docker Entrypoint Script for Disaster Map Backend

set -e

# Environment variables with defaults
APP_NAME="${APP_NAME:-disaster-map-backend}"
LOG_LEVEL="${LOG_LEVEL:-info}"
DEBUG_MODE="${DEBUG_MODE:-false}"
CONFIG_FILE="${CONFIG_FILE:-config/default.yaml}"

echo "========================================"
echo "  Disaster Map Backend Service Started"
echo "========================================"
echo ""
echo "Configuration:"
echo "  App Name:    $APP_NAME"
echo "  Config File: $CONFIG_FILE"
echo "  Log Level:   $LOG_LEVEL"
echo "  Debug Mode:  $DEBUG_MODE"
echo ""

# Health check endpoint setup
create_health_endpoint() {
    # Create a simple health check route if using FastAPI
    if [ -f "src/main.py" ]; then
        echo "Health check endpoint will be available at /health"
    fi
}

# Load configuration
load_config() {
    if [ -f "$CONFIG_FILE" ]; then
        echo "Loading configuration from $CONFIG_FILE"
    else
        echo "Warning: Configuration file not found, using defaults"
    fi
}

# Setup logging
setup_logging() {
    export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}$(pwd)"
    
    # Configure Python logging
    python -c "
import logging
import sys
from datetime import datetime

logging.basicConfig(
    level=getattr(logging, '$LOG_LEVEL'.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger('$APP_NAME')
logger.info('Disaster Map Backend initialized')
" 2>&1 || true
}

# Main entrypoint
main() {
    create_health_endpoint
    load_config
    setup_logging
    
    # Execute the main application
    exec python src/main.py "$@"
}

# Run main function with all arguments
main "$@"