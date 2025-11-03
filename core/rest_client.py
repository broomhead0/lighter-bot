# core/rest_client.py
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import aiohttp

from modules.funding_optimizer import PairMetrics, FundingDataSource

logger = logging.getLogger(__name__)


@dataclass
class RestConfig:
    base_url: str
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    timeout_s: int = 10


class RestClient(FundingDataSource):
    def __init__(self, cfg: RestConfig):
        self._cfg = cfg
        self._session: Optional[aiohttp.ClientSession] = None

    async def ensure_session(self) -> None:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self._cfg.timeout_s)
            self._session = aiohttp.ClientSession(timeout=timeout)

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        await self.ensure_session()
        url = self._cfg.base_url.rstrip("/") + "/" + path.lstrip("/")
        headers = {}
        if self._cfg.api_key:
            headers["X-API-KEY"] = self._cfg.api_key
        async with self._session.get(url, headers=headers, params=params) as resp:
            resp.raise_for_status()
            return await resp.json()

    # --- M6: metrics provider ---
    async def fetch_pair_metrics(self) -> List[PairMetrics]:
        """
        Return funding/OI/spread metrics for all candidate markets.
        If the real endpoints aren’t wired yet, return [] to disable optimization.
        """
        try:
            # TODO: replace with real endpoints when available and return a list of PairMetrics.
            return []
        except Exception as e:
            logger.warning("[rest] fetch_pair_metrics failed: %s", e)
            return []
