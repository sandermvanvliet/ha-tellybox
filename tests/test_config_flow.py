"""Config, reauth and options flows."""

from __future__ import annotations

import pytest
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType
from pytellybox import TellyboxAuthError, TellyboxConnectionError, TellyboxError

from custom_components.tellybox.const import (
    CONF_CONTROL,
    CONF_DISK_FREE_GB,
    CONF_TOKEN,
    CONF_TV_UNREACHABLE_MINUTES,
    CONF_URL,
    DEFAULT_DISK_FREE_GB,
    DEFAULT_TV_UNREACHABLE_MINUTES,
    DOMAIN,
)

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


async def _options_form(hass, entry):
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    return result


def _defaults(result):
    return {str(k): k.default() for k in result["data_schema"].schema}


async def test_options_flow_defaults_and_save(hass, core, config_entry):
    result = await _options_form(hass, config_entry)
    # legacy entry with only {control: True}: the new options show their defaults
    assert _defaults(result) == {
        CONF_CONTROL: True,
        CONF_TV_UNREACHABLE_MINUTES: DEFAULT_TV_UNREACHABLE_MINUTES,
        CONF_DISK_FREE_GB: DEFAULT_DISK_FREE_GB,
    }
    assert (DEFAULT_TV_UNREACHABLE_MINUTES, DEFAULT_DISK_FREE_GB) == (60, 5)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_CONTROL: False, CONF_TV_UNREACHABLE_MINUTES: 15, CONF_DISK_FREE_GB: 20}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {CONF_CONTROL: False, CONF_TV_UNREACHABLE_MINUTES: 15, CONF_DISK_FREE_GB: 20}


async def test_options_flow_shows_saved_values(hass, core, config_entry):
    hass.config_entries.async_update_entry(
        config_entry, options={CONF_CONTROL: True, CONF_TV_UNREACHABLE_MINUTES: 5, CONF_DISK_FREE_GB: 0}
    )
    result = await _options_form(hass, config_entry)
    assert _defaults(result) == {CONF_CONTROL: True, CONF_TV_UNREACHABLE_MINUTES: 5, CONF_DISK_FREE_GB: 0}


async def test_options_flow_accepts_boundaries(hass, core, config_entry):
    result = await _options_form(hass, config_entry)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_CONTROL: True, CONF_TV_UNREACHABLE_MINUTES: 0, CONF_DISK_FREE_GB: 10000}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options[CONF_TV_UNREACHABLE_MINUTES] == 0
    assert config_entry.options[CONF_DISK_FREE_GB] == 10000


@pytest.mark.parametrize(
    "bad",
    [{CONF_TV_UNREACHABLE_MINUTES: -1}, {CONF_TV_UNREACHABLE_MINUTES: 1441},
     {CONF_DISK_FREE_GB: -1}, {CONF_DISK_FREE_GB: 10001}],
)
async def test_options_flow_rejects_out_of_range(hass, core, config_entry, bad):
    result = await _options_form(hass, config_entry)
    values = {CONF_CONTROL: True, CONF_TV_UNREACHABLE_MINUTES: 60, CONF_DISK_FREE_GB: 5} | bad
    with pytest.raises(vol.Invalid):
        await hass.config_entries.options.async_configure(result["flow_id"], values)
    assert config_entry.options == {CONF_CONTROL: True}
