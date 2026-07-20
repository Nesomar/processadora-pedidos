from pdf_generator.domain.validacao import validar_solicitacao

_ITEM = {
    "product_id": 1,
    "quantity": 3,
    "unit_price": "9.99",
    "discount_percentage": "10.48",
    "line_total": "26.82",
    "product_title": "Essence Mascara Lash Princess",
    "product_sku": "BEA-ESS-ESS-001",
}


def _payload(**overrides: object) -> dict:
    base = {
        "customer_name": "Maria Silva",
        "customer_document": "52998224725",
        "items": [_ITEM],
        "subtotal": "29.97",
        "discount_total": "3.15",
        "total": "26.82",
    }
    base.update(overrides)
    return base


def test_valida_payload_completo_retorna_none() -> None:
    assert validar_solicitacao(_payload()) is None


def test_lista_de_itens_vazia_e_dado_incompleto() -> None:
    assert validar_solicitacao(_payload(items=[])) is not None


def test_customer_document_ausente_e_dado_incompleto() -> None:
    payload = _payload()
    del payload["customer_document"]
    assert validar_solicitacao(payload) is not None


def test_customer_name_ausente_e_dado_incompleto() -> None:
    payload = _payload()
    del payload["customer_name"]
    assert validar_solicitacao(payload) is not None


def test_totais_ausentes_e_dado_incompleto() -> None:
    payload = _payload()
    del payload["total"]
    assert validar_solicitacao(payload) is not None


def test_item_sem_campo_numerico_e_dado_incompleto() -> None:
    """Clarifications: item sem quantity/unit_price/discount_percentage/line_total."""
    item_incompleto = {**_ITEM}
    del item_incompleto["unit_price"]
    payload = _payload(items=[item_incompleto])

    assert validar_solicitacao(payload) is not None


def test_item_sem_product_title_ou_sku_nao_e_dado_incompleto() -> None:
    """Edge case: fallback cobre titulo/SKU ausentes, nao e motivo de rejeicao."""
    item = {**_ITEM, "product_title": None, "product_sku": None}
    payload = _payload(items=[item])

    assert validar_solicitacao(payload) is None
