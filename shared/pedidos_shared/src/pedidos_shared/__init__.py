"""pedidos_shared: contratos, máquina de estados e utilitários compartilhados.

`Order.customer_document` MUST passar por `mask_document` antes de qualquer log ou saída — nunca
logar o documento em claro (constitution VII.6, FR-011/FR-012).
"""

from pedidos_shared.clients.dynamodb import DynamoDbClient
from pedidos_shared.clients.s3 import S3Client
from pedidos_shared.clients.sqs import SqsClient
from pedidos_shared.file_layout import (
    ArquivoInvalidoError,
    LinhaInvalidaError,
    PedidoInvalidoError,
    parse_file,
)
from pedidos_shared.idempotency import is_message_processed, mark_message_processed
from pedidos_shared.logging import get_logger
from pedidos_shared.masking import mask_document
from pedidos_shared.models import MessageEnvelope, Order, OrderItem
from pedidos_shared.settings import Settings
from pedidos_shared.status import OrderStatus, is_valid_transition

__all__ = [
    "Order",
    "OrderItem",
    "MessageEnvelope",
    "OrderStatus",
    "is_valid_transition",
    "Settings",
    "SqsClient",
    "DynamoDbClient",
    "S3Client",
    "is_message_processed",
    "mark_message_processed",
    "get_logger",
    "mask_document",
    "parse_file",
    "ArquivoInvalidoError",
    "LinhaInvalidaError",
    "PedidoInvalidoError",
]
