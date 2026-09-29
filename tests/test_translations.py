"""Every language has exactly the keys and placeholders of strings.json; en.json equals strings.json."""

import json
import re
from pathlib import Path

import pytest

BASE = Path(__file__).parent.parent / "custom_components" / "tellybox"


def flatten(o, p=""):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from flatten(v, f"{p}.{k}" if p else k)
    else:
        yield p, o


def test_en_matches_strings():
    assert json.loads((BASE / "strings.json").read_text()) == json.loads((BASE / "translations/en.json").read_text())


@pytest.mark.parametrize("lang", ["nl", "de"])
def test_language_complete(lang):
    en = dict(flatten(json.loads((BASE / "strings.json").read_text())))
    tr = dict(flatten(json.loads((BASE / f"translations/{lang}.json").read_text())))
    assert tr.keys() == en.keys()
    for key, text in en.items():
        assert set(re.findall(r"\{\w+\}", tr[key])) == set(re.findall(r"\{\w+\}", text)), key
