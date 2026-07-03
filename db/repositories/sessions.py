# MVP: заглушка. Состояние воронки хранится только в FSM (MemoryStorage).
# Подключается на Stage 3 (персист draft, детект брошенных сессий).


async def noop(*args, **kwargs):
    return None