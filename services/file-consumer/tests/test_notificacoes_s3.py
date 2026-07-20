from file_consumer.adapters.notificacoes_s3 import NotificacaoArquivo, extrair_notificacoes

_REAL_EVENT = {
    "Records": [
        {
            "eventName": "ObjectCreated:Put",
            "s3": {
                "bucket": {"name": "pedidos-bucket"},
                "object": {"key": "uploads/pedidos+20260718.txt"},
            },
        }
    ]
}

_TEST_EVENT = {"Service": "Amazon S3", "Event": "s3:TestEvent", "Bucket": "pedidos-bucket"}


def test_extrair_notificacoes_returns_bucket_and_decoded_key() -> None:
    result = extrair_notificacoes(_REAL_EVENT)

    assert result == [
        NotificacaoArquivo(bucket="pedidos-bucket", key="uploads/pedidos 20260718.txt")
    ]


def test_extrair_notificacoes_ignores_test_event() -> None:
    assert extrair_notificacoes(_TEST_EVENT) == []


def test_extrair_notificacoes_ignores_empty_records() -> None:
    assert extrair_notificacoes({"Records": []}) == []


def test_extrair_notificacoes_handles_multiple_records() -> None:
    body = {
        "Records": [
            {"s3": {"bucket": {"name": "b"}, "object": {"key": "uploads/a.txt"}}},
            {"s3": {"bucket": {"name": "b"}, "object": {"key": "uploads/b.txt"}}},
        ]
    }

    result = extrair_notificacoes(body)

    assert [n.key for n in result] == ["uploads/a.txt", "uploads/b.txt"]
