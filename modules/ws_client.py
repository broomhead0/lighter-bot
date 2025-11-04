# modules/ws_client.py
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Optional

import aiohttp

logger = logging.getLogger(__name__)


@dataclass
class WSConfig:
    url: str
    ping_interval_sec: int = 15
    connect_timeout_sec: int = 10
    max_reconnect_backoff_sec: int = 60
    subscriptions: List[str] = None


class WSClient:
    """
    Minimal WS client:
      - connects to url
      - subscribes to configured channels
      - routes messages to a callback
      - auto-reconnects with backoff
    """

    def __init__(
        self, cfg: WSConfig, on_message: Callable[[Dict[str, Any]], Awaitable[None]]
    ):
        self._cfg = cfg
        self._on_message = on_message
        self._session: Optional[aiohttp.ClientSession] = None
        self._ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self._running = False

    async def start(self) -> None:
        self._running = True
        asyncio.create_task(self._run_loop(), name="WSClientLoop")
        logger.info("[ws] started.")

    async def stop(self) -> None:
        self._running = False
        try:
            if self._ws and not self._ws.closed:
                await self._ws.close()
        finally:
            if self._session and not self._session.closed:
                await self._session.close()
        logger.info("[ws] stopped.")

    async def _run_loop(self) -> None:
        backoff = 1.0
        while self._running:
            try:
                await self._connect_once()
                backoff = 1.0
                await self._read_loop()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("[ws] loop error: %s", e)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2.0, float(self._cfg.max_reconnect_backoff_sec))

    async def _connect_once(self) -> None:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self._cfg.connect_timeout_sec)
            self._session = aiohttp.ClientSession(timeout=timeout)

        logger.info("[ws] connecting to %s ...", self._cfg.url)
        self._ws = await self._session.ws_connect(
            self._cfg.url, heartbeat=self._cfg.ping_interval_sec
        )
        logger.info("[ws] connected.")

        subs = list(self._cfg.subscriptions or [])
        if subs:
            msg = {"op": "subscribe", "channels": subs}
            await self._ws.send_str(json.dumps(msg))
            logger.info("[ws] subscribed: %s", subs)

    async def _read_loop(self) -> None:
        assert self._ws is not None
        async for msg in self._ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                except Exception:
                    logger.debug("[ws] non-json text: %s", msg.data[:200])
                    continue
                await self._safe_on_message(data)
            elif msg.type == aiohttp.WSMsgType.BINARY:
                continue
            elif msg.type == aiohttp.WSMsgType.ERROR:
                err = self._ws.exception()
                logger.warning("[ws] error frame: %s", err)
                break
            elif msg.type in (
                aiohttp.WSMsgType.CLOSE,
                aiohttp.WSMsgType.CLOSING,
                aiohttp.WSMsgType.CLOSED,
            ):
                logger.info("[ws] server closed connection.")
                break

    async def _safe_on_message(self, data: Dict[str, Any]) -> None:
        try:
            await self._on_message(data)
        except Exception as e:
            logger.debug("[ws] on_message error: %s", e)
