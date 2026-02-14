.PHONY: dev dev-backend dev-frontend infra migrate test

# Start infrastructure (PostgreSQL + Redis)
infra:
	docker compose up -d

# Stop infrastructure
infra-down:
	docker compose down

# Run database migrations
migrate:
	cd backend && alembic upgrade head

# Create a new migration
migration:
	cd backend && alembic revision --autogenerate -m "$(msg)"

# Start backend dev server
dev-backend:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Start Celery worker
dev-worker:
	cd backend && celery -A app.tasks.celery_app worker --loglevel=info

# Start Celery beat scheduler
dev-beat:
	cd backend && celery -A app.tasks.celery_app beat --loglevel=info

# Start frontend dev server
dev-frontend:
	cd frontend && npm run dev

# Run backend tests
test:
	cd backend && pytest -v

# Install backend dependencies
install-backend:
	cd backend && pip install -e ".[dev]"

# Install frontend dependencies
install-frontend:
	cd frontend && npm install

# Full setup
setup: infra install-backend install-frontend migrate
