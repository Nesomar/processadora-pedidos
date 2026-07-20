"""Builders dos payloads publicados em pdf_response_queue."""


def montar_resposta_sucesso(s3_key: str) -> dict:
    return {"success": True, "s3_key": s3_key, "error_message": None}


def montar_resposta_falha(mensagem: str) -> dict:
    return {"success": False, "s3_key": None, "error_message": mensagem}
