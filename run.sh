#!/bin/bash

# run.sh - Script to run the RAG on PostgreSQL server
# This script handles both backend and frontend setup and execution

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print colored output
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

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check if Python package is installed
python_package_exists() {
    python -c "import $1" >/dev/null 2>&1
}

# Parse command line arguments
FRONTEND_DEV=false
BACKEND_ONLY=false
SETUP_ONLY=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --frontend-dev)
            FRONTEND_DEV=true
            shift
            ;;
        --backend-only)
            BACKEND_ONLY=true
            shift
            ;;
        --setup-only)
            SETUP_ONLY=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --frontend-dev    Run frontend in development mode (hot reloading)"
            echo "  --backend-only    Run only the backend server"
            echo "  --setup-only      Only perform setup, don't start servers"
            echo "  --help, -h        Show this help message"
            echo ""
            echo "Default: Run backend server with built frontend"
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

print_status "🚀 Starting RAG on PostgreSQL server setup..."

# Check required tools
print_status "Checking required tools..."

if ! command_exists python; then
    print_error "Python is not installed. Please install Python 3.10+ and try again."
    exit 1
fi

if ! command_exists node && [ "$BACKEND_ONLY" = false ]; then
    print_error "Node.js is not installed. Please install Node.js 18+ and try again."
    exit 1
fi

print_success "Required tools are available"

# Check if we're in the right directory
if [ ! -f "azure.yaml" ] || [ ! -d "src/backend" ]; then
    print_error "This script must be run from the project root directory"
    exit 1
fi

# Setup environment file
if [ ! -f ".env" ]; then
    if [ -f ".env.sample" ]; then
        print_status "Creating .env file from .env.sample..."
        cp .env.sample .env
        print_warning "Please edit .env file to configure your environment variables"
    else
        print_warning ".env file not found. You may need to create one manually."
    fi
fi

# Install Python dependencies if needed
print_status "Checking Python dependencies..."
if ! python_package_exists "fastapi" || ! python_package_exists "uvicorn"; then
    print_status "Installing Python dependencies..."
    python -m pip install -r requirements-dev.txt
    python -m pip install -e src/backend
    print_success "Python dependencies installed"
else
    print_success "Python dependencies are already installed"
fi

# Build frontend if not running backend-only
if [ "$BACKEND_ONLY" = false ]; then
    print_status "Setting up frontend..."
    
    cd src/frontend
    
    # Install npm dependencies if needed
    if [ ! -d "node_modules" ]; then
        print_status "Installing frontend dependencies..."
        npm install
        print_success "Frontend dependencies installed"
    else
        print_success "Frontend dependencies are already installed"
    fi
    
    # Build frontend if not in dev mode
    if [ "$FRONTEND_DEV" = false ]; then
        print_status "Building frontend..."
        npm run build
        print_success "Frontend built successfully"
    fi
    
    cd ../../
fi

# Check database setup
print_status "Checking database setup..."
if python -c "
import sys
sys.path.append('src/backend')
try:
    from fastapi_app.postgres_engine import create_postgres_engine_from_env
    print('Database configuration appears valid')
except ImportError as e:
    print(f'Database import error: {e}')
    sys.exit(1)
except Exception as e:
    print(f'Database setup may need attention: {e}')
" 2>/dev/null; then
    print_success "Database configuration looks good"
else
    print_warning "Database may need setup. You may need to run:"
    print_warning "  python ./src/backend/fastapi_app/setup_postgres_database.py"
    print_warning "  python ./src/backend/fastapi_app/setup_postgres_seeddata.py"
fi

# Exit if setup-only mode
if [ "$SETUP_ONLY" = true ]; then
    print_success "Setup completed successfully!"
    exit 0
fi

print_success "🎉 Setup completed! Starting server(s)..."

# Function to handle cleanup on exit
cleanup() {
    print_status "Shutting down servers..."
    # Kill background processes
    jobs -p | xargs -r kill
    exit 0
}

trap cleanup SIGINT SIGTERM

# Start servers based on mode
if [ "$FRONTEND_DEV" = true ]; then
    print_status "🔥 Starting backend server with hot reloading..."
    python -m uvicorn fastapi_app:create_app --factory --reload --host 0.0.0.0 --port 8000 &
    BACKEND_PID=$!
    
    print_status "⚡ Starting frontend development server with hot reloading..."
    cd src/frontend
    npm run dev &
    FRONTEND_PID=$!
    cd ../../
    
    print_success "🌟 Servers started!"
    print_status "📍 Backend: http://localhost:8000"
    print_status "📍 Frontend: http://localhost:5173"
    print_status "Press Ctrl+C to stop both servers"
    
    # Wait for both processes
    wait $BACKEND_PID $FRONTEND_PID

elif [ "$BACKEND_ONLY" = true ]; then
    print_status "🔥 Starting backend server only..."
    print_success "🌟 Backend server started!"
    print_status "📍 Backend: http://localhost:8000"
    print_status "Press Ctrl+C to stop the server"
    
    python -m uvicorn fastapi_app:create_app --factory --reload --host 0.0.0.0 --port 8000

else
    print_status "🔥 Starting backend server with built frontend..."
    print_success "🌟 Server started!"
    print_status "📍 Application: http://localhost:8000"
    print_status "Press Ctrl+C to stop the server"
    
    python -m uvicorn fastapi_app:create_app --factory --reload --host 0.0.0.0 --port 8000
fi