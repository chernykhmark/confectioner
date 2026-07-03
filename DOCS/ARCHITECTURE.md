# 🎂 Телеграм-бот «Конструктор тортов»
## Полное техническое задание и архитектура

**Версия:** 1.1
**Стек:** Python 3.11+ / aiogram 3.x / PostgreSQL (внешняя БД по URL) / SQLAlchemy 2.0 async

---

## Содержание
1. Обзор проекта
2. Ключевое архитектурное решение
3. Функциональные требования
4. Пользовательский путь и жизненный цикл заказа
5. Этапы разработки
6. Архитектура БД
7. Схема связей БД
8. Диаграмма состояний FSM
9. Структура проекта
10. Технические механики
11. Инициализация схемы и seed-данные
12. Настройка окружения и запуск
13. MVP-объём

---

## 1. Обзор проекта

Телеграм-бот для кондитера. Заказчик собирает торт по шагам (конструктор) либо выбирает готовый шаблон. Кондитер получает структурированную заявку и ведёт её по статусам.

**Роли:**
- **Пользователь** — собирает/оформляет заказ.
- **Администратор** (один, задаётся через env) — принимает заказы, меняет статусы, мониторит воронку.

---

## 2. Ключевое архитектурное решение

**Требование:** любой путь по конструктору должен приводить к валидному изделию (никаких тупиков).

**Решение — «Свободный конструктор + агрегация цены по компонентам» (Подход А):**

- **Единственный источник вариантов на шагах воронки — таблица `components`.** На каждом шаге показываются все активные (`is_active=True`) компоненты нужного типа. Любая комбинация валидна по умолчанию.
- **Цена изделия рассчитывается динамически:** `base_price` (константа/настройка) + сумма `price_delta` всех выбранных компонентов. Готового `products`-изделия для кастомного заказа не создаётся — итог хранится в самом заказе (описание + рассчитанная цена).
- **`products` / `product_components` используются ТОЛЬКО для готовых шаблонов** (`is_template=True`) — быстрый путь «Популярные заказы». Конструктор их не задействует.
- **Совместимость компонентов** (например, «Цифра» несовместима с «15+ персон») выносится в отдельную таблицу-исключений `component_conflicts` — реализуется на **Stage 1+**. На MVP все сочетания считаются валидными → «нет тупиков» обеспечивается автоматически.

> Это решает проблему «конструктор превращается в выбор из N шаблонов»: пользователь свободно комбинирует любые компоненты, цена собирается из надбавок.

---

## 3. Функциональные требования

### 3.1 Общие
- На каждом экране (кроме стартового) — кнопки **«⬅️ Назад»** и **«🏠 В главное меню»**.
- При переходе между шагами предыдущее сообщение бота **удаляется**.
- **Состояние воронки на MVP хранится только в FSM (MemoryStorage).** Таблица `user_sessions` создаётся в схеме, но подключается к чтению/записи только на **Stage 3** (детект брошенных сессий). Это избавляет от двойного источника истины на MVP.

### 3.2 Пользователь
| # | Требование |
|---|---|
| U1 | Стартовое меню: «Популярные заказы», «Создать самому», «Справка» |
| U2 | Заказ по готовому шаблону без воронки |
| U3 | Прохождение воронки (7 шагов) |
| U4 | Прервать сборку и вернуться в начало |
| U5 | Итог заказа + рассчитанная цена + изображение |
| U6 | Отменить заказ и вернуться в меню |
| U7 | Уведомления о смене статуса |
| U8 | Оставить отзыв (уходит админу) |

### 3.3 Администратор
| # | Требование |
|---|---|
| A1 | «Заказы» → «Открытые»/«Закрытые» → список |
| A2 | Мониторинг воронки (активные сессии + статусы) |
| A3 | Смена статуса заказа (уведомляет юзера) |
| A4 | Уведомление о новом заказе |
| A5 | Получение отзывов |

---

## 4. Пользовательский путь и жизненный цикл заказа

**Воронка:**
```
Старт → Приветствие
├── «Популярные заказы» → выбор шаблона → Итог → Заказ
├── «Справка» → текст → назад
└── «Создать самому»:
      1. Повод      2. Кол-во персон   3. Форма
      4. Начинка    5. Оформление      6. Дата+пожелания
      7. Итог (состав + цена + изображение) → отправка админу
```

**Жизненный цикл заказа (order_status):**
```
created → confirmed → in_progress → ready → paid → closed
                          (in_progress, paid — Stage 2)
cancelled — из любого статуса
```

---

## 5. Этапы разработки

| Этап | Содержание | Зависит от |
|---|---|---|
| **MVP** | Старт → воронка (свободный конструктор, цена по компонентам) → заказ → уведомления. Админ получает заказ, меняет статус. Шаблоны в БД вручную. Состояние — только в FSM. | — |
| **Stage 1** | Фото популярных + быстрый заказ. Фото компонентов на шагах. Таблица `component_conflicts` (ограничения совместимости). | MVP |
| **Stage 2** | Аванс + полная оплата, чек, закрытие. Интеграция ЮKassa/Robokassa. | MVP, S1 |
| **Stage 3** | Подключение `user_sessions` (персист draft), детект брошенных сессий → админ подключается в чат. | MVP |
| **Stage 4** | Создание изделий админом через бота + уведомления о новинках. | MVP |

---

## 6. Архитектура БД (PostgreSQL)

Схема создаётся из SQLAlchemy-моделей (`db/models.py`) через `Base.metadata.create_all`. Ручных миграций нет — при изменении моделей схема пересоздаётся скриптом `scripts/init_db.py` (для MVP допустимо, см. п.11).

### 6.1 ENUM-типы

ENUM-типы объявляются как Python `enum.Enum` (наследники `str, enum.Enum`) и оборачиваются в `SAEnum` в `models.py` — создаются автоматически вместе с таблицами. Наследование от `str` позволяет сравнивать member со строкой; **в коде и seed передаются именно member-ы Enum**, не строки.

```python
import enum

class OrderStatus(str, enum.Enum):
    created = "created"
    confirmed = "confirmed"
    in_progress = "in_progress"
    ready = "ready"
    paid = "paid"
    closed = "closed"
    cancelled = "cancelled"

class PaymentStatus(str, enum.Enum):
    none = "none"
    advance_paid = "advance_paid"
    fully_paid = "fully_paid"

class ProductStatus(str, enum.Enum):
    active = "active"
    unavailable = "unavailable"
    archived = "archived"

class ComponentType(str, enum.Enum):
    occasion = "occasion"
    persons = "persons"
    shape = "shape"
    filling = "filling"
    decor = "decor"
```

Использование в модели:
```python
from sqlalchemy import Enum as SAEnum
type: Mapped[ComponentType] = mapped_column(SAEnum(ComponentType))
```

### 6.2 Таблицы (эквивалент DDL)
```sql
-- Пользователи
CREATE TABLE users (
    id           SERIAL PRIMARY KEY,
    telegram_id  BIGINT UNIQUE NOT NULL,
    username     VARCHAR(64),
    first_name   VARCHAR(64),
    is_admin     BOOLEAN NOT NULL DEFAULT FALSE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Состояние воронки (персист draft — используется со Stage 3)
CREATE TABLE user_sessions (
    id           SERIAL PRIMARY KEY,
    user_id      INT NOT NULL REFERENCES users(id),
    current_step VARCHAR(32),
    draft        JSONB NOT NULL DEFAULT '{}',
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(user_id)
);

-- Компоненты (варианты выбора + надбавка к цене)
CREATE TABLE components (
    id           SERIAL PRIMARY KEY,
    type         component_type NOT NULL,
    name         VARCHAR(64) NOT NULL,
    image_url    TEXT,
    weight_grams DECIMAL(7,2),
    price_delta  DECIMAL(9,2) NOT NULL DEFAULT 0,   -- надбавка к базовой цене
    sort_order   INT NOT NULL DEFAULT 0,
    is_active    BOOLEAN NOT NULL DEFAULT TRUE
);

-- Изделия / шаблоны (только для «Популярных заказов»)
CREATE TABLE products (
    id                SERIAL PRIMARY KEY,
    name              VARCHAR(64) NOT NULL,
    description       VARCHAR(255),
    price             DECIMAL(9,2) NOT NULL,
    image_url         TEXT,
    is_template       BOOLEAN NOT NULL DEFAULT FALSE,
    status            product_status NOT NULL DEFAULT 'active',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    status_changed_at TIMESTAMPTZ
);

-- Связь шаблон ↔ компоненты
CREATE TABLE product_components (
    id           SERIAL PRIMARY KEY,
    product_id   INT NOT NULL REFERENCES products(id),
    component_id INT NOT NULL REFERENCES components(id),
    UNIQUE(product_id, component_id)
);

-- Заказы
CREATE TABLE orders (
    id                SERIAL PRIMARY KEY,
    user_id           INT NOT NULL REFERENCES users(id),
    product_id        INT REFERENCES products(id),      -- NULL для кастомного заказа
    description       VARCHAR(255),                     -- состав кастомного торта
    total_price       DECIMAL(9,2),                     -- рассчитанная цена
    desired_date      DATE,
    status            order_status NOT NULL DEFAULT 'created',
    result_image_url  TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    status_changed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    closed_at         TIMESTAMPTZ
);

-- Состав кастомного заказа (какие компоненты выбраны)
CREATE TABLE order_components (
    id           SERIAL PRIMARY KEY,
    order_id     INT NOT NULL REFERENCES orders(id),
    component_id INT NOT NULL REFERENCES components(id),
    UNIQUE(order_id, component_id)
);

-- Оплаты (Stage 2)
CREATE TABLE payments (
    id                SERIAL PRIMARY KEY,
    order_id          INT NOT NULL REFERENCES orders(id),
    advance_amount    DECIMAL(9,2),
    total_amount      DECIMAL(9,2),
    status            payment_status NOT NULL DEFAULT 'none',
    advance_paid_at   TIMESTAMPTZ,
    fully_paid_at     TIMESTAMPTZ,
    receipt_url       TEXT,
    status_changed_at TIMESTAMPTZ
);

-- Отзывы
CREATE TABLE reviews (
    id         SERIAL PRIMARY KEY,
    order_id   INT NOT NULL REFERENCES orders(id),
    user_id    INT NOT NULL REFERENCES users(id),
    text       VARCHAR(1000),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Конфликты компонентов (Stage 1+)
CREATE TABLE component_conflicts (
    id     SERIAL PRIMARY KEY,
    a_id   INT NOT NULL REFERENCES components(id),
    b_id   INT NOT NULL REFERENCES components(id),
    UNIQUE(a_id, b_id)
);

-- Индексы
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_orders_user ON orders(user_id);
CREATE INDEX idx_prodcomp_product ON product_components(product_id);
CREATE INDEX idx_prodcomp_component ON product_components(component_id);
CREATE INDEX idx_ordercomp_order ON order_components(order_id);
CREATE INDEX idx_components_type ON components(type);
```

Все индексы задаются в моделях (`index=True` / `Index(...)`) и создаются вместе с таблицами.

> `component_conflicts` создаётся в схеме сразу (пустая), логика проверки подключается на Stage 1.

---

## 7. Схема связей БД

```
users ──1:1── user_sessions
  │
  ├──1:N── orders ──N:1── products ──M:N── components
  │            │           (product_components)         (шаблоны)
  │            ├──M:N── components (order_components)    (кастом)
  │            ├──1:1── payments
  │            └──1:N── reviews
  │
components ──M:N── components (component_conflicts, Stage 1+)
```

---

## 8. Диаграмма состояний FSM

Группа состояний воронки `OrderFSM` (aiogram `StatesGroup`). **Draft хранится в FSM-data** (на MVP — MemoryStorage):

```
                    ┌──────────────┐
                    │  main_menu   │  (нет состояния / стартовое)
                    └──────┬───────┘
             ┌─────────────┼───────────────┐
             ▼             ▼               ▼
     «Популярные»   «Создать самому»   «Справка»
             │             │               │
             ▼             ▼               ▼
     choosing_template  occasion       (текст, возврат)
             │             │
             │             ▼
             │          persons
             │             │
             │             ▼
             │          shape
             │             │
             │             ▼
             │          filling
             │             │
             │             ▼
             │          decoration
             │             │
             │             ▼
             │          date_wishes   (ввод текста)
             │             │
             └─────────────┤
                           ▼
                       confirming     (Итог: состав + цена + фото)
                           │
                  ┌────────┴─────────┐
                  ▼                  ▼
             «Заказать»          «Отменить»
                  │                  │
                  ▼                  ▼
             order_created      main_menu
             (заказ + состав,   (сброс FSM-data)
              уведомление
              админу, сброс FSM)
```

**Переходы:**
- «⬅️ Назад» — на предыдущее состояние, выбор в FSM-data сохраняется, шаг восстанавливается.
- «🏠 В главное меню» — `state.clear()`, возврат к main_menu.

**Определение в коде:**
```python
from aiogram.fsm.state import State, StatesGroup

class OrderFSM(StatesGroup):
    choosing_template = State()
    occasion    = State()
    persons     = State()
    shape       = State()
    filling     = State()
    decoration  = State()
    date_wishes = State()
    confirming  = State()
```

---

## 9. Структура проекта

```
cake_bot/
├── bot.py                    # точка входа, запуск polling/webhook
├── config.py                 # чтение env (pydantic-settings), base_price
├── requirements.txt
├── .env.example
│
├── db/
│   ├── __init__.py
│   ├── base.py               # engine, async_session, Base
│   ├── models.py             # SQLAlchemy-модели (таблицы, ENUM, индексы)
│   └── repositories/
│       ├── users.py
│       ├── sessions.py
│       ├── products.py
│       ├── components.py
│       └── orders.py
│
├── states/
│   └── order.py              # OrderFSM
│
├── keyboards/
│   ├── common.py             # «Назад», «В главное меню»
│   ├── user.py               # меню, шаги воронки
│   └── admin.py              # меню админа, статусы
│
├── handlers/
│   ├── __init__.py           # регистрация роутеров
│   ├── common.py             # /start, назад, в меню
│   ├── user/
│   │   ├── funnel.py         # воронка «создать самому»
│   │   ├── templates.py      # популярные заказы
│   │   ├── order.py          # подтверждение, отмена
│   │   └── review.py         # отзывы
│   └── admin/
│       ├── orders.py         # список, смена статуса
│       └── monitoring.py     # воронка A2
│
├── services/
│   ├── funnel_service.py     # компоненты шага + расчёт цены
│   ├── order_service.py      # создание заказа, смена статуса
│   └── notify_service.py     # уведомления юзеру/админу
│
├── utils/
│   └── message.py            # удаление прошлого сообщения бота
│
└── scripts/
    ├── init_db.py            # создание схемы из моделей
    └── seed.py               # начальные данные
```

---

## 10. Технические механики

### 10.1 Удаление предыдущего сообщения
Хранить `last_bot_message_id` в FSM-data. Перед отправкой нового шага:
```python
async def send_step(bot, chat_id, state, text, kb):
    data = await state.get_data()
    if mid := data.get("last_bot_message_id"):
        try: await bot.delete_message(chat_id, mid)
        except: pass
    msg = await bot.send_message(chat_id, text,ные

Так как Alembic не используется, схема создаётся напрямую из моделей.

### 11.1 `db/base.py` (ключевое)
```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from config import settings

class Base(DeclarativeBase):
    pass

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False)
```

### 11.2 `scripts/init_db.py` — создание схемы
```python
# scripts/init_db.py
import asyncio
from db.base import engine, Base
import db.models  # noqa: F401 — регистрирует все модели в metadata

async def init_db(drop: bool = False):
    async with engine.begin() as conn:
        if drop:
            await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Схема БД создана")

if __name__ == "__main__":
    import sys
    asyncio.run(init_db(drop="--drop" in sys.argv))
```
- `python scripts/init_db.py` — создать недостающие таблицы (безопасно, `create_all` не трогает существующие).
- `python scripts/init_db.py --drop` — пересоздать схему с нуля (данные теряются; для MVP/разработки).

### 11.3 `scripts/seed.py` — начальные данные
Заполняет **компоненты с надбавками к цене** (основа конструктора) и 3 готовых шаблона (для «Популярных заказов»). ENUM передаётся member-ом (`ComponentType.occasion`, `ProductStatus.active`).

```python
# scripts/seed.py
import asyncio
from db.base import async_session
from db.models import (
    Component, Product, ProductComponent,
    ComponentType, ProductStatus,
)

# type: [(name, weight_grams, price_delta)]
COMPONENTS = {
    ComponentType.occasion: [
        ("День рождения", None, 0), ("Свадьба", None, 0), ("Без повода", None, 0),
    ],
    ComponentType.persons: [
        ("6-8 персон", 1000, 0), ("10-12 персон", 1600, 800), ("15+ персон", 2500, 1800),
    ],
    ComponentType.shape: [
        ("Круглый", None, 0), ("Квадратный", None, 200), ("Цифра", None, 700),
    ],
    ComponentType.filling: [
        ("Красный бархат", None, 300), ("Шоколадный", None, 200), ("Ванильный", None, 0),
    ],
    ComponentType.decor: [
        ("Классика крем", None, 0), ("Ягоды сверху", None, 500), ("Мастика", None, 900),
    ],
}

# Готовые шаблоны (Популярные заказы). price — фиксированная цена шаблона.
TEMPLATES = [
    {
        "name": "Классический ДР",
        "description": "Круглый, красный бархат, крем",
        "price": 3500, "is_template": True,
        "components": ["День рождения", "10-12 персон", "Круглый",
                       "Красный бархат", "Классика крем"],
    },
```python
    {
        "name": "Свадебный ярус",
        "description": "Квадратный, ванильный, мастика",
        "price": 7000, "is_template": True,
        "components": ["Свадьба", "15+ персон", "Квадратный",
                       "Ванильный", "Мастика"],
    },
    {
        "name": "Шоколадная цифра",
        "description": "Цифра, шоколад, ягоды",
        "price": 4200, "is_template": True,
        "components": ["Без повода", "6-8 персон", "Цифра",
                       "Шоколадный", "Ягоды сверху"],
    },
]

async def seed():
    async with async_session() as s:
        # 1. Компоненты
        name_to_comp = {}
        for ctype, items in COMPONENTS.items():
            for order, (name, weight, delta) in enumerate(items):
                c = Component(
                    type=ctype,               # member Enum, не строка
                    name=name,
                    weight_grams=weight,
                    price_delta=delta,
                    sort_order=order,
                )
                s.add(c); await s.flush()
                name_to_comp[name] = c.id
        # 2. Шаблоны + связи
        for t in TEMPLATES:
            p = Product(
                name=t["name"],
                description=t["description"],
                price=t["price"],
                is_template=t["is_template"],
                status=ProductStatus.active,   # member Enum
            )
            s.add(p); await s.flush()
            for cname in t["components"]:
                s.add(ProductComponent(
                    product_id=p.id,
                    component_id=name_to_comp[cname],
                ))
        await s.commit()
        print("✅ Seed завершён")

if __name__ == "__main__":
    asyncio.run(seed())
```

> **Важно:** компоненты — основа конструктора (любой их выбор валиден, цена = `base_price` + сумма `price_delta`). Шаблоны выше нужны только для быстрого пути «Популярные заказы» и не ограничивают воронку.

---

## 12. Настройка окружения и запуск

**requirements.txt (ключевое):**
```
aiogram>=3.4
sqlalchemy>=2.0
asyncpg
pydantic-settings
apscheduler          # для Stage 3
```

**.env.example:**
```
BOT_TOKEN=123456:ABC...
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/cakebot
ADMIN_TELEGRAM_ID=123456789
BASE_PRICE=2500
```

**config.py:**
```python
from decimal import Decimal
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    bot_token: str
    database_url: str
    admin_telegram_id: int
    base_price: Decimal = Decimal("2500")   # базовая цена кастомного торта
    class Config:
        env_file = ".env"

settings = Settings()
```

**Запуск:**
```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # заполнить значения

python scripts/init_db.py     # создать схему из моделей
python scripts/seed.py        # залить стартовые данные
python bot.py                 # запуск бота
```

---

## 13. MVP-объём

**Таблицы (создаются все, но активно используются):** `users`, `components`, `products`, `product_components`, `orders`, `order_components`.
**Создаются, но не задействованы на MVP:** `user_sessions` (Stage 3), `component_conflicts` (Stage 1), `payments` (Stage 2), `reviews` (Stage 4).

**Функции:**
- старт → воронка (свободный конструктор, цена по компонентам) → создание заказа + состав → уведомление админу → смена статуса → уведомление юзеру;
- популярные шаблоны (без фото).

**Состояние воронки — только в FSM (MemoryStorage), без записи в БД.**

**Не входит:** оплаты, отзывы, фото-примеры, ограничения совместимости, создание изделий через бота, детект брошенных сессий, персист сессий в БД.


**Конец документа**