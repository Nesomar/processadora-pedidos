"""Configuracao do order-validator."""

from functools import lru_cache

from pedidos_shared import Settings


class OrderValidatorSettings(Settings):
    catalog_products_base_url: str = "https://dummyjson.com"


@lru_cache
def get_settings() -> OrderValidatorSettings:
    return OrderValidatorSettings()
