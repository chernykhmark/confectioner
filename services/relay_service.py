"""
Admin-to-user relay: двусторонний мост админ ↔ пользователь.

Почему in-memory, а НЕ FSM:
- Relay-диалог не относится к воронке заказа; мешать их в одном FSM-стейте нельзя.
- Нужен двусторонний маппинг, читаемый из хендлеров ОБЕИХ сторон
  (FSM админа не виден из хендлера юзера, и наоборот).
- Relay эфемерен (до «Завершить диалог») — персист в БД избыточен.

Хранит один активный диалог админа (админ один — settings.admin_telegram_id).
При масштабировании до N админов структура легко расширяется до dict по admin_id.
"""
import logging

log = logging.getLogger(__name__)


class RelayState:
    def __init__(self):
        # admin_tg_id -> user_tg_id   и   user_tg_id -> admin_tg_id
        self._admin_to_user: dict[int, int] = {}
        self._user_to_admin: dict[int, int] = {}

    def start(self, admin_id: int, user_id: int):
        self._admin_to_user[admin_id] = user_id
        self._user_to_admin[user_id] = admin_id
        log.info("relay_started admin_id=%s user_id=%s", admin_id, user_id)

    def stop_by_admin(self, admin_id: int):
        user_id = self._admin_to_user.pop(admin_id, None)
        if user_id is not None:
            self._user_to_admin.pop(user_id, None)
            log.info("relay_stopped admin_id=%s user_id=%s", admin_id, user_id)
        return user_id

    def user_for_admin(self, admin_id: int) -> int | None:
        return self._admin_to_user.get(admin_id)

    def admin_for_user(self, user_id: int) -> int | None:
        return self._user_to_admin.get(user_id)

    def is_user_in_relay(self, user_id: int) -> bool:
        return user_id in self._user_to_admin


relay = RelayState()
