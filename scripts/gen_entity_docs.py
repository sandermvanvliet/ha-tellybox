"""Generate docs/entities.md from the entity descriptions and strings.json.

Regenerate with: .venv/bin/python scripts/gen_entity_docs.py
"""

from __future__ import annotations

import json
import sys
from enum import Enum
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from homeassistant.util import slugify  # noqa: E402

from custom_components.tellybox.binary_sensor import BINARY_SENSORS, PROFILE_BINARY_SENSORS  # noqa: E402
from custom_components.tellybox.button import BUTTONS, PROFILE_BUTTONS  # noqa: E402
from custom_components.tellybox.image import PICTURE  # noqa: E402
from custom_components.tellybox.media_player import PLAYER  # noqa: E402
from custom_components.tellybox.sensor import PROFILE_SENSORS, SENSORS  # noqa: E402

STRINGS = ROOT / "custom_components" / "tellybox" / "strings.json"
OUTPUT = ROOT / "docs" / "entities.md"
COMMAND = ".venv/bin/python scripts/gen_entity_docs.py"

HEADER = ["Entity id", "Name", "Category", "Device class", "Unit", "Notes"]


def english_names() -> dict[str, dict[str, Any]]:
    return json.loads(STRINGS.read_text(encoding="utf-8"))["entity"]


def _value(v: Any) -> str:
    if v is None:
        return ""
    return str(v.value if isinstance(v, Enum) else v)


def _row(platform: str, description: Any, prefix: str, names: dict[str, Any]) -> tuple[str, str, list[str]]:
    key = description.key
    if platform == "media_player":
        name, entity_id = "(device name)", f"media_player.{prefix}"
    else:
        name = names[platform][key]["name"]
        entity_id = f"{platform}.{prefix}_{slugify(name)}"
    notes = []
    if description.entity_registry_enabled_default is False:
        notes.append("disabled by default")
    if getattr(description, "entity_registry_visible_default", True) is False:
        notes.append("parent controls only; hidden by default")
    if platform == "sensor" and description.options:
        notes.append("values: " + ", ".join(description.options))
    cells = [
        f"`{entity_id}`",
        name,
        _value(description.entity_category),
        _value(description.device_class),
        _value(getattr(description, "native_unit_of_measurement", None)),
        "; ".join(notes),
    ]
    return platform, key, cells


def _table(groups: list[tuple[str, tuple[Any, ...]]], prefix: str, names: dict[str, Any]) -> list[str]:
    rows = sorted((_row(p, d, prefix, names) for p, ds in groups for d in ds), key=lambda r: (r[0], r[1]))
    lines = ["| " + " | ".join(HEADER) + " |", "|" + "|".join("---" for _ in HEADER) + "|"]
    lines += ["| " + " | ".join(c.replace("|", "\\|") for c in cells) + " |" for _, _, cells in rows]
    return lines


def render() -> str:
    names = english_names()
    out = [
        "# Entity reference",
        "",
        "This file is generated from the entity descriptions: do not edit it. "
        f"Regenerate it with `{COMMAND}`.",
        "",
        "Entity ids follow the device name, so a renamed device or kid changes the prefix. "
        "Below, `<kid>` stands for the slug of a kid's profile name (for example `mila`).",
        "",
        "## Tellybox device",
        "",
    ]
    out += _table(
        [("sensor", SENSORS), ("binary_sensor", BINARY_SENSORS), ("button", BUTTONS), ("media_player", (PLAYER,))],
        "tellybox",
        names,
    )
    out += ["", "## Each kid (`<kid>`)", ""]
    out += _table(
        [("sensor", PROFILE_SENSORS), ("binary_sensor", PROFILE_BINARY_SENSORS), ("button", PROFILE_BUTTONS), ("image", (PICTURE,)), ("media_player", (PLAYER,))],
        "<kid>",
        names,
    )
    return "\n".join(out) + "\n"


def main() -> None:
    OUTPUT.write_text(render(), encoding="utf-8", newline="\n")
    print(f"Wrote {OUTPUT.relative_to(ROOT)}. Commit it together with the entity change.")


if __name__ == "__main__":
    main()
