"""Local background worker with P0/P1/P2 priorities.

One worker thread processes ingestion jobs sequentially, so KOI never floods a data source.
P0 (selected company) always jumps ahead of P1 (main peers) and P2 (wider sector).
"""

from __future__ import annotations

import heapq
import itertools
import logging
import threading
import time
from typing import Any

from . import companies, db, ingest

log = logging.getLogger("koi.worker")

P0, P1, P2 = 0, 1, 2


class IngestionQueue:
    def __init__(self) -> None:
        self._heap: list[tuple[int, int, str]] = []
        self._counter = itertools.count()
        self._cv = threading.Condition()
        self._state: dict[str, dict[str, Any]] = {}   # symbol -> {status, priority, ...}
        self._thread: threading.Thread | None = None
        self._stop = False

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop = False
        self._thread = threading.Thread(target=self._run, name="koi-ingest", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        with self._cv:
            self._stop = True
            self._cv.notify_all()

    def submit(self, symbol: str, priority: int, force: bool = False) -> dict[str, Any]:
        with self._cv:
            st = self._state.get(symbol)
            if st and st["status"] == "running":
                return st
            if st and st["status"] == "queued":
                if priority < st["priority"]:   # upgrade priority; stale heap entries are skipped
                    st["priority"] = priority
                    heapq.heappush(self._heap, (priority, next(self._counter), symbol))
                    self._cv.notify()
                st["force"] = st.get("force", False) or force
                return st
            if not force and not ingest.needs_refresh(symbol):
                self._state[symbol] = {"symbol": symbol, "status": "fresh", "priority": priority}
                return self._state[symbol]
            st = {"symbol": symbol, "status": "queued", "priority": priority, "force": force,
                  "queued_at": db.now_iso()}
            self._state[symbol] = st
            heapq.heappush(self._heap, (priority, next(self._counter), symbol))
            self._cv.notify()
            return st

    def status(self, symbol: str) -> dict[str, Any] | None:
        with self._cv:
            st = self._state.get(symbol)
            return dict(st) if st else None

    def snapshot(self) -> dict[str, Any]:
        with self._cv:
            states = list(self._state.values())
        return {
            "queued": sorted([s["symbol"] for s in states if s["status"] == "queued"]),
            "running": [s["symbol"] for s in states if s["status"] == "running"],
            "alive": bool(self._thread and self._thread.is_alive()),
        }

    def _next(self) -> tuple[str, dict[str, Any]] | None:
        with self._cv:
            while not self._stop:
                while self._heap:
                    prio, _, symbol = heapq.heappop(self._heap)
                    st = self._state.get(symbol)
                    if st and st["status"] == "queued" and st["priority"] == prio:
                        st["status"] = "running"
                        st["started_at"] = db.now_iso()
                        return symbol, st
                self._cv.wait(timeout=5)
            return None

    def _run(self) -> None:
        while True:
            item = self._next()
            if item is None:
                return
            symbol, st = item
            try:
                result = ingest.ingest_company(symbol, force=st.get("force", False))
                status = "done" if result["status"] in ("ok", "partial", "fresh") else "error"
                with self._cv:
                    st.update(status=status, result=result, finished_at=db.now_iso())
                if st["priority"] == P0 and status == "done":
                    # Sector may only be known after the first ingest (non-curated companies).
                    peers = companies.peers_for(symbol)
                    for s in peers["p1"]:
                        self.submit(s, P1)
                    for s in peers["p2"]:
                        self.submit(s, P2)
            except Exception as e:  # never let the worker die
                log.exception("ingestion failed for %s", symbol)
                with self._cv:
                    st.update(status="error", result={"message": f"{type(e).__name__}: {e}"}, finished_at=db.now_iso())
                time.sleep(1)


queue = IngestionQueue()


def request_company(symbol: str, force: bool = False) -> dict[str, Any]:
    """Queue the selected company (P0) and prefetch its peers (P1, P2)."""
    p0 = queue.submit(symbol, P0, force=force)
    peers = companies.peers_for(symbol)
    for s in peers["p1"]:
        queue.submit(s, P1)
    for s in peers["p2"]:
        queue.submit(s, P2)
    return {"company": p0, "peers": peers}


def master_refresh_async() -> None:
    def run() -> None:
        try:
            if companies.master_is_stale():
                companies.refresh_master()
        except Exception:
            log.exception("company master refresh failed")
    threading.Thread(target=run, name="koi-master", daemon=True).start()
