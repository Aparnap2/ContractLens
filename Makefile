# ContractLens Makefile
# ======================
# Development workflow automation.
# Phase A: local-first, single-tenant with Docker Compose.

.PHONY: install lint typecheck test migrate db-up up down clean

# ── Install ────────────────────────────────────────────────────────────────────
install:
	pip install --upgrade pip
	pip install -e ".[dev]"

# ── Lint ───────────────────────────────────────────────────────────────────────
lint:
	ruff check .
	ruff format --check .

lint-fix:
	ruff check --fix .
	ruff format .

# ── Typecheck ──────────────────────────────────────────────────────────────────
typecheck:
	mypy .

# ── Test ───────────────────────────────────────────────────────────────────────
test:
	pytest --cov=packages --cov-report=term-missing --cov-report=html --asyncio-mode=auto

test-unit:
	pytest tests/unit -m unit --asyncio-mode=auto

test-integration:
	pytest tests/integration -m integration --asyncio-mode=auto

test-coverage:
	pytest --cov=packages --cov-report=xml --cov-report=term-missing --asyncio-mode=auto

# ── Database migrations ────────────────────────────────────────────────────────
migrate:
	@echo "Running SQL migrations..."
	@for f in infra/migrations/*.sql; do \
		echo "  Applying $$f..."; \
		psql "$${DATABASE_URL}" -f "$$f"; \
	done
	@echo "Running seed data..."
	@for f in infra/seed/*.sql; do \
		echo "  Seeding $$f..."; \
		psql "$${DATABASE_URL}" -f "$$f"; \
	done
	@echo "Migrations complete."

# ── Local infrastructure (Docker) ──────────────────────────────────────────────
db-up:
	docker compose up -d postgres redis
	@echo "Waiting for postgres..."
	@until docker compose exec postgres pg_isready -U contractlens 2>/dev/null; do sleep 1; done
	@echo "Postgres is ready."
	@echo "Waiting for redis..."
	@until docker compose exec redis redis-cli ping 2>/dev/null; do sleep 1; done
	@echo "Redis is ready."

# ── Full application ───────────────────────────────────────────────────────────
up:
	docker compose up --build -d

up-logs:
	docker compose up --build

down:
	docker compose down

down-volumes:
	docker compose down -v

# ── Utilities ──────────────────────────────────────────────────────────────────
clean:
	rm -rf build/ dist/ *.egg-info/ .pytest_cache/ .mypy_cache/ .ruff_cache/
	rm -rf htmlcov/ coverage.xml .coverage
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

logs:
	docker compose logs -f

shell:
	docker compose exec api bash

psql:
	docker compose exec postgres psql -U contractlens contractlens

# ── Help ───────────────────────────────────────────────────────────────────────
help:
	@echo "ContractLens Makefile"
	@echo "====================="
	@echo "install           — pip install with dev dependencies"
	@echo "lint              — run ruff check + format check"
	@echo "lint-fix          — auto-fix lint issues"
	@echo "typecheck         — run mypy type checker"
	@echo "test              — run all tests with coverage"
	@echo "test-unit         — run unit tests only"
	@echo "test-integration  — run integration tests only"
	@echo "migrate           — apply SQL migrations and seed data"
	@echo "db-up             — start postgres + redis via docker compose"
	@echo "up                — docker compose up (full stack)"
	@echo "up-logs           — docker compose up with logs attached"
	@echo "down              — docker compose down"
	@echo "down-volumes      — docker compose down with volume cleanup"
	@echo "clean             — remove build artifacts and caches"
	@echo "logs              — tail docker compose logs"
	@echo "shell             — open bash in api container"
	@echo "psql              — open psql in postgres container"
