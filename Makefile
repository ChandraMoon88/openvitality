# Makefile for HAI - Free AI Hospital
#
# This file provides convenient shortcuts for common development tasks.
# To use, simply type `make <command>` in your terminal.
# Example: `make install`

# Define Python interpreter to ensure consistency
PYTHON = python

.PHONY: install run test lint format docker-up clean backup help

help:
	@echo "Available commands:"
	@echo "  make install      - Install all production and development dependencies."
	@echo "  make run          - Start the development server with auto-reload."
	@echo "  make test         - Run all unit and integration tests with coverage."
	@echo "  make lint         - Check the code for style issues and potential errors."
	@echo "  make format       - Automatically format the code to match style guidelines."
	@echo "  make docker-up    - Start required services (like Postgres & Redis) using Docker."
	@echo "  make clean        - Remove temporary files like __pycache__ and .coverage."
	@echo "  make backup       - Create a timestamped backup of the PostgreSQL database."

install:
	@echo "Installing production dependencies..."
	$(PYTHON) -m pip install -r requirements.txt
	@echo "Installing development dependencies..."
	$(PYTHON) -m pip install -r requirements-dev.txt
	@echo "Downloading NLP models..."
	$(PYTHON) -m spacy download en_core_web_lg
	@echo "Installation complete."

run:
	@echo "Starting FastAPI development server on http://127.0.0.1:8000"
	@echo "Press CTRL+C to stop."
	uvicorn src.main:app --reload

test:
	@echo "Running tests with coverage..."
	pytest --cov=src --cov-report=term-missing

lint:
	@echo "Running linters and security scanner..."
	flake8 src/
	mypy src/
	bandit -r src/

format:
	@echo "Formatting code with black and isort..."
	black .
	isort .


docker-up:
	@echo "Starting Docker containers for PostgreSQL and Redis..."
	@if not exist docker-compose.yml (echo "docker-compose.yml not found. Please create one."; exit 1)
	docker-compose up -d

clean:
	@echo "Cleaning up cache files..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -exec rm -rf {} +
	rm -f .coverage

backup:
	@echo "Backing up the database..."
	@if not exist .env (echo ".env file not found. Cannot perform backup."; exit 1)
	# This is a simplified example. A real script would be more robust.
	# Requires `pg_dump` to be in the system's PATH.
	@PGPASSWORD=$(shell grep DATABASE_URL .env | cut -d'@' -f1 | cut -d':' -f3) pg_dump \
		-U $(shell grep DATABASE_URL .env | cut -d'@' -f1 | cut -d':' -f2 | cut -d'/' -f3) \
		-h $(shell grep DATABASE_URL .env | cut -d'@' -f2 | cut -d':' -f1) \
		-p $(shell grep DATABASE_URL .env | cut -d':' -f3 | cut -d'/' -f1) \
		$(shell grep DATABASE_URL .env | cut -d'/' -f4) \
		> backup_$(shell date +%Y%m%d_%H%M%S).sql
	@echo "Backup complete."
