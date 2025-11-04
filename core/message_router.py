import os
import json
import logging
from decimal import Decimal, InvalidOperation

logger = logging.getLogger(__name__)


class MessageRouter:
    """
    Routes raw WS frames and extracts mids from a variety of possible shapes.
    Tolerant parser:
      - channel/type from: channel/topic/op/event
      - stats in: "market_stats", "data", "updates", or top-level list
      - id fields: market_id/marketId/id
      - price fields: mark_price/markPrice/mid OR avg(index,last) with variants
    Debug:
      - Set ROUTER_DEBUG=1 to dump the first 3 unknown frames (keys only or full if small).
    """

    def __init__(self, state_store, market_id_map=None):
        self.state = state_store
        self.market_id_map = market_id_map or {}
        self._debug_count = 0
        self._debug_limit = 3
        self._debug_enabled = os.getenv("ROUTER_DEBUG", "0") == "1"

    # ---------- helpers ----------
    def _to_dec(self, x):
        if x is None:
            return None
        try:
            return Decimal(str(x))
        except (InvalidOperation, ValueError, TypeError):
            return None

    def _norm_pair(self, market_id):
        # normalize to "market:<id>" string; allow strings already in that form
        if market_id is None:
            return None
        s = str(market_id)
        return s if s.startswith("market:") else f"market:{s}"

    def _derive_mid_from_entry(self, e):
        """
        Try multiple field combos on a single market entry.
        Returns (pair, mid) or (None, None).
        """
        if not isinstance(e, dict):
            return (None, None)

        mid = None
        # possible ids
        market_id = e.get("market_id") or e.get("marketId") or e.get("id")
        pair = self._norm_pair(market_id)

        # price candidates
        for k in ("mark_price", "markPrice", "mid"):
            mid = self._to_dec(e.get(k))
            if mid is not None:
                break

        if mid is None:
            # attempt average of index + last (with multiple key variants)
            index = (
                self._to_dec(e.get("index_price"))
                or self._to_dec(e.get("indexPrice"))
                or self._to_dec(e.get("index"))
            )
            last = (
                self._to_dec(e.get("last_price"))
                or self._to_dec(e.get("lastPrice"))
                or self._to_dec(e.get("last"))
            )
            if index is not None and last is not None:
                mid = (index + last) / Decimal("2")

        return (pair, mid)

    def _log_unknown(self, d):
        if not self._debug_enabled:
            return
        if self._debug_count >= self._debug_limit:
            return
        self._debug_count += 1
        try:
            if isinstance(d, dict):
                keys = list(d.keys())
                logger.info("[router][debug] unknown frame keys=%s", keys)
                # If small, show full (helps us converge quickly)
                s = json.dumps(d)
                if len(s) <= 2000:
                    logger.info("[router][debug] sample=%s", s)
            else:
                logger.info("[router][debug] non-dict frame type=%s", type(d).__name__)
        except Exception:
            pass

    # ---------- main entry ----------
    def route(self, raw_text: str):
        # Some gateways may batch JSON lines
        chunks = [x for x in raw_text.splitlines() if x.strip()] or [raw_text]

        for chunk in chunks:
            try:
                d = json.loads(chunk)
            except Exception:
                # silently ignore non-JSON messages
                continue

            channel = d.get("channel") or d.get("topic")
            typ = d.get("type") or d.get("event") or d.get("op")

            # log what we see
            logger.info("[router] got frame channel=%s type=%s", channel, typ)

            # 1) Direct "market_stats" key
            if (
                isinstance(d, dict)
                and "market_stats" in d
                and isinstance(d["market_stats"], list)
            ):
                any_mid = False
                for e in d["market_stats"]:
                    pair, mid = self._derive_mid_from_entry(e)
                    if pair and mid is not None:
                        self.state.update_mid(pair, mid)
                        any_mid = True
                        logger.info("[router] mid updated %s -> %s", pair, mid)
                if any_mid:
                    continue  # handled

            # 2) Common "data" wrapping
            data = d.get("data")
            if isinstance(data, list):
                any_mid = False
                for e in data:
                    pair, mid = self._derive_mid_from_entry(e)
                    if pair and mid is not None:
                        self.state.update_mid(pair, mid)
                        any_mid = True
                        logger.info("[router] mid updated %s -> %s", pair, mid)
                if any_mid:
                    continue

            if isinstance(data, dict):
                # e.g. data: { updates: [ ... ] }
                updates = data.get("updates") or data.get("markets") or data.get("rows")
                if isinstance(updates, list):
                    any_mid = False
                    for e in updates:
                        pair, mid = self._derive_mid_from_entry(e)
                        if pair and mid is not None:
                            self.state.update_mid(pair, mid)
                            any_mid = True
                            logger.info("[router] mid updated %s -> %s", pair, mid)
                    if any_mid:
                        continue

            # 3) Top-level list (rare but possible if gateway strips wrapper)
            if isinstance(d, list):
                any_mid = False
                for e in d:
                    pair, mid = self._derive_mid_from_entry(e)
                    if pair and mid is not None:
                        self.state.update_mid(pair, mid)
                        any_mid = True
                        logger.info("[router] mid updated %s -> %s", pair, mid)
                if any_mid:
                    continue

            # If we got here, we didn’t extract mids
            self._log_unknown(d)
            if isinstance(d, dict):
                logger.info(
                    "[router] no mids extracted; keys seen: top=%s", list(d.keys())[:5]
                )
