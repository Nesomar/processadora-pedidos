"""Settings do api-gateway: reaproveita pedidos_shared.Settings, valida o que este serviço usa."""

from functools import lru_cache

from pedidos_shared import Settings

_REQUIRED_FIELDS = (
    "solicitar_pedido_queue_url",
    "editar_pedido_queue_url",
    "cancelar_pedido_queue_url",
)


def _validate(settings: Settings) -> Settings:
    missing = [field for field in _REQUIRED_FIELDS if getattr(settings, field) is None]
    if missing:
        raise ValueError(
            f"api-gateway requer as seguintes variáveis de ambiente, ausentes: {missing}"
        )
    return settings


@lru_cache
def get_settings() -> Settings:
    return _validate(Settings())
