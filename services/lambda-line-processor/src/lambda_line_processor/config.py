"""Settings do lambda-line-processor: reaproveita pedidos_shared.Settings + api_gateway_base_url."""

from functools import lru_cache

from pedidos_shared import Settings

_REQUIRED_FIELDS = ("pedido_lines_queue_url",)


class LambdaLineProcessorSettings(Settings):
    api_gateway_base_url: str


def _validate(settings: Settings) -> Settings:
    missing = [field for field in _REQUIRED_FIELDS if getattr(settings, field) is None]
    if missing:
        raise ValueError(
            f"lambda-line-processor requer as seguintes variáveis de ambiente, ausentes: {missing}"
        )
    return settings


@lru_cache
def get_settings() -> LambdaLineProcessorSettings:
    return _validate(LambdaLineProcessorSettings())
