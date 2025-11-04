from __future__ import annotations
from typing import TypedDict, Literal, Any

MsgType = Literal[
    "connected",
    "update/height",
    "update/market_stats",
    "error",
]


class WSFrame(TypedDict, total=False):
    type: MsgType
    channel: str
    session_id: str
    error: dict
    height: int
    data: Any
