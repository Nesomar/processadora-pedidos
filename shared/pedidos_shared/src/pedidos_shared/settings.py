"""Configuração de infraestrutura via variáveis de ambiente (data-model.md — Settings)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None)

    aws_endpoint_url: str
    aws_region: str
    aws_access_key_id: str
    aws_secret_access_key: str

    orders_table_name: str = "orders"
    processed_messages_table_name: str
    pedidos_bucket_name: str = "pedidos-bucket"

    solicitar_pedido_queue_url: str | None = None
    editar_pedido_queue_url: str | None = None
    cancelar_pedido_queue_url: str | None = None
    validar_pedido_queue_url: str | None = None
    validar_pedido_response_queue_url: str | None = None
    pdf_request_queue_url: str | None = None
    pdf_response_queue_url: str | None = None
    s3_notifications_queue_url: str | None = None
    pedido_lines_queue_url: str | None = None
