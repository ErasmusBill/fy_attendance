# ==============================================================
# Makefile for Church Attendance System (fy_attendacne)
# ==============================================================

.PHONY: help build up down restart logs status shell migrate createsuperuser test clean seed

help: ## Show this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

build: ## Build all Docker containers
	docker compose build

up: ## Start all production containers in detached mode
	docker compose up -d

down: ## Stop and remove all containers
	docker compose down

restart: ## Restart all containers
	docker compose restart

logs: ## Follow live logs from all containers
	docker compose logs -f

logs-web: ## Follow logs from web container
	docker compose logs -f web

logs-celery: ## Follow logs from Celery worker & beat
	docker compose logs -f celery_worker celery_beat

status: ## Show status of running containers
	docker compose ps

shell: ## Open interactive Django shell inside the web container
	docker compose exec web python manage.py shell

bash: ## Open bash shell inside the web container
	docker compose exec web bash

migrate: ## Run database migrations inside container
	docker compose exec web python manage.py migrate

createsuperuser: ## Create a new Django superuser inside container
	docker compose exec web python manage.py createsuperuser

collectstatic: ## Collect static files inside container
	docker compose exec web python manage.py collectstatic --noinput

seed: ## Seed database with seeders inside container
	docker compose exec web python manage.py seed_users || true

test: ## Run tests inside container
	docker compose exec web python manage.py test

clean: ## Stop containers and remove volumes (WARNING: wipes DB & cache)
	docker compose down -v
