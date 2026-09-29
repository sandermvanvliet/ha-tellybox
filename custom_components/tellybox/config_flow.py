"""Config flow: URL and token, reauth when the token is revoked, options (parent controls on/off).

Contract only: subagent B implements it (see docs/plan.md).
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigFlow
from pytellybox import TellyboxClient  # noqa: F401  (tests patch it here)

from .const import DOMAIN


class TellyboxConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1
