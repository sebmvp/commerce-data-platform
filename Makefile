.PHONY: help doctor up down seed seed-heldout test eval eval-heldout eval-compare frontend demo demo-cli test-e2e clean migrate

PYTHON ?= .venv/bin/python
PIP ?= .venv/bin/pip
CDP ?= .venv/bin/cdp
COMPOSE ?= docker compose
WEB ?= web
HELDOUT_URL ?= postgresql://cdp:***@127.0.0.1:5432/cdp_heldout
HELDOUT_DATA ?= sample_data_heldout

help:
	@echo "Commerce Data Platform — developer commands"
	@echo ""
	@echo "  make doctor       Check Python, Node, Postgres, env (REQUIRED vs OPTIONAL)"
	@echo "  make up           Start PostgreSQL if Docker is available"
	@echo "  make down         Stop compose services"
	@echo "  make seed         Load the demo world"
	@echo "  make seed-heldout Load the held-out world into cdp_heldout"
	@echo "  make test         Run backend tests"
	@echo "  make eval         Gold Context Engine evaluation"
	@echo "  make eval-heldout Held-out scenario validation"
	@echo "  make eval-compare Engine vs lexical retrieval baseline"
	@echo "  make demo         Visual product demo (API + inspector)"
	@echo "  make demo-cli     Isolated CLI/system behavior demo"
	@echo "  make test-e2e     Playwright smoke against a running inspector"
	@echo "  make clean        Remove safe generated artifacts (not private data)"
	@echo "  make migrate      Apply Alembic migrations"

doctor:
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

seed-heldout: up
	@$(PYTHON) -c "from cdp_cli.db import ensure_database; ensure_database('$(HELDOUT_URL)')"
	CDP_DATABASE_URL=$(HELDOUT_URL) CDP_DATA=$(HELDOUT_DATA) $(CDP) build --sample --force

test: up
	$(PYTHON) -m pytest -q

eval: up
	$(CDP) eval

eval-heldout: seed-heldout
	CDP_DATABASE_URL=$(HELDOUT_URL) CDP_DATA=$(HELDOUT_DATA) $(CDP) eval --heldout

eval-compare: up
	$(CDP) eval --compare

frontend:
	cd $(WEB) && npm install && npm run dev -- --port 5173 --host 127.0.0.1

demo: up
	$(PYTHON) scripts/run_visual_demo.py

demo-cli: up seed
	$(CDP) demo

test-e2e:
	cd $(WEB) && npm install && npx playwright test

clean:
	rm -rf .pytest_cache .ruff_cache src/*.egg-info web/dist web/node_modules/.vite
	find . -type d -name __pycache__ -not -path './.venv/*' -prune -exec rm -rf {} +
	@echo "left sample_data/, sample_data_heldout/, .env, and any private calibration paths untouched"
