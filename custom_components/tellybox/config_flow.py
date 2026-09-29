"""Config flow: URL and token, reauth when the token is revoked, options (parent controls on/off)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from pytellybox import (
    TellyboxAuthError,
    TellyboxClient,
    TellyboxConnectionError,
    TellyboxError,
)
from yarl import URL

from .const import CONF_CONTROL, CONF_TOKEN, CONF_URL, DOMAIN
from .coordinator import TellyboxConfigEntry


def normalize_url(value: str) -> str | None:
    """`http(s)://host[:port][/path]` without a trailing slash, or None when there is no usable scheme/host."""
    try:
        url = URL(value.strip())
    except ValueError:
        return None
    if url.scheme not in ("http", "https") or not url.host:
        return None
    return str(url).rstrip("/")


class TellyboxConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: TellyboxConfigEntry) -> TellyboxOptionsFlow:
        return TellyboxOptionsFlow()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        user_input = user_input or {}
        if CONF_URL in user_input:
            url = normalize_url(user_input[CONF_URL])
            token = user_input[CONF_TOKEN].strip()
            if url is None:
                errors[CONF_URL] = "invalid_url"
            else:
                client = TellyboxClient(url, token, async_get_clientsession(self.hass))
                instance_id, error = await self._check(client)
                if error:
                    errors["base"] = error
                else:
                    await self.async_set_unique_id(instance_id)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title="Tellybox", data={CONF_URL: url, CONF_TOKEN: token}, options={CONF_CONTROL: True}
                    )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_URL, default=user_input.get(CONF_URL, vol.UNDEFINED)): str,
                vol.Required(CONF_TOKEN): str,
            }),
            errors=errors,
        )

    async def _check(self, client: TellyboxClient) -> tuple[str, str | None]:
        """Returns (instance id, error key)."""
        try:
            info = await client.info()
        except TellyboxConnectionError:
            return "", "cannot_connect"
        except (TellyboxError, ValueError, KeyError, TypeError):
            return "", "not_tellybox"
        try:
            await client.state()
        except TellyboxAuthError:
            return "", "invalid_auth"
        except TellyboxConnectionError:
            return "", "cannot_connect"
        except TellyboxError:
            return "", "unknown"
        return info.instance_id, None

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            token = user_input[CONF_TOKEN].strip()
            client = TellyboxClient(entry.data[CONF_URL], token, async_get_clientsession(self.hass))
            instance_id, error = await self._check(client)
            if error:
                errors["base"] = error
            elif instance_id != entry.unique_id:
                return self.async_abort(reason="wrong_instance")
            else:
                return self.async_update_reload_and_abort(entry, data_updates={CONF_TOKEN: token})
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_TOKEN): str}),
            description_placeholders={"name": entry.title},
            errors=errors,
        )


class TellyboxOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        current = self.config_entry.options.get(CONF_CONTROL, True)
        return self.async_show_form(
            step_id="init", data_schema=vol.Schema({vol.Required(CONF_CONTROL, default=current): bool})
        )
