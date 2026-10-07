"""The single-source brand gate.

`agents/n8n/datasets/brand.json` is the only place this repository may write a
brand colour or a typeface. Every surface that produces a visual must read it:
the prompts that describe a look and the type registry. This test walks those
files and fails on a hex literal or a typeface that the brand document does not
carry, so a surface cannot quietly grow a second palette.

This is the mechanism the design calls D6. It is review-only otherwise, and this
repository already records that an unenforced rule drifts.
"""

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]  # agents/n8n
BRAND_PATH = ROOT / "datasets" / "brand.json"

# Files the gate deliberately does not read. Empty now: the render service's
# third-party catalog and fonts went with the render service, and nothing else
# carries a value the gate should skip. Every entry is exercised by
# test_allow_list_is_the_expected_set, so a stray entry fails rather than hides.
ALLOW = ()

HEX_RE = re.compile(r"#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})\b")
FONT_RE = re.compile(r"font-family:\s*([^;{}\n]+)")
# An unresolved template placeholder is not a value a surface chose; the workflow
# fills it from brand.json at run time. `%%TOKEN%%` is this repository's markup
# convention and `{{ TOKEN }}` is DownloadTemplate's.
PLACEHOLDER_RE = re.compile(r"^(?:%%[A-Z_]+%%|\{\{[^}]*\}\})$")

# CSS keywords that are not brand typefaces and never need to be one.
GENERIC_FONTS = {
    "serif",
    "sans-serif",
    "monospace",
    "ui-sans-serif",
    "ui-monospace",
    "system-ui",
    "cursive",
    "fantasy",
    "inherit",
    "initial",
    "unset",
}


def brand() -> dict:
    return json.loads(BRAND_PATH.read_text(encoding="utf-8"))


def strings(node):
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for value in node.values():
            yield from strings(value)
    elif isinstance(node, list):
        for value in node:
            yield from strings(value)


def brand_hexes() -> set:
    return {s.lower() for s in strings(brand()) if HEX_RE.fullmatch(s.strip())}


def brand_fonts() -> set:
    return set(brand()["typography"].values())


def targets():
    paths = []
    paths += [
        ROOT / "prompts" / name
        for name in ("visual_raster.md", "linkedin_image_prompt.md", "diagram_generator.md")
    ]
    paths += [ROOT / "datasets" / "visual_types.json"]
    for path in paths:
        if path.is_file() and not is_allowed(path):
            yield path


def is_allowed(path: Path) -> bool:
    rel = path.relative_to(ROOT).as_posix()
    return any(rel == entry or rel.startswith(entry) for entry in ALLOW)


def test_allow_list_is_the_expected_set():
    assert ALLOW == (), (
        "the brand gate's allow-list changed; justify the new entry in a comment "
        "and update this assertion deliberately"
    )


def test_brand_has_no_template_placeholder():
    # brand.json is fetched through DownloadTemplate with an empty template_vars,
    # and that node scans the whole text for {{ ... }} and fails on any it was not
    # handed. A doubled brace anywhere here kills every asset run.
    text = BRAND_PATH.read_text(encoding="utf-8")
    assert "{{" not in text and "}}" not in text


def test_every_surface_is_walked():
    # A path-list typo would silently skip a whole surface, so assert every
    # expected surface is present.
    walked = [p.relative_to(ROOT).as_posix() for p in targets()]
    assert "prompts/visual_raster.md" in walked
    assert "datasets/visual_types.json" in walked


@pytest.mark.parametrize("path", list(targets()), ids=lambda p: p.relative_to(ROOT).as_posix())
def test_no_off_brand_hex(path: Path):
    allowed = brand_hexes()
    bad = [m.group(0) for m in HEX_RE.finditer(path.read_text(encoding="utf-8")) if m.group(0).lower() not in allowed]
    assert not bad, f"{path.relative_to(ROOT)} uses colour(s) not in brand.json: {sorted(set(bad))}"


@pytest.mark.parametrize("path", list(targets()), ids=lambda p: p.relative_to(ROOT).as_posix())
def test_only_brand_typefaces(path: Path):
    allowed = brand_fonts() | GENERIC_FONTS
    bad = []
    for value in FONT_RE.findall(path.read_text(encoding="utf-8")):
        for token in value.split(","):
            token = token.strip().strip("'\"")
            if not token or token.startswith("var(") or PLACEHOLDER_RE.match(token) or token in allowed:
                continue
            bad.append(token)
    assert not bad, f"{path.relative_to(ROOT)} uses typeface(s) not in brand.json: {sorted(set(bad))}"


def test_extraction_is_idempotent():
    """A re-run against an unchanged checkout produces the committed bytes.

    Skipped when no site checkout is present (CI has none): the extraction is a
    human sync step, so this is the local proof that it is a no-op, not a CI gate.
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import extract_brand

    if not extract_brand.BRAND_REPO.is_dir():
        pytest.skip(f"no brand checkout at {extract_brand.BRAND_REPO}")
    assert extract_brand.render(extract_brand.build_document()) == BRAND_PATH.read_text(encoding="utf-8")


def test_legacy_diagram_datasets_do_not_offer_other_palettes():
    """The legacy diagram flow's datasets are reconciled, not a palette beside the brand.

    `diagram_color_presets.json` collapses to the brand's two schemes and
    `image_motifs.json` carries the brand's photographic art direction. This test is
    what stops either from drifting back into an off-brand palette.
    """
    allowed = brand_hexes()

    presets = json.loads((ROOT / "datasets" / "diagram_color_presets.json").read_text(encoding="utf-8"))
    assert [p["id"] for p in presets] == ["dark", "light"]
    for preset in presets:
        stray = [m.group(0) for m in HEX_RE.finditer(preset["description"]) if m.group(0).lower() not in allowed]
        assert not stray, f"color preset '{preset['id']}' names off-brand colour(s): {stray}"

    styles = json.loads((ROOT / "datasets" / "diagram_visual_styles.json").read_text(encoding="utf-8"))
    for style in styles:
        assert "brand's dark or light scheme" in style["description"], style["id"]

    motifs = json.loads((ROOT / "datasets" / "image_motifs.json").read_text(encoding="utf-8"))
    assert motifs["art_direction"] == brand()["photographic"]["artDirection"]
    assert "{{" not in json.dumps(motifs)
