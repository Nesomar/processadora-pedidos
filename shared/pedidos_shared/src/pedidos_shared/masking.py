"""Mascaramento de documento do cliente (FR-011, FR-012)."""


def mask_document(document: str) -> str:
    """Preserva os últimos 4 caracteres de `document`, mascara o resto com `*`.

    Documentos com 4 caracteres ou menos são mascarados integralmente. O comprimento original é
    sempre preservado.
    """
    if len(document) <= 4:
        return "*" * len(document)
    return "*" * (len(document) - 4) + document[-4:]
