"""Config, reauth and options flows."""

from __future__ import annotations

import pytest
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType
from pytellybox import TellyboxAuthError, TellyboxConnectionError, TellyboxError

from custom_components.tellybox.const import CONF_CONTROL, CONF_TOKEN, CONF_URL, DOMAIN

from .conftest import INSTANCE_ID, TOKEN, URL
from .helpers import core, no_platforms  # noqa: F401


async def _start(hass, user_input):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    return await hass.config_entries.flow.async_configure(result["flow_id"], user_input)


async def test_user_success(hass, patch_client, no_platforms):
    result = await _start(hass, {CONF_URL: "  http://tellybox.test/  ", CONF_TOKEN: TOKEN})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Tellybox"
    assert result["data"] == {CONF_URL: URL, CONF_TOKEN: TOKEN}
    assert result["options"] == {CONF_CONTROL: True}
    assert result["result"].unique_id == INSTANCE_ID


@pytest.mark.parametrize("value", ["tellybox.test", "ftp://x", "http://"])
async def test_user_invalid_url(hass, patch_client, value):
    result = await _start(hass, {CONF_URL: value, CONF_TOKEN: TOKEN})
    assert result["errors"] == {CONF_URL: "invalid_url"}


@pytest.mark.parametrize(
    ("exc", "error"),
    [(TellyboxConnectionError("x"), "cannot_connect"), (TellyboxError("404"), "not_tellybox"),
     (ValueError("bad json"), "not_tellybox")],
)
async def test_user_info_errors(hass, patch_client, exc, error):
    patch_client.fail_with = exc
    result = await _start(hass, {CONF_URL: URL, CONF_TOKEN: TOKEN})
    assert result["errors"] == {"base": error}


async def test_user_invalid_auth_then_success(hass, patch_client, no_platforms):
    async def bad_state():
        raise TellyboxAuthError("x")

    good_state = patch_client.state
    patch_client.state = bad_state
    result = await _start(hass, {CONF_URL: URL, CONF_TOKEN: TOKEN})
    assert result["errors"] == {"base": "invalid_auth"}
    patch_client.state = good_state
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_URL: URL, CONF_TOKEN: TOKEN})
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_already_configured(hass, patch_client, config_entry, no_platforms):
    config_entry.add_to_hass(hass)
    result = await _start(hass, {CONF_URL: URL, CONF_TOKEN: TOKEN})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_success(hass, core, config_entry):
    new = "tbx_" + "b" * 43
    result = await config_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_TOKEN: new})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert config_entry.data[CONF_TOKEN] == new
    assert config_entry.data[CONF_URL] == URL


async def test_reauth_wrong_instance(hass, core, config_entry, fake_client):
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reauth_flow(hass)
    from pytellybox import Info

    async def other_info():
        return Info("other", "1", 1, ())

    fake_client.info = other_info
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_TOKEN: "tbx_new"})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_instance"
    assert config_entry.data[CONF_TOKEN] == TOKEN


async def test_reauth_invalid_token(hass, core, config_entry, fake_client):
    result = await config_entry.start_reauth_flow(hass)
    async def bad_state():
        raise TellyboxAuthError("x")

    fake_client.state = bad_state
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_TOKEN: "tbx_new"})
    assert result["errors"] == {"base": "invalid_auth"}


async def test_options_flow(hass, core, config_entry):
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(result["flow_id"], {CONF_CONTROL: False})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {CONF_CONTROL: False}
