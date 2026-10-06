"""inbox_ping.yaml through the Home Assistant harness (real mobile_app notify device action)."""

from __future__ import annotations

from .blueprint_helpers import add_phone, automation_from_blueprint, notified, settle  # noqa: F401

FILE = "inbox_ping.yaml"
LATEST = "sensor.inbox_latest_received"
PENDING = "sensor.inbox_pending"


async def setup(hass, *, pending="3", latest="2026-10-06T10:00:00+00:00", **extra):
    phone = await add_phone(hass)
    hass.states.async_set(LATEST, latest)
    hass.states.async_set(PENDING, pending)
    await automation_from_blueprint(
        hass,
        FILE,
        {"latest_received_sensor": LATEST, "pending_sensor": PENDING, "notify_device": phone, **extra},
    )
    return phone


async def test_new_upload_notifies_once_with_pending_count(hass, notified):
    phone = await setup(hass, pending="3")
    hass.states.async_set(LATEST, "2026-10-06T11:00:00+00:00")
    await settle()

    assert len(notified) == 1
    assert notified[0]["device_id"] == phone
    assert "3" in notified[0]["message"]
    assert notified[0]["message"] == "3 new Tellybox upload(s) waiting for approval."


async def test_unavailable_then_value_does_not_notify(hass, notified):
    await setup(hass)
    hass.states.async_set(LATEST, "unavailable")
    await settle()
    hass.states.async_set(LATEST, "2026-10-06T11:00:00+00:00")
    await settle()
    assert notified == []


async def test_unknown_then_value_does_not_notify(hass, notified):
    await setup(hass)
    hass.states.async_set(LATEST, "unknown")
    await settle()
    hass.states.async_set(LATEST, "2026-10-06T11:00:00+00:00")
    await settle()
    assert notified == []


async def test_pending_zero_does_not_notify(hass, notified):
    await setup(hass, pending="0")
    hass.states.async_set(LATEST, "2026-10-06T11:00:00+00:00")
    await settle()
    assert notified == []


async def test_pending_non_numeric_does_not_notify(hass, notified):
    await setup(hass, pending="unavailable")
    hass.states.async_set(LATEST, "2026-10-06T11:00:00+00:00")
    await settle()
    assert notified == []


async def test_empty_inbox_url_sends_no_click_action(hass, notified):
    await setup(hass)
    hass.states.async_set(LATEST, "2026-10-06T11:00:00+00:00")
    await settle()
    assert len(notified) == 1
    assert "clickAction" not in (notified[0].get("data") or {})


async def test_inbox_url_becomes_click_action(hass, notified):
    await setup(hass, inbox_url="https://example.invalid/inbox")
    hass.states.async_set(LATEST, "2026-10-06T11:00:00+00:00")
    await settle()
    assert len(notified) == 1
    assert notified[0]["data"]["clickAction"] == "https://example.invalid/inbox"


async def test_custom_message_renders_pending(hass, notified):
    await setup(hass, pending="5", message="Inbox: {{ pending }} waiting")
    hass.states.async_set(LATEST, "2026-10-06T11:00:00+00:00")
    await settle()
    assert [n["message"] for n in notified] == ["Inbox: 5 waiting"]
