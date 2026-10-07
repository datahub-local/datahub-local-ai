"""Guard the animated playback pace: a type may declare its own duration.

The GIF/WebP pace is ``frames / duration``; the LinkedIn type was reported too fast
because the duration came from the authoring model's spec. These are properties of the
graph and the registry, so they are asserted here, offline, against both committed
copies (the exports carry their nodes twice, and a fix applied to one is a live bug).
"""

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STUDIO = ROOT / "workflows" / "visual_studio.workflow.json"
TYPES = ROOT / "datasets" / "visual_types.json"
SPEC_PROMPT = ROOT / "prompts" / "visual_spec.md"

CEILING = 20000


def _copies():
    doc = json.loads(STUDIO.read_text())
    yield "top", doc
    if isinstance(doc.get("activeVersion"), dict) and "nodes" in doc["activeVersion"]:
        yield "activeVersion", doc["activeVersion"]


def _code(doc, name):
    for node in doc["nodes"]:
        if node["name"] == name:
            return node["parameters"].get("jsCode") or node["parameters"].get("scriptCode") or ""
    raise AssertionError(f"node {name!r} is missing from the export")


@pytest.mark.parametrize("label,doc", list(_copies()))
def test_the_type_pace_reaches_the_merge(label, doc):
    assert "DURATION_MS: Number(t.durationMs || 0)" in _code(doc, "parse_registry")
    merge = _code(doc, "merge_assets")
    # The type's value wins; the spec is only the fallback.
    assert "Number(a.DURATION_MS) || specDuration" in merge
    assert "r.DURATION_MS = String(dur)" in merge
    assert "Math.floor(dur * fpsCap / 1000)" in merge
    # The animation timeline the markup bakes must be the same `dur`.
    assert "buildMarkup(htmlT, spec, a.FPS, a.FRAMES, a.VIEWPORT, dur, false, brandTokens)" in merge


@pytest.mark.parametrize("label,doc", list(_copies()))
def test_the_animated_ceiling_is_raised(label, doc):
    for name in ("capture_frames", "build_assemble"):
        assert f"Math.min({CEILING}, Number(a.DURATION_MS) || 3000)" in _code(doc, name), name
    assert f"Math.min({CEILING}, Number(a.DURATION_MS) || specDuration)" in _code(doc, "merge_assets")
    assert f"Math.min({CEILING}, (spec && spec.motion && spec.motion.durationMs) || 3000)" in _code(doc, "merge_assets")


@pytest.mark.parametrize("label,doc", list(_copies()))
def test_the_authored_range_is_widened(label, doc):
    for name in ("spec_from_param", "parse_spec"):
        assert "d > 12000" in _code(doc, name)


@pytest.mark.parametrize("label,doc", list(_copies()))
def test_the_frame_cap_is_raised(label, doc):
    # More samples across the same window is what makes a slow transition read; the
    # cap was 36, which a longer duration cannot exceed.
    for name in ("capture_frames", "build_assemble"):
        assert "Math.min(90, Number(a.FRAME_COUNT) || 36)" in _code(doc, name), name
    assert "Math.min(90, Number(a.FRAMES) || 36)" in _code(doc, "merge_assets")


@pytest.mark.parametrize("label,doc", list(_copies()))
def test_a_request_without_a_spec_does_not_crash(label, doc):
    # A raster-only request (hero_static) carries no spec, and merge_assets computes
    # the duration before it branches, so an unguarded `spec.motion` null-derefs and
    # the whole run 500s ("Cannot read properties of null (reading 'motion')").
    merge = _code(doc, "merge_assets")
    assert "spec && spec.motion && spec.motion.durationMs" in merge
    assert "(spec.motion && spec.motion.durationMs)" not in merge


def test_the_linkedin_type_declares_a_pace():
    registry = json.loads(TYPES.read_text())
    li = [t for t in registry["types"] if t["id"] == "diagram_animated_linkedin"]
    assert len(li) == 1
    # 9000 ms over 48 frames is 5.3 fps, 3x the 3000 ms default and 2x the old 24 frames.
    assert li[0]["durationMs"] == 9000
    budget = li[0]["budget"]
    assert budget["frames"] == 48
    # The extra frames must stay inside the platform's total-pixel cap at 4:5.
    height = round(budget["viewport"] * 5 / 4)
    assert budget["frames"] * budget["viewport"] * height <= 36152320
    # No leftover comparison type from tuning the pace.
    assert not [t for t in registry["types"] if t["id"].startswith("diagram_animated_linkedin_")]


def test_the_spec_prompt_states_the_new_range():
    text = SPEC_PROMPT.read_text()
    assert "2000 to 12000" in text
    assert "2000 to 4000" not in text
