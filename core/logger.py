import logging
import os

LOG_PATH = os.path.join("logs", "bot.log")
os.makedirs("logs", exist_ok=True)

_formatter = logging.Formatter(
    fmt="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

_handler = logging.FileHandler(LOG_PATH)
_handler.setFormatter(_formatter)

_console = logging.StreamHandler()
_console.setFormatter(_formatter)

logger = logging.getLogger("lighter")
logger.setLevel(logging.INFO)
logger.addHandler(_handler)
logger.addHandler(_console)
