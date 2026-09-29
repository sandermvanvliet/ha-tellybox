"""The contract imports and the fake client behaves (controller's smoke test of the scaffolding)."""

from pytellybox import AdminState

from custom_components.tellybox.const import DOMAIN, profile_device_identifier


async def test_fake_client_overrides_change_state(fake_client):
    state = await fake_client.add_time(15, [2])
    assert isinstance(state, AdminState)
    assert state.profile(2).remaining_s == 900 and state.profile(2).can_start
    assert profile_device_identifier("x", 2) == (DOMAIN, "x_profile_2")
