.PHONY: help doctor up down seed test eval frontend demo clean migrate

PYTHON ?= .venv/bin/python
PIP ?= .venv/bin/pip
CDP ?= .venv/bin/cdp
COMPOSE ?= docker compose
WEB ?= web

help:
	@echo "Commerce Data Platform — developer commands"
	@echo ""
	@echo "  make doctor     Check Python, Node, ports, env, database"
	@echo "  make up         Start PostgreSQL if Docker is available"
	@echo "  make down       Stop compose services"
	@echo "  make seed       Load the public synthetic evaluation world"
	@echo "  make test       Run backend tests"
	@echo "  make eval       Run gold Context Engine evaluation"
	@echo "  make frontend   Start the Context Inspector (Vite)"
	@echo "  make demo       Isolated demo path"
	@echo "  make clean      Remove safe generated artifacts (not private data)"
	@echo "  make migrate    Apply Alembic migrations"

doctor:
	@$(PYTHON) -c "import sys; assert sys.version_info >= (3,11), sys.version"
	@node -v
	@npm -v
	@$(PYTHON) -c "from cdp_cli.doctor import main; raise SystemExit(main())"

up:
	@if docker info >/dev/null 2>&1; then $(COMPOSE) up -d postgres; else echo "docker unavailable — using whatever postgres is on :5432"; fi
	@$(PYTHON) -c "from cdp_cli.db import DEFAULT_URL, TEST_URL, ensure_database; ensure_database(DEFAULT_URL); ensure_database(TEST_URL)"

down:
	-$(COMPOSE) down

migrate: up
	$(PYTHON) -m alembic upgrade head

seed: up
	$(CDP) build --sample --force

test: up
	$(PYTHON) -m pytest -q

eval: up
	$(CDP) eval

frontend:
	cd $(WEB) && npm install && npm run dev -- --port 5173 --host 127.0.0.1

demo: up seed
	$(CDP) demo

clean:
	rm -rf .pytest_cache .ruff_cache src/*.egg-info web/dist web/node_modules/.vite
	find . -type d -name __pycache__ -not -path './.venv/*' -prune -exec rm -rf {} +
	@echo "left sample_data/, .env, and any private calibration paths untouched"
