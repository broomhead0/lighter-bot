from __future__ import annotations
import os
import yaml
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass
class CaptureConfig:
    write_raw: bool = True
    raw_path: str = "logs/ws_raw.jsonl"

@dataclass
class MetricsConfig:
    report_interval_sec: int = 30

@dataclass
class WSConfig:
    url: str
    ping_interval_sec: int = 15
    connect_timeout_sec: int = 10
    max_reconnect_backoff_sec: int = 60
    subscriptions: list = None

@dataclass
class AppConfig:
    name: str = "lighter-bot"
    log_level: str = "INFO"

@dataclass
class Config:
    app: AppConfig
    ws: WSConfig
    capture: CaptureConfig
    metrics: MetricsConfig

def load_config(path: str = "config.yaml") -> Config:
    with open(path, "r") as f:
        raw = yaml.safe_load(f)

    app = raw.get("app", {})
    ws = raw.get("ws", {})
    capture = raw.get("capture", {})
    metrics = raw.get("metrics", {})

    url = ws.get("url", "")
    if isinstance(url, str) and url.startswith("${") and url.endswith("}"):
        env_key = url[2:-1]
        url = os.environ.get(env_key, "")

    return Config(
        app=AppConfig(
            name=app.get("name", "lighter-bot"),
            log_level=app.get("log_level", "INFO"),
        ),
        ws=WSConfig(
            url=url,
            ping_interval_sec=int(ws.get("ping_interval_sec", 15)),
            connect_timeout_sec=int(ws.get("connect_timeout_sec", 10)),
            max_reconnect_backoff_sec=int(ws.get("max_reconnect_backoff_sec", 60)),
            subscriptions=ws.get("subscriptions", []) or [],
        ),
        capture=CaptureConfig(
            write_raw=bool(capture.get("write_raw", True)),
            raw_path=capture.get("raw_path", "logs/ws_raw.jsonl"),
        ),
        metrics=MetricsConfig(
            report_interval_sec=int(metrics.get("report_interval_sec", 30)),
        ),
    )
