#!/bin/bash
# LOG Deployment Script - Automated Installation
# Usage: ./deploy.sh [install|uninstall|status]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$PROJECT_ROOT/.env.local"
SERVICE_NAME="log-orthomosaic"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

check_dependencies() {
    log_info "Checking dependencies..."
    
    local deps=(
        "python3>=3.9"
        "pip>=21.0"
        "docker>=20.0"
        "redis-cli"
    )
    
    for dep in "${deps[@]}"; do
        if ! command -v "$dep" &> /dev/null; then
            log_error "Missing dependency: $dep"
            return 1
        fi
    done
    
    log_info "All dependencies installed ✓"
}

install_python_deps() {
    log_info "Installing Python dependencies..."
    
    local venv_dir="$PROJECT_ROOT/.venv"
    
    if [ -d "$venv_dir" ]; then
        log_warn "Virtual environment already exists at $venv_dir"
        
        # Check if requirements are up to date
        cd "$PROJECT_ROOT"
        pip install --upgrade pip > /dev/null 2>&1
        
        if ! pip list | grep -q "log-orthomosaic"; then
            log_info "Installing LOG package..."
            pip install -e ".[dev]" > /dev/null 2>&1 || {
                log_warn "Package installation failed, using requirements.txt"
                pip install -r "$PROJECT_ROOT/requirements.txt" > /dev/null 2>&1
            }
        fi
        
        log_info "Python dependencies installed ✓"
    else
        log_error "Virtual environment not found. Run: python3 -m venv .venv"
        return 1
    fi
}

install_systemd() {
    log_info "Installing systemd service..."
    
    local service_file="$SCRIPT_DIR/log-orthomosaic.service"
    local unit_dir="/etc/systemd/system"
    
    if [ ! -f "$service_file" ]; then
        log_error "Service file not found: $service_file"
        return 1
    fi
    
    # Create user and group if they don't exist
    if id "log" &>/dev/null; then
        log_info "User 'log' already exists, skipping creation"
    else
        log_info "Creating user 'log'..."
        useradd -r -s /usr/sbin/nologin -d "$PROJECT_ROOT" log 2>/dev/null || {
            log_warn "Could not create user 'log', running as root instead"
        }
    fi
    
    # Install service file
    if [ -d "$unit_dir" ]; then
        cp "$service_file" "$unit_dir/"
        
        # Reload systemd daemon
        systemctl daemon-reload 2>/dev/null || {
            log_warn "Could not reload systemd daemon (not running as root)"
        }
        
        log_info "Systemd service installed ✓"
    else
        log_error "Unit directory not found: $unit_dir"
        return 1
    fi
}

setup_directories() {
    log_info "Setting up directories..."
    
    local dirs=(
        "$PROJECT_ROOT/data"
        "$PROJECT_ROOT/outputs"
        "$PROJECT_ROOT/temp"
    )
    
    for dir in "${dirs[@]}"; do
        mkdir -p "$dir"
        chmod 755 "$dir"
    done
    
    log_info "Directories created ✓"
}

start_service() {
    log_info "Starting LOG server..."
    
    # Check if running as root (required for systemd)
    if [ "$(id -u)" != "0" ]; then
        log_error "This script requires root privileges to start the service"
        log_info "Run: sudo $0 start"
        return 1
    fi
    
    # Start with docker-compose if available
    if command -v docker-compose &> /dev/null; then
        cd "$PROJECT_ROOT"
        docker-compose up -d log-server
        
        sleep 5
        
        if docker ps | grep -q "log-server"; then
            log_info "LOG server started ✓"
            return 0
        else
            log_error "Failed to start LOG server"
            return 1
        fi
    elif command -v systemctl &> /dev/null; then
        # Start with systemd
        if [ -f "/etc/systemd/system/log-orthomosaic.service" ]; then
            systemctl enable --now log-orthomosaic
            
            sleep 2
            
            if systemctl is-active --quiet log-orthomosaic; then
                log_info "LOG server started via systemd ✓"
                return 0
            else
                log_error "Failed to start LOG server via systemd"
                return 1
            fi
        else
            log_error "Systemd service not installed. Run: $0 install"
            return 1
        fi
    else
        log_error "No container manager or systemd found"
        return 1
    fi
}

stop_service() {
    log_info "Stopping LOG server..."
    
    if command -v docker-compose &> /dev/null; then
        cd "$PROJECT_ROOT"
        docker-compose down log-server
        
        log_info "LOG server stopped ✓"
    elif command -v systemctl &> /dev/null; then
        systemctl stop log-orthomosaic 2>/dev/null || true
        log_info "LOG server stopped ✓"
    else
        log_warn "No container manager or systemd found to stop service"
    fi
}

show_status() {
    log_info "LOG Server Status:"
    
    if command -v docker-compose &> /dev/null; then
        cd "$PROJECT_ROOT"
        docker-compose ps
        
        echo ""
        echo "Logs (last 20 lines):"
        docker-compose logs --tail=20 || true
    elif command -v systemctl &> /dev/null; then
        if systemctl is-active --quiet log-orthomosaic; then
            echo "Status: Running"
            systemctl status log-orthomosaic --no-pager -l 2>/dev/null | head -10
        else
            echo "Status: Stopped"
        fi
    else
        log_warn "No container manager or systemd found to check status"
    fi
    
    echo ""
    echo "Health Check:"
    
    if command -v curl &> /dev/null; then
        if curl -s http://localhost:8080/health &>/dev/null; then
            log_info "Server is responding ✓"
        else
            log_warn "Server not responding at localhost:8080"
        fi
    fi
}

uninstall() {
    log_info "Uninstalling LOG server..."
    
    stop_service
    
    if command -v systemctl &> /dev/null; then
        systemctl disable --now log-orthomosaic 2>/dev/null || true
        rm -f "/etc/systemd/system/log-orthomosaic.service"
        systemctl daemon-reload 2>/dev/null || true
        
        # Remove user if it was created by this script
        id "log" &>/dev/null && userdel log 2>/dev/null || true
    fi
    
    log_info "LOG server uninstalled ✓"
}

# Main command handler
case "${1:-status}" in
    install)
        check_dependencies || exit 1
        install_python_deps || exit 1
        setup_directories
        install_systemd
        log_info "Installation complete!"
        ;;
    
    uninstall)
        uninstall
        ;;
    
    start)
        check_dependencies || exit 1
        install_python_deps || exit 1
        start_service
        ;;
    
    stop)
        stop_service
        ;;
    
    status)
        show_status
        ;;
    
    restart)
        stop_service
        sleep 2
        start_service
        ;;
    
    *)
        echo "Usage: $0 {install|uninstall|start|stop|status|restart}"
        exit 1
        ;;
esac
