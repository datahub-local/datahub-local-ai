# n8n agents

Workflow exports, the datasets and prompts they fetch, and the two local
renderers they drive.

```
workflows/    exported n8n workflows (a backup of the live instance)
datasets/     JSON fetched at run time by DownloadTemplate
prompts/      prompt templates fetched by DownloadTemplate
templates/    HTML/SVG markup the animated and SVG asset types assemble
render/       the standalone video render service (its own README)
scripts/      operational scripts and the offline export guards
```

## Brand tokens

`datasets/brand.json` is the only copy of the project's palette and typefaces in
this repository. Every surface that generates a visual reads it — the render
service, the infographic templates, the prompts that describe a look, and the
type registry — and `scripts/test_brand.py` fails on a colour or a typeface that
appears anywhere else, so no surface can grow a second palette.

The tokens are extracted from the site repository that owns the brand,
`datahub-local/datahub-local`, whose `mkdocs.yml` names the typefaces and whose
`docs/stylesheets/extra.css` carries the MOSS palette. To re-sync after the site
changes:

```
git clone git@github.com:datahub-local/datahub-local.git ../datahub-local   # once
python agents/n8n/scripts/extract_brand.py
```

`BRAND_REPO` overrides the checkout location. The script writes deterministically
(sorted keys), so re-running it against an unchanged checkout produces no diff
and a real upstream change shows up as a reviewable one. It is never run at
generation time: an asset reads the committed JSON, so a render touches no
network.

`datasets/brand.json` is fetched like any other template through
`DownloadTemplate` (`datasets/brand.json`); that workflow is generic — it reads
whatever path under `agents/n8n/` it is given — so a new dataset needs no
registration, only the file on `main`.
