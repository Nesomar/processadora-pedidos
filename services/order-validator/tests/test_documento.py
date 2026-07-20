from order_validator.domain.documento import validar_documento


def test_validar_documento_accepts_valid_cpf() -> None:
    assert validar_documento("52998224725")


def test_validar_documento_accepts_valid_cnpj() -> None:
    assert validar_documento("11222333000181")


def test_validar_documento_rejects_invalid_size() -> None:
    assert not validar_documento("123")


def test_validar_documento_rejects_invalid_verifier_digit() -> None:
    assert not validar_documento("52998224724")


def test_validar_documento_rejects_repeated_digits() -> None:
    assert not validar_documento("11111111111")
