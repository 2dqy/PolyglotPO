#!/bin/bash

# PO Translation Tool - Docker Startup Script
# This script helps you easily deploy and manage the translation tool with Docker

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Docker is installed
check_docker() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
}

# Check if .env file exists
check_env() {
    if [ ! -f ".env" ]; then
        print_warning ".env file not found. Creating template..."
        cat > .env << EOF
# DeepSeek API Configuration
DEEPSEEK_API_KEY=your-deepseek-api-key-here

# Server Configuration
HOST=0.0.0.0
PORT=8002
DEBUG=false

# Storage Configuration
STORAGE_RETENTION_DAYS=1
CLEANUP_INTERVAL=3600

# Logging
LOG_LEVEL=INFO
EOF
        print_warning "Please edit .env file and add your DeepSeek API key before starting."
        return 1
    fi
    return 0
}

# Create data directories
create_directories() {
    print_status "Creating data directories..."
    mkdir -p data/storage/uploads
    mkdir -p data/storage/processed
    mkdir -p data/storage/downloads
    mkdir -p data/logs
    print_success "Data directories created."
}

# Build and start the application
start_app() {
    print_status "Building Docker image..."
    docker-compose build
    
    print_status "Starting PO Translation Tool..."
    docker-compose up -d
    
    print_success "PO Translation Tool is starting up!"
    print_status "Waiting for application to be ready..."
    
    # Wait for health check
    for i in {1..30}; do
        if curl -f http://localhost:8002/health &> /dev/null; then
            print_success "Application is ready!"
            print_success "Access the tool at: http://localhost:8002"
            return 0
        fi
        sleep 2
        echo -n "."
    done
    
    print_error "Application failed to start properly. Check logs with: docker-compose logs"
    return 1
}

# Stop the application
stop_app() {
    print_status "Stopping PO Translation Tool..."
    docker-compose down
    print_success "Application stopped."
}

# Show logs
show_logs() {
    docker-compose logs -f
}

# Show status
show_status() {
    print_status "Container Status:"
    docker-compose ps
    
    print_status "Application Health:"
    if curl -f http://localhost:8002/health &> /dev/null; then
        print_success "Application is healthy and running at http://localhost:8002"
    else
        print_error "Application is not responding"
    fi
}

# Cleanup old data
cleanup_data() {
    print_warning "This will remove all translation data and logs. Are you sure? (y/N)"
    read -r response
    if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
        print_status "Cleaning up data..."
        docker-compose down
        sudo rm -rf data/
        print_success "Data cleaned up."
    else
        print_status "Cleanup cancelled."
    fi
}

# Main script logic
case "${1:-start}" in
    "start")
        check_docker
        if check_env; then
            create_directories
            start_app
        else
            print_error "Please configure .env file first."
            exit 1
        fi
        ;;
    "stop")
        stop_app
        ;;
    "restart")
        stop_app
        sleep 2
        create_directories
        start_app
        ;;
    "logs")
        show_logs
        ;;
    "status")
        show_status
        ;;
    "cleanup")
        cleanup_data
        ;;
    "build")
        check_docker
        print_status "Building Docker image..."
        docker-compose build --no-cache
        print_success "Build completed."
        ;;
    *)
        echo "PO Translation Tool - Docker Management Script"
        echo ""
        echo "Usage: $0 [command]"
        echo ""
        echo "Commands:"
        echo "  start    - Start the application (default)"
        echo "  stop     - Stop the application"
        echo "  restart  - Restart the application"
        echo "  logs     - Show application logs"
        echo "  status   - Show application status"
        echo "  build    - Rebuild Docker image"
        echo "  cleanup  - Remove all data (destructive)"
        echo ""
        echo "Examples:"
        echo "  $0 start    # Start the application"
        echo "  $0 logs     # View logs"
        echo "  $0 status   # Check if running"
        ;;
esac 