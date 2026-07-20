"""Composition root: monta a app FastAPI, GET /health (constitution IV)."""

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from api_gateway.handlers.cancelar_pedido import router as cancelar_pedido_router
from api_gateway.handlers.consultar_pedido import router as consultar_pedido_router
from api_gateway.handlers.editar_pedido import router as editar_pedido_router
from api_gateway.handlers.listar_pedidos import router as listar_pedidos_router
from api_gateway.handlers.solicitar_pedido import router as solicitar_pedido_router

app = FastAPI(title="api-gateway")
app.include_router(solicitar_pedido_router)
app.include_router(editar_pedido_router)
app.include_router(cancelar_pedido_router)
app.include_router(listar_pedidos_router)
app.include_router(consultar_pedido_router)


@app.exception_handler(RequestValidationError)
def _payload_invalido_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = exc.errors()
    detail = errors[0]["msg"] if errors else "Payload inválido"
    return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"detail": detail})


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
