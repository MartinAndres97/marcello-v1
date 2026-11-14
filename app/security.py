"""Autenticación del panel (sesión firmada + bcrypt) y límites de frecuencia."""
import getpass
import hmac
import threading
import time
from collections import defaultdict, deque

import bcrypt
from fastapi import HTTPException, Request

from app.config import get_settings, hash_password


class SlidingWindowLimiter:
    def __init__(self, max_events: int, window_seconds: int):
        self.max_events = max_events
        self.window = window_seconds
        self._events = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, key, now):
        q = self._events[key]
        while q and now - q[0] > self.window:
            q.popleft()
        if not q:
            self._events.pop(key, None)

    def blocked(self, key: str) -> bool:
        with self._lock:
            self._prune(key, time.monotonic())
            return len(self._events.get(key, ())) >= self.max_events

    def hit(self, key: str) -> None:
        with self._lock:
            now = time.monotonic()
            self._prune(key, now)
            self._events[key].append(now)

    def reset(self) -> None:
        with self._lock:
            self._events.clear()


login_limiter = SlidingWindowLimiter(max_events=5, window_seconds=300)    # 5 fallos / 5 min por IP
submit_limiter = SlidingWindowLimiter(max_events=30, window_seconds=60)   # 30 envíos / min por IP


def reset_limiters() -> None:
    login_limiter.reset()
    submit_limiter.reset()


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def verify_admin(username: str, password: str) -> bool:
    s = get_settings()
    user_ok = hmac.compare_digest(username.encode("utf-8"), s.admin_user.encode("utf-8"))
    try:
        pw_ok = bcrypt.checkpw(password.encode("utf-8")[:72], s.admin_password_hash)
    except ValueError:
        pw_ok = False
    return user_ok and pw_ok  # siempre se evalúa bcrypt, para no filtrar si el usuario existe


def is_admin(request: Request) -> bool:
    return bool(request.session.get("admin"))


def require_admin(request: Request) -> None:
    if not is_admin(request):
        raise HTTPException(status_code=401, detail="No autenticado")


if __name__ == "__main__":  # python -m app.security  → genera un hash para ADMIN_PASSWORD_HASH
    print(hash_password(getpass.getpass("Contraseña: ")).decode())
