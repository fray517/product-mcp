"""Точка входа MCP-сервера product-mcp (stdio)."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

import db as db_module
from tools import add_product, calculate, find_product, list_products


def load_env() -> None:
    """Подхватывает переменные из .env в корне репозитория и в mcp_server/."""

    here = Path(__file__).resolve().parent
    load_dotenv(here / ".env")
    load_dotenv(here.parent / ".env")


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )


def _stdio_line_buffering() -> None:
    """Снижает риск «залипания» JSON-RPC на Windows из-за буфера stdout."""

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(line_buffering=True)
        except (AttributeError, OSError, ValueError):
            pass


mcp = FastMCP("product-mcp")


@mcp.tool(name="list_products")
def list_products_tool() -> list[dict[str, int | str | float]]:
    """Возвращает список всех товаров из локальной БД."""

    return list_products()


@mcp.tool(name="find_product")
def find_product_tool(name: str) -> list[dict[str, int | str | float]]:
    """Ищет товары по подстроке в поле name (без учёта регистра)."""

    return find_product(name)


@mcp.tool(name="add_product")
def add_product_tool(
    name: str,
    category: str,
    price: float,
) -> dict[str, object]:
    """Добавляет новый товар: имя, категория, цена."""

    return add_product(name, category, price)


@mcp.tool(name="calculate")
def calculate_tool(expression: str) -> dict[str, object]:
    """
    Безопасный калькулятор: +, -, *, /, //, %, **, скобки. Без eval.
    """

    return calculate(expression)


def main() -> None:
    parser = argparse.ArgumentParser(description="product-mcp (stdio MCP)")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Проверить БД и выйти (без stdio MCP).",
    )
    args, _unknown = parser.parse_known_args()

    load_env()
    _configure_logging()
    db_module.init_db()

    if args.check:
        n = len(db_module.list_products())
        logging.getLogger(__name__).info(
            "Проверка OK: в каталоге %s товар(ов).",
            n,
        )
        return

    _stdio_line_buffering()
    logging.getLogger(__name__).info(
        "Режим stdio: клиент MCP (например Cursor) должен подключаться "
        "к этому процессу. Для Telegram-бота поднимите отдельно: "
        "python http_api.py",
    )
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
