
---

# Промпты для поэтапной реализации

```
[ВЕСЬ ДОКУМЕНТ АРХИТЕКТУРЫ v1.1]

---

[ПРОМПТ КОНКРЕТНОГО ЭТАПА СМОТРИ НИЖЕ]
```

---

## 📌 Промпт 0 — Фундамент проекта (выполнить ПЕРВЫМ)

```
Выше приведена архитектура проекта «Телеграм-бот Конструктор тортов» v1.1.

ЗАДАЧА: создай базовый каркас проекта — фундамент, на который будут наслаиваться следующие этапы. Ничего из бизнес-логики этапов реализовывать НЕ нужно, только инфраструктуру.

Реализуй строго по разделам 6 (БД), 9 (структура), 11 (инициализация схемы), 12 (окружение):

1. requirements.txt и .env.example — как в разделе 12 (БЕЗ alembic; .env содержит BASE_PRICE).
2. config.py — на pydantic-settings, как в разделе 12: bot_token, database_url, admin_telegram_id, base_price (Decimal, дефолт из документа).
3. db/base.py — async engine, async_session (async_sessionmaker), declarative Base (DeclarativeBase). Подключение через settings.database_url. Ровно как в разделе 11.1.
4. db/models.py — ВСЕ модели SQLAlchemy 2.0 (mapped_column, типизация) строго по разделу 6.2: users, user_sessions, components (с полем price_delta), products, product_components, orders (с полем total_price), order_components, payments, reviews, component_conflicts. ENUM-типы — как Python Enum (наследники str, enum.Enum) из раздела 6.1, обёрнутые в SQLAlchemy Enum (создаются вместе с таблицами). Все связи (relationship) и индексы из документа (index=True / Index(...)).
5. scripts/init_db.py — создание схемы из моделей через Base.metadata.create_all, ровно как в разделе 11.2 (с поддержкой флага --drop). Импорт db.models для регистрации всех моделей в metadata.
6. bot.py — точка входа: инициализация Bot, Dispatcher (MemoryStorage), подключение роутеров из handlers/__init__.py (пока пустой список), запуск long polling.
7. handlers/__init__.py — функция register_all_routers(dp), пока без роутеров.
8. scripts/seed.py — ровно как в разделе 11.3: компоненты с price_delta и 3 шаблона. ENUM передавать member-ами (ComponentType.occasion, ProductStatus.active), НЕ строками.

ТРЕБОВАНИЯ:
- Python 3.11+, aiogram 3.x, SQLAlchemy 2.0 async, asyncpg.
- НЕ используй Alembic и миграции — схема создаётся только через scripts/init_db.py (Base.metadata.create_all).
- ENUM объявляй как классы str, enum.Enum; в seed/коде передавай member-ы Enum, не строки.
- Код должен запускаться: python scripts/init_db.py → python scripts/seed.py → python bot.py.
- Соблюдай структуру каталогов из раздела 9 буквально (папки migrations/ и файла alembic.ini НЕТ).
- Добавь __init__.py где нужно для импортов.
- Никаких сторонних решений вместо указанного стека.

Выведи все файлы с путями. В конце — краткая инструкция проверки.
```

---

## 📌 Промпт 1 — MVP: воронка (свободный конструктор), заказы, статусы

```
Выше — архитектура проекта v1.1. Фундамент (Промпт 0) уже реализован: есть db/models.py со всеми моделями (включая components.price_delta, orders.total_price, order_components), db/base.py (async_session, Base), config.py (settings с bot_token, database_url, admin_telegram_id, base_price), bot.py с register_all_routers, scripts/init_db.py, scripts/seed.py залит. Миграций и Alembic в проекте нет.

ЗАДАЧА: реализуй MVP (раздел 5 «MVP» + раздел 13). Опирайся на разделы 2 (Подход А — свободный конструктор), 3 (U1-U7, A1-A4), 4 (путь), 8 (FSM), 10 (механики).

КЛЮЧЕВОЕ (Подход А):
- Состояние воронки хранится ТОЛЬКО в FSM-data (MemoryStorage). Таблицу user_sessions НЕ читать и НЕ писать на MVP (раздел 3.1, 5).
- На каждом шаге воронки показываются ВСЕ активные компоненты нужного типа (components.is_active=True). Любая комбинация валидна (component_conflicts НЕ используется на MVP).
- Цена кастомного заказа = base_price + сумма price_delta выбранных компонентов (раздел 10.2).
- Шаблоны (products, is_template=True) используются ТОЛЬКО для «Популярных заказов», в воронке не задействованы.

Реализуй:

1. states/order.py — класс OrderFSM (StatesGroup) точно по разделу 8: choosing_template, occasion, persons, shape, filling, decoration, date_wishes, confirming.

2. utils/message.py — функция send_step(bot, chat_id, state, text, kb) с удалением предыдущего сообщения через last_bot_message_id (раздел 10.1).

3. keyboards/common.py — «⬅️ Назад» и «🏠 В главное меню» (inline). keyboards/user.py — главное меню (U1) и клавиатуры шагов воронки. keyboards/admin.py — меню «Заказы»→«Открытые»/«Закрытые», кнопки смены статуса.

4. db/repositories/ — репозитории users, products, components, orders с методами для MVP (get_or_create_user, list components by type, list templates, create_order + запись order_components, get_orders_by_status, update_order_status и т.д.). Репозиторий sessions создай как заглушку — на MVP не используется.

5. services/funnel_service.py — components_for_step(session, step_type): все активные компоненты типа, сортировка по sort_order (раздел 10.2). calculate_price(session, selected_ids, base_price): base_price + SUM(price_delta) (раздел 10.2). services/order_service.py — создание заказа из FSM-data: собрать component_id, рассчитать total_price, создать orders (product_id=NULL, description=состав, total_price) + order_components; смена статуса (раздел 10.3). services/notify_service.py — уведомления юзеру (смена статуса, U7) и админу (новый заказ A4) через settings.admin_telegram_id.

6. handlers/common.py — /start (регистрация юзера, главное меню). Восстановление сессии из БД НЕ делать (Stage 3). Обработка «Назад» (возврат на предыдущий шаг с сохранением выбора в FSM-data) и «В главное меню» (state.clear()).

7. handlers/user/funnel.py — воронка «Создать самому» (occasion→...→date_wishes→confirming): на каждом шаге components_for_step, удаление прошлого сообщения, сохранение выбора в FSM-data. handlers/user/templates.py — «Популярные заказы» (U2): список is_template=True → выбор → confirming (цена = products.price). handlers/user/order.py — экран confirming (состав + итоговая цена + result_image_url если есть, U5), «Заказать» (create_order, уведомить админа, state.clear), «Отменить» (U6).

8. handlers/admin/orders.py — «Заказы» (A1): открытые/закрытые списки, карточка заказа (состав + total_price), смена статуса (A3) с уведомлением юзера. handlers/admin/monitoring.py — мониторинг воронки (A2) на MVP: список активных FSM-контекстов (юзер + текущий шаг). Если получить активные FSM-контексты из MemoryStorage напрямую сложно — реализуй простой in-memory реестр активных сессий (обоснуй выбор). user_sessions НЕ использовать.

9. Зарегистрируй все роутеры в handlers/__init__.py. Проверка is_admin — по settings.admin_telegram_id (фильтр).

ТРЕБОВАНИЯ:
- Строго стек и структура из документа. Импорты из существующих db/models.py, db/base.py, config.py. Alembic не использовать.
- MVP статусы заказа: created → confirmed → ready → closed (+ cancelled). in_progress/paid НЕ трогать (Stage 2).
- Отзывы, фото компонентов, ограничения совместимости, создание изделий — НЕ реализовывать.
- Каждый шаг воронки удаляет предыдущее сообщение бота.
- Код должен интегрироваться с фундаментом без переписывания моделей.

Выведи все новые/изменённые файлы с полными путями. В конце — сценарий ручной проверки MVP (включая проверку расчёта цены).
```

---

## 📌 Промпт 2 — Stage 1: изображения + ограничения совместимости

```
Выше — архитектура v1.1. Реализованы Промпт 0 (фундамент, схема через scripts/init_db.py, без Alembic) и Промпт 1 (MVP: свободный конструктор, заказы, статусы, шаблоны без фото; состояние воронки только в FSM).

ЗАДАЧА: реализуй Stage 1 (раздел 5): фото популярных заказов + быстрый заказ; фото-примеры компонентов на шагах воронки (U2, U3 с изображениями); ограничения совместимости компонентов через таблицу component_conflicts.

Реализуй, НЕ ломая MVP:

ЧАСТЬ A — Изображения:
1. handlers/user/templates.py — при показе «Популярных заказов» выводить products.image_url для каждого шаблона (карточка с фото). Быстрый заказ: выбор шаблона сразу ведёт на confirming с фото готового изделия.
2. handlers/user/funnel.py — на шагах, где у components есть image_url, показывать варианты с изображениями-примерами. Учитывай ограничение aiogram (media group или фото на конкретный вариант — реши оптимально и объясни выбор).
3. utils/message.py — при необходимости helper send_photo_step, сохраняя логику удаления предыдущего сообщения (раздел 10.1); учти, что удаляемое сообщение может быть фото.

ЧАСТЬ B — Совместимость (раздел 2, component_conflicts):
4. services/funnel_service.py — расширь components_for_step: исключай компоненты, конфликтующие (по component_conflicts) с уже выбранными в FSM-data. Гарантия «нет тупиков» сохраняется: если исключений слишком много — не должно оставаться пустого шага (опиши, как это обеспечиваешь; при необходимости — валидация seed-конфликтов).
5. scripts/seed.py — добавь несколько демонстрационных записей в component_conflicts (например, «Цифра» × «15+ персон») как заглушки, помеченные комментарием.

ТРЕБОВАНИЯ:
- Изображения по URL или Telegram file_id (раздел 14) — поддержи URL, опиши замену на file_id.
- Не менять схему БД (image_url, component_conflicts, price_delta уже есть; Alembic не используется).
- Сохранить работу удаления предыдущих сообщений, расчёт цены и всю логику MVP.

Выведи изменённые файлы с путями и краткую инструкцию по добавлению реальных картинок и конфликтов.
```

---

## 📌 Промпт 3 — Stage 2: оплаты

```
Выше — архитектура v1.1. Реализованы Промпт 0, 1 (MVP), 2 (Stage 1). Схема БД создаётся через scripts/init_db.py, Alembic не используется.

ЗАДАЧА: реализуй Stage 2 (раздел 5): пользователь вносит аванс и полную оплату; админ отправляет чек и закрывает заказ. Провайдер — ПЛЕЙСХОЛДЕР, но с чистой абстракцией под будущую ЮKassa/Robokassa.

Реализуй, НЕ ломая предыдущие этапы:

1. Активируй полный жизненный цикл заказа (раздел 4): created → confirmed → in_progress → ready → paid → closed. in_progress — после оплаты аванса, paid — после полной оплаты.

2. services/payment_service.py — абстракция PaymentProvider (интерфейс create_invoice/check) + MockPaymentProvider (сразу «успех» по кнопке). Логика: создать payment по order, отметить advance_paid / fully_paid, проставить даты и статусы в таблице payments (раздел 6.2).

3. handlers/user/order.py (или новый payment.py) — после confirmed юзер видит кнопку оплаты аванса → MockPaymentProvider → payment.status=advance_paid, order.status=in_progress, уведомление. После ready — кнопка полной оплаты → fully_paid, order.status=paid.

4. handlers/admin/orders.py — админ: прислать чек (receipt_url) юзеру и закрыть заказ (order.status=closed, closed_at). Уведомление юзеру с чеком.

5. services/notify_service.py — добавь уведомления по оплатам и чеку.

6. keyboards — кнопки оплаты (юзер), «Отправить чек»/«Закрыть» (админ).

ТРЕБОВАНИЯ:
- Таблица payments уже есть — использовать, схему не менять (Alembic не используется).
- Реальную платёжку не подключать: всё через MockPaymentProvider, замена на ЮKassa = замена одного класса.
- Суммы: total_amount = orders.total_price (кастом) ИЛИ products.price (шаблон). advance_amount — правило, напр. 50% от total_amount. Задай единый способ получения суммы заказа независимо от типа (кастом/шаблон) и опиши его.
- Не ломать воронку, расчёт цены, статусы MVP, изображения и конфликты Stage 1.

Выведи новые/изменённые файлы с путями и инструкцию, как позже подключить реальный провайдер.
```

---

## 📌 Промпт 4 — Stage 3: персист сессий + брошенные сессии

```
Выше — архитектура v1.1. Реализованы Промпт 0, 1 (MVP), 2, 3. Схема БД создаётся через scripts/init_db.py (Base.metadata.create_all), Alembic и миграции отсутствуют. ВАЖНО: на MVP состояние воронки хранилось ТОЛЬКО в FSM; таблица user_sessions создана, но не использовалась. На этом этапе она подключается впервые.

ЗАДАЧА: реализуй Stage 3 (раздел 5): персист draft воронки в user_sessions + детект брошенных сессий → админ подключается в чат пользователя.

Реализуй, НЕ ломая предыдущие этапы:

1. Подключение user_sessions (раздел 3.1, 10.5):
   - db/repositories/sessions.py — методы upsert_session(user_id, current_step, draft), get_session(user_id), delete_session(user_id).
   - handlers/user/funnel.py — на каждом шаге дублировать текущий шаг и выбор в user_sessions (updated_at обновляется). При создании заказа / выходе в меню — удалять сессию.
   - handlers/common.py — при /start, если есть незавершённый draft в user_sessions, предложить «Продолжить»/«Начать заново» (раздел 10.5). Синхронизация FSM-data и user_sessions — единый источник при восстановлении.

2. Фоновая задача на APScheduler (раздел 12): периодически проверяет user_sessions.updated_at. Если сессия активна (есть draft, заказ не создан) и не обновлялась дольше TIMEOUT (config, напр. 30 мин) — «брошенная».

3. При брошенной сессии — уведомить админа (settings.admin_telegram_id): кто, на каком шаге, содержимое draft. Кнопка «Написать пользователю».

4. services/ — «admin-to-user relay»: админ выбирает юзера → его сообщения пересылаются юзеру от имени бота, ответы юзера — обратно админу, до команды «Завершить диалог». Состояние relay храни в FSM админа или отдельной структуре — обоснуй.

5. Интеграция запуска scheduler в bot.py при старте.

ТРЕБОВАНИЯ:
- Схему БД не менять (user_sessions.updated_at, draft уже есть). Если КРАЙНЕ необходимо новое поле — добавь ТОЛЬКО в db/models.py и применяй через `python scripts/init_db.py --drop` (данные теряются — предупреди). Alembic не использовать.
- Таймаут и интервал — через config.
- Relay не должен конфликтовать с активной FSM-воронкой пользователя — опиши, как разруливаешь.
- Не ломать воронку, оплаты, статусы, изображения, конфликты.
- Обнови раздел monitoring (A2): теперь мониторинг может читать активные сессии из user_sessions вместо in-memory реестра MVP.

Выведи новые/изменённые файлы с путями и описание работы relay.
```

---

## 📌 Промпт 5 — Stage 4: создание изделий + отзывы

```
Выше — архитектура v1.1. Реализованы Промпт 0, 1 (MVP), 2, 3, 4. Схема БД создаётся через scripts/init_db.py, Alembic не используется.

ЗАДАЧА: реализуй Stage 4 (раздел 5) + функцию отзывов (U8, A5), отложенную с MVP.

Реализуй, НЕ ломая предыдущие этапы:

ЧАСТЬ A — Создание изделий админом (Stage 4):
1. handlers/admin/products.py — мастер создания изделия (отдельная StatesGroup AdminProductFSM): ввод названия, описания, цены, image_url, выбор набора компонентов (по типам), флаг is_template. Сохранение в products + product_components.
2. Управление статусом изделия (product_status: active/unavailable/archived).
3. При создании нового активного шаблона (is_template=True) — рассылка «новинка» всем пользователям из users.
4. services/notify_service.py — метод массовой рассылки (try/except на каждого юзера, асинхронно, без блокировки бота).

ЧАСТЬ B — Отзывы:
5. handlers/user/review.py — после закрытия заказа (order.status=closed) предложить оставить отзыв (текст). Сохранить в reviews, переслать админу (A5).
6. db/repositories — методы create_review, list_users (для рассылки).

ТРЕБОВАНИЯ:
- Таблицы products, product_components, reviews, users уже есть — использовать, схему не менять (Alembic не используется).
- Мастер создания шаблона должен собирать корректный набор: по одному компоненту на каждый тип из component_type (occasion, persons, shape, filling, decor). Так шаблон остаётся консистентным.
- Массовая рассылка — асинхронно, с обработкой ошибок.
- Не ломать воронку, оплаты, relay, изображения, конфликты, расчёт цены.

Выведи новые/изменённые файлы с путями и сценарий проверки: создание изделия админом → уведомление юзерам → заказ → закрытие → отзыв админу.
```

