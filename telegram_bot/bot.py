"""Telegram-бот: OpenAI решает, когда вызывать MCP по HTTP."""

from __future__ import annotations

import json
import logging
from typing import Any

from openai import AsyncOpenAI
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from config import settings
from mcp_client import McpHttpError, call_mcp_tool

logger = logging.getLogger(__name__)

_MAX_TOOL_ROUNDS = 8
_MAX_REPLY_LEN = 4000

OPENAI_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "list_products",
            "description": (
                "Вернуть полный список товаров из каталога (id, name, "
                "category, price). Используй, когда нужен весь каталог."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_product",
            "description": (
                "Найти товары по подстроке в названии (без учёта регистра)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Фрагмент названия, например «чай».",
                    },
                },
                "required": ["name"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_product",
            "description": (
                "Добавить новый товар. Нужны точные name, category и price."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "category": {"type": "string"},
                    "price": {"type": "number", "description": "Цена ≥ 0"},
                },
                "required": ["name", "category", "price"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": (
                "Безопасный калькулятор: + − * / // % ** и скобки. "
                "Без функций и переменных."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Арифметическое выражение, напр. (2+3)*4",
                    },
                },
                "required": ["expression"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_to_cart",
            "description": (
                "Положить товар в корзину по product_id из каталога. "
                "quantity по умолчанию 1."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "client_id": {
                        "type": "string",
                        "description": "Id клиента (дан системой).",
                    },
                    "product_id": {"type": "integer", "minimum": 1},
                    "quantity": {
                        "type": "integer",
                        "minimum": 1,
                        "default": 1,
                    },
                },
                "required": ["client_id", "product_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "view_cart",
            "description": (
                "Показать корзину: позиции, сумма товаров, доставка 10%, итог."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "client_id": {
                        "type": "string",
                        "description": "Id клиента (дан системой).",
                    },
                },
                "required": ["client_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "clear_cart",
            "description": "Очистить корзину клиента.",
            "parameters": {
                "type": "object",
                "properties": {
                    "client_id": {
                        "type": "string",
                        "description": "Id клиента (дан системой).",
                    },
                },
                "required": ["client_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "place_delivery_order",
            "description": (
                "Оформить доставку: сохранить заказ, показать доставку и итог, "
                "очистить корзину."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "client_id": {
                        "type": "string",
                        "description": "Id клиента (дан системой).",
                    },
                },
                "required": ["client_id"],
                "additionalProperties": False,
            },
        },
    },
]

SYSTEM_PROMPT = (
    "Ты — вежливый русскоязычный ассистент магазина (каталог в БД).\n\n"
    "Инструменты: list_products, find_product, add_product, calculate, "
    "add_to_cart, view_cart, clear_cart, place_delivery_order.\n"
    "Доставка считается как 10% от суммы товаров в корзине; сумма и "
    "стоимость доставки видны в view_cart и после place_delivery_order.\n\n"
    "Правила:\n"
    "- Отвечай структурировано: короткий заголовок, затем списки или "
    "таблично.\n"
    "- Цены выводи с двумя знаками после запятой (например 120.00).\n"
    "- Если запрос неясен (категория, цена, что искать) — задай ОДИН "
    "уточняющий вопрос, без выдуманных данных.\n"
    "- Если инструмент вернул ошибку (поле error / ok=false) — объясни "
    "пользователю простыми словами.\n"
    "- Не выдумывай товары: для фактов опирайся только на результат "
    "инструментов.\n"
    "- Добавление товара: извлеки name, category, price из фразы; если "
    "чего-то не хватает — спроси. Пример: «яблоки 120 фрукты» → name=яблоки, "
    "price=120, category=фрукты.\n"
    "- Корзина: сначала list_products/find_product, затем add_to_cart с "
    "нужным product_id. Для просмотра и доставки используй view_cart и "
    "place_delivery_order.\n"
)


def _tool_calls_to_dicts(raw: list[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for tc in raw:
        out.append(
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments or "{}",
                },
            },
        )
    return out


async def _run_tools_and_reply(
    client: AsyncOpenAI,
    messages: list[dict[str, Any]],
) -> str:
    for _ in range(_MAX_TOOL_ROUNDS):
        response = await client.chat.completions.create(
            model=settings.openai_model,
            messages=messages,
            tools=OPENAI_TOOLS,
            tool_choice="auto",
            temperature=0.2,
        )
        choice = response.choices[0]
        msg = choice.message

        if msg.tool_calls:
            messages.append(
                {
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": _tool_calls_to_dicts(msg.tool_calls),
                },
            )
            for tc in msg.tool_calls:
                name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                try:
                    data = await call_mcp_tool(
                        settings.mcp_http_base_url,
                        name,
                        args,
                        timeout=settings.mcp_http_timeout,
                    )
                    payload = json.dumps(data, ensure_ascii=False)
                except McpHttpError as exc:
                    payload = json.dumps(
                        {"error": str(exc)},
                        ensure_ascii=False,
                    )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": payload,
                    },
                )
            continue

        text = (msg.content or "").strip()
        return text if text else "Готово."

    return (
        "Слишком много шагов с инструментами. Уточните запрос или "
        "попробуйте позже."
    )


async def process_user_text(
    user_text: str,
    *,
    cart_client_id: str | None = None,
) -> str:
    """Один цикл диалога: модель + при необходимости MCP по HTTP."""

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    system = SYSTEM_PROMPT
    if cart_client_id:
        system += (
            "\n\nОбязательно: для add_to_cart, view_cart, clear_cart и "
            "place_delivery_order всегда передавай "
            f'client_id="{cart_client_id}".'
        )
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_text},
    ]
    return await _run_tools_and_reply(client, messages)


def _split_for_telegram(text: str) -> list[str]:
    if len(text) <= _MAX_REPLY_LEN:
        return [text]
    parts: list[str] = []
    start = 0
    while start < len(text):
        parts.append(text[start : start + _MAX_REPLY_LEN])
        start += _MAX_REPLY_LEN
    return parts


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    await update.message.reply_text(
        "Привет! Каталог, корзина и доставка (10% от суммы товаров).\n\n"
        "Примеры:\n"
        "• покажи все товары\n"
        "• добавь в корзину товар id 3, два штуки\n"
        "• что в корзине\n"
        "• оформи доставку\n"
        "• посчитай (19.5 + 2) * 3",
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await cmd_start(update, context)


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None or update.effective_chat is None:
        return
    raw = (update.message.text or "").strip()
    if not raw:
        return

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action="typing",
    )
    try:
        answer = await process_user_text(
            raw,
            cart_client_id=str(update.effective_chat.id),
        )
    except Exception:
        logger.exception("Ошибка обработки сообщения")
        answer = (
            "Произошла внутренняя ошибка. Проверьте ключи OpenAI и что "
            "запущен MCP HTTP (см. README)."
        )

    for chunk in _split_for_telegram(answer):
        await update.message.reply_text(chunk)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    app = (
        Application.builder()
        .token(settings.telegram_api_token)
        .concurrent_updates(True)
        .build()
    )
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, on_text),
    )
    logger.info("Бот запущен (polling). MCP: %s", settings.mcp_http_base_url)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
