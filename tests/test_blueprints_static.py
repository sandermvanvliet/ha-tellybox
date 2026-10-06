"""Static checks over every blueprint in blueprints/automation/tellybox/."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from homeassistant.components.automation.config import AUTOMATION_BLUEPRINT_SCHEMA
from homeassistant.components.blueprint.models import Blueprint
from homeassistant.util import yaml as yaml_util

ROOT = Path(__file__).parent.parent
FILES = sorted((ROOT / "blueprints" / "automation" / "tellybox").glob("*.yaml"))
HA_MIN = json.loads((ROOT / "hacs.json").read_text())["homeassistant"]
SOURCE = "https://github.com/sandermvanvliet/ha-tellybox/blob/main/blueprints/automation/tellybox/"
FORBIDDEN = (re.compile(r"tbx_"), re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b"), re.compile(r"://"))


def test_blueprints_exist():
    assert FILES, "no blueprints found"


@pytest.fixture(params=FILES, ids=lambda p: p.name)
def blueprint(request) -> tuple[Path, dict, Blueprint]:
    raw = yaml_util.load_yaml_dict(request.param)  # handles the !input tag
    bp = Blueprint(raw, expected_domain="automation", path=request.param.name, schema=AUTOMATION_BLUEPRINT_SCHEMA)
    return request.param, raw, bp


def test_metadata(blueprint):
    path, _raw, bp = blueprint
    meta = bp.data["blueprint"]
    assert meta["domain"] == "automation"
    assert meta["homeassistant"]["min_version"] == HA_MIN
    assert meta["source_url"] == SOURCE + path.name
    assert meta["name"] and meta["description"]


def test_inputs_documented(blueprint):
    _path, _raw, bp = blueprint
    assert bp.inputs
    for key, spec in bp.inputs.items():
        assert spec, key
        assert spec.get("name"), f"{key}: name"
        assert spec.get("description"), f"{key}: description"
        assert spec.get("selector"), f"{key}: selector"


def test_no_hosts_ips_or_tokens_in_defaults(blueprint):
    _path, _raw, bp = blueprint
    for key, spec in bp.inputs.items():
        text = json.dumps(spec.get("default", ""))
        for pattern in FORBIDDEN:
            assert not pattern.search(text), f"{key}: default matches {pattern.pattern}"
