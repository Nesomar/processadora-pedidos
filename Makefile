.PHONY: up down bootstrap test e2e seed-file upload

# Alvos que falam com o Ministack de fora do compose (bootstrap, seed-file, upload) precisam das
# credenciais/endpoint no ambiente; sem isso, `build_client` estoura KeyError: 'AWS_ENDPOINT_URL'.
-include .env
export

up:
	docker compose -f infra/docker-compose.yml up -d

down:
	docker compose -f infra/docker-compose.yml down

bootstrap:
	uv run --package infra-bootstrap python infra/bootstrap/main.py

# --import-mode=importlib: vários serviços têm arquivos de teste de mesmo nome (test_health.py,
# test_cancelar_pedido.py...) e nenhum diretório de testes é pacote; no modo padrão do pytest isso
# colide na coleta ("import file mismatch").
test:
	uv run --all-packages pytest --import-mode=importlib $(wildcard shared/*/tests infra/*/tests services/*/tests)

e2e:
	@if [ -d tests/e2e ]; then \
		uv run --all-packages pytest tests/e2e; \
	else \
		echo "tests/e2e ainda não existe — nenhum teste e2e definido até o momento"; \
	fi

seed-file:
	uv run --package infra-bootstrap python infra/bootstrap/seed_file.py

upload:
ifndef FILE
	$(error uso: make upload FILE=examples/arquivo-valido.txt)
endif
	uv run --package infra-bootstrap python infra/bootstrap/seed_file.py $(FILE)
