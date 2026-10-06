#!/usr/bin/env python3
"""Extract the MOSS brand tokens from a checkout of the site repository.

The published site (`datahub-local/datahub-local`) owns the canonical brand:
`mkdocs.yml` names the two typefaces and `docs/stylesheets/extra.css` carries the
`MOSS BRAND PALETTE` colours, once per colour scheme. This script reads those two
files and writes `agents/n8n/datasets/brand.json`, which is the only copy of the
brand in this repository and the only place a surface may read a colour or a
typeface from.

It is a human-run sync step, never part of a render: an asset reads the committed
JSON, so generation touches no network and does not depend on what is deployed.
Re-running it against an unchanged checkout is a byte-identical no-op.

Usage:
    uv run --python 3.11 python agents/n8n/scripts/extract_brand.py
    BRAND_REPO=/path/to/datahub-local python3 agents/n8n/scripts/extract_brand.py

The site checkout defaults to a sibling `datahub-local` directory; BRAND_REPO
overrides it. A missing checkout is a readable error rather than a traceback.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
DATASETS = HERE.parent / "datasets"
BRAND_JSON = DATASETS / "brand.json"
BRAND_REPO = Path(os.environ.get("BRAND_REPO", REPO_ROOT.parent / "datahub-local"))

# The site's scheme blocks in extra.css, keyed by the data-md-color-scheme value.
DARK_BLOCK = "slate"
LIGHT_BLOCK = "default"

# The shape idioms are the site's own, taken from the border-radius values its
# CSS uses for cards, panels and pills and from its explicit `box-shadow: none`.
SHAPE = {
    "hairlineAlpha": 0.1,
    "radiusCard": "0.75rem",
    "radiusPanel": "1rem",
    "radiusPill": "99rem",
    "shadow": "none",
}

# The brand typefaces are what the render service vendors and uses. The n8n
# capture path runs in the browserless/chromium sidecar, a third-party image that
# carries neither face; the closest families it does carry are declared here as
# the fallback a surface names after the brand face, so a typeface is still a
# value from this document and never a literal in a surface. The render service
# loads the brand faces first, so it never reaches the fallback.
TEXT_FALLBACK = "Roboto"
CODE_FALLBACK = "DejaVu Sans Mono"

# One sentence, in the site's own photographic direction: dark studio, matte
# subject, moss light. It is what a raster hero is described with, never a UI
# token, so a hero never renders as an interface card.
PHOTOGRAPHIC_ART_DIRECTION = (
    "dark studio photograph, matte subject, one soft moss-green key light raking "
    "across the form, deep near-black background, restrained contrast, fine "
    "physical texture, no gloss, no screen or interface, no text"
)


def _fail(message: str) -> None:
    raise SystemExit(f"extract_brand: {message}")


def read_typefaces(mkdocs_yml: Path) -> dict:
    """Read theme.font.text and theme.font.code from mkdocs.yml.

    A plain scan, not a YAML parse: the root project's dev dependencies carry no
    PyYAML, and the two words are all this needs.
    """
    if not mkdocs_yml.is_file():
        _fail(f"no mkdocs.yml at {mkdocs_yml}")
    lines = mkdocs_yml.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        if not re.match(r"^\s*font:\s*$", line):
            continue
        base = len(line) - len(line.lstrip())
        block = {}
        for follow in lines[i + 1:]:
            if not follow.strip():
                continue
            indent = len(follow) - len(follow.lstrip())
            if indent <= base:
                break
            m = re.match(r"\s*([A-Za-z_]+):\s*(.+?)\s*$", follow)
            if m:
                block[m.group(1)] = m.group(2)
        text, code = block.get("text"), block.get("code")
        if not text or not code:
            _fail(f"theme.font in {mkdocs_yml} does not name both text and code")
        return {"code": code, "text": text}
    _fail(f"no theme.font block in {mkdocs_yml}")


def read_scheme(css: str, scheme: str) -> dict:
    pattern = r'\[data-md-color-scheme="' + re.escape(scheme) + r'"]\s*\{(.*?)\}'
    m = re.search(pattern, css, re.DOTALL)
    if not m:
        _fail(f'no [data-md-color-scheme="{scheme}"] block in extra.css')
    props = {}
    for pm in re.finditer(r"--md-([a-z0-9-]+)\s*:\s*([^;]+);", m.group(1)):
        props[pm.group(1)] = pm.group(2).strip()
    return props


def rgba(hex_value: str, alpha: float) -> str:
    h = hex_value.lstrip("#")
    if len(h) != 6:
        _fail(f"cannot derive an alpha for {hex_value}")
    r, g, b = (int(h[i : i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r}, {g}, {b}, {alpha})"


def need(props: dict, key: str) -> str:
    if key not in props:
        _fail(f"extra.css scheme block is missing --md-{key}")
    return props[key]


def build_schemes(css: str) -> dict:
    dark = read_scheme(css, DARK_BLOCK)
    light = read_scheme(css, LIGHT_BLOCK)

    dark_ink = need(dark, "default-fg-color")
    light_ink = need(light, "default-fg-color")
    light_code_bg = need(light, "code-bg-color")

    return {
        "dark": {
            "accent": need(dark, "primary-fg-color"),
            "accentDeep": need(dark, "primary-fg-color--dark"),
            "accentStrong": need(dark, "accent-fg-color"),
            "codeBg": need(dark, "code-bg-color"),
            "codeInk": need(dark, "code-fg-color"),
            "ink": dark_ink,
            "inkMuted": need(dark, "default-fg-color--light"),
            "shell": need(dark, "default-bg-color"),
            "surface": need(dark, "default-bg-color--light"),
            "surfaceRaised": need(dark, "default-bg-color--lighter"),
        },
        "light": {
            "accent": need(light, "accent-fg-color"),
            "accentDeep": need(light, "primary-fg-color--dark"),
            "accentStrong": need(light, "primary-fg-color"),
            "codeBg": light_code_bg,
            "codeInk": need(light, "code-fg-color"),
            "ink": light_ink,
            # The light block names no muted ink or raised surface; both are the
            # site's own values with one documented derivation applied.
            "inkMuted": rgba(light_ink, 0.75),
            "shell": need(light, "default-bg-color"),
            "surface": light_code_bg,
            "surfaceRaised": light_code_bg,
        },
    }


def build_document() -> dict:
    mkdocs = BRAND_REPO / "mkdocs.yml"
    css_path = BRAND_REPO / "docs" / "stylesheets" / "extra.css"
    if not BRAND_REPO.is_dir():
        _fail(
            f"no brand checkout at {BRAND_REPO}. Clone datahub-local/datahub-local "
            f"beside this repository, or set BRAND_REPO to point at it."
        )
    if not css_path.is_file():
        _fail(f"no stylesheet at {css_path}")
    fonts = read_typefaces(mkdocs)
    return {
        "defaultScheme": "dark",
        "photographic": {"artDirection": PHOTOGRAPHIC_ART_DIRECTION},
        "schemes": build_schemes(css_path.read_text(encoding="utf-8")),
        "shape": dict(SHAPE),
        "typography": {
            "code": fonts["code"],
            "codeFallback": CODE_FALLBACK,
            "text": fonts["text"],
            "textFallback": TEXT_FALLBACK,
        },
    }


def render(document: dict) -> str:
    return json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Regenerate agents/n8n/datasets/brand.json")
    parser.add_argument("--check", action="store_true", help="fail instead of writing when the file would change")
    args = parser.parse_args()

    text = render(build_document())
    current = BRAND_JSON.read_text(encoding="utf-8") if BRAND_JSON.is_file() else None
    if args.check:
        if current != text:
            _fail(f"{BRAND_JSON} is out of date; re-run without --check")
        print(f"{BRAND_JSON} is up to date")
        return 0
    if current == text:
        print(f"{BRAND_JSON} unchanged")
        return 0
    BRAND_JSON.parent.mkdir(parents=True, exist_ok=True)
    BRAND_JSON.write_text(text, encoding="utf-8")
    print(f"wrote {BRAND_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
