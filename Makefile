.PHONY: dev migrate seed test lint smoke down lock

dev:
	docker compose up --build -d --wait
migrate:
	docker compose run --rm migrate
seed:
	docker compose exec api python -m app.seed
test:
	docker compose exec api pytest -q
lint:
	docker compose exec api ruff check . --no-cache
	cd apps/web && npm run typecheck && npm run lint
smoke:
	docker compose exec api python -m app.smoke
down:
	docker compose down
lock:
	cd apps/api && uv lock
	cd apps/web && npm install --package-lock-only --ignore-scripts
