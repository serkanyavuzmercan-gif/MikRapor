"""
İşbirlikçi iptal jetonu — süren HTTP bağlantısını kesmek için.

RaporWorker iptalde jetonu işaretler ve bağlı http.client bağlantısını kapatır;
MikroClient transport'u thread-local jetonu okur.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

_tls = threading.local()


class CancelToken:
    """Başka thread'den iptal edilebilir; bağlı bağlantıyı kapatır."""

    def __init__(self) -> None:
        self._evt = threading.Event()
        self._lock = threading.Lock()
        self._conn: Any = None

    def iptal(self) -> None:
        self._evt.set()
        with self._lock:
            conn = self._conn
        if conn is not None:
            try:
                conn.close()
            except Exception:  # noqa: BLE001 — iptalde best-effort
                pass

    def iptal_mi(self) -> bool:
        return self._evt.is_set()

    def bagla(self, conn: Any) -> None:
        """Aktif HTTP bağlantısını kaydet; zaten iptalse hemen kapat."""
        with self._lock:
            self._conn = conn
        if self._evt.is_set():
            try:
                conn.close()
            except Exception:  # noqa: BLE001
                pass

    def birak(self) -> None:
        with self._lock:
            self._conn = None


def aktif_iptal() -> CancelToken | None:
    return getattr(_tls, "token", None)


@contextmanager
def iptal_baglam(token: CancelToken | None) -> Iterator[CancelToken | None]:
    """Worker run() içinde thread-local iptal jetonunu bağlar."""
    onceki = getattr(_tls, "token", None)
    _tls.token = token
    try:
        yield token
    finally:
        _tls.token = onceki
