"""The user docs and dashboard examples must match the code, keep kid views read-only, and leak nothing private."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml
from homeassistant.const import Platform
from homeassistant.helpers import entity_registry as er

from custom_components.tellybox.button import BUTTONS, PROFILE_BUTTONS

from .platform_helpers import entity_id, setup_platform

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
DASHBOARDS = DOCS / "dashboards"
ADMIN = DASHBOARDS / "admin.yaml"
KID_SAFE = DASHBOARDS / "kid-safe.yaml"
SERVICES = ROOT / "custom_components" / "tellybox" / "services.yaml"

REQUIRED_FILES = (
    "docs/dashboards/admin.yaml",
    "docs/dashboards/kid-safe.yaml",
    "docs/dashboards.md",
    "docs/automations.md",
    "docs/safety.md",
)

# Entity ids the integration owns: the Tellybox device and the two fixture kids (Mila, Noah).
OWN_ENTITY_RE = re.compile(r"\b(?:sensor|binary_sensor|button|media_player)\.(?:tellybox|mila|noah)[a-z0-9_]*")
# One sensor per browser playing in the kid app, created at runtime, so never in the fixture registry.
DYNAMIC_PREFIX = "sensor.tellybox_watching_on_"
SERVICE_RE = re.compile(r"\btellybox\.([a-z0-9_]+)")
FENCE_RE = re.compile(r"^```ya?ml[ \t]*\n(.*?)^```[ \t]*$", re.DOTALL | re.MULTILINE)

# Fenced yaml blocks that deliberately do not parse on their own, as (file name, 0-based block index).
# Empty on purpose: a block is only allowed here with a reason next to it.
PARTIAL_BLOCKS: set[tuple[str, int]] = set()


# -- helpers


def doc_files() -> list[Path]:
    """README.md plus every docs/*.md that exists."""
    return [ROOT / "README.md", *sorted(DOCS.glob("*.md"))]


def dashboard_files() -> list[Path]:
    return sorted(DASHBOARDS.glob("*.yaml"))


def fenced_blocks() -> list[tuple[str, int, str]]:
    """(file name, block index within the file, source) for every fenced yaml block."""
    out = []
    for path in doc_files():
        for i, m in enumerate(FENCE_RE.finditer(path.read_text())):
            out.append((path.relative_to(ROOT).as_posix(), i, m.group(1)))
    return out


def yaml_sources() -> list[tuple[str, str]]:
    """(label, text) for every dashboard file and every fenced yaml block."""
    sources = [(p.relative_to(ROOT).as_posix(), p.read_text()) for p in dashboard_files()]
    sources += [(f"{name} block {i}", text) for name, i, text in fenced_blocks()]
    return sources


def service_names() -> set[str]:
    return set(yaml.safe_load(SERVICES.read_text()))


# -- privacy scanner

RFC1918_RE = re.compile(
    r"(?<![\d.])(?:10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2})(?!\d|\.\d)"
)
LOCAL_HOST_RE = re.compile(r"\b[a-z0-9-]+\.(?:local|lan)\b", re.IGNORECASE)
TAILNET_RE = re.compile(r"\.ts\.net\b", re.IGNORECASE)
TOKEN_RE = re.compile(r"tbx_([A-Za-z0-9_-]{43})(?![A-Za-z0-9_-])")


def privacy_findings(text: str) -> list[str]:
    """What in `text` looks like an owner address, host name or token. A one-character token is the test placeholder."""
    found = [m.group(0) for m in RFC1918_RE.finditer(text)]
    found += [m.group(0) for m in LOCAL_HOST_RE.finditer(text)]
    found += [m.group(0) for m in TAILNET_RE.finditer(text)]
    found += [m.group(0) for m in TOKEN_RE.finditer(text) if len(set(m.group(1))) > 1]
    return found


def scanned_files() -> list[Path]:
    paths = [ROOT / "README.md"]
    for sub, suffixes in (
        ("docs", {".md", ".yaml", ".yml"}),
        ("custom_components", {".py", ".json", ".yaml", ".yml", ".md"}),
        ("tests", {".py", ".json", ".yaml", ".yml", ".md"}),
        ("blueprints", {".yaml", ".yml", ".md"}),
    ):
        paths += [p for p in sorted((ROOT / sub).rglob("*")) if p.is_file() and p.suffix in suffixes and "__pycache__" not in p.parts]
    return [p for p in paths if p.exists()]


def test_privacy_scanner_catches_and_spares() -> None:
    private = [
        "http://" + ".".join(["192", "168", "1", "20"]) + ":8080",
        "ip " + ".".join(["10", "0", "0", "5"]),
        "ip " + ".".join(["172", "20", "1", "1"]),
        "host " + "tellybox" + "." + "local",
        "host " + "nas" + "." + "lan",
        "host " + "box.tail1234" + "." + "ts" + ".net",
        "tbx_" + "Ab3" * 14 + "x",  # 43 characters, not a repeated one
    ]
    for text in private:
        assert privacy_findings(text), text
    harmless = [
        "min Home Assistant 2026.4.0 and 2026.10.1",
        "version 1.2.3.4x is fine as a file name: docs/entities.md, tests/test_button.py",
        "http://tellybox.test and tellybox.example",
        "tbx_" + "a" * 43,  # the test placeholder
        "tbx_" + "a" * 20,  # too short to be a token
        "172.32.0.1 and 11.0.0.1",  # outside the private ranges
    ]
    for text in harmless:
        assert not privacy_findings(text), text


@pytest.mark.parametrize("path", scanned_files(), ids=lambda p: p.relative_to(ROOT).as_posix())
def test_no_private_details(path: Path) -> None:
    assert not privacy_findings(path.read_text()), f"{path.relative_to(ROOT)} contains private-looking details"


# -- required files, one test each


@pytest.mark.parametrize("name", REQUIRED_FILES)
def test_required_file_exists(name: str) -> None:
    assert (ROOT / name).is_file(), f"{name} is missing"


# -- parsing


def test_every_dashboard_file_parses() -> None:
    for path in dashboard_files():
        data = yaml.safe_load(path.read_text())
        assert isinstance(data, dict) and "views" in data, f"{path.name} is not a dashboard (needs views)"


def test_every_fenced_yaml_block_parses() -> None:
    bad = []
    for name, i, text in fenced_blocks():
        if (name, i) in PARTIAL_BLOCKS:
            continue
        try:
            yaml.safe_load(text)
        except yaml.YAMLError as err:
            bad.append(f"{name} block {i}: {str(err).splitlines()[0]}")
    assert not bad, "fenced yaml blocks that do not parse:\n" + "\n".join(bad)


def test_partial_block_allow_list_is_not_stale() -> None:
    present = {(name, i) for name, i, _ in fenced_blocks()}
    assert PARTIAL_BLOCKS <= present, f"allow-listed blocks that do not exist: {PARTIAL_BLOCKS - present}"


# -- entities and services against the integration


async def test_documented_entities_exist(hass, config_entry, fake_client) -> None:
    await setup_platform(hass, config_entry, fake_client, control=True)
    registry_ids = {e.entity_id for e in er.async_entries_for_config_entry(er.async_get(hass), config_entry.entry_id)}
    assert "button.mila_add_15_minutes" in registry_ids and "media_player.tellybox" in registry_ids, (
        f"fixture registry looks wrong, naming scheme changed? {sorted(registry_ids)[:10]}"
    )
    missing = []
    for label, text in yaml_sources():
        for found in sorted(set(OWN_ENTITY_RE.findall(text))):
            if found.startswith(DYNAMIC_PREFIX) or found in registry_ids:
                continue
            missing.append(f"{label}: {found}")
    assert not missing, "ids that are not entities of the integration:\n" + "\n".join(missing)


def test_documented_actions_exist() -> None:
    known = service_names()
    unknown = []
    for label, text in yaml_sources():
        # Only yaml values count: strip comments so prose in comments is not read as an action.
        code = "\n".join(re.sub(r"\s#.*$", "", line) for line in text.splitlines())
        for found in sorted(set(SERVICE_RE.findall(code))):
            if found in known:
                continue
            # entity ids such as `sensor.tellybox_x` never match: the pattern needs `tellybox.` as a whole word
            unknown.append(f"{label}: tellybox.{found}")
    assert not unknown, f"actions missing from services.yaml ({sorted(known)}):\n" + "\n".join(unknown)


def test_service_pattern_ignores_entity_ids() -> None:
    assert SERVICE_RE.findall("action: tellybox.add_time") == ["add_time"]
    assert not SERVICE_RE.findall("entity_id: sensor.tellybox_time_left")


# -- dashboard structure


def _walk(node):
    yield node
    if isinstance(node, dict):
        for k, v in node.items():
            yield from _walk(k)
            yield from _walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk(v)


def test_kid_safe_dashboard_has_no_controls() -> None:
    assert KID_SAFE.is_file(), "docs/dashboards/kid-safe.yaml is missing"
    text = KID_SAFE.read_text()
    for forbidden in ("button.", "perform-action", "call-service", "tellybox.", "media_player.", "media-control"):
        # `tellybox.` must not be an action; sensor ids like `sensor.tellybox_x` have no dot after tellybox
        assert forbidden not in text, f"kid-safe.yaml contains {forbidden!r}"
    data = yaml.safe_load(text)
    for node in _walk(data):
        if isinstance(node, str):
            assert not node.startswith(("button.", "media_player.", "tellybox.")), node
            assert node not in ("perform-action", "call-service", "media-control"), node
        if isinstance(node, dict):
            assert node.get("type") != "media-control", "kid-safe.yaml has a media-control card"
            assert "tap_action" not in node or node["tap_action"].get("action") in (None, "none", "more-info", "navigate"), (
                f"kid-safe.yaml has an active tap_action: {node['tap_action']}"
            )


async def test_admin_dashboard_has_every_button(hass, config_entry, fake_client) -> None:
    assert ADMIN.is_file(), "docs/dashboards/admin.yaml is missing"
    await setup_platform(hass, config_entry, fake_client, Platform.BUTTON, control=True)
    text = ADMIN.read_text()
    expected = {entity_id(hass, "button", d.key) for d in BUTTONS}
    for profile_id in (1, 2):  # Mila and Noah
        expected |= {entity_id(hass, "button", d.key, profile_id) for d in PROFILE_BUTTONS}
    assert len(expected) == len(BUTTONS) + 2 * len(PROFILE_BUTTONS)
    missing = sorted(e for e in expected if not re.search(rf"\b{re.escape(e)}\b", text))
    assert not missing, f"admin.yaml lacks buttons: {missing}"


# -- README links

LINK_RE = re.compile(r"https://github\.com/sandermvanvliet/ha-tellybox/blob/main/([^\s)\"'>\]]+)")


def test_github_blob_links_point_at_files_in_the_repo() -> None:
    broken = []
    for path in doc_files():
        for rel in LINK_RE.findall(path.read_text()):
            target = rel.split("#", 1)[0]
            if not (ROOT / target).is_file():
                broken.append(f"{path.relative_to(ROOT)}: {target}")
    assert not broken, "links to files that do not exist:\n" + "\n".join(broken)
