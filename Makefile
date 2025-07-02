# FENIX - Fenestration Intelligence eXpert
# Makefile for development and deployment

.PHONY: help build up down logs test clean install-deps dev-setup

# Default target
help:
	@echo "FENIX - Available commands:"
	@echo "  build      - Build all Docker containers"
	@echo "  up         - Start all services"
	@echo "  down       - Stop all services"
	@echo "  logs       - Show logs from all services"
	@echo "  test       - Run tests for all services"
	@echo "  clean      - Clean up containers and volumes"
	@echo "  dev-setup  - Set up development environment"
	@echo "  install-deps - Install Python dependencies locally"
	@echo "  lint       - Check code quality with ruff"
	@echo "  format     - Format code with ruff"
	@echo "  lint-fix   - Fix linting issues automatically"
	@echo "  setup-dev  - Setup pre-commit hooks and dev tools"
	@echo "  check-code - Run both linting and formatting"

# Build all containers
build:
	@echo "Building FENIX containers..."
	docker compose build

# Start all services
up:
	@echo "Starting FENIX services..."
	docker compose up -d
	@echo "Services started. Gateway available at http://localhost:8000"

# Stop all services
down:
	@echo "Stopping FENIX services..."
	docker compose down

# Show logs
logs:
	@echo "Showing FENIX logs..."
	docker compose logs -f

# Run tests
test:
	@echo "Running tests..."
	docker compose exec eagle pytest tests/ -v || echo "Eagle tests not available yet"

# Code quality commands
lint:
	@echo "Running linting for all services..."
	cd fenix-eagle && ruff check .
	cd fenix-gateway && ruff check .
	cd fenix-core && ruff check .
	cd fenix-oracle && ruff check .
	cd fenix-archer && ruff check .
	cd fenix-bolt && ruff check .
	cd fenix-shield && ruff check .

format:
	@echo "Formatting code for all services..."
	cd fenix-eagle && ruff format .
	cd fenix-gateway && ruff format .
	cd fenix-core && ruff format .
	cd fenix-oracle && ruff format .
	cd fenix-archer && ruff format .
	cd fenix-bolt && ruff format .
	cd fenix-shield && ruff format .

lint-fix:
	@echo "Fixing linting issues for all services..."
	cd fenix-eagle && ruff check --fix .
	cd fenix-gateway && ruff check --fix .
	cd fenix-core && ruff check --fix .
	cd fenix-oracle && ruff check --fix .
	cd fenix-archer && ruff check --fix .
	cd fenix-bolt && ruff check --fix .
	cd fenix-shield && ruff check --fix .

# Pre-commit setup
setup-dev:
	@echo "Setting up development environment..."
	pip install pre-commit ruff
	pre-commit install
	@echo "Development environment ready!"

check-code: lint format
	@echo "Code quality check complete!"
	
# Clean up
clean:
	@echo "Cleaning up FENIX..."
	docker compose down -v
	docker system prune -f
	docker volume prune -f

# Development setup
dev-setup:
	@echo "Setting up FENIX development environment..."
	cp .env.example .env
	@echo "Please edit .env file with your API keys and configuration"
	@echo "Then run 'make build && make up' to start the services"

# Install local dependencies for development
install-deps:
	@echo "Installing Python dependencies locally..."
	cd fenix-eagle && pip install -r requirements.txt
	cd fenix-archer && pip install -r requirements.txt
	cd fenix-oracle && pip install -r requirements.txt
	cd fenix-bolt && pip install -r requirements.txt
	cd fenix-shield && pip install -r requirements.txt
	cd fenix-core && pip install -r requirements.txt

# Individual service commands
eagle-up:
	docker compose up -d eagle

gateway-up:
	docker compose up -d gateway

# Development commands
dev-eagle:
	@echo "Starting FENIX Eagle in development mode..."
	cd fenix-eagle && python3 -m venv venv || true && source venv/bin/activate && pip install -r requirements.txt && uvicorn src.main:app --reload --host 0.0.0.0 --port 8001

dev-gateway:
	@echo "Starting FENIX Gateway in development mode..."
	cd fenix-gateway && source venv/bin/activate && uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# Quick local testing without Docker
test-local:
	@echo "Testing FENIX services locally..."
	@echo "Gateway Health Check:"
	@curl -s http://localhost:8000/health | python3 -m json.tool || echo "Gateway not running"
	@echo "\nGateway Services:"
	@curl -s http://localhost:8000/ | python3 -m json.tool || echo "Gateway not running"

# Start all services locally (no Docker)
start-local:
	@echo "Starting FENIX services locally..."
	cd fenix-gateway && source venv/bin/activate && uvicorn src.main:app --host 0.0.0.0 --port 8000 &
	@echo "Gateway started on http://localhost:8000"
	@echo "Use 'make test-local' to verify services"

stop-local:
	@echo "Stopping local FENIX services..."
	pkill -f "uvicorn.*fenix" || echo "No FENIX services running"

# Monitoring commands
status:
	@echo "FENIX Services Status:"
	docker-compose ps

health:
	@echo "Checking FENIX health..."
	@curl -s http://localhost:8000/health || echo "Gateway not responding"
	@curl -s http://localhost:8001/health || echo "Eagle not responding"