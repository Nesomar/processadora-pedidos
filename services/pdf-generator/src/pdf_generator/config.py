"""Settings do pdf-generator: reaproveita pedidos_shared.Settings, valida o que este usa."""

from functools import lru_cache

from pedidos_shared import Settings

_REQUIRED_FIELDS = (
    "pdf_request_queue_url",
    "pdf_response_queue_url",
)


def _validate(settings: Settings) -> Settings:
    missing = [field for field in _REQUIRED_FIELDS if getattr(settings, field) is None]
    if missing:
        raise ValueError(
            f"pdf-generator requer as seguintes variáveis de ambiente, ausentes: {missing}"
        )
    return settings


@lru_cache
def get_settings() -> Settings:
    return _validate(Settings())
