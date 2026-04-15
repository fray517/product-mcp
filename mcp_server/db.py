"""SQLite: каталог, корзина и заказы с доставкой."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    price REAL NOT NULL
);
"""

_CART_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS carts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS cart_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cart_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (cart_id) REFERENCES carts(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id),
    UNIQUE(cart_id, product_id),
    CHECK(quantity > 0)
);
CREATE TABLE IF NOT EXISTS delivery_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    items_subtotal REAL NOT NULL,
    delivery_fee REAL NOT NULL,
    total REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS delivery_order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    product_name TEXT NOT NULL,
    unit_price REAL NOT NULL,
    quantity INTEGER NOT NULL,
    line_total REAL NOT NULL,
    FOREIGN KEY (order_id) REFERENCES delivery_orders(id) ON DELETE CASCADE
);
"""

DELIVERY_FEE_RATE = 0.10

_SEED_COUNT = 100

_CATEGORIES = (
    "Электроника",
    "Продукты",
    "Книги",
    "Одежда",
    "Спорт",
    "Дом и сад",
    "Игрушки",
    "Авто",
    "Красота",
    "Зоотовары",
)

_ADJECTIVES = (
    "Умный",
    "Компактный",
    "Премиум",
    "Базовый",
    "Профессиональный",
    "Детский",
    "Садовый",
    "Спортивный",
    "Домашний",
    "Уличный",
    "Мягкий",
    "Твёрдый",
    "Лёгкий",
    "Тёплый",
    "Свежий",
)

_NOUNS = (
    "датчик",
    "кабель",
    "йогурт",
    "кофе",
    "роман",
    "учебник",
    "футболка",
    "кроссовки",
    "гиря",
    "коврик",
    "горшок",
    "пазл",
    "масло",
    "шампунь",
    "корм",
)


def get_db_path() -> Path:
    """Путь к файлу БД рядом с этим пакетом."""

    return Path(__file__).resolve().parent / "products.db"


def _connect() -> sqlite3.Connection:
    path = get_db_path()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """Создаёт схему и при пустой таблице заполняет тестовыми строками."""

    with _connect() as conn:
        conn.executescript(_SCHEMA_SQL)
        conn.executescript(_CART_SCHEMA_SQL)
        count_row = conn.execute(
            "SELECT COUNT(*) AS c FROM products",
        ).fetchone()
        assert count_row is not None
        if int(count_row["c"]) == 0:
            _seed_products(conn)
            logger.info(
                "Таблица products пуста: добавлено %s тестовых записей.",
                _SEED_COUNT,
            )


def _seed_products(conn: sqlite3.Connection) -> None:
    rows = []
    for i in range(_SEED_COUNT):
        name = (
            f"{_ADJECTIVES[i % len(_ADJECTIVES)]} "
            f"{_NOUNS[(i * 7) % len(_NOUNS)]} #{i + 1}"
        )
        category = _CATEGORIES[i % len(_CATEGORIES)]
        price = round(49.9 + (i * 13.37) % 9500, 2)
        rows.append((name, category, price))
    conn.executemany(
        "INSERT INTO products (name, category, price) VALUES (?, ?, ?)",
        rows,
    )


def list_products() -> list[dict[str, int | str | float]]:
    """Возвращает все товары."""

    with _connect() as conn:
        cur = conn.execute(
            "SELECT id, name, category, price FROM products ORDER BY id",
        )
        return [_row_to_dict(row) for row in cur.fetchall()]


def find_products_by_name(substring: str) -> list[dict[str, int | str | float]]:
    """Поиск по подстроке в имени (без учёта регистра)."""

    needle = substring.strip()
    if not needle:
        return []
    pattern = f"%{needle}%"
    with _connect() as conn:
        cur = conn.execute(
            """
            SELECT id, name, category, price
            FROM products
            WHERE name LIKE ? COLLATE NOCASE
            ORDER BY id
            """,
            (pattern,),
        )
        return [_row_to_dict(row) for row in cur.fetchall()]


def add_product_row(
    name: str,
    category: str,
    price: float,
) -> int:
    """Добавляет товар; возвращает id."""

    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO products (name, category, price)
            VALUES (?, ?, ?)
            """,
            (name.strip(), category.strip(), float(price)),
        )
        conn.commit()
        return int(cur.lastrowid)


def _row_to_dict(row: sqlite3.Row) -> dict[str, int | str | float]:
    return {
        "id": int(row["id"]),
        "name": str(row["name"]),
        "category": str(row["category"]),
        "price": float(row["price"]),
    }


def _round_money(value: float) -> float:
    return round(float(value), 2)


def _get_or_create_cart_id(conn: sqlite3.Connection, client_id: str) -> int:
    cid = (client_id or "").strip()
    if not cid:
        raise ValueError("client_id не может быть пустым.")
    row = conn.execute(
        "SELECT id FROM carts WHERE client_id = ?",
        (cid,),
    ).fetchone()
    if row is not None:
        return int(row["id"])
    cur = conn.execute(
        "INSERT INTO carts (client_id) VALUES (?)",
        (cid,),
    )
    return int(cur.lastrowid)


def add_cart_item(
    client_id: str,
    product_id: int,
    quantity: int = 1,
) -> dict[str, object]:
    """Добавляет позицию в корзину (суммирует quantity, если уже есть)."""

    try:
        qty = int(quantity)
    except (TypeError, ValueError):
        return {"ok": False, "error": "Некорректное количество."}
    if qty < 1:
        return {"ok": False, "error": "Количество должно быть ≥ 1."}
    try:
        pid = int(product_id)
    except (TypeError, ValueError):
        return {"ok": False, "error": "Некорректный id товара."}

    with _connect() as conn:
        prod = conn.execute(
            "SELECT id FROM products WHERE id = ?",
            (pid,),
        ).fetchone()
        if prod is None:
            return {"ok": False, "error": "Товар с таким id не найден."}
        try:
            cart_id = _get_or_create_cart_id(conn, client_id)
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        row = conn.execute(
            """
            SELECT id, quantity FROM cart_items
            WHERE cart_id = ? AND product_id = ?
            """,
            (cart_id, pid),
        ).fetchone()
        if row is None:
            conn.execute(
                """
                INSERT INTO cart_items (cart_id, product_id, quantity)
                VALUES (?, ?, ?)
                """,
                (cart_id, pid, qty),
            )
        else:
            new_q = int(row["quantity"]) + qty
            conn.execute(
                """
                UPDATE cart_items SET quantity = ?
                WHERE id = ?
                """,
                (new_q, int(row["id"])),
            )
        conn.commit()
    return {"ok": True, "product_id": pid, "added_quantity": qty}


def get_cart_view(client_id: str) -> dict[str, object]:
    """Корзина: позиции, сумма товаров, доставка 10%, итог."""

    cid = (client_id or "").strip()
    if not cid:
        return {"ok": False, "error": "client_id не может быть пустым."}

    with _connect() as conn:
        cart_row = conn.execute(
            "SELECT id FROM carts WHERE client_id = ?",
            (cid,),
        ).fetchone()
        if cart_row is None:
            return {
                "ok": True,
                "client_id": cid,
                "items": [],
                "items_subtotal": 0.0,
                "delivery_fee_rate": DELIVERY_FEE_RATE,
                "delivery_fee": 0.0,
                "total": 0.0,
            }
        cart_id = int(cart_row["id"])
        cur = conn.execute(
            """
            SELECT
                ci.product_id AS product_id,
                ci.quantity AS quantity,
                p.name AS name,
                p.category AS category,
                p.price AS unit_price
            FROM cart_items ci
            JOIN products p ON p.id = ci.product_id
            WHERE ci.cart_id = ?
            ORDER BY p.id
            """,
            (cart_id,),
        )
        items: list[dict[str, object]] = []
        subtotal = 0.0
        for row in cur.fetchall():
            unit = float(row["unit_price"])
            q = int(row["quantity"])
            line = _round_money(unit * q)
            subtotal += line
            items.append(
                {
                    "product_id": int(row["product_id"]),
                    "name": str(row["name"]),
                    "category": str(row["category"]),
                    "unit_price": _round_money(unit),
                    "quantity": q,
                    "line_total": line,
                },
            )
        subtotal_r = _round_money(subtotal)
        delivery = _round_money(subtotal_r * DELIVERY_FEE_RATE)
        total = _round_money(subtotal_r + delivery)
        return {
            "ok": True,
            "client_id": cid,
            "items": items,
            "items_subtotal": subtotal_r,
            "delivery_fee_rate": DELIVERY_FEE_RATE,
            "delivery_fee": delivery,
            "total": total,
        }


def clear_cart(client_id: str) -> dict[str, object]:
    """Очищает корзину клиента."""

    cid = (client_id or "").strip()
    if not cid:
        return {"ok": False, "error": "client_id не может быть пустым."}
    with _connect() as conn:
        row = conn.execute(
            "SELECT id FROM carts WHERE client_id = ?",
            (cid,),
        ).fetchone()
        if row is None:
            return {"ok": True, "removed_lines": 0}
        cart_id = int(row["id"])
        cur = conn.execute(
            "DELETE FROM cart_items WHERE cart_id = ?",
            (cart_id,),
        )
        conn.commit()
        return {"ok": True, "removed_lines": int(cur.rowcount)}


def place_delivery_order(client_id: str) -> dict[str, object]:
    """
    Оформляет доставку: заказ в БД, доставка = 10% от суммы товаров,
    корзина очищается.
    """

    snapshot = get_cart_view(client_id)
    if snapshot.get("ok") is not True:
        return snapshot
    raw_items = snapshot.get("items") or []
    if len(raw_items) == 0:
        return {
            "ok": False,
            "error": "Корзина пуста. Добавьте товары перед оформлением.",
        }
    items: list[dict[str, object]] = [dict(x) for x in raw_items]
    subtotal = float(snapshot["items_subtotal"])
    delivery = float(snapshot["delivery_fee"])
    total = float(snapshot["total"])
    cid = str(snapshot["client_id"])

    with _connect() as conn:
        cart_row = conn.execute(
            "SELECT id FROM carts WHERE client_id = ?",
            (cid,),
        ).fetchone()
        if cart_row is None:
            return {
                "ok": False,
                "error": "Корзина не найдена. Добавьте товары снова.",
            }
        cart_id = int(cart_row["id"])

        cur = conn.execute(
            """
            INSERT INTO delivery_orders
                (client_id, items_subtotal, delivery_fee, total)
            VALUES (?, ?, ?, ?)
            """,
            (cid, subtotal, delivery, total),
        )
        order_id = int(cur.lastrowid)
        for it in items:
            conn.execute(
                """
                INSERT INTO delivery_order_items (
                    order_id,
                    product_id,
                    product_name,
                    unit_price,
                    quantity,
                    line_total
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    order_id,
                    int(it["product_id"]),
                    str(it["name"]),
                    float(it["unit_price"]),
                    int(it["quantity"]),
                    float(it["line_total"]),
                ),
            )
        conn.execute(
            "DELETE FROM cart_items WHERE cart_id = ?",
            (cart_id,),
        )
        conn.commit()

    return {
        "ok": True,
        "order_id": order_id,
        "client_id": cid,
        "items": items,
        "items_subtotal": subtotal,
        "delivery_fee_rate": DELIVERY_FEE_RATE,
        "delivery_fee": delivery,
        "total": total,
        "message": "Заказ оформлен, корзина очищена.",
    }
