.PHONY: help up down restart logs clean test build run-etl shell db-shell

help:
	@echo "Available commands:"
	@echo "  make up          - Start all services (database + ETL service)"
	@echo "  make down        - Stop all services"
	@echo "  make restart     - Restart all services"
	@echo "  make logs        - View logs from all services"
	@echo "  make build       - Build Docker images"
	@echo "  make test        - Run test suite"
	@echo "  make run-etl     - Manually trigger ETL pipeline"
	@echo "  make shell       - Open shell in ETL service container"
	@echo "  make db-shell    - Open PostgreSQL shell"
	@echo "  make clean       - Remove all containers and volumes"

up:
	@echo "Starting services..."
	docker-compose up -d
	@echo "Services started!"
	@echo "API available at: http://localhost:8000"
	@echo "API docs at: http://localhost:8000/docs"

down:
	@echo "Stopping services..."
	docker-compose down
	@echo "Services stopped!"

restart:
	@echo "Restarting services..."
	docker-compose restart
	@echo "Services restarted!"

logs:
	docker-compose logs -f

logs-api:
	docker-compose logs -f etl_service

logs-db:
	docker-compose logs -f postgres

build:
	@echo "Building Docker images..."
	docker-compose build
	@echo "Build complete!"

test:
	@echo "Running test suite..."
	docker-compose exec etl_service pytest tests/ -v --cov=. --cov-report=term-missing
	@echo "Tests complete!"

run-etl:
	@echo "Manually triggering ETL pipeline..."
	docker-compose exec etl_service python -m ingestion.etl_orchestrator
	@echo "ETL pipeline complete!"

shell:
	@echo "Opening shell in ETL service container..."
	docker-compose exec etl_service /bin/bash

db-shell:
	@echo "Opening PostgreSQL shell..."
	docker-compose exec postgres psql -U postgres -d etl_db

clean:
	@echo "Cleaning up all containers and volumes..."
	docker-compose down -v
	@echo "Cleanup complete!"

# Development commands
dev-setup:
	@echo "Setting up development environment..."
	python -m venv venv
	. venv/bin/activate && pip install -r requirements.txt
	cp .env.example .env
	@echo "Development environment ready!"
	@echo "Please edit .env file with your API keys"

dev-run:
	@echo "Running application in development mode..."
	uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

dev-test:
	@echo "Running tests in development mode..."
	pytest tests/ -v --cov=. --cov-report=html
	@echo "Coverage report generated in htmlcov/index.html"
