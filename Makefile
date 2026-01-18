.PHONY: help build up down logs shell db-shell clean dev prod

# Default target
help:
	@echo "BidOps AI - Docker Commands"
	@echo ""
	@echo "Development:"
	@echo "  make dev          - Start development environment (backend services)"
	@echo "  make dev-logs     - View development logs"
	@echo "  make dev-down     - Stop development environment"
	@echo "  make frontend     - Run frontend dev server (npm run dev)"
	@echo ""
	@echo "Production:"
	@echo "  make prod         - Build and start production environment"
	@echo "  make prod-logs    - View production logs"
	@echo "  make prod-down    - Stop production environment"
	@echo ""
	@echo "Utilities:"
	@echo "  make build        - Build all containers"
	@echo "  make shell        - Open backend shell"
	@echo "  make db-shell     - Open database shell"
	@echo "  make ollama-pull  - Pull Ollama models"
	@echo "  make migrate      - Run database migrations"
	@echo "  make clean        - Remove containers and volumes"

# ============================================
# Development Commands
# ============================================

dev:
	docker-compose -f docker-compose.dev.yml up -d
	@echo ""
	@echo "==================================="
	@echo "Development environment started!"
	@echo "==================================="
	@echo ""
	@echo "Services:"
	@echo "  Backend API:  http://localhost:8000"
	@echo "  API Docs:     http://localhost:8000/docs"
	@echo "  PostgreSQL:   localhost:5432"
	@echo "  Redis:        localhost:6379"
	@echo "  Qdrant:       http://localhost:6333"
	@echo "  Ollama:       http://localhost:11434"
	@echo ""
	@echo "To start frontend: cd frontend && npm install && npm run dev"
	@echo ""

dev-logs:
	docker-compose -f docker-compose.dev.yml logs -f

dev-down:
	docker-compose -f docker-compose.dev.yml down

frontend:
	cd frontend && npm install && npm run dev

# ============================================
# Production Commands
# ============================================

prod:
	docker-compose up -d --build
	@echo ""
	@echo "==================================="
	@echo "Production environment started!"
	@echo "==================================="
	@echo ""
	@echo "Application: http://localhost"
	@echo "API:         http://localhost/api/v1"
	@echo ""

prod-logs:
	docker-compose logs -f

prod-down:
	docker-compose down

# ============================================
# Build Commands
# ============================================

build:
	docker-compose build

build-no-cache:
	docker-compose build --no-cache

build-backend:
	docker-compose build api worker

build-frontend:
	docker-compose build frontend

# ============================================
# Shell Access
# ============================================

shell:
	docker-compose exec api bash

db-shell:
	docker-compose exec postgres psql -U bidops -d bidops

redis-cli:
	docker-compose exec redis redis-cli

qdrant-shell:
	@echo "Qdrant API: http://localhost:6333/dashboard"

# ============================================
# Ollama Model Management
# ============================================

ollama-pull:
	docker-compose exec ollama ollama pull llama3.1:8b
	docker-compose exec ollama ollama pull nomic-embed-text
	@echo "Models downloaded successfully!"

ollama-pull-small:
	docker-compose exec ollama ollama pull llama3.2:3b
	docker-compose exec ollama ollama pull nomic-embed-text
	@echo "Small models downloaded successfully!"

ollama-list:
	docker-compose exec ollama ollama list

# ============================================
# Database Management
# ============================================

migrate:
	docker-compose exec api alembic upgrade head

migrate-create:
	@read -p "Enter migration message: " msg; \
	docker-compose exec api alembic revision --autogenerate -m "$$msg"

migrate-down:
	docker-compose exec api alembic downgrade -1

# ============================================
# Cleanup
# ============================================

clean:
	docker-compose down -v --remove-orphans
	docker-compose -f docker-compose.dev.yml down -v --remove-orphans

clean-all:
	docker-compose down -v --remove-orphans
	docker-compose -f docker-compose.dev.yml down -v --remove-orphans
	docker system prune -af --volumes
	@echo "All containers, images, and volumes removed!"

# ============================================
# Status & Health
# ============================================

status:
	@echo "Container Status:"
	@docker-compose ps
	@echo ""
	@docker-compose -f docker-compose.dev.yml ps 2>/dev/null || true

health:
	@echo "Checking service health..."
	@echo ""
	@echo "Backend API:"
	@curl -s http://localhost:8000/api/v1/health 2>/dev/null && echo "" || echo "  Not responding"
	@echo ""
	@echo "Ollama:"
	@curl -s http://localhost:11434/api/tags 2>/dev/null | head -c 100 && echo "..." || echo "  Not responding"
	@echo ""
	@echo "Qdrant:"
	@curl -s http://localhost:6333/readiness 2>/dev/null || echo "  Not responding"

# ============================================
# Quick Start
# ============================================

setup: dev ollama-pull-small migrate
	@echo ""
	@echo "==================================="
	@echo "Setup complete!"
	@echo "==================================="
	@echo ""
	@echo "Run 'make frontend' in another terminal to start the frontend"
