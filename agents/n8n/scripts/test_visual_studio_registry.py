"""Guard the visual registry.

Authoring is one composer turn, so the registry no longer declares a content-spec
template or a markup template: it declares how each type is authored and the frame
the composer is briefed to produce. Those are data, so they are asserted here,
offline, against the committed registry.

Two properties this change adds are asserted here: no animated type may mandate a
frozen frame (a hold during which nothing moves), and a deck type declares the paired
video the same run yields.
"""

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TYPES = ROOT / "datasets" / "visual_types.json"
PROMPTS = ROOT / "prompts"

# LinkedIn's documented GIF cap: at most 500 frames, at most 36,152,320 pixels.
GIF_FRAME_CAP = 500
GIF_PIXEL_CAP = 36152320

# A clip is at least this long, and a multi-scene clip gives each scene at least
# SCENE_SECONDS; the brief asks for max(durationSeconds, SCENES * secondsPerScene).
VIDEO_FLOOR_SECONDS = 30
SCENE_SECONDS = 10

AUTHORS = {"image", "agent"}
RENDERS = {"static", "video", "deck"}

RETIRED = {
    "hero_static", "infographic_static", "diagram_animated", "diagram_animated_linkedin",
    "animated_svg", "motion_clip", "diagram_video", "diagram_agent",
}


@pytest.fixture(scope="module")
def registry():
    return json.loads(TYPES.read_text())


def test_the_registry_declares_the_expected_types(registry):
    ids = [t["id"] for t in registry["types"]]
    assert ids == [
        "image",
        "image_wide",
        "animation",
        "animation_linkedin",
        "animation_linkedin_video",
        "svg",
        "svg_wide",
        "deck",
        "launch_card",
    ]


def test_the_wide_types_are_the_landscape_frame(registry):
    # An article is read on a screen, so its hero is landscape. The wide pair is the same
    # medium as `image`/`svg` at the frame a page wants, which is why it is a registry entry
    # rather than a change to the LinkedIn types (4:5) or a new request parameter.
    by_id = {t["id"]: t for t in registry["types"]}
    assert by_id["image_wide"]["aspect"] == "16:9"
    assert by_id["svg_wide"]["aspect"] == "16:9"
    assert by_id["image_wide"]["author"] == "image"
    assert by_id["image_wide"]["format"] == "png"
    assert by_id["svg_wide"]["author"] == "agent"
    assert by_id["svg_wide"]["format"] == "svg"
    # The LinkedIn frames stay what the platform wants.
    assert by_id["image"]["aspect"] == "4:5"
    assert by_id["svg"]["aspect"] == "4:5"


def test_a_type_may_pin_the_form_it_means(registry):
    # A type can declare the composition shape it means, and the studio honours it ahead of
    # the caller's FORCE: choosing the type is choosing its shape. `svg_wide` is the article's
    # diagram, so it pins `diagram` rather than hoping the composer picks it (it did, but by
    # choice -- the article's second asset must be a diagram every run).
    by_id = {t["id"]: t for t in registry["types"]}
    assert by_id["svg_wide"]["form"] == "diagram"
    # A form is one of the vocabulary's names, never a new word: the enum, the curator's
    # arrays and prompts/visual_forms.md are one list (test_hook_registry.py pins that), and a
    # typo here would reach the composer as prose it may ignore.
    text = (PROMPTS / "visual_forms.md").read_text(encoding="utf-8")
    known = set(re.findall(r"^- `([a-z_]+)`:", text, re.M))
    assert known, "the form vocabulary could not be read"
    for t in registry["types"]:
        if "form" in t:
            assert t["form"] in known, f"{t['id']} declares an unknown form {t['form']}"


def test_every_type_declares_a_known_author_and_render(registry):
    for t in registry["types"]:
        assert t["author"] in AUTHORS, f"{t['id']} has an unknown author {t['author']}"
        assert t["render"] in RENDERS, f"{t['id']} has an unknown render {t['render']}"


def test_the_svg_type_is_composer_authored(registry):
    entry = next(t for t in registry["types"] if t["id"] == "svg")
    assert entry["author"] == "agent"
    assert entry["format"] == "svg"
    assert entry["available"] is True


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
    for tid, fmt in (
        ("animation", "mp4"),
        ("animation_linkedin", "gif"),
        ("animation_linkedin_video", "mp4"),
    ):
        entry = next(t for t in registry["types"] if t["id"] == tid)
        assert entry["author"] == "agent", tid
        assert entry["render"] == "video", tid
        assert entry["format"] == fmt, tid
        assert entry["available"] is True, tid
        assert entry.get("durationSeconds", 0) > 0, f"{tid} declares no duration"


def test_no_animated_type_mandates_a_frozen_frame(registry):
    """Nothing may require the frame to stop; the brief asks for an ambient idle."""
    for t in registry["types"]:
        if t["render"] == "video":
            assert "holdSeconds" not in t, f"{t['id']} mandates a frozen final frame"


def test_the_linkedin_video_type_is_the_feed_frame(registry):
    entry = next(t for t in registry["types"] if t["id"] == "animation_linkedin_video")
    assert entry["aspect"] == "4:5"
    assert entry["budget"]["fps"] == 30
    assert entry["durationSeconds"] == VIDEO_FLOOR_SECONDS
    assert entry["budget"]["frames"] == entry["durationSeconds"] * entry["budget"]["fps"]
    assert entry["secondsPerScene"] == SCENE_SECONDS


@pytest.mark.parametrize("tid", ["animation", "animation_linkedin_video", "deck"])
def test_every_animated_video_declares_the_floor_and_a_scene_minimum(registry, tid):
    """A clip runs at least the floor, and each named scene gets at least its minimum."""
    entry = next(t for t in registry["types"] if t["id"] == tid)
    assert entry["durationSeconds"] >= VIDEO_FLOOR_SECONDS, f"{tid} is shorter than the floor"
    assert entry["secondsPerScene"] == SCENE_SECONDS, f"{tid} declares no per-scene minimum"
    # Frames follow the declared rate, so extending a clip lengthens it instead of
    # speeding it up.
    assert entry["budget"]["frames"] == entry["durationSeconds"] * entry["budget"]["fps"], tid


def test_the_gif_type_keeps_its_short_clip(registry):
    """A per-scene floor would blow the platform pixel cap, so the GIF declares none."""
    entry = next(t for t in registry["types"] if t["id"] == "animation_linkedin")
    assert "secondsPerScene" not in entry
    assert entry["durationSeconds"] < VIDEO_FLOOR_SECONDS


def test_the_linkedin_gif_type_is_inside_the_platform_caps(registry):
    entry = next(t for t in registry["types"] if t["id"] == "animation_linkedin")
    assert entry["aspect"] == "4:5"
    budget = entry["budget"]
    width = budget["viewport"]
    height = round(width * 5 / 4)
    assert budget["frames"] <= GIF_FRAME_CAP
    assert budget["frames"] * width * height <= GIF_PIXEL_CAP


def test_the_deck_type_declares_its_paired_video(registry):
    entry = next(t for t in registry["types"] if t["id"] == "deck")
    assert entry["author"] == "agent"
    assert entry["render"] == "deck"
    assert entry["format"] == "html"
    assert entry["paired"]["format"] == "mp4"
    assert entry["paired"]["assetType"], "the paired asset has no type name"


def test_the_launch_card_is_a_still_at_the_announcement_frame(registry):
    """The one agent-authored still raster: a card is a frame, not a clip."""
    entry = next(t for t in registry["types"] if t["id"] == "launch_card")
    assert entry["author"] == "agent"
    assert entry["render"] == "static"
    assert entry["format"] == "png"
    assert entry["aspect"] == "1.91:1"
    # A still ships one frame, so there is no scene to give a floor to, no duration
    # to run for and nothing to hold.
    assert "secondsPerScene" not in entry
    assert "durationSeconds" not in entry
    assert "holdSeconds" not in entry
    width = entry["budget"]["viewport"]
    aw, ah = (float(x) for x in entry["aspect"].split(":"))
    height = round(width * ah / aw)
    assert width > height, "the announcement frame is wider than it is tall"
    assert width >= 1200, "the frame is below the platform's recommended long edge"


def test_a_png_type_is_a_still(registry):
    """The brief branches on the format to compose a still in one frame, so a png
    type that animated would be handed the still brief."""
    for t in registry["types"]:
        if t["format"] == "png":
            assert t["render"] == "static", f"{t['id']} declares png with a {t['render']} render"


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
