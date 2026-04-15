"""HTTP-API тех же инструментов, что и у MCP (для Telegram-бота и др. клиентов)."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel, Field

import db as db_module
from tools import (
    add_product,
    add_to_cart,
    calculate,
    clear_cart,
    find_product,
    list_products,
    place_delivery_order,
    view_cart,
)

logger = logging.getLogger(__name__)


def load_env() -> None:
    """Подхватывает .env рядом с модулем и в корне репозитория."""

    here = Path(__file__).resolve().parent
    load_dotenv(here / ".env")
    load_dotenv(here.parent / ".env")


@asynccontextmanager
async def _lifespan(app: FastAPI):
    load_env()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    db_module.init_db()
    logger.info("HTTP-API готова, БД инициализирована.")
    yield


app = FastAPI(
    title="product-mcp HTTP",
    version="1.0.0",
    lifespan=_lifespan,
)


class FindProductBody(BaseModel):
    name: str = Field(
        ...,
        min_length=1,
        description="Подстрока для поиска в name",
    )


class AddProductBody(BaseModel):
    name: str = Field(..., min_length=1)
    category: str = Field(..., min_length=1)
    price: float = Field(..., ge=0)


class CalculateBody(BaseModel):
    expression: str = Field(..., min_length=1)


class ClientIdBody(BaseModel):
    client_id: str = Field(..., min_length=1)


class AddToCartBody(BaseModel):
    client_id: str = Field(..., min_length=1)
    product_id: int = Field(..., ge=1)
    quantity: int = Field(default=1, ge=1)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/tools/list_products")
async def http_list_products() -> list[dict[str, Any]]:
    return list_products()


@app.post("/api/tools/find_product")
async def http_find_product(body: FindProductBody) -> list[dict[str, Any]]:
    return find_product(body.name)


@app.post("/api/tools/add_product")
async def http_add_product(body: AddProductBody) -> dict[str, Any]:
    return add_product(body.name, body.category, body.price)


@app.post("/api/tools/calculate")
async def http_calculate(body: CalculateBody) -> dict[str, Any]:
    return calculate(body.expression)


@app.post("/api/tools/add_to_cart")
async def http_add_to_cart(body: AddToCartBody) -> dict[str, Any]:
    return add_to_cart(body.client_id, body.product_id, body.quantity)


@app.post("/api/tools/view_cart")
async def http_view_cart(body: ClientIdBody) -> dict[str, Any]:
    return view_cart(body.client_id)


@app.post("/api/tools/clear_cart")
async def http_clear_cart(body: ClientIdBody) -> dict[str, Any]:
    return clear_cart(body.client_id)


@app.post("/api/tools/place_delivery_order")
async def http_place_delivery_order(body: ClientIdBody) -> dict[str, Any]:
    return place_delivery_order(body.client_id)


def main() -> None:
    """Запуск через uvicorn (удобно для локальной отладки)."""

    import uvicorn

    load_env()
    host = os.getenv("MCP_HTTP_HOST", "127.0.0.1")
    port = int(os.getenv("MCP_HTTP_PORT", "8765"))
    uvicorn.run(
        "http_api:app",
        host=host,
        port=port,
        reload=False,
    )


if __name__ == "__main__":
    main()
