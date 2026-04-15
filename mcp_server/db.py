"""Инициализация SQLite и операции с таблицей products."""

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
    return conn


def init_db() -> None:
    """Создаёт схему и при пустой таблице заполняет тестовыми строками."""

    with _connect() as conn:
        conn.executescript(_SCHEMA_SQL)
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
