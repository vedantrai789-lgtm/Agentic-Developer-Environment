.PHONY: setup start stop test lint clean

# One command to set up and start everything
setup:
	bash scripts/bootstrap.sh

# Start services + API server (assumes setup was already run)
start:
	docker compose up -d
	.venv/bin/ade serve

# Stop everything
stop:
	docker compose down

# Run tests
test:
	.venv/bin/python -m pytest tests/ -v

# Lint
lint:
	.venv/bin/ruff check ade/ tests/

# Start UI dev server (separate terminal)
ui:
	cd ade/ui && npm run dev

# Clean up
clean:
	docker compose down -v
	rm -rf .venv ade/ui/node_modules
