"""Testes do logger JSON estruturado (FR-009)."""

import json
import logging

from pedidos_shared.logging import get_logger


def test_logger_emits_valid_json_with_order_and_correlation_id(
    capsys: object,
) -> None:
    logger = get_logger("test-with-ids")
    logger.info("teste", extra={"order_id": "111", "correlation_id": "222"})

    captured = capsys.readouterr()  # type: ignore[attr-defined]
    line = captured.out.strip().splitlines()[-1]
    payload = json.loads(line)

    assert payload["orderId"] == "111"
    assert payload["correlationId"] == "222"
    assert payload["message"] == "teste"


def test_logger_emits_valid_json_without_order_or_correlation_id(
    capsys: object,
) -> None:
    logger = get_logger("test-without-ids")
    logger.info("sem ids")

    captured = capsys.readouterr()  # type: ignore[attr-defined]
    line = captured.out.strip().splitlines()[-1]
    payload = json.loads(line)

    assert payload["message"] == "sem ids"
    assert payload["orderId"] is None
    assert payload["correlationId"] is None


def test_get_logger_returns_stdlib_logger() -> None:
    logger = get_logger("test-type")
    assert isinstance(logger, logging.Logger)
