from unittest.mock import MagicMock

import pytest
from pedidos_shared import Settings

from file_consumer.handlers import processar_notificacao


def _record(record_type: str, *fields: tuple[str, int, str]) -> str:
    line = record_type
    for text, width, align in fields:
        line += text.rjust(width, "0") if align == "R0" else text.ljust(width)
    return line.ljust(200)


def _valid_file_bytes(order_count: int = 2) -> bytes:
    header = _record("0", ("20260720", 8, "L"), ("TESTE", 30, "L"), ("1", 6, "R0"))
    rows = [header]
    for i in range(1, order_count + 1):
        rows.append(
            _record(
                "1",
                ("SOLICITAR", 10, "L"),
                ("", 36, "L"),
                (f"CUST0000{i}", 20, "L"),
                (f"CLIENTE {i}", 60, "L"),
                ("11111111111", 14, "R0"),
                ("1", 2, "R0"),
            )
        )
        rows.append(_record("2", (str(i), 8, "R0"), ("10", 8, "R0")))
    rows.append(_record("9", (str(order_count), 8, "R0"), (str(order_count), 8, "R0")))
    return ("\n".join(rows) + "\n").encode("utf-8")


_NOTIFICATION_BODY = {
    "Records": [
        {
            "eventName": "ObjectCreated:Put",
            "s3": {
                "bucket": {"name": "pedidos-bucket"},
                "object": {"key": "uploads/pedidos.txt"},
            },
        }
    ]
}


def test_handle_valid_file_publishes_one_message_per_order(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_s3 = MagicMock()
    fake_s3.get_object.return_value = _valid_file_bytes(order_count=2)
    monkeypatch.setattr(processar_notificacao, "S3Client", lambda _settings: fake_s3)

    fake_sqs = MagicMock()
    monkeypatch.setattr(processar_notificacao, "SqsClient", lambda _settings: fake_sqs)

    processar_notificacao.handle(_NOTIFICATION_BODY, settings)

    fake_s3.get_object.assert_called_once_with("pedidos-bucket", "uploads/pedidos.txt")
    assert fake_sqs.send_raw.call_count == 2
    queue_url, message_1 = fake_sqs.send_raw.call_args_list[0].args
    assert queue_url == settings.pedido_lines_queue_url
    assert message_1["operation"] == "SOLICITAR"
    assert message_1["source_file"] == "uploads/pedidos.txt"
    assert message_1["parsed"]["channel"] == "BATCH"


def test_handle_structurally_invalid_file_publishes_nothing(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    header = _record("0", ("20260720", 8, "L"), ("TESTE", 30, "L"), ("1", 6, "R0"))
    # sem trailer -> arquivo inteiro invalido
    conteudo = (header + "\n").encode("utf-8")

    fake_s3 = MagicMock()
    fake_s3.get_object.return_value = conteudo
    monkeypatch.setattr(processar_notificacao, "S3Client", lambda _settings: fake_s3)
    fake_sqs = MagicMock()
    monkeypatch.setattr(processar_notificacao, "SqsClient", lambda _settings: fake_sqs)

    processar_notificacao.handle(_NOTIFICATION_BODY, settings)

    fake_sqs.send_raw.assert_not_called()


def test_handle_partially_invalid_file_publishes_only_valid_orders(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    header = _record("0", ("20260720", 8, "L"), ("TESTE", 30, "L"), ("1", 6, "R0"))
    order_ok = _record(
        "1",
        ("SOLICITAR", 10, "L"),
        ("", 36, "L"),
        ("CUST00001", 20, "L"),
        ("CLIENTE UM", 60, "L"),
        ("11111111111", 14, "R0"),
        ("1", 2, "R0"),
    )
    item_ok = _record("2", ("1", 8, "R0"), ("10", 8, "R0"))
    order_bad = _record(
        "1",
        ("SOLICITAR", 10, "L"),
        ("", 36, "L"),
        ("CUST00002", 20, "L"),
        ("CLIENTE DOIS", 60, "L"),
        ("22222222222", 14, "R0"),
        ("2", 2, "R0"),  # declara 2 itens, so 1 vem a seguir
    )
    item_bad = _record("2", ("2", 8, "R0"), ("5", 8, "R0"))
    trailer = _record("9", ("2", 8, "R0"), ("2", 8, "R0"))
    conteudo = ("\n".join([header, order_ok, item_ok, order_bad, item_bad, trailer]) + "\n").encode(
        "utf-8"
    )

    fake_s3 = MagicMock()
    fake_s3.get_object.return_value = conteudo
    monkeypatch.setattr(processar_notificacao, "S3Client", lambda _settings: fake_s3)
    fake_sqs = MagicMock()
    monkeypatch.setattr(processar_notificacao, "SqsClient", lambda _settings: fake_sqs)

    processar_notificacao.handle(_NOTIFICATION_BODY, settings)

    assert fake_sqs.send_raw.call_count == 1
    _, published = fake_sqs.send_raw.call_args_list[0].args
    assert published["parsed"]["customer_id"] == "CUST00001"


def test_handle_s3_technical_failure_propagates_without_publishing(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_s3 = MagicMock()
    fake_s3.get_object.side_effect = RuntimeError("s3 indisponivel")
    monkeypatch.setattr(processar_notificacao, "S3Client", lambda _settings: fake_s3)
    fake_sqs = MagicMock()
    monkeypatch.setattr(processar_notificacao, "SqsClient", lambda _settings: fake_sqs)

    with pytest.raises(RuntimeError, match="s3 indisponivel"):
        processar_notificacao.handle(_NOTIFICATION_BODY, settings)

    fake_sqs.send_raw.assert_not_called()


def test_handle_test_event_publishes_nothing(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_s3 = MagicMock()
    monkeypatch.setattr(processar_notificacao, "S3Client", lambda _settings: fake_s3)
    fake_sqs = MagicMock()
    monkeypatch.setattr(processar_notificacao, "SqsClient", lambda _settings: fake_sqs)

    processar_notificacao.handle({"Service": "Amazon S3", "Event": "s3:TestEvent"}, settings)

    fake_s3.get_object.assert_not_called()
    fake_sqs.send_raw.assert_not_called()
