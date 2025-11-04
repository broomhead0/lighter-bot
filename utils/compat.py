# utils/compat.py
import logging
from types import SimpleNamespace
from typing import Any, Dict

LOG = logging.getLogger("compat")


class ConfigCompat(SimpleNamespace):
    """
    Attribute-access config with:
      - sensible defaults for unknown fields
      - one-way alias mapping (e.g., w_funding -> apr_weight)
      - 'warn once' behavior on unknown attrs to avoid log spam
    """

    _warned: Dict[str, bool] = {}

    def __init__(
        self, base: Dict[str, Any], defaults: Dict[str, Any], aliases: Dict[str, str]
    ):
        # load base into namespace first
        super().__init__(**base)
        self.__dict__["_defaults"] = defaults
        self.__dict__["_aliases"] = aliases

    def __getattr__(self, name: str) -> Any:
        # exact
        if name in self.__dict__:
            return self.__dict__[name]
        # alias
        aliases = self.__dict__.get("_aliases", {})
        if name in aliases:
            target = aliases[name]
            return getattr(self, target)  # recurse once
        # default
        defaults = self.__dict__.get("_defaults", {})
        if name in defaults:
            return defaults[name]
        # warn once, then return a safe neutral default (0 / 0.0 / False / None heuristic)
        if not self._warned.get(name):
            LOG.warning(
                "[compat] optimizer config missing '%s' — using neutral default.", name
            )
            self._warned[name] = True
        # neutral default heuristic
        # strings -> "", bool -> False, numbers -> 0.0
        return 0.0
