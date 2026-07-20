"""Handler de s3_notifications_queue."""

from pedidos_shared import S3Client, Settings, SqsClient, get_logger
from pedidos_shared.file_layout import ArquivoInvalidoError, parse_file

from file_consumer.adapters.notificacoes_s3 import extrair_notificacoes
from file_consumer.domain.mensagens import montar_linha_pedido

logger = get_logger("file_consumer")


def _publish_line(sqs: SqsClient, queue_url: str, message: dict) -> None:
    sqs.send_raw(queue_url, message)


def handle(body: dict, settings: Settings) -> None:
    notificacoes = extrair_notificacoes(body)
    if not notificacoes:
        return

    s3 = S3Client(settings)
    sqs = SqsClient(settings)

    for notificacao in notificacoes:
        conteudo = s3.get_object(notificacao.bucket, notificacao.key)
        linhas = conteudo.decode("utf-8").splitlines()

        try:
            resultado = parse_file(linhas)
        except ArquivoInvalidoError as error:
            logger.error(
                "arquivo rejeitado",
                extra={"source_file": notificacao.key, "erro": str(error)},
            )
            continue

        for erro in resultado.errors:
            logger.error(
                "registro rejeitado",
                extra={"source_file": notificacao.key, "erro": str(erro)},
            )

        for order in resultado.orders:
            mensagem = montar_linha_pedido(notificacao.key, order)
            _publish_line(sqs, settings.pedido_lines_queue_url, mensagem)
