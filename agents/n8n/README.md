# n8n agents

Workflow exports, the datasets and prompts they fetch, and the two local
renderers they drive.

```
workflows/    exported n8n workflows (a backup of the live instance)
datasets/     JSON fetched at run time by DownloadTemplate
prompts/      prompt templates still fetched by DownloadTemplate; the article and post prompts live in agents/adapters/pi-writer/prompts/
templates/    HTML/SVG markup the animated and SVG asset types assemble
render/       the standalone video render service (its own README)
scripts/      operational scripts: apply a change to live, extract brand tokens
```

## Gates

The offline guards are gone: those that asserted a prompt, a dataset or an export
were removed on 2026-11-05, and the remaining `scripts/test_*.py` on 2026-11-07.
A test that pins those files goes red on the next correct edit, because they are
edited for reasons it cannot know. Do not add another unit test for a workflow, a
Code node, a prompt or a dataset. What is left is review — the diff, the live
apply, the next backup run — and `scripts/`, the Python that actually runs.

## Brand tokens

`datasets/brand.json` is the only copy of the project's palette and typefaces in
this repository. Every surface that generates a visual reads it — the render
service, the infographic templates, the prompts that describe a look, and the
type registry — so a second palette is a copy to review against this one.

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
