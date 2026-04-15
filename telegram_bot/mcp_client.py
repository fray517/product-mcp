"""HTTP-клиент к инструментам MCP (см. mcp_server/http_api.py)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class McpHttpError(Exception):
    """Ошибка вызова HTTP-API MCP."""


async def call_mcp_tool(
    base_url: str,
    tool_name: str,
    arguments: dict[str, Any],
    *,
    timeout: float,
) -> Any:
    """
    Вызывает инструмент по имени (как в MCP: list_products, find_product, …).

    list_products передаётся с пустым телом (без JSON).
    """

    root = base_url.rstrip("/")
    url = f"{root}/api/tools/{tool_name}"
    headers = {"Accept": "application/json"}

    if tool_name == "list_products":
        payload = None
    else:
        payload = arguments

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            if payload is None:
                response = await client.post(url, headers=headers)
            else:
                response = await client.post(
                    url,
                    headers=headers,
                    json=payload,
                )
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text
        logger.error("MCP HTTP %s: %s", exc.response.status_code, detail)
        raise McpHttpError(
            f"Сервис товаров вернул ошибку {exc.response.status_code}.",
        ) from exc
    except httpx.RequestError as exc:
        logger.error("MCP HTTP сеть: %s", exc)
        raise McpHttpError(
            "Не удалось связаться с MCP HTTP. Запущен ли mcp_server/http_api?",
        ) from exc

    if response.headers.get("content-type", "").startswith("application/json"):
        return response.json()
    return response.text
