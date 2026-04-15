"""Реализация инструментов MCP: товары и безопасный калькулятор."""

from __future__ import annotations

import ast
import operator as op
from typing import Any

import db as db_module


def list_products() -> list[dict[str, int | str | float]]:
    """Список всех товаров из БД."""

    return db_module.list_products()


def find_product(name: str) -> list[dict[str, int | str | float]]:
    """Товары, в имени которых встречается указанная подстрока."""

    return db_module.find_products_by_name(name)


def add_to_cart(
    client_id: str,
    product_id: int,
    quantity: int = 1,
) -> dict[str, Any]:
    """Кладёт товар в корзину клиента (количество суммируется)."""

    return db_module.add_cart_item(client_id, product_id, quantity)


def view_cart(client_id: str) -> dict[str, Any]:
    """
    Корзина: позиции, сумма товаров, стоимость доставки (10%), итог.
    """

    return db_module.get_cart_view(client_id)


def clear_cart(client_id: str) -> dict[str, Any]:
    """Очищает корзину клиента."""

    return db_module.clear_cart(client_id)


def place_delivery_order(client_id: str) -> dict[str, Any]:
    """Оформляет доставку: заказ в БД, показана доставка 10%, корзина пуста."""

    return db_module.place_delivery_order(client_id)


def add_product(name: str, category: str, price: float) -> dict[str, Any]:
    """Добавляет товар; возвращает id и поля записи."""

    n = (name or "").strip()
    c = (category or "").strip()
    if not n:
        return {"ok": False, "error": "Имя товара не может быть пустым."}
    if not c:
        return {"ok": False, "error": "Категория не может быть пустой."}
    try:
        p = float(price)
    except (TypeError, ValueError):
        return {"ok": False, "error": "Некорректная цена."}
    if p < 0:
        return {"ok": False, "error": "Цена не может быть отрицательной."}
    new_id = db_module.add_product_row(n, c, p)
    return {
        "ok": True,
        "id": new_id,
        "name": n,
        "category": c,
        "price": p,
    }


_ALLOWED_BINOPS: dict[type[ast.operator], Any] = {
    ast.Add: op.add,
    ast.Sub: op.sub,
    ast.Mult: op.mul,
    ast.Div: op.truediv,
    ast.Pow: op.pow,
    ast.Mod: op.mod,
    ast.FloorDiv: op.floordiv,
}

_ALLOWED_UNARY: dict[type[ast.unaryop], Any] = {
    ast.UAdd: op.pos,
    ast.USub: op.neg,
}


def calculate(expression: str) -> dict[str, Any]:
    """
    Безопасно вычисляет арифметическое выражение (+ − * / // % **, скобки).

    Запрещены вызовы функций, имена, атрибуты и прочие узлы AST.
    """

    src = (expression or "").strip()
    if not src:
        return {"ok": False, "error": "Пустое выражение."}
    try:
        tree = ast.parse(src, mode="eval")
    except SyntaxError as exc:
        return {"ok": False, "error": f"Синтаксическая ошибка: {exc}"}
    try:
        value = float(_eval_ast(tree.body))
    except ZeroDivisionError:
        return {"ok": False, "error": "Деление на ноль."}
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "value": value}


def _eval_ast(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _eval_ast(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)) and not isinstance(
            node.value,
            bool,
        ):
            return float(node.value)
        raise ValueError("Допустимы только числовые константы.")
    if isinstance(node, ast.Num):  # для совместимости со старыми версиями
        return float(node.n)
    if isinstance(node, ast.BinOp):
        if type(node.op) not in _ALLOWED_BINOPS:
            raise ValueError("Недопустимая операция.")
        left = _eval_ast(node.left)
        right = _eval_ast(node.right)
        fn = _ALLOWED_BINOPS[type(node.op)]
        return float(fn(left, right))
    if isinstance(node, ast.UnaryOp):
        if type(node.op) not in _ALLOWED_UNARY:
            raise ValueError("Недопустимая унарная операция.")
        fn = _ALLOWED_UNARY[type(node.op)]
        return float(fn(_eval_ast(node.operand)))
    raise ValueError("В выражении есть недопустимые элементы.")
