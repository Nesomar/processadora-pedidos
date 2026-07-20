.PHONY: up down bootstrap test e2e seed-file

up:
	docker compose -f infra/docker-compose.yml up -d

down:
	docker compose -f infra/docker-compose.yml down

bootstrap:
	uv run --package infra-bootstrap python infra/bootstrap/main.py

test:
	uv run --all-packages pytest $(wildcard shared/*/tests infra/*/tests services/*/tests)

e2e:
	@if [ -d tests/e2e ]; then \
		uv run --all-packages pytest tests/e2e; \
	else \
		echo "tests/e2e ainda não existe — nenhum teste e2e definido até o momento"; \
	fi

seed-file:
	uv run --package infra-bootstrap python infra/bootstrap/seed_file.py
