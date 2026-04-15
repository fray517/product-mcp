# product-mcp

Проект: **MCP-сервер** (SQLite, инструменты каталога + калькулятор), **HTTP-API** тех же инструментов и **Telegram-бот** с OpenAI (function calling → вызов MCP по HTTP).

## Требования

- Python 3.10+
- Windows PowerShell (команды ниже — для PowerShell)
- Файл `.env` в корне репозитория (см. `env.example`)

## Переменные окружения

Скопируйте `env.example` в `.env` и заполните:

- `TELEGRAM_API_TOKEN` — токен бота от BotFather
- `OPENAI_API_KEY` — ключ OpenAI
- `OPENAI_MODEL` — например `gpt-4o-mini` или `gpt-4o`
- `MCP_HTTP_BASE_URL` — URL HTTP-API (по умолчанию `http://127.0.0.1:8765`)

## Установка зависимостей

Из корня репозитория `product-mcp`:

```powershell
Set-Location .\mcp_server
pip install -r requirements.txt
Set-Location ..
Set-Location .\telegram_bot
pip install -r requirements.txt
Set-Location ..
```

## Запуск MCP по stdio (для Cursor и других MCP-клиентов)

Быстрая проверка без запуска протокола (создаст/проверит БД и выйдет):

```powershell
Set-Location .\mcp_server
python server.py --check
```

Обычный stdio-режим (для клиента MCP):

```powershell
Set-Location .\mcp_server
python -u server.py
```

Флаг `-u` на Windows желателен, чтобы не буферизовать stdout.

### Подключение в Cursor

В репозитории есть [`.cursor/mcp.json`](.cursor/mcp.json). По [документации Cursor](https://cursor.com/docs/context/mcp) для stdio нужно поле **`"type": "stdio"`**, иначе сервер может не подключаться.

1. Откройте в Cursor именно папку **`product-mcp`** как корень проекта (чтобы сработали `${workspaceFolder}` и путь к `venv`).
2. В `mcp.json` по умолчанию указан интерпретатор Windows:  
   `venv/Scripts/python.exe`. Если используете Linux/macOS, замените на  
   `venv/bin/python`.
3. Установите зависимости в этот venv (`pip install -r mcp_server/requirements.txt`).
4. После правок **полностью перезапустите Cursor** (не только окно).
5. Отладка: **View → Output → MCP Logs** — там видны ошибки запуска и импорта.

Если venv лежит не в корне или команда `python` без venv, отредактируйте `command` / `cwd` в `mcp.json` вручную.

## Запуск MCP HTTP (нужен боту)

В отдельном окне PowerShell:

```powershell
Set-Location .\mcp_server
python http_api.py
```

Либо явно через uvicorn:

```powershell
Set-Location .\mcp_server
python -m uvicorn http_api:app --host 127.0.0.1 --port 8765
```

Проверка: откройте в браузере или через `Invoke-RestMethod`:

- `GET http://127.0.0.1:8765/health` → `{"status":"ok"}`
- `POST http://127.0.0.1:8765/api/tools/list_products` без тела — список товаров

Хост и порт можно задать в `.env`: `MCP_HTTP_HOST`, `MCP_HTTP_PORT` (для `python http_api.py`).

## Запуск Telegram-бота

Убедитесь, что HTTP-API MCP запущена и `MCP_HTTP_BASE_URL` в `.env` указывает на неё.

```powershell
Set-Location .\telegram_bot
python bot.py
```

## Структура

- `mcp_server/server.py` — MCP (stdio)
- `mcp_server/http_api.py` — те же инструменты по HTTP
- `mcp_server/db.py`, `mcp_server/tools.py` — БД и логика
- `telegram_bot/bot.py` — бот (OpenAI + HTTP MCP)
- `telegram_bot/mcp_client.py` — клиент HTTP
- `telegram_bot/config.py` — настройки из `.env`

## Примеры фраз для бота

- «покажи все товары»
- «найди чай»
- «добавь товар яблоки категория фрукты цена 120»
- «добавь в корзину товар id 5, 2 штуки» → затем «что в корзине» / «оформи доставку»
- «посчитай (2+3)*4»

**Корзина и доставка:** стоимость доставки = **10%** от суммы товаров в корзине. В ответе `view_cart` и `place_delivery_order` есть поля `items_subtotal`, `delivery_fee`, `total` и `delivery_fee_rate` (0.1). Для Telegram `client_id` подставляется автоматически (id чата).

## Частые проблемы

### `server.py` в консоли «завис» или после Ctrl+C — длинный traceback

`server.py` работает только по **stdio** для MCP-клиентов: в обычной консоли он будет ждать ввода. **Ctrl+C** завершает процесс — сообщения `CancelledError` / `KeyboardInterrupt` ожидаемы. Для бота это не тот процесс; ему нужен **`http_api.py`**.

### Бот: `409 Conflict` / `only one bot instance`

Одновременно может опрашивать Telegram **только один** процесс с этим токеном. Закройте вторую копию `bot.py`, другой терминал/ПК с тем же ботом или отключите webhook у этого бота. Затем перезапустите `python bot.py`.

### Бот: «не удалось связаться с MCP HTTP»

Сначала в отдельном окне запустите HTTP-API (`python http_api.py` из `mcp_server`) и проверьте `MCP_HTTP_BASE_URL` в `.env`.
