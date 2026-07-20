"""Validacao de CPF/CNPJ por digito verificador modulo 11."""


def _digits(document: str) -> str:
    return "".join(char for char in document if char.isdigit())


def _all_equal(value: str) -> bool:
    return len(set(value)) == 1


def _cpf_digit(base: str, weights: range) -> str:
    total = sum(int(digit) * weight for digit, weight in zip(base, weights, strict=True))
    rest = (total * 10) % 11
    return "0" if rest == 10 else str(rest)


def _validar_cpf(document: str) -> bool:
    if _all_equal(document):
        return False
    first = _cpf_digit(document[:9], range(10, 1, -1))
    second = _cpf_digit(document[:9] + first, range(11, 1, -1))
    return document[-2:] == first + second


def _cnpj_digit(base: str, weights: list[int]) -> str:
    total = sum(int(digit) * weight for digit, weight in zip(base, weights, strict=True))
    rest = total % 11
    return "0" if rest < 2 else str(11 - rest)


def _validar_cnpj(document: str) -> bool:
    if _all_equal(document):
        return False
    first = _cnpj_digit(document[:12], [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    second = _cnpj_digit(document[:12] + first, [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    return document[-2:] == first + second


def validar_documento(document: str) -> bool:
    digits = _digits(document)
    if len(digits) == 11:
        return _validar_cpf(digits)
    if len(digits) == 14:
        return _validar_cnpj(digits)
    return False
