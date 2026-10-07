"""Guard the three-type visual registry.

Authoring is one composer turn, so the registry no longer declares a content-spec
template or a markup template: it declares how each type is authored and the frame
the composer is briefed to produce. Those are data, so they are asserted here,
offline, against the committed registry.
"""

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TYPES = ROOT / "datasets" / "visual_types.json"

# LinkedIn's documented GIF cap: at most 500 frames, at most 36,152,320 pixels.
GIF_FRAME_CAP = 500
GIF_PIXEL_CAP = 36152320

RETIRED = {
    "hero_static", "infographic_static", "diagram_animated", "diagram_animated_linkedin",
    "animated_svg", "motion_clip", "diagram_video", "diagram_agent",
}


@pytest.fixture(scope="module")
def registry():
    return json.loads(TYPES.read_text())


def test_the_registry_declares_exactly_three_types(registry):
    ids = [t["id"] for t in registry["types"]]
    assert ids == ["image", "animation", "animation_linkedin"]


def test_no_retired_type_remains(registry):
    ids = {t["id"] for t in registry["types"]}
    assert not (ids & RETIRED), f"retired type id(s) still declared: {sorted(ids & RETIRED)}"
    for t in registry["types"]:
        assert "specTemplate" not in t, f"{t['id']} still carries a spec template"
        assert "template" not in t, f"{t['id']} still carries a markup template"


def test_the_image_type_is_a_gemini_raster(registry):
    entry = next(t for t in registry["types"] if t["id"] == "image")
    assert entry["author"] == "image"
    assert entry["render"] == "static"
    assert entry["format"] == "png"
    assert entry["available"] is True
    # A type is photographic (brand art direction, no lettering) or diagrammatic
    # (brand scheme, lettered); the single image type declares one, and the
    # composer's raster prompt keeps both modes.
    assert entry["brandKind"] in ("photographic", "diagrammatic")


def test_the_animation_types_are_composer_authored(registry):
    for tid, fmt in (("animation", "mp4"), ("animation_linkedin", "gif")):
        entry = next(t for t in registry["types"] if t["id"] == tid)
        assert entry["author"] == "agent", tid
        assert entry["render"] == "video", tid
        assert entry["format"] == fmt, tid
        assert entry["available"] is True, tid
        assert entry.get("durationSeconds", 0) > 0, f"{tid} declares no duration"


def test_the_linkedin_type_is_inside_the_platform_caps(registry):
    entry = next(t for t in registry["types"] if t["id"] == "animation_linkedin")
    assert entry["aspect"] == "4:5"
    budget = entry["budget"]
    width = budget["viewport"]
    height = round(width * 5 / 4)
    assert budget["frames"] <= GIF_FRAME_CAP
    assert budget["frames"] * width * height <= GIF_PIXEL_CAP


def test_default_types_are_declared(registry):
    ids = {t["id"] for t in registry["types"]}
    assert registry["default_types"], "no default type"
    assert set(registry["default_types"]) <= ids


def test_the_registry_has_no_template_placeholder():
    # Fetched through DownloadTemplate with an empty template_vars, which scans
    # the whole text for {{ ... }} and fails on any it was not handed.
    text = TYPES.read_text()
    assert "{{" not in text and "}}" not in text


def test_the_registry_is_valid_json_with_no_off_brand_hex(registry):
    # The brand gate walks this file too; a hex here must be a brand colour. This
    # only asserts the shape, so a stray literal is caught by test_brand.py.
    assert re.search(r"#(?:[0-9a-fA-F]{6})\b", json.dumps(registry)) is None
