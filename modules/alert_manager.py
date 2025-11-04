# modules/alert_manager.py
import asyncio
import json
import logging
from typing import Any, Dict, Optional
from urllib import request, error

LOG = logging.getLogger("alert")


class AlertManager:
    """
    Lightweight Discord webhook alerting, no external deps.
    - Non-blocking: network calls run in a background thread via run_in_executor
    - Graceful when disabled or URL missing: logs instead of raising
    - NEW: Auto-disables on first 4xx (e.g., 403 Cloudflare 1010) to avoid log spam
    """

    def __init__(
        self,
        webhook_url: Optional[str],
        enabled: bool = True,
        app_name: str = "lighter-bot",
        loop: Optional[asyncio.AbstractEventLoop] = None,
    ):
        self.webhook_url = webhook_url
        self.enabled = enabled and bool(webhook_url)
        self.app_name = app_name
        self.loop = loop

        # internal flag set when remote rejects us (e.g., bad/placeholder URL)
        self._remote_disabled = False

    async def send(
        self,
        level: str,
        title: str,
        message: str = "",
        fields: Optional[Dict[str, Any]] = None,
        ping: bool = False,
    ) -> None:
        """
        Send an alert to Discord.
        level: one of {"info","warning","error","kill_switch"}
        """
        if not self.enabled or self._remote_disabled or not self.webhook_url:
            LOG.info(
                "[alert:dryrun] %s | %s | %s | %s", level, title, message, fields or {}
            )
            return

        payload = self._build_payload(level, title, message, fields, ping)
        await self._post_json(payload)

    def _build_payload(
        self,
        level: str,
        title: str,
        message: str,
        fields: Optional[Dict[str, Any]],
        ping: bool,
    ) -> Dict[str, Any]:
        color = {
            "info": 0x2B8A3E,  # green-ish
            "warning": 0xFFC107,  # amber
            "error": 0xDC3545,  # red
            "kill_switch": 0x6F42C1,  # purple
        }.get(
            level, 0x4B5563
        )  # default gray

        embed_fields = []
        if fields:
            for k, v in fields.items():
                embed_fields.append({"name": str(k), "value": f"`{v}`", "inline": True})

        content = "@here " + message if ping else message

        return {
            "content": content[:1990] if content else None,
            "embeds": [
                {
                    "title": f"[{self.app_name}] {title}"[:256],
                    "color": color,
                    "fields": embed_fields[:24],
                }
            ],
        }

    async def _post_json(self, payload: Dict[str, Any]) -> None:
        data = json.dumps(payload).encode("utf-8")

        def _do_post():
            req = request.Request(
                self.webhook_url,
                data=data,
                headers={"Content-Type": "application/json"},
            )
            try:
                with request.urlopen(req, timeout=10) as resp:
                    resp.read()
            except error.HTTPError as e:
                # Auto-disable on 4xx (bad/blocked webhook); log once
                if 400 <= e.code < 500:
                    LOG.warning(
                        "[alert] disabling remote alerts due to HTTP %s; switching to dry-run.",
                        e.code,
                    )
                    self._remote_disabled = True
                    return
                LOG.error("[alert] HTTPError %s %s", e.code, e.read())
            except Exception as e:
                # Network/transient errors: keep enabled but log
                LOG.error("[alert] Post failed: %s", e)

        # pick loop if not passed
        loop = self.loop or asyncio.get_event_loop()
        await loop.run_in_executor(None, _do_post)

    # Convenience shortcuts
    async def info(self, title: str, message: str = "", **kwargs):
        await self.send("info", title, message, **kwargs)

    async def warning(self, title: str, message: str = "", **kwargs):
        await self.send("warning", title, message, **kwargs)

    async def error(self, title: str, message: str = "", **kwargs):
        await self.send("error", title, message, **kwargs)

    async def kill_switch(self, title: str, message: str = "", **kwargs):
        await self.send("kill_switch", title, message, **kwargs)
