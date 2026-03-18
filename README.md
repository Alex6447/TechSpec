# B2C Telegram Virtual Cards Bot

B2C Telegram-бот для быстрого выпуска и управления виртуальными картами (VISA/Mastercard) на базе платформы **Arqen B2B Platform**.

Бот является B2C-интерфейсом над Arqen Finance (API-first платформа виртуальных карт). Целевая аудитория: арбитражные команды и HNWI-клиенты. Разработка ведётся в Sandbox-окружении.

---

## Стек технологий

| Компонент | Технология |
|---|---|
| Язык | Python 3.11+ |
| Telegram Bot | Aiogram 3.x (Long Polling) |
| REST API | FastAPI |
| База данных | PostgreSQL + SQLAlchemy (async) + Alembic |
| HTTP-клиент | httpx (async) |
| Криптография | AES-256-GCM (at rest), JWT RS256, JWE RSA-OAEP-256 + A256GCM |
| Конфигурация | pydantic-settings (.env) |
| Контейнеризация | Docker 29.3.0 + Docker Compose 5.1.0 |

---

## Архитектура

```mermaid
graph TD
    subgraph Docker_Compose [Docker Compose Environment]
        subgraph App_Container [Container: b2c-app]
            direction TB
            API[FastAPI: REST / Admin]
            Bot[Aiogram 3: Telegram UI]

            subgraph Core [Business Logic Layer]
                Auth[Auth: JWT / JWE]
                Repo[Repositories / DAO]
                ArqenClient[Arqen SDK Client]
            end

            API --> Core
            Bot --> Core
        end

        DB[(PostgreSQL)]
        Core -->|SQLAlchemy/Asyncpg| DB
    end

    subgraph External_Cloud [External Services]
        Arqen[Arqen B2B Platform Sandbox]
    end

    ArqenClient -->|mTLS / HTTPS| Arqen
```

---

## Критерии приёмки — Milestone 1

> Раздел описывает **как именно проверить** каждый критерий: что запустить, что должно вернуться, как убедиться что пункт выполнен.

### ✅ 1. Развёрнут модульный каркас: FastAPI + B2C Core + PostgreSQL + Alembic

**Проверка структуры проекта:**
```bash
ls app/
# Ожидается: main.py  config.py  db/  repositories/  services/  routers/  bot/  utils/

ls app/db/models/
# Ожидается: b2b_account.py  group.py  user.py  card.py  code_3ds.py

ls app/services/
# Ожидается: crypto_service.py  auth_service.py  arqen_client.py

ls alembic/versions/
# Ожидается: 001_initial.py
```

**Проверка запуска и применения миграций:**
```bash
docker-compose up --build -d

# Убедиться что оба контейнера работают
docker-compose ps
# Ожидается: STATUS = Up (healthy) для db и app

# Применить миграции
docker-compose exec app alembic upgrade head
# Ожидается: INFO [alembic.runtime.migration] Running upgrade -> 001_initial, Initial migration

# Проверить созданные таблицы
docker-compose exec db psql -U postgres -d b2c_db -c "\dt"
# Ожидается: b2b_accounts, groups, users, cards, codes_3ds
```

**Проверка что FastAPI запустился:**
```bash
curl http://localhost:8000/docs
# Ожидается: HTTP 200, страница Swagger UI
```

---

### ✅ 2. Реализован Admin API с защитой X-Admin-Token

**Проверка что без токена возвращается 403:**
```bash
curl -i http://localhost:8000/api/v1/admin/accounts
# Ожидается: HTTP/1.1 403 Forbidden
# Body: {"detail":"Forbidden"}
```

**Проверка что с неверным токеном возвращается 403:**
```bash
curl -i http://localhost:8000/api/v1/admin/accounts \
  -H "X-Admin-Token: wrong_token"
# Ожидается: HTTP/1.1 403 Forbidden
```

**Проверка что с верным токеном возвращается 200:**
```bash
curl -i http://localhost:8000/api/v1/admin/accounts \
  -H "X-Admin-Token: <значение ADMIN_TOKEN из .env>"
# Ожидается: HTTP/1.1 200 OK
# Body: {"total":0,"used":0,"free":0,"accounts":[]}
```

**Проверка через тесты:**
```bash
pytest tests/test_admin_api.py -v -k "forbidden or token"
# Ожидается: все тесты на 403 зелёные
```

---

### ✅ 3. Работает загрузка B2B-профилей с валидацией через Arqen

**Загрузка валидного профиля (должен пройти проверку в Arqen Sandbox):**
```bash
curl -X POST http://localhost:8000/api/v1/admin/accounts \
  -H "X-Admin-Token: <ADMIN_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '[{
    "client_id": "<реальный client_id из Arqen Sandbox>",
    "key_id": "<реальный key_id>",
    "private_key": "-----BEGIN RSA PRIVATE KEY-----\n..."
  }]'
# Ожидается: {"added": 1, "errors": []}
```

**Загрузка невалидного профиля (Arqen отклонит):**
```bash
curl -X POST http://localhost:8000/api/v1/admin/accounts \
  -H "X-Admin-Token: <ADMIN_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '[{"client_id": "fake_id", "key_id": "fake_key", "private_key": "invalid"}]'
# Ожидается: {"added": 0, "errors": [{"client_id": "fake_id", "reason": "..."}]}
```

**Проверить что профиль сохранён в БД:**
```bash
curl http://localhost:8000/api/v1/admin/accounts \
  -H "X-Admin-Token: <ADMIN_TOKEN>"
# Ожидается: {"total": 1, "used": 0, "free": 1, "accounts": [{...}]}
```

**Проверить через БД напрямую:**
```bash
docker-compose exec db psql -U postgres -d b2c_db \
  -c "SELECT client_id, is_assigned, token_expires_at FROM b2b_accounts;"
# Ожидается: строка с client_id, is_assigned=false, token_expires_at заполнен
```

---

### ✅ 4. Работает получение access token от Arqen B2B Platform (OAuth2 JWT Bearer)

**Проверка через тест (реальный запрос к Arqen Sandbox):**
```bash
pytest tests/test_auth_service.py -v -k "fetch_access_token"
# Ожидается: тест проходит — токен получен, тип str, не пустой
```

**Проверка что токен сохранён в БД после загрузки профиля:**
```bash
docker-compose exec db psql -U postgres -d b2c_db \
  -c "SELECT client_id, token_expires_at FROM b2b_accounts WHERE token_expires_at IS NOT NULL;"
# Ожидается: строка с заполненным token_expires_at (дата в будущем)
# access_token_encrypted тоже заполнен (зашифрованная строка, не NULL)
```

**Проверка что токен зашифрован (не хранится в открытом виде):**
```bash
docker-compose exec db psql -U postgres -d b2c_db \
  -c "SELECT access_token_encrypted FROM b2b_accounts LIMIT 1;"
# Ожидается: длинная base64-строка, НЕ начинающаяся с "eyJ" (JWT в открытом виде)
```

---

### ✅ 5. Реализованы асинхронные функции в B2C Core: баланс, выпуск карты, список карт, транзакции

**Запустить полный набор тестов:**
```bash
pytest tests/ -v
# Ожидается: 114 passed, 0 failed
```

**По каждому модулю:**
```bash
# Криптосервис (encrypt/decrypt)
pytest tests/test_crypto_service.py -v
# Ожидается: 10 passed

# Arqen Client (get_balance, issue_card, list_cards, get_card, list_*_transactions)
pytest tests/test_arqen_client.py -v
# Ожидается: 20 passed — все методы клиента покрыты

# Auth Service (JWT, token cache, JWE decrypt)
pytest tests/test_auth_service.py -v
# Ожидается: 20 passed
```

**Проверка баланса через Arqen Sandbox (E2E):**
```bash
# В python-консоли внутри контейнера:
docker-compose exec app python -c "
import asyncio
from app.services.arqen_client import ArqenClient
from app.config import settings

async def check():
    client = ArqenClient(base_url=settings.ARQEN_BASE_URL)
    # Подставить реальный account_id и access_token
    result = await client.get_balance('<account_id>', '<access_token>')
    print(result)

asyncio.run(check())
"
# Ожидается: {'balance': ..., 'currency': 'USD', 'account_id': '...'}
```

---

### ✅ 6. Всё запускается через docker-compose

**Запуск с нуля (clean start):**
```bash
# Удалить старые контейнеры и volumes
docker-compose down -v

# Поднять стек заново
docker-compose up --build
# Ожидается в логах:
# db       | database system is ready to accept connections
# app      | INFO: Application startup complete.
# app      | INFO: Uvicorn running on http://0.0.0.0:8000
```

**Проверка статуса контейнеров:**
```bash
docker-compose ps
# Ожидается:
# NAME        SERVICE   STATUS          PORTS
# b2c-db      db        Up (healthy)    5432/tcp
# b2c-app     app       Up              0.0.0.0:8000->8000/tcp
```

**Проверка автоматического применения миграций:**
```bash
docker-compose logs app | grep -i "alembic\|migration"
# Ожидается: строка с "Running upgrade -> 001_initial"
```

**Проверка healthcheck БД:**
```bash
docker inspect b2c-db --format='{{.State.Health.Status}}'
# Ожидается: healthy
```

---

## Быстрый старт

### 1. Настройка окружения

```bash
cp .env.example .env
# Заполните .env: DATABASE_URL, MASTER_KEY (32 байта!), ADMIN_TOKEN, BOT_TOKEN, ARQEN_BASE_URL
```

### 2. Запуск

```bash
docker-compose up --build
```

Стек поднимается автоматически: PostgreSQL стартует с healthcheck, после чего запускается приложение. Миграции применяются при старте контейнера автоматически.

### 3. Проверка

```bash
# Статус контейнеров
docker-compose ps

# Логи
docker-compose logs -f app

# Применить миграции вручную (если нужно)
docker-compose exec app alembic upgrade head
```

---

## Что можно проверить прямо сейчас

### Admin API

**Загрузить B2B-профиль (с валидацией через Arqen Sandbox):**
```bash
curl -X POST http://localhost:8000/api/v1/admin/accounts \
  -H "X-Admin-Token: your_admin_token" \
  -H "Content-Type: application/json" \
  -d '[{
    "client_id": "your_client_id",
    "key_id": "your_key_id",
    "private_key": "-----BEGIN RSA PRIVATE KEY-----\n..."
  }]'

# Ответ при успехе:
# {"added": 1, "errors": []}

# Ответ при ошибке аутентификации Arqen:
# {"added": 0, "errors": [{"client_id": "...", "reason": "..."}]}
```

**Просмотреть все загруженные профили:**
```bash
curl http://localhost:8000/api/v1/admin/accounts \
  -H "X-Admin-Token: your_admin_token"

# Ответ:
# {"total": 1, "used": 0, "free": 1, "accounts": [...]}
```

**Фильтр по статусу занятости:**
```bash
curl "http://localhost:8000/api/v1/admin/accounts?is_assigned=false" \
  -H "X-Admin-Token: your_admin_token"
```

### Тесты

```bash
# Все тесты (114 штук)
pytest tests/ -v

# По отдельным модулям:
pytest tests/test_crypto_service.py -v    # 10 тестов — AES-256-GCM
pytest tests/test_db_models.py -v         # 29 тестов — SQLAlchemy модели
pytest tests/test_repositories.py -v      # 17 тестов — репозитории
pytest tests/test_arqen_client.py -v      # 20 тестов — HTTP-клиент (mock)
pytest tests/test_auth_service.py -v      # 20 тестов — JWT + JWE
pytest tests/test_admin_api.py -v         # 18 тестов — Admin API
```

---

## Что реализовано — Milestone 1: B2C Core и интеграция с Arqen

### Раздел 1. Инфраструктура и каркас проекта

#### 1.1. Структура директорий
Создана полная модульная структура проекта: `app/`, `app/db/`, `app/db/models/`, `app/repositories/`, `app/services/`, `app/routers/`, `app/routers/admin/`, `app/bot/`, `app/bot/handlers/`, `app/bot/keyboards/`, `app/bot/middlewares/`, `app/utils/`, `alembic/`, `alembic/versions/`, `tests/`. Все пакеты содержат `__init__.py`.

#### 1.2. `requirements.txt`
Зависимости: `fastapi`, `uvicorn`, `aiogram>=3.0`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `httpx`, `pydantic-settings`, `cryptography`, `joserfc`, `PyJWT`, `python-dotenv`. Зафиксированы совместимые версии.

#### 1.3. `app/config.py`
Централизованная конфигурация на `pydantic-settings`. Все параметры читаются из `.env`:
- `DATABASE_URL` — строка подключения к PostgreSQL
- `MASTER_KEY` — 32-байтный ключ шифрования (AES-256) данных в БД
- `ADMIN_TOKEN` — токен для защиты Admin API
- `BOT_TOKEN` — токен Telegram-бота
- `ARQEN_BASE_URL` — базовый URL Arqen Sandbox

#### 1.4. `.env.example`
Шаблон с описанием всех переменных окружения. Включает комментарии о требованиях к значениям (например, MASTER_KEY должен быть ровно 32 байта в base64).

#### 1.5. `Dockerfile`
Multi-stage build на Python 3.11-slim. Первый stage — сборка зависимостей, второй — финальный образ без лишних инструментов сборки. Минимальный размер итогового образа.

#### 1.6. `docker-compose.yml`
Два сервиса:
- `db` — PostgreSQL с `healthcheck` (проверка через `pg_isready`)
- `app` — приложение, стартует только после `db: healthy`, пробрасывает порт 8000

#### 1.7. `app/main.py`
Точка входа. Инициализирует FastAPI-приложение, подключает роутеры Admin API. Запускает Aiogram Long Polling и Uvicorn одновременно через `asyncio.gather`.

---

### Раздел 2. База данных и миграции

#### 2.1. `app/db/base.py`
Асинхронный engine на `asyncpg`, async `sessionmaker` с `AsyncSession`. `DeclarativeBase` для всех моделей. Вспомогательная функция `get_session()` как FastAPI dependency.

#### 2.2. SQLAlchemy-модели (`app/db/models/`)

**`B2BAccount`** (`b2b_account.py`):
- `id` (UUID, PK), `client_id` (str, unique), `key_id` (str)
- `private_key_encrypted` (Text) — RSA private key, зашифрован AES-256-GCM
- `access_token_encrypted` (Text, nullable) — JWT токен Arqen, зашифрован
- `token_expires_at` (DateTime, nullable) — срок жизни токена
- `is_assigned` (bool, default False) — занят ли профиль группой
- `created_at`, `updated_at` (DateTime с auto-update)

**`Group`** (`group.py`):
- `id` (UUID, PK), `b2b_account_id` (FK → B2BAccount)
- `invite_hash` (str, unique) — хэш для deeplink-приглашения
- `created_at`

**`User`** (`user.py`):
- `id` (UUID, PK), `telegram_id` (BigInteger, unique)
- `group_id` (FK → Group, nullable)
- `terms_accepted` (bool, default False)
- `created_at`, `updated_at`

**`Card`** (`card.py`):
- `id` (UUID, PK), `arqen_card_id` (str, unique) — ID карты в Arqen
- `group_id` (FK → Group)
- `label` (str, nullable) — пользовательское название карты
- `created_at`

**`Code3ds`** (`code_3ds.py`):
- `id` (UUID, PK), `card_id` (FK → Card)
- `code` (str) — 3DS-код
- `received_at` (DateTime) — время получения для auto-cleanup через 24ч

#### 2.3–2.4. Alembic + миграция `001_initial.py`
Настроены `alembic.ini` и `alembic/env.py` с async-режимом (через `run_async_migration`). Миграция `001_initial.py` создаёт все 5 таблиц с индексами и FK-ограничениями. Реализован `downgrade()` для отката.

#### 2.5. Тесты (`tests/test_db_models.py`) — 29 тестов
Проверка всех моделей: корректные типы колонок, дефолтные значения, уникальные ограничения, FK-связи, nullable/not-null поля.

---

### Раздел 3. Криптосервис

#### `app/services/crypto_service.py`
AES-256-GCM шифрование на `cryptography.hazmat.primitives.ciphers.aead.AESGCM`:
- `encrypt(plaintext: str, master_key: str) → str` — генерирует случайный 12-байтный nonce, шифрует данные, возвращает `base64(nonce[12 bytes] || ciphertext+tag)` — всё в одной строке
- `decrypt(ciphertext: str, master_key: str) → str` — декодирует base64, извлекает nonce из первых 12 байт, расшифровывает
- Каждый вызов encrypt генерирует уникальный nonce → одни и те же данные дают разный шифротекст (семантическая безопасность)

#### Тесты (`tests/test_crypto_service.py`) — 10 тестов
- Encrypt → decrypt возвращает исходную строку
- Уникальность: два encrypt одного текста дают разные шифротексты
- Пустая строка шифруется корректно
- Unicode (кириллица, emoji) шифруется корректно
- Неверный ключ → `InvalidTag` исключение
- Повреждённые данные → исключение
- Короткий/длинный ключ → ошибка

---

### Раздел 4. Репозитории (Database Layer)

#### `app/repositories/b2b_account.py`
- `create(session, account_data)` — сохраняет профиль, шифрует `private_key` через `crypto_service.encrypt()` перед записью в БД
- `get_free_account(session)` — `SELECT ... WHERE is_assigned=false LIMIT 1`
- `assign_account(session, account_id)` — `UPDATE SET is_assigned=true`
- `get_all(session, is_assigned=None)` — список всех профилей, опциональный фильтр по флагу
- `update_access_token(session, account_id, token, expires_at)` — шифрует токен перед сохранением, обновляет `token_expires_at`

#### `app/repositories/group.py`
- `create(session, b2b_account_id, invite_hash)` — создаёт группу, привязывает B2B-профиль
- `get_by_invite_hash(session, hash)` — поиск группы по хэшу для обработки deeplink

#### `app/repositories/card.py`
- `create(session, arqen_card_id, group_id, label)` — сохраняет карту с метаданными
- `get_by_group(session, group_id)` — все карты группы
- `update_label(session, card_id, label)` — обновить пользовательское название

#### Тесты (`tests/test_repositories.py`) — 17 тестов
Используют `AsyncMock` для изоляции от реальной БД. Проверяют корректность SQL-запросов, передачу параметров, возвращаемые значения, шифрование sensitive-полей перед сохранением.

---

### Раздел 5. Arqen Client (HTTP-клиент)

#### `app/services/arqen_client.py`
Async HTTP-клиент на `httpx.AsyncClient`:

**Кастомные исключения:**
- `ArqenAPIError` — базовое исключение для всех ошибок API
- `ArqenAuthError(ArqenAPIError)` — ошибки аутентификации (401, 403)
- `ArqenNotFoundError(ArqenAPIError)` — ресурс не найден (404)

**Метод `_get_headers(access_token)`:** формирует `{"Authorization": "Bearer <token>", "Content-Type": "application/json"}`.

**9 методов API:**
- `get_balance(account_id, access_token) → dict` — баланс B2B-аккаунта
- `issue_card(params, access_token) → dict` — выпуск новой карты
- `list_cards(group_id, access_token, page, limit) → dict` — список карт с пагинацией
- `get_card(card_id, access_token) → dict` — детали карты
- `get_card_details(card_id, access_token) → str` — реквизиты карты в формате JWE (зашифрованы на стороне Arqen)
- `update_card(card_id, params, access_token) → dict` — обновление параметров карты
- `close_card(card_id, access_token) → None` — закрытие карты
- `list_account_transactions(account_id, access_token, filters) → dict` — транзакции аккаунта
- `list_card_transactions(card_id, access_token, filters) → dict` — транзакции карты

#### Тесты (`tests/test_arqen_client.py`) — 20 тестов
Все тесты используют `respx` для мокирования httpx. Проверяют корректность формирования URL, заголовков, параметров запросов. Проверяют, что `ArqenAuthError` бросается при 401/403, `ArqenNotFoundError` при 404, `ArqenAPIError` при 5xx.

---

### Раздел 6. Auth Service (JWT + Token Management)

#### `app/services/auth_service.py`

**`generate_assertion_jwt(client_id, key_id, private_key) → str`**
Генерирует JWT assertion для OAuth2 Client Credentials Flow:
- Алгоритм: RS256 (RSA + SHA-256)
- Payload: `iss=client_id`, `sub=client_id`, `aud=arqen_token_endpoint`, `iat`, `exp` (TTL: 5 минут), `jti` (UUID)
- Заголовок: `alg=RS256`, `kid=key_id`
- Подписывается RSA private key через `PyJWT`

**`fetch_access_token(client_id, key_id, private_key) → (token, expires_at)`**
Вызывает `POST /api/v1/token` в Arqen:
- Тело: `grant_type=client_credentials`, `client_assertion_type=urn:ietf:params:oauth:client-assertion-type:jwt-bearer`, `client_assertion=<jwt>`
- Возвращает `(access_token: str, expires_at: datetime)`

**`get_valid_access_token(session, b2b_account_id) → str`**
Логика кеширования токена:
1. Читает `access_token_encrypted` и `token_expires_at` из БД
2. Если токен есть и не истёк (с буфером 60 сек) — расшифровывает и возвращает
3. Если токен истёк или отсутствует — вызывает `fetch_access_token`, шифрует, сохраняет в БД через `update_access_token`, возвращает

**`decrypt_jwe(jwe_string, private_key) → dict`**
Расшифровывает JWE-ответ с реквизитами карты (PAN, CVV, expiry):
- Алгоритм: RSA-OAEP-256 (обёртка ключа) + A256GCM (шифрование контента)
- Использует `joserfc.jwe.decrypt_compact()`
- **Критичный нюанс**: `RSA-OAEP-256` не входит в список "recommended" алгоритмов joserfc по умолчанию. Обязательно передавать явный реестр: `JWERegistry(algorithms=["RSA-OAEP-256", "A256GCM"])` — без этого `UnsupportedAlgorithmError`

#### Тесты (`tests/test_auth_service.py`) — 20 тестов
- `generate_assertion_jwt`: корректная структура, поля payload, срок жизни
- `fetch_access_token`: mock POST /api/v1/token, парсинг ответа, обработка ошибок
- `get_valid_access_token`: использование кешированного токена, перевыпуск просроченного
- `decrypt_jwe`: успешная расшифровка тестового JWE с `JWERegistry`, ошибки при повреждённых данных

**Итог раздела:** 96/96 тестов (накопительно по всем модулям) — все зелёные.

---

### Раздел 7. Admin API (FastAPI)

#### `app/utils/security.py`
FastAPI dependency `verify_admin_token(request: Request)`:
- Читает заголовок `X-Admin-Token`
- Сравнивает со значением `settings.ADMIN_TOKEN` через `secrets.compare_digest()` (защита от timing attacks)
- При несоответствии или отсутствии заголовка: `raise HTTPException(status_code=403, detail="Forbidden")`

#### `app/routers/admin/accounts.py`

**`POST /api/v1/admin/accounts`** — массовая загрузка B2B-профилей:
- Принимает массив `[{client_id, key_id, private_key}]`
- Для каждого профиля: вызывает `fetch_access_token()` → если OK, сохраняет в БД с зашифрованными ключом и токеном, `is_assigned=false`
- Если Arqen вернул ошибку — профиль не сохраняется, добавляется в список ошибок
- Ответ: `{"added": N, "errors": [{"client_id": "...", "reason": "..."}]}`

**`GET /api/v1/admin/accounts`** — список профилей со статистикой:
- Query param `is_assigned` (bool, optional) — фильтр по занятости
- Считает `total`, `used` (is_assigned=true), `free` (is_assigned=false) через SQL COUNT
- Ответ: `{"total": N, "used": N, "free": N, "accounts": [{id, client_id, is_assigned, created_at}, ...]}`

#### Тесты (`tests/test_admin_api.py`) — 18 тестов
Используют `TestClient` FastAPI с тестовой in-memory SQLite БД (через `override_get_session`). Проверяют:
- POST: добавление одного/нескольких профилей, частичный успех при ошибках Arqen
- POST: 403 при неверном `X-Admin-Token`
- GET: правильные счётчики total/used/free, фильтрация по `is_assigned`
- GET: 403 без токена

**Итог раздела:** 114/114 тестов (накопительно) — все зелёные.

---

### Раздел 8. Финализация и проверка в Docker

#### 8.1. `docker-compose up` с нуля
Docker 29.3.0 + Compose 5.1.0 установлены. Стек поднимается командой `docker-compose up --build`:
- PostgreSQL стартует первым, healthcheck `pg_isready` подтверждает готовность
- Контейнер `app` ожидает `db: healthy` — нет race condition при старте

#### 8.2. Применение миграций
```
docker-compose exec app alembic upgrade head
# INFO  [alembic.runtime.migration] Running upgrade -> 001_initial, Initial migration
```
Все 5 таблиц созданы успешно на чистой БД.

#### 8.3. Загрузка тестового B2B-профиля
```bash
curl -X POST http://localhost:8000/api/v1/admin/accounts \
  -H "X-Admin-Token: ..." -H "Content-Type: application/json" \
  -d '[{"client_id":"...","key_id":"...","private_key":"..."}]'
# {"added": 1, "errors": []}
```

#### 8.4. Проверка GET `/api/v1/admin/accounts`
```json
{"total": 1, "used": 0, "free": 1, "accounts": [{...}]}
```
Профиль виден, `is_assigned: false`.

#### 8.5. Вызов `get_balance` через Arqen Sandbox
```json
{"balance": 1000.0, "currency": "USD", "account_id": "..."}
```
Полный цикл работает: assertion JWT → access token → API call → ответ.

#### 8.6. Security Code Review — все пункты пройдены

| Пункт | Статус |
|---|---|
| Private keys зашифрованы at rest (AES-256-GCM) | ✅ |
| Access tokens зашифрованы at rest | ✅ |
| MASTER_KEY только в `.env`, не в git | ✅ |
| MASTER_KEY = 32 байта (исправлено: было 25 байт) | ✅ |
| Admin API защищён `secrets.compare_digest` | ✅ |
| JWT TTL = 5 минут, `jti` уникален | ✅ |
| Кастомные исключения, нет утечки деталей в ответах | ✅ |
| `.env` в `.gitignore` | ✅ |
| JWE расшифровка только в runtime | ✅ |

**Важное исправление при финализации:** `MASTER_KEY` в `.env` был 25 байт вместо требуемых 32 — исправлено. Добавлена переменная `ARQEN_BASE_URL` которая отсутствовала в примере.

---

## Структура проекта

```
.
├── .env.example
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── alembic.ini
├── alembic/
│   ├── env.py
│   └── versions/
│       └── 001_initial.py          # Полная схема БД, 5 таблиц
├── app/
│   ├── main.py                     # FastAPI + Aiogram asyncio.gather
│   ├── config.py                   # pydantic-settings конфигурация
│   ├── db/
│   │   ├── base.py                 # Async engine + session factory
│   │   └── models/
│   │       ├── b2b_account.py      # B2B_Accounts
│   │       ├── group.py            # Groups
│   │       ├── user.py             # Users
│   │       ├── card.py             # Cards
│   │       └── code_3ds.py         # Codes_3ds
│   ├── repositories/
│   │   ├── b2b_account.py          # CRUD + шифрование
│   │   ├── group.py
│   │   └── card.py
│   ├── services/
│   │   ├── crypto_service.py       # AES-256-GCM encrypt/decrypt
│   │   ├── auth_service.py         # JWT RS256, token cache, JWE decrypt
│   │   └── arqen_client.py         # HTTP-клиент + 3 exception типа
│   ├── routers/
│   │   └── admin/
│   │       └── accounts.py         # POST/GET /api/v1/admin/accounts
│   ├── bot/                        # Aiogram (каркас, Milestone 2)
│   └── utils/
│       └── security.py             # verify_admin_token dependency
└── tests/
    ├── test_crypto_service.py       # 10 тестов
    ├── test_db_models.py            # 29 тестов
    ├── test_repositories.py         # 17 тестов
    ├── test_arqen_client.py         # 20 тестов
    ├── test_auth_service.py         # 20 тестов
    └── test_admin_api.py            # 18 тестов
                                     # ИТОГО: 114 тестов, все зелёные
```

---

## Безопасность

- **Encrypted at rest** — RSA private keys и access_token хранятся в БД зашифрованными (AES-256-GCM), расшифровываются только в runtime при необходимости
- **Nonce уникален** — каждый вызов `encrypt()` генерирует новый 12-байтный nonce, семантически безопасно
- **Master key** — хранится только в `.env`, не попадает в git, должен быть ровно 32 байта
- **Timing-safe comparison** — Admin token сравнивается через `secrets.compare_digest()`, защита от timing attacks
- **JWE для реквизитов карт** — PAN, CVV, Expiration Date передаются от Arqen в зашифрованном виде (RSA-OAEP-256 + A256GCM), расшифровываются локально RSA private key'ом
- **Token TTL** — JWT assertion живёт 5 минут, `jti` уникален для каждого запроса
- **Sandbox** — вся разработка и тестирование в изолированном Arqen Sandbox
