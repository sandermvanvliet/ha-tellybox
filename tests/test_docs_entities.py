"""docs/entities.md is generated from the entity descriptions and must not drift."""

from __future__ import annotations

import pytest

from custom_components.tellybox.binary_sensor import BINARY_SENSORS, PROFILE_BINARY_SENSORS
from custom_components.tellybox.button import BUTTONS, PROFILE_BUTTONS
from custom_components.tellybox.sensor import PROFILE_SENSORS, SENSORS
from scripts import gen_entity_docs as gen

PLATFORM_TUPLES = [
    ("sensor", SENSORS),
    ("sensor", PROFILE_SENSORS),
    ("binary_sensor", BINARY_SENSORS),
    ("binary_sensor", PROFILE_BINARY_SENSORS),
    ("button", BUTTONS),
    ("button", PROFILE_BUTTONS),
]
CASES = [(platform, d.key) for platform, ds in PLATFORM_TUPLES for d in ds]


def test_render_is_stable() -> None:
    text = gen.render()
    assert text == gen.render()
    assert text.endswith("\n") and not text.endswith("\n\n")
    assert "\r" not in text


def test_entities_doc_is_current() -> None:
    current = gen.OUTPUT.read_text(encoding="utf-8")
    assert current == gen.render(), f"docs/entities.md is stale: regenerate with `{gen.COMMAND}`"


@pytest.mark.parametrize(("platform", "key"), CASES)
def test_every_description_key_has_an_english_name(platform: str, key: str) -> None:
    name = gen.english_names().get(platform, {}).get(key, {}).get("name")
    assert name, f"strings.json lacks entity.{platform}.{key}.name"


def test_every_description_key_is_in_the_doc() -> None:
    names = gen.english_names()
    doc = gen.OUTPUT.read_text(encoding="utf-8")
    for platform, key in CASES:
        assert f"| {names[platform][key]['name']} |" in doc, f"{platform}.{key} missing from docs/entities.md"
    assert "`media_player.tellybox`" in doc
