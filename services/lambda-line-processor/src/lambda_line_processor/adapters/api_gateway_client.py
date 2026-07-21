"""Cliente HTTP para o api-gateway (constitution I.1 v1.0.2 — segunda exceção documentada).

Timeout explícito e retry curto só para erro de conexão/timeout (research.md #1) — mesma decisão
já tomada em `005-order-validator` para a chamada ao catálogo externo. Um `5xx` ou qualquer status
de resposta NÃO é tratado aqui: a `Response` é devolvida como veio, e quem decide se é sucesso,
recusa de negócio ou falha técnica é o handler.
"""

import time

import httpx

DEFAULT_TIMEOUT_SECONDS = 5.0
MAX_ATTEMPTS = 3
DEFAULT_RETRY_SLEEP_SECONDS = 0.5


def chamar(client: httpx.Client, method: str, path: str, body: dict) -> httpx.Response:
    last_error: Exception | None = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            return client.request(method, path, json=body, timeout=DEFAULT_TIMEOUT_SECONDS)
        except httpx.RequestError as error:
            last_error = error
            if attempt == MAX_ATTEMPTS - 1:
                break
            time.sleep(DEFAULT_RETRY_SLEEP_SECONDS)

    raise last_error
