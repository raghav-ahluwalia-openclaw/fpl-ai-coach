# FPL AI Coach - Backend Development Makefile
# Common development and deployment tasks

.PHONY: help install dev test lint format migrate docker-run docker-stop clean

# Default target
help:
	@echo "FPL AI Coach - Backend Development"
	@echo ""
	@echo "Targets:"
	@echo "  install     - Install dependencies in virtual environment"
	@echo "  dev         - Start development server with hot reload"
	@echo "  test        - Run tests with coverage"
	@echo "  test-watch  - Run tests in watch mode"
	@echo "  lint        - Run linting checks"
	@echo "  format      - Format code with black"
	@echo "  migrate     - Create and apply database migration"
	@echo "  docker-run  - Start PostgreSQL with Docker"
	@echo "  docker-stop - Stop PostgreSQL Docker container"
	@echo "  clean       - Clean build artifacts and cache"

# Install dependencies
install:
	@echo "Creating virtual environment..."
	python3 -m venv .venv
	@echo "Activating and installing dependencies..."
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -r requirements.txt
	@echo "✅ Installation complete!"
	@echo ""
	@echo "To activate: source .venv/bin/activate"

# Development server
dev:
	@echo "Starting development server..."
	uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# Run tests
test:
	@echo "Running tests..."
	.venv/bin/pytest

# Run tests in watch mode
test-watch:
	@echo "Running tests in watch mode..."
	.venv/bin/pytest -w

# Linting
lint:
	@echo "Running linting checks..."
	.venv/bin/flake8 app tests
	.venv/bin/mypy app --ignore-missing-imports

# Code formatting
format:
	@echo "Formatting code..."
	.venv/bin/black app tests
	.venv/bin/isort app tests

# Database migrations
migrate-create:
	@echo "Creating new migration..."
	@read -p "Enter migration message: " msg; \
	.venv/bin/alembic revision --autogenerate -m "$$msg"

migrate-up:
	@echo "Applying migrations..."
	.venv/bin/alembic upgrade head

migrate-down:
	@echo "Rolling back migration..."
	.venv/bin/alembic downgrade -1

migrate-status:
	@echo "Migration status..."
	.venv/bin/alembic current

migrate-history:
	@echo "Migration history..."
	.venv/bin/alembic history -v

# Docker commands
docker-run:
	@echo "Starting PostgreSQL..."
	docker compose up -d db
	@echo "✅ PostgreSQL started on port 5432"

docker-stop:
	@echo "Stopping PostgreSQL..."
	docker compose stop db
	@echo "✅ PostgreSQL stopped"

docker-logs:
	docker compose logs -f db

# Clean build artifacts
clean:
	@echo "Cleaning build artifacts..."
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	find . -type d -name "htmlcov" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .venv
	rm -f test_fpl.db
	rm -f coverage.xml
	@echo "✅ Clean complete!"

# Security checks
security:
	@echo "Running security checks..."
	.venv/bin/pip-audit
	.venv/bin/bandit -r app

# Database commands
db-reset:
	@echo "Resetting database..."
	rm -f fpl.db
	.venv/bin/alembic upgrade head
	@echo "✅ Database reset complete!"

db-shell:
	@echo "Opening database shell..."
	.venv/bin/sqlite3 fpl.db

# Model training
train-model:
	@echo "Training ML model..."
	.venv/bin/python ml/train_xgb.py

# Validation
validate:
	@echo "Running full validation..."
	./scripts/validate_backend.py
