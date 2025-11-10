from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, asdict
from decimal import Decimal
from pathlib import Path
from typing import Dict, Iterable, Iterator, Optional


_LOCKS: Dict[Path, threading.RLock] = {}


def _get_lock(path: Path) -> threading.RLock:
    lock = _LOCKS.get(path)
    if lock is None:
        lock = threading.RLock()
        _LOCKS[path] = lock
    return lock


@dataclass(frozen=True)
class FillEvent:
    """
    Persistent representation of a single fill from the exchange.

    - All monetary quantities are stored as strings to preserve precision.
    - `source` is free-form to distinguish e.g. "account_listener" vs "hedger".
    """

    timestamp: float
    market: str
    role: str
    side: str
    size: str
    price: str
    notional: str
    base_delta: str
    quote_delta: str
    fee_paid: str
    fee_currency: Optional[str] = None
    mid_price: Optional[str] = None
    trade_id: Optional[int] = None
    source: str = "account_listener"

    def as_decimals(self) -> Dict[str, Decimal]:
        return {
            "size": Decimal(self.size),
            "price": Decimal(self.price),
            "notional": Decimal(self.notional),
            "base_delta": Decimal(self.base_delta),
            "quote_delta": Decimal(self.quote_delta),
            "fee_paid": Decimal(self.fee_paid),
            "mid_price": Decimal(self.mid_price) if self.mid_price is not None else None,
        }


class MetricsLedger:
    """
    Append-only JSON Lines ledger for fills.

    Each line contains the JSON encoding of :class:`FillEvent`.
    """

    def __init__(
        self,
        path: Path,
        *,
        archive_dir: Optional[Path] = None,
        max_bytes: Optional[int] = None,
    ):
        self.path = path
        self.archive_dir = archive_dir
        self.max_bytes = max_bytes
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.archive_dir:
            self.archive_dir.mkdir(parents=True, exist_ok=True)

    def append(self, event: FillEvent) -> None:
        payload = json.dumps(asdict(event), separators=(",", ":"))
        lock = _get_lock(self.path)
        with lock:
            self._rotate_if_needed(len(payload))
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(payload + "\n")

    def iter_events(self, *, since_ts: Optional[float] = None) -> Iterator[FillEvent]:
        if not self.path.exists():
            return iter(())
        lock = _get_lock(self.path)
        with lock, self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ts = float(data.get("timestamp", 0))
                if since_ts is not None and ts < since_ts:
                    continue
                yield FillEvent(
                    timestamp=ts,
                    market=str(data.get("market", "")),
                    role=str(data.get("role", "")),
                    side=str(data.get("side", "")),
                    size=str(data.get("size", "0")),
                    price=str(data.get("price", "0")),
                    notional=str(data.get("notional", "0")),
                    base_delta=str(data.get("base_delta", "0")),
                    quote_delta=str(data.get("quote_delta", "0")),
                    fee_paid=str(data.get("fee_paid", "0")),
                    mid_price=str(data["mid_price"]) if data.get("mid_price") is not None else None,
                    trade_id=int(data["trade_id"]) if data.get("trade_id") is not None else None,
                    source=str(data.get("source", "account_listener")),
                )

    def read_all(self) -> Iterable[FillEvent]:
        return self.iter_events()

    def reset(self) -> Optional[Path]:
        """
        Archive the current ledger (if archive_dir provided) and start fresh.
        """
        lock = _get_lock(self.path)
        with lock:
            if not self.path.exists():
                return None
            archive_path = None
            if self.archive_dir:
                timestamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
                archive_path = self.archive_dir / f"fills-{timestamp}.jsonl"
                self.path.replace(archive_path)
            else:
                self.path.unlink()
            return archive_path

    def _rotate_if_needed(self, incoming_bytes: int) -> None:
        if self.max_bytes is None or not self.path.exists():
            return
        try:
            current_size = self.path.stat().st_size
        except OSError:
            return
        if current_size + incoming_bytes <= self.max_bytes:
            return
        if not self.archive_dir:
            # Best effort truncate to keep file bounded.
            self.path.unlink(missing_ok=True)
            return
        timestamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
        archive_path = self.archive_dir / f"fills-{timestamp}.jsonl"
        self.path.replace(archive_path)

