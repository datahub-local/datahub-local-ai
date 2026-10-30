"""Guard the Article Content Writer entry point's graph.

The entry point is authored as a create body, so nothing about it is live yet and its
behaviour cannot be exercised here. What can be asserted offline is the set of decisions the
graph has to get right for the live run in 6.2 to mean anything -- each of these has a failure
mode that is silent at run time, which is why they are pinned rather than reviewed once:

  * the references the run needs that do not exist yet (the sheet page, the two Data Tables)
    are addressed **by name**, so the export is complete before the human creates them;
  * the claim is written before the first model call, and every sheet write is keyed on
    `row_number`, because an update that matches nothing is a silent no-op;
  * the publish path never borrows a node from the asset path: a resumed publish run has not
    executed `if_all_assets_approved`, and `$('that node').first()` would throw;
  * a raster asset's bytes have no durable handle, so they are stored on the asset row, while
    an agent asset is re-fetched from its object key;
  * the studio is asked for the pending types on a resume, so an approved asset is never
    re-authored.
"""

import base64
import json
import re
import shutil
import subprocess
import tempfile
import textwrap
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

BASE = Path(__file__).resolve().parents[1]  # agents/n8n
WORKFLOWS = BASE / "workflows"

ENTRY = WORKFLOWS / "article_content_writer.workflow.json"
REF_RE = re.compile(r"\$\(\s*['\"]([^'\"]+)['\"]\s*\)")
NODE_REQUIRED = "node is required to execute a Code node"


def _doc():
    return json.loads(ENTRY.read_text(encoding="utf-8"))


def _nodes():
    return {n["name"]: n for n in _doc()["nodes"]}


def _connections():
    return _doc()["connections"]


def _targets(source, output=0):
    branches = (_connections().get(source) or {}).get("main") or []
    branch = branches[output] if output < len(branches) else []
    return [edge["node"] for edge in (branch or [])]


def _reachable(*sources):
    seen, queue = set(sources), list(sources)
    while queue:
        for target in _targets(queue.pop()):
            if target not in seen:
                seen.add(target)
                queue.append(target)
    return seen


def _js(name):
    return _nodes()[name]["parameters"]["jsCode"]


def test_the_new_references_are_addressed_by_name():
    nodes = _nodes()
    sheet_refs = [
        n["parameters"]["sheetName"]
        for n in _doc()["nodes"]
        if n["type"] == "n8n-nodes-base.googleSheets"
    ]
    assert sheet_refs, "no sheet node at all"
    for ref in sheet_refs:
        assert ref["value"] == "article_queue"
        assert ref["mode"] == "name"
    tables = {
        n["parameters"]["dataTableId"]["value"]
        for n in _doc()["nodes"]
        if n["type"] == "n8n-nodes-base.dataTable"
    }
    assert tables == {"article_drafts", "article_assets"}
    for node in nodes.values():
        ref = (node.get("parameters") or {}).get("dataTableId")
        if ref:
            assert ref["mode"] == "name"


def test_every_sheet_write_is_keyed_on_the_row_number():
    updates = [
        n
        for n in _doc()["nodes"]
        if n["type"] == "n8n-nodes-base.googleSheets" and n["parameters"].get("operation") == "update"
    ]
    assert updates
    for node in updates:
        assert node["parameters"]["columns"]["matchingColumns"] == ["row_number"], node["name"]


def test_the_claim_is_written_before_the_first_model_call():
    assert _targets("select_article_to_queue") == ["update_status_in_progress"]
    claim = _nodes()["update_status_in_progress"]["parameters"]["columns"]["value"]
    assert claim["STATUS"] == "IN_PROGRESS"
    assert claim["EXECUTION_ID"] == "={{ $execution.id }}"
    # The creator is downstream of the claim, not the other way round.
    assert "execute_article_creator" in _reachable("update_status_in_progress")


def test_the_draft_is_gated_before_anything_is_reviewed():
    # A failed draft is recorded and reported, then stops. It must not reach a review notice -
    # the run has no draft to review - and it must not leave the row reading as awaiting
    # approval, which is what execution 14055 did for an hour (2026-10-18).
    assert _targets("check_draft_error", 1) == ["build_failure"]
    assert _targets("build_failure") == ["record_failed_draft"]
    assert _targets("record_failed_draft") == ["notify_draft_failed"]
    assert _targets("notify_draft_failed") == ["fail_draft"]
    downstream = _reachable("build_failure")
    assert "notify_article_review" not in downstream
    assert "notification_retry_or_cancel" not in downstream
    assert _targets("check_draft_error", 0) == ["read_draft_for_improvement"], (
        "a draft that passed the gate must enter the improvement pass"
    )


def test_a_thrown_failure_is_reported_like_a_returned_one():
    """The creator can fail two ways and both must mark the row and tell a human.

    Measured 2026-10-18 (execution 14145): the creator *threw* `Max iterations (12) reached`,
    n8n stopped the graph at the call node, and neither the reporter nor `check_draft_error` ran
    — so the row stayed IN_PROGRESS with no ERROR and no notice, which is the gap the reporter
    exists to close. `continueErrorOutput` is what puts a thrown failure on a branch, and unlike
    `continueRegularOutput` n8n sets `json.error` on it (measured with a probe, 2026-10-18).
    """
    node = _nodes()["execute_article_creator"]
    assert node.get("onError") == "continueErrorOutput", "a thrown failure stops the graph again"
    assert _targets("execute_article_creator", 0) == ["check_draft_error"]
    assert _targets("execute_article_creator", 1) == ["build_failure"]
    assert _targets("check_draft_error", 1) == ["build_failure"]
    build = _js("build_failure")
    assert "$json.ERROR" in build, "the reason a *returned* failure carries is no longer read"
    assert "$json.error" in build, "the reason a *thrown* failure carries is no longer read"


def test_a_failed_draft_is_recorded_and_reported():
    """The failure path writes the row and tells a human, because nothing else will.

    The error workflow does not fire for a manual execution, so a failure that only stops is
    invisible in the sheet, in Slack and in the logs at once.
    """
    cols = _nodes()["record_failed_draft"]["parameters"]["columns"]
    assert cols["value"]["STATUS"] == "ERROR", "a failed run must not leave a live-looking status"
    assert cols["value"]["ERROR"] == "={{ $json.REASON }}"
    assert cols["matchingColumns"] == ["row_number"]
    entry = next(s for s in cols["schema"] if s["id"] == "ERROR")
    assert entry["removed"] is False, "the Sheets node would silently not write ERROR"
    build = _js("build_failure")
    assert "select_article_to_queue" in build and "REASON" in build, (
        "the creator returns no row fields, so the row has to come from the selector"
    )
    message = _nodes()["fail_draft"]["parameters"]["errorMessage"]
    assert "$('build_failure').first()" in message, "the report must not read through a paired item"
    assert "$('execute_article_creator').item" not in message
    notice = _nodes()["notify_draft_failed"]["parameters"]["text"]
    assert "build_failure" in notice and "ERROR" in notice, "the notice names neither row nor reason"


def test_the_human_retry_improves_the_draft_the_human_read():
    """The retry re-enters the improvement pass, handed the draft the human read.

    The edge used to loop back into `execute_article_creator`, which regenerated the whole
    article against feedback naming one section (run 14178, 2026-10-18: two human rounds, two
    fresh articles). `build_improvement_context` reads `select_final_draft`'s own earlier run,
    so the edit starts from the draft of record; a node reading its own earlier runs is
    measured rather than assumed (a probe cycle on 2026-10-18, execution 14195, had
    `$('step').last()` answer the previous run's value on the second pass).
    """
    assert _targets("switch_article_retry", 0) == ["build_improvement_context"], (
        "the human's Retry no longer re-enters the improvement pass"
    )
    assert "execute_article_creator" not in _targets("switch_article_retry")
    code = _js("build_improvement_context")
    assert "$('select_final_draft').isExecuted" in code, "the draft the human read is not preferred"
    assert "$('execute_article_creator').isExecuted" in code, "the first pass has no fallback"
    assert "$('read_draft_for_improvement')" in code, "a resumed review has no stored draft"
    assert "select_final_draft').last()" in code, "a second round would re-send the first draft"
    # the carry is the improvement context's, not the sub-workflow's
    assert "PREVIOUS_DRAFT" not in _nodes()["execute_article_creator"]["parameters"]["workflowInputs"]["value"]
    assert "PREVIOUS_DRAFT" not in [
        s["id"] for s in _nodes()["execute_article_creator"]["parameters"]["workflowInputs"]["schema"]
    ]


def test_the_rendered_asset_is_the_only_thing_that_gets_reviewed():
    # An asset the studio could not render keeps its reason and takes no review.
    assert _targets("if_asset_rendered") == ["if_asset_has_bytes"]


def test_a_resumed_asset_phase_asks_only_for_the_pending_types():
    # The pending set is resolved once, in the splitter, and the studio is then called with
    # one type per call. The studio cannot answer a two-type request with two assets: a
    # sub-workflow's response is its last node's last run, so the other branch's item is
    # dropped inside n8n (measured 2026-10-17, executions 13722 and 13720).
    studio = _nodes()["execute_visual_studio"]["parameters"]["workflowInputs"]["value"]
    assert studio["ASSET_TYPES"] == "={{ $json.ASSET_TYPE }}"
    code = _js("split_pending_types")
    assert "PENDING_ASSETS" in code and "ASSET_TYPE: type" in code
    assert _targets("read_draft_for_assets") == ["split_pending_types"]
    assert _targets("split_pending_types") == ["execute_visual_studio"]
    # The retry path re-asks too, and it must not bypass the splitter: a retry that sent the
    # whole pending set would lose every asset but the last one again.
    assert _targets("switch_asset_retry", 0) == ["split_pending_types"]
    # The draft comes from the Data Table, not from a node that did not run in this execution.
    assert studio["CONTENT"] == "={{ $('read_draft_for_assets').first().json.ARTICLE_TEXT }}"
    # The row fields ride on the item rather than through `$('node').item`, which a fan-out
    # from one item to many no longer pairs.
    assert studio["SESSION_ID"] == "={{ 'blog-' + $json.ENTRY_ID }}"


def test_the_publish_path_owns_its_own_reads():
    # A resumed publish run has not executed the asset-review nodes, so anything it borrows
    # from them throws at run time.
    publish = _reachable("read_asset_rows_for_publish")
    for node in (
        "plan_asset_uploads",
        "build_commit_files",
        "collect_tree_entries",
        "record_published",
        "send_published_notification",
    ):
        assert node in publish, node
        references = set(REF_RE.findall(json.dumps(_nodes()[node]["parameters"])))
        assert "if_all_assets_approved" not in references, node
    assert _targets("switch_phase", 2) == ["read_asset_rows_for_publish"]
    # The gate's clear path is what owns the publish read; its blocked path reports.
    assert _targets("if_all_assets_approved") == ["if_assets_blocked"]
    assert _targets("if_assets_blocked", 1) == ["read_asset_rows_for_publish"]


def test_a_raster_is_stored_and_an_agent_asset_is_refetched():
    store = _nodes()["store_assets"]["parameters"]["columns"]["value"]
    assert "DATA_BASE64" in store
    assert "IMAGE" in store["DATA_BASE64"]
    plan = _js("plan_asset_uploads")
    assert "DATA_BASE64" in plan
    assert "S3_KEY" in plan
    assert "NEEDS_FETCH" in plan
    # The fetch branch exists and converges back on the blob call.
    # NEEDS_FETCH true is the agent asset: an object key and no local bytes, so it must be
    # fetched. The local-bytes case goes straight to the blob. The outputs were the other way
    # round until 2026-10-18, which is why the published SVG was a 0-byte file.
    assert _targets("if_asset_needs_fetch", 0) == ["presign_asset_publish"]
    assert _targets("if_asset_needs_fetch", 1) == ["create_blobs"]
    assert "create_blobs" in _reachable("asset_bytes_from_download")


@pytest.mark.skipif(shutil.which("node") is None, reason=NODE_REQUIRED)
def test_the_fetched_asset_bytes_are_read_from_the_binary_store():
    """In queue mode the payload is not on the item, and the item says so in one word.

    Measured on execution 14259 (2026-10-19): the fetch branch ran, the signed URL served
    14,338 bytes, and the published SVG was 8 bytes reading `database` — the literal value
    `binary.data.data` carries in this deployment, which the commit then base64-encoded. The
    bytes are read through `helpers.getBinaryDataBuffer`, the helper `encode_stills` in
    Visual Studio already uses for the same reason.
    """
    payload = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720"></svg>'
    harness = textwrap.dedent(
        """
        (async () => {
          const scope = {
            plan_asset_uploads: [{ S3_KEY: 'visual-studio/14304-svg_wide.svg', ASSET_TYPE: 'svg_wide' }],
            asset_publish_url: [{ S3_KEY: 'visual-studio/14304-svg_wide.svg' }],
          };
          const payload = Buffer.from('%s', 'base64');
          const incoming = [{
            json: { ...scope.plan_asset_uploads[0], NEEDS_FETCH: true },
            binary: { data: { data: 'database', id: 'database:fake', mimeType: 'image/svg+xml', bytes: payload.length } },
          }];
          const $ = (n) => {
            const items = scope[n].map((json) => ({ json }));
            return { first: () => items[0], all: () => items, item: items[0] };
          };
          const $input = { all: () => incoming, first: () => incoming[0] };
          const $json = incoming[0].json;
          const helpers = { getBinaryDataBuffer: async () => payload };
          const fn = new Function('$', '$input', '$json', 'helpers', 'return (async function(){' + %s + '})()');
          const out = await fn($, $input, $json, helpers);
          process.stdout.write(JSON.stringify(out));
        })();
        """
    ) % (base64.b64encode(payload).decode(), json.dumps(_js("asset_bytes_from_download")))
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as fh:
        fh.write(harness)
        path = fh.name
    try:
        done = subprocess.run(["node", path], capture_output=True, text=True, check=False)
    finally:
        Path(path).unlink()
    assert done.returncode == 0, done.stderr
    item = json.loads(done.stdout)[0]["json"]
    assert base64.b64decode(item["FILE_BASE64"]) == payload, "the placeholder was committed instead of the bytes"
    assert item["FILE_BYTES"] == len(payload)


def test_the_draft_row_is_upserted_so_a_round_does_not_accumulate_rows():
    draft = _nodes()["store_draft"]["parameters"]
    assert draft["operation"] == "upsert"
    assert draft["filters"]["conditions"][0]["keyName"] == "ENTRY_ID"
    # The slug is frozen at the draft, which is what a retry reuses (D11).
    assert "SLUG" in draft["columns"]["value"]


def test_the_article_text_is_committed_inline_and_assets_as_blobs():
    body = _js("build_commit_files")
    assert "FILE_IS_BINARY" in body
    assert "categories: [" in body
    assert "authors: [alvsanand]" in body
    # A marker the draft omitted is placed rather than dropped.
    assert "placed without a marker" in body
    entries = _js("collect_tree_entries")
    assert "content = f.FILE_TEXT" in entries
    assert "expected[i]" in entries  # a mis-paired sha fails instead of committing the wrong file


# The accepted draft of execution 13994 (2026-10-18), verbatim: the first article run the
# review loop published after retrying two over-budget drafts (462/400, then 412/400, then
# 345/400). Its marker sits on line 3, before the first `## ` heading on line 5.
PUBLISHED_DRAFT = """My homelab platform ingested CSV into bronze with dlt, and dbt built silver and gold into Iceberg on S3, queried through Trino. Every night `dbt build` ran across 40 models and took 22 minutes on the four-board cluster: three Orange Pi 5B boards, one Orange Pi 4 LTS, plus an amd64 NAS. That is a long time to hold a window for work that mostly rebuilds rows the source has not touched.

<!-- asset:image_wide -->

## What made it buildable

The models are materialized as tables with `incremental_strategy merge` and an `is_incremental()` guard, and the lookback window is three days. Since dbt runs on Trino, the build is a set of distributed SQL statements against Iceberg on Garage; cutting the window to 6 minutes was mostly about scoping those statements.

## The key is the whole game

`_dlt_id` is stable per load but not per logical row, and `_batch_timestamp` is the loader's own clock, not the source's. So the models use the business key, deduplicating with a `row_number` window ordered by `_batch_timestamp` to keep the newest version of each key. Late-arriving rows are handled by the three-day lookback rather than full history, which assumes corrections older than three days are rare enough that a deliberate full refresh is cheaper than scanning everything nightly.

Two traps worth naming. An incremental model with a wrong unique key silently duplicates rows on every run. A full-refresh run on Iceberg rewrites every data file, which took longer than the original batch window ever did.

Granularity is where wrongness hides. `silver.bodega.invoice_items` expands `items_json` and `taxes_json` into 1682 line items from 85 invoices, and `silver.bodega.product_prices` flattens a nested prices object to one row per shop, product and date. Gold then aggregates per shop and day. Nothing user-facing reads bronze, because a chart on bronze would count invoices where it meant line items, and the MCP server scopes itself to `silver.bodega` and `gold.bodega`.

Airflow still schedules the dlt ingest at 01:00 with the dbt build after it, both as Kubernetes pods.

What I take away: the incremental key deserves more scrutiny than the incremental strategy."""


def _run_code_node(name, scope, input_items=None, expect_error=False):
    """Execute a committed Code node's jsCode with a stubbed n8n context.

    n8n runs a Code node body inside an async wrapper, so ``new Function`` is the shape that
    accepts its top-level ``return``. Every ``$('node')`` reference the body makes must be in
    ``scope``, so a body reaching for a node the test did not provide throws instead of
    reading ``undefined``. ``input_items`` is the node's incoming stream, for a body that reads
    ``$input``.
    """
    harness = textwrap.dedent(
        """
        const scope = %s;
        const incoming = %s;
        const logs = [];
        const $ = (n) => {
          if (!(n in scope)) throw new Error('the test did not provide node ' + n);
          const items = scope[n].map((json) => ({ json }));
          return { first: () => items[0], all: () => items, item: items[0] };
        };
        const $input = {
          all: () => incoming.map((json) => ({ json })),
          first: () => ({ json: incoming[0] }),
        };
        const $json = incoming[0];
        const console = { log: (...a) => logs.push(a.join(' ')) };
        const fn = new Function('$', 'console', '$input', '$json', %s);
        process.stdout.write(JSON.stringify({ out: fn($, console, $input, $json), logs }));
        """
    ) % (json.dumps(scope), json.dumps(input_items or []), json.dumps(_js(name)))
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as fh:
        fh.write(harness)
        path = fh.name
    try:
        done = subprocess.run(["node", path], capture_output=True, text=True, check=False)
    finally:
        Path(path).unlink()
    if expect_error:
        return done
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


@pytest.mark.skipif(shutil.which("node") is None, reason=NODE_REQUIRED)
def test_the_hero_reference_replaces_the_marker_where_the_writer_put_it():
    """The published file carries the hero at the draft's marker, not at the fallback position.

    Executed against the committed jsCode with the draft execution 13994 actually published,
    because the two positions are one branch apart and reading the code cannot tell which one
    a given draft takes. `<!-- asset:image -->` -- what the writer emitted before this change
    for a row requesting `image_wide` -- matches nothing, so the hero fell to the fallback and
    landed after the first `## ` heading instead of after the opening paragraph.
    """
    slug = "cutting-a-nightly-dbt-rebuild-to-six-minutes"
    result = _run_code_node(
        "build_commit_files",
        {
            "disambiguate_slug": [{"SLUG": slug}],
            "read_draft_for_publish": [{"ARTICLE_TEXT": PUBLISHED_DRAFT, "TITLE": "Cutting a Nightly dbt Rebuild to Six Minutes"}],
            "read_asset_rows_for_publish": [{"ASSET_TYPE": "image_wide", "CONTENT_TYPE": "image/png"}],
            "select_article_to_queue": [
                {"CATEGORIES": "Data", "ENTRY_ID": 1, "ROW_NUMBER": 1, "REQUESTED_ASSETS": "image_wide"}
            ],
        },
    )
    assert not [line for line in result["logs"] if "placed without a marker" in line], (
        "the hero fell to the fallback position"
    )
    article = next(f["json"] for f in result["out"] if not f["json"]["FILE_IS_BINARY"])
    lines = article["FILE_TEXT"].split("\n")
    assert not [line for line in lines if "<!-- asset:" in line], "a marker survived into the file"
    at = next(
        (i for i, line in enumerate(lines) if f"](/img/{slug}-image_wide.png)" in line),
        None,
    )
    assert at is not None, "the hero reference is not in the committed file"
    heading = next(i for i, line in enumerate(lines) if line.startswith("## "))
    assert at < heading, "the hero landed after the first heading, which is the fallback position"

    # The same draft with the marker the writer used to emit, so the assertion above cannot
    # pass vacuously: a marker no requested type matches takes the fallback branch.
    stale = _run_code_node(
        "build_commit_files",
        {
            "disambiguate_slug": [{"SLUG": slug}],
            "read_draft_for_publish": [
                {"ARTICLE_TEXT": PUBLISHED_DRAFT.replace("<!-- asset:image_wide -->", "<!-- asset:image -->"),
                 "TITLE": "Cutting a Nightly dbt Rebuild to Six Minutes"}
            ],
            "read_asset_rows_for_publish": [{"ASSET_TYPE": "image_wide", "CONTENT_TYPE": "image/png"}],
            "select_article_to_queue": [
                {"CATEGORIES": "Data", "ENTRY_ID": 1, "ROW_NUMBER": 1, "REQUESTED_ASSETS": "image_wide"}
            ],
        },
    )
    assert [line for line in stale["logs"] if "placed without a marker: image_wide" in line], (
        "an unmatched marker no longer takes the fallback, so this test asserts nothing"
    )


def test_the_requested_set_is_derived_once_and_read_by_its_consumers():
    """One definition of the hero rule, read by the gate and by the commit path.

    The rule was derived twice, in `select_article_to_queue` and again in
    `if_all_assets_approved`, coupled only by a comment. The commit path derived nothing and took
    every row the table held, which is how an entry that once requested `image` and now requests
    `image_wide` committed both.
    """
    selector = _js("select_article_to_queue")
    assert "REQUESTED_ASSETS" in selector, "the selector no longer publishes the set it derived"
    assert selector.count("includes('image_wide')") == 1, "the hero rule is derived more than once"
    for name in ("if_all_assets_approved", "build_commit_files"):
        code = _js(name)
        assert "REQUESTED_ASSETS" in code, f"{name} does not read the selector's set"
        assert "includes('image_wide')" not in code, f"{name} derives the hero rule again"


@pytest.mark.skipif(shutil.which("node") is None, reason=NODE_REQUIRED)
def test_a_row_for_a_type_the_entry_no_longer_requests_is_not_committed():
    """The commit carries the entry's requested set, not every row the table holds.

    Found while applying `add-content-writer-agent` 4.17 (2026-10-17): `read_asset_rows_for_publish`
    filters on `ENTRY_ID` alone, so an entry whose requested set had changed committed its old
    asset too — an orphan image in the repository and a commit that did not match the set the run
    reported. Worked around by deleting the stale row by hand; fixed here.
    """
    slug = "cutting-a-nightly-dbt-rebuild-to-six-minutes"
    result = _run_code_node(
        "build_commit_files",
        {
            "disambiguate_slug": [{"SLUG": slug}],
            "read_draft_for_publish": [{"ARTICLE_TEXT": PUBLISHED_DRAFT, "TITLE": "Cutting a Nightly dbt Rebuild to Six Minutes"}],
            "read_asset_rows_for_publish": [
                {"ASSET_TYPE": "image_wide", "STATUS": "APPROVED", "CONTENT_TYPE": "image/png"},
                {"ASSET_TYPE": "image", "STATUS": "APPROVED", "CONTENT_TYPE": "image/png"},
            ],
            "select_article_to_queue": [
                {"CATEGORIES": "Data", "ENTRY_ID": 1, "ROW_NUMBER": 1, "REQUESTED_ASSETS": "image_wide"}
            ],
        },
    )
    paths = [f["json"]["FILE_PATH"] for f in result["out"]]
    assert f"docs/img/{slug}-image_wide.png" in paths, "the requested asset was not committed"
    assert f"docs/img/{slug}-image.png" not in paths, "a row for an unrequested type was committed"
    assert [line for line in result["logs"] if "not requested by this entry: image" in line], (
        "the dropped type was not reported, so the run would not show it"
    )
    article = next(f["json"] for f in result["out"] if not f["json"]["FILE_IS_BINARY"])
    assert f"](/img/{slug}-image.png)" not in article["FILE_TEXT"], (
        "the article references an asset that was not committed"
    )


@pytest.mark.skipif(shutil.which("node") is None, reason=NODE_REQUIRED)
def test_a_type_named_twice_is_requested_once():
    """The requested set names each type once, whatever the row's `ASSET_TYPES` holds.

    A test row on 2026-10-18 carried `svg_wide,svg_wide`, and the set went through undeduplicated
    (`PENDING_ASSETS: "image_wide,svg_wide,svg_wide"`, execution 14018). Downstream that is two
    studio calls for one type and two committed files at one `docs/img/` path.
    """

    def run(asset_types, assets):
        return _run_code_node(
            "select_article_to_queue",
            {
                "validate_categories": [
                    {"row_number": 1, "ENTRY_ID": "e1", "ASSET_TYPES": asset_types, "ARTICLE_STATUS": ""}
                ]
            },
            assets,
        )["out"][0]["json"]

    # A duplicated non-hero type: the hero rule adds the animated wide one, once.
    out = run("svg_wide,svg_wide", [{"ASSET_TYPE": "svg_wide", "STATUS": "APPROVED"}])
    assert out["REQUESTED_ASSETS"] == "svg_wide", out["REQUESTED_ASSETS"]
    assert out["PENDING_ASSETS"] == "", out["PENDING_ASSETS"]

    # A duplicated hero type is one hero, not two.
    out = run("image_wide,image_wide", [])
    assert out["REQUESTED_ASSETS"] == "image_wide", out["REQUESTED_ASSETS"]
    assert out["PENDING_ASSETS"] == "image_wide", out["PENDING_ASSETS"]


@pytest.mark.skipif(shutil.which("node") is None, reason=NODE_REQUIRED)
def test_the_hero_a_row_does_not_name_is_animated():
    """The hero is `svg_wide`, not a still raster.

    Measured 2026-10-18: article run 14196 asked the studio for `image_wide` - a Gemini png -
    because the hero rule prepended a raster to a row whose own `ASSET_TYPES` was `svg_wide`. The
    animated asset the row did ask for never got authored (studio execution 14219).
    """

    def run(types):
        return _run_code_node(
            "select_article_to_queue",
            {
                "validate_categories": [
                    {"row_number": 1, "ENTRY_ID": "e1", "ASSET_TYPES": types, "ARTICLE_STATUS": ""}
                ]
            },
            [],
        )["out"][0]["json"]

    # A row naming an animated type keeps it, and no raster is added behind its back.
    assert run("svg_wide,svg_wide")["REQUESTED_ASSETS"] == "svg_wide"
    assert run("animation")["REQUESTED_ASSETS"] == "svg_wide,animation"
    assert run("tiles_wide")["REQUESTED_ASSETS"] == "svg_wide,tiles_wide"
    assert run("")["REQUESTED_ASSETS"] == "svg_wide"
    # A row that names its own wide raster keeps that choice.
    assert run("image_wide")["REQUESTED_ASSETS"] == "image_wide"


@pytest.mark.skipif(shutil.which("node") is None, reason=NODE_REQUIRED)
def test_the_article_lane_never_requests_the_portrait_pair():
    """A 4:5 asset is a phone poster in a text column, so the lane normalizes it away.

    Measured 2026-10-30: row gh-80, imported from the board, carried the intake default
    `image,svg`; `select_article_to_queue` counted `image` as a hero, the writer put that marker
    where the lead image goes, and the studio authored a 928x1152 png for a post read at 80%
    width. The intake default is the wide pair now, and this is the backstop for a row that
    already carries the portrait ids.
    """

    def run(types):
        return _run_code_node(
            "select_article_to_queue",
            {
                "validate_categories": [
                    {"row_number": 1, "ENTRY_ID": "e1", "ASSET_TYPES": types, "ARTICLE_STATUS": ""}
                ]
            },
            [],
        )["out"][0]["json"]

    assert run("image,svg")["REQUESTED_ASSETS"] == "image_wide,svg_wide"
    assert run("image")["REQUESTED_ASSETS"] == "image_wide"
    assert run("svg")["REQUESTED_ASSETS"] == "svg_wide"
    # Normalizing collapses the pair rather than requesting both frames.
    assert run("image,image_wide")["REQUESTED_ASSETS"] == "image_wide"
    assert run("svg,svg_wide")["REQUESTED_ASSETS"] == "svg_wide"


@pytest.mark.skipif(shutil.which("node") is None, reason=NODE_REQUIRED)
def test_an_svg_asset_commits_with_an_svg_extension():
    """`image/svg+xml` split on the slash is `svg+xml`, which is not an extension.

    Every SVG asset - and now the default hero - would have committed at
    `docs/img/<slug>-svg_wide.svg+xml` with the article referencing that path.
    """
    result = _run_code_node(
        "build_commit_files",
        {
            "disambiguate_slug": [{"SLUG": "an-entry"}],
            "read_draft_for_publish": [
                {"ARTICLE_TEXT": "Opening.\n\n<!-- asset:svg_wide -->\n\n## A section\n\nBody.", "TITLE": "An Entry"}
            ],
            "read_asset_rows_for_publish": [
                {"ASSET_TYPE": "svg_wide", "STATUS": "APPROVED", "CONTENT_TYPE": "image/svg+xml"}
            ],
            "select_article_to_queue": [
                {"CATEGORIES": "Data", "ENTRY_ID": 1, "ROW_NUMBER": 1, "REQUESTED_ASSETS": "svg_wide"}
            ],
        },
    )
    paths = [f["json"]["FILE_PATH"] for f in result["out"]]
    assert "docs/img/an-entry-svg_wide.svg" in paths, paths
    assert not [p for p in paths if "+" in p], paths
    article = next(f["json"] for f in result["out"] if not f["json"]["FILE_IS_BINARY"])
    assert "](/img/an-entry-svg_wide.svg)" in article["FILE_TEXT"], "the reference is a site path"


@pytest.mark.skipif(shutil.which("node") is None, reason=NODE_REQUIRED)
def test_the_published_url_is_the_one_the_site_serves():
    """The URL is built from the title, not the entry's slug, and the host is `www.`.

    Measured 2026-10-18: run 14228 announced
    `https://alvsanand.com/blog/2026/10/18/sympozium-when-one-ai-agent-isn-t-enough/` and the
    site serves `https://www.alvsanand.com/blog/2026/10/18/sympozium-when-one-ai-agent-isnt-enough/`
    — the blog plugin slugifies the *title*, so "isn't" loses its apostrophe rather than gaining
    a hyphen, and the filename's `202610-` prefix never appears.
    """
    result = _run_code_node(
        "build_commit_files",
        {
            "disambiguate_slug": [{"SLUG": "sympozium-when-one-ai-agent-isn-t-enough"}],
            "read_draft_for_publish": [
                {
                    "ARTICLE_TEXT": "Opening.\n\n<!-- asset:svg_wide -->\n\n## A section\n\nBody.",
                    "TITLE": "Sympozium: when one AI agent isn't enough",
                }
            ],
            "read_asset_rows_for_publish": [
                {"ASSET_TYPE": "svg_wide", "STATUS": "APPROVED", "CONTENT_TYPE": "image/svg+xml"}
            ],
            "select_article_to_queue": [
                {"CATEGORIES": "OSS", "ENTRY_ID": 1, "ROW_NUMBER": 1, "REQUESTED_ASSETS": "svg_wide"}
            ],
        },
    )
    article = result["out"][0]["json"]
    day = re.search(r"^date: (\d{4}-\d{2}-\d{2})$", article["FILE_TEXT"], re.MULTILINE).group(1)
    yyyy, mm, dd = day.split("-")
    assert article["PUBLISHED_URL"] == (
        f"https://www.alvsanand.com/blog/{yyyy}/{mm}/{dd}/sympozium-when-one-ai-agent-isnt-enough/"
    ), article["PUBLISHED_URL"]


def test_one_commit_sequence_with_a_guarded_fast_forward_retry():
    names = set(_nodes())
    assert {"create_tree", "create_commit", "patch_ref"} <= names
    assert _nodes()["patch_ref"].get("onError") == "continueErrorOutput"
    # The retry re-reads the branch and rebuilds on its new head rather than force-pushing.
    assert _targets("patch_ref", 1) == ["get_base_ref_again"]
    assert "force: false" in _nodes()["patch_ref"]["parameters"]["jsonBody"]
    assert "force: false" in _nodes()["patch_ref_again"]["parameters"]["jsonBody"]
    assert _targets("patch_ref_again") == ["check_ref_retry"]
    assert _targets("check_ref_retry") == ["record_published"]


def test_the_row_categories_are_checked_before_anything_is_drafted():    # The one taxonomy copy is fetched, not restated in the node, and an unreadable file fails
    # the run rather than skipping the check.
    download = _nodes()["download_blog_categories"]["parameters"]["workflowInputs"]["value"]
    assert download["template_name"] == "datasets/blog_categories.json"
    assert download["template_vars"] == "={{ {} }}"
    code = _js("validate_categories")
    assert "known.categories" in code
    assert "throw new Error" in code
    assert _targets("pick_candidate") == ["download_blog_categories"]
    assert _targets("validate_categories") == ["read_asset_rows_for_entry"]


def test_the_asset_read_always_emits_so_a_fresh_entry_can_be_phased():
    # A fresh entry has no asset rows, and the DataTable read then emits *nothing* --
    # n8n ends the execution on an empty output, so the run stopped at this node and
    # never reached `select_article_to_queue`, which is what decides the phase. Found
    # live on 2026-10-17 (execution 13703: in=0 out=0, lastNodeExecuted this node) on
    # the first run of a QUEUE row.
    node = _nodes()["read_asset_rows_for_entry"]
    assert node["alwaysOutputData"] is True
    assert _targets("read_asset_rows_for_entry") == ["select_article_to_queue"]
    # The consumer must survive the empty item that flag emits: it treats every input
    # item as an asset row, and one with no ASSET_TYPE matches no requested type.
    assert "ASSET_TYPE" in _js("select_article_to_queue")
    assert "!hit" in _js("select_article_to_queue")


def test_every_asset_the_studio_answers_with_reaches_the_asset_rows():
    # The studio answers with one item per asset branch -- its own merge runs once per
    # branch -- so a two-type request arrives as two items carrying one asset each.
    # Reading only the first is how the svg was authored, rendered and then dropped on
    # 2026-10-17 (execution 13705): the asset rows never saw it, the publish gate found
    # `svg=MISSING`, and the run ended with no commit and no notice.
    code = _js("split_assets")
    assert "$input.all()" in code
    assert "$input.first()" not in code
    assert "flatMap" in code
    # The empty case still fails loudly rather than reaching the rows as no asset.
    assert "the studio returned no asset at all" in code


def test_the_blocked_publish_reports_instead_of_ending_the_run():
    # The gate's verdict is data and the branch on it is a node, because returning nothing
    # from the gate is how a blocked publish ended the execution as `success` with no commit
    # and no notice (execution 13705, 2026-10-17: `svg=MISSING`, the svg having never
    # reached the asset rows).
    gate = _js("if_all_assets_approved")
    assert "BLOCKED:" in gate and "BLOCKING:" in gate
    assert "return [];" not in gate
    assert _targets("if_all_assets_approved") == ["if_assets_blocked"]
    assert _targets("if_assets_blocked", 0) == ["notify_assets_blocked"]
    assert _targets("if_assets_blocked", 1) == ["read_asset_rows_for_publish"]
    # The notice is a message, not a gate: a blocked publish must not park the run on a
    # Slack wait, and nothing continues from it into the commit.
    notice = _nodes()["notify_assets_blocked"]
    assert notice["type"] == "n8n-nodes-base.slack"
    assert notice["parameters"]["select"] == "channel"
    assert notice["parameters"]["channelId"]["value"] == "C08RQNXQV3P"
    assert notice["credentials"]["slackApi"]["id"] == _nodes()["notify_asset_review"]["credentials"]["slackApi"]["id"]
    assert "BLOCKING" in notice["parameters"]["text"]
    assert _targets("notify_assets_blocked") == []


def test_the_hero_every_run_asks_for_is_the_wide_frame():
    # The hero is the wide 16:9 frame and it is animated - `svg_wide` - so a row that asks for an
    # animated type is not handed a still raster it never named. A row naming its own raster keeps
    # it. The splitter's fallback for a row that names nothing is the same wide frame.
    assert "['svg_wide', ...list]" in _js("select_article_to_queue")
    assert "'svg_wide'" in _js("split_pending_types")
    # The gate reads the set the selector derived instead of repeating the rule, so the fallback
    # exists once. See test_the_requested_set_is_derived_once_and_read_by_its_consumers.
    assert "REQUESTED_ASSETS" in _js("if_all_assets_approved")
    assert "['svg_wide', ..." not in _js("if_all_assets_approved")
    assert "'image,svg'" not in _js("split_pending_types")


def test_the_only_continue_regular_output_is_normalised_downstream():
    # A non-AI node forwards its input unchanged on failure, so the flag has to be set by a
    # following node rather than read off the failed one. `review_aspect_llm` is the aspect
    # reviewer: a failed call forwards the downloaded prompt, so `merge_aspect_findings` reads
    # only the reviewer's own `text` field and never the input, and the rest of the aspects run.
    lenient = [n["name"] for n in _doc()["nodes"] if n.get("onError") == "continueRegularOutput"]
    assert lenient == ["download_content", "review_aspect_llm"]
    assert _targets("download_content") == ["set_link_flags"]
    assert "LINK_USED" in _js("set_link_flags")
    assert _targets("review_aspect_llm") == ["merge_aspect_findings"]
    merge = _js("merge_aspect_findings")
    assert ".text || ''" in merge and "output" not in merge, (
        "the merge reads the forwarded prompt instead of the reviewer's answer"
    )


def test_the_schedule_is_declared_and_the_handler_is_this_repositorys():
    # 6.6 keeps the schedule inactive until every path has been exercised; the workflow is
    # created inactive, so that is a live state, not a field in this body.
    assert any(n["type"] == "n8n-nodes-base.scheduleTrigger" for n in _doc()["nodes"])
    handler = json.loads((WORKFLOWS / "article_content_writer_error.workflow.json").read_text(encoding="utf-8"))
    assert _doc()["settings"]["errorWorkflow"] == handler["id"], (
        "the entry point's handler must be the workflow this repository carries"
    )
    # The handler does not report to itself.
    assert "errorWorkflow" not in handler["settings"]

def test_the_link_outcome_is_recorded_and_not_only_carried():
    # The spec asks the run to record that the link content was not used, so the flag lands on
    # the draft row rather than living only in this execution.
    draft = _nodes()["store_draft"]["parameters"]["columns"]["value"]
    assert draft["LINK_USED"] == "={{ $('set_link_flags').item.json.LINK_USED }}"


def test_an_overlapping_trigger_skips_a_fresh_claim_and_recovers_a_stale_one():
    # Two runs must not work the same entry. Nothing can ask n8n whether an execution is alive,
    # so the claim's own UPDATE_DATE is the observable: fresh means someone is on it, stale
    # means the run died and the entry becomes actionable again.
    code = _js("pick_candidate")
    assert "STALE_CLAIM_HOURS" in code
    assert "Date.now() - claimedAt" in code
    assert "return false" in code


@pytest.mark.skipif(shutil.which("node") is None, reason=NODE_REQUIRED)
def test_a_stale_claim_is_resumed_before_a_fresh_row():
    """The entry in flight is finished before a new one is started.

    Row 4 was left `IN_PROGRESS` with `ARTICLE_STATUS=APPROVED` when its run was cancelled. With
    a fresh row in the sheet, QUEUE-first starts that one and leaves row 4 to the ceiling, which
    cancels it rather than completing it. The stale claim is the work a human is already waiting
    on, so it wins.
    """
    now = datetime.now(UTC)
    fresh = {"row_number": 9, "ENTRY_ID": "e9", "STATUS": "QUEUE", "TOPIC": "new",
             "UPDATE_DATE": now.isoformat()}
    stale = {"row_number": 4, "ENTRY_ID": "e4", "STATUS": "IN_PROGRESS",
             "ARTICLE_STATUS": "APPROVED", "TOPIC": "old",
             "UPDATE_DATE": (now - timedelta(hours=5)).isoformat()}
    out = _run_code_node("pick_candidate", {}, [fresh, stale])["out"]
    assert [i["json"]["ENTRY_ID"] for i in out] == ["e4"]

    # A claim inside the window still belongs to a live run and is skipped.
    live = dict(stale, UPDATE_DATE=(now - timedelta(hours=1)).isoformat())
    out = _run_code_node("pick_candidate", {}, [fresh, live])["out"]
    assert [i["json"]["ENTRY_ID"] for i in out] == ["e9"]


# --------------------------------------------------------------- the improvement pass

def test_the_three_draft_consumers_read_the_converged_draft():
    """One convergence node, or the better draft is stored and a worse one is uploaded.

    `derive_slug`, `store_draft` and `draft_to_file` used to read `execute_article_creator`
    directly. A pass that produced its draft anywhere else would leave the slug, the DataTable
    row and the reviewed file pointing at the gate-passed draft the improvement replaced.
    """
    slug = _nodes()["derive_slug"]["parameters"]["jsCode"]
    store = _nodes()["store_draft"]["parameters"]["columns"]["value"]
    draft_file = _js("draft_to_file")
    assert "$('select_final_draft').first().json.title" in slug
    assert store["ARTICLE_TEXT"] == "={{ $('select_final_draft').item.json.text }}"
    assert "$('select_final_draft').first().json.text" in draft_file
    for code in (slug, draft_file):
        assert "execute_article_creator" not in code, "a consumer still reads the sub-workflow"
    assert "execute_article_creator" not in store["ARTICLE_TEXT"]


def test_the_review_message_names_the_improvement():
    """The reviewer sees the motion: whether the draft was improved, and what the aspects said."""
    message = _nodes()["notify_article_review"]["parameters"]["message"]
    assert "select_final_draft" in message and "IMPROVED" in message
    assert "FINDINGS_SUMMARY" in message
    # the anchor the message has always carried stays, so the row is still identifiable
    assert "row_number" in message and "DRAFT_TITLE" in message


@pytest.mark.skipif(shutil.which("node") is None, reason=NODE_REQUIRED)
def test_an_improved_draft_wins_and_a_rejected_one_falls_back():
    """Precedence is resolution in one node: improved-passed, otherwise the gate-passed draft."""

    def select(item):
        return _run_code_node(
            "select_final_draft",
            {
                "build_improvement_context": [
                    {"BASE_TEXT": "Base body.", "BASE_TITLE": "Base Title", "BASE_WORD_COUNT": 2,
                     "ENTRY_ID": "e1", "AUDIENCE": "LOW"}
                ],
                "merge_aspect_findings": [{"FINDINGS_SUMMARY": "structure: 1, clarity: none, flow: none"}],
            },
            [item],
        )["out"][0]["json"]

    improved = select({"IMPROVED_TEXT": "Improved body.", "IMPROVED_TITLE": "Improved Title",
                       "WORD_COUNT": 2, "PROBLEM": ""})
    assert improved["IMPROVED"] == "IMPROVED"
    assert improved["text"] == "Improved body." and improved["title"] == "Improved Title"
    assert improved["FINDINGS_SUMMARY"].startswith("structure: 1")

    fallback = select({"IMPROVED_TEXT": "Too long.", "IMPROVED_TITLE": "Improved Title",
                       "WORD_COUNT": 99, "PROBLEM": "OVER_BUDGET: 99 words against MAX_WORDS=2"})
    assert fallback["IMPROVED"] == "FALLBACK"
    assert fallback["text"] == "Base body." and fallback["title"] == "Base Title"
    assert "OVER_BUDGET" in fallback["IMPROVEMENT_NOTE"], "the fallback hides why it fell back"

    failed = select({"error": {"message": "Max iterations (8) reached"}})
    assert failed["IMPROVED"] == "FAILED"
    assert failed["text"] == "Base body."
    assert "Max iterations" in failed["IMPROVEMENT_NOTE"]

    nothing = select({"HAS_ANY": False, "FINDINGS_SUMMARY": "structure: none, clarity: none, flow: none"})
    assert nothing["IMPROVED"] == "NONE"
    assert nothing["text"] == "Base body."


def _creator_js(name):
    creator = json.loads((WORKFLOWS / "article_creator.workflow.json").read_text(encoding="utf-8"))
    return next(n for n in creator["nodes"] if n["name"] == name)["parameters"]["jsCode"]


@pytest.mark.skipif(shutil.which("node") is None, reason=NODE_REQUIRED)
def test_the_improvement_re_check_is_the_writers_counter_with_the_same_verdicts():
    """Budget and markers are counted in code in both places, and the two counters agree.

    The check is a twin of `parse_article` because the improved draft never goes back through
    the sub-workflow's gate. Two counters that disagree would deliver a draft the drafting gate
    would have rejected, or reject one it would have accepted -- so they run on the same fixture
    and must answer the same thing.
    """
    ctx = {"MAX_WORDS": 10, "ASSET_TYPES": "svg_wide", "BASE_TITLE": "A Title", "ENTRY_ID": "e1"}

    def improved(body):
        return _run_code_node("check_improved_draft", {"build_improvement_context": [ctx]},
                              [{"output": "<article>\n" + body + "\n</article>"}])["out"][0]["json"]

    def drafted(body):
        harness_scope = {"set_workflow_vars": [{"MAX_WORDS": 10}], "main_trigger": [{"ASSET_TYPES": "svg_wide"}]}
        harness = textwrap.dedent(
            """
            const scope = %s;
            const incoming = %s;
            const $ = (n) => {
              const items = scope[n].map((json) => ({ json }));
              return { first: () => items[0], all: () => items, item: items[0] };
            };
            const $input = { all: () => incoming.map((json) => ({ json })), first: () => ({ json: incoming[0] }) };
            const $json = incoming[0];
            const fn = new Function('$', '$input', '$json', %s);
            process.stdout.write(JSON.stringify(fn($, $input, $json)));
            """
        ) % (json.dumps(harness_scope),
             json.dumps([{"output": "<article>\n" + body + "\n</article>"}]),
             json.dumps(_creator_js("parse_article")))
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as fh:
            fh.write(harness)
            path = fh.name
        try:
            done = subprocess.run(["node", path], capture_output=True, text=True, check=False)
        finally:
            Path(path).unlink()
        assert done.returncode == 0, done.stderr
        return json.loads(done.stdout)["json"]["PROBLEM"]

    fixtures = (
        "# A Title\nOpening.\n\n<!-- asset:svg_wide -->\n\n## S\nBody.",
        "# A Title\nOpening.\n\n<!-- asset:svg_wide -->\n\n## S\n<!-- asset:svg_wide -->\n\nBody.",
        "# A Title\nOpening.\n\n## S\nBody.",
        "# A Title\nOpening.\n\n<!-- asset:image_wide -->\n\n## S\nBody.",
        "# A Title\n" + "word " * 20 + "\n\n<!-- asset:svg_wide -->",
        # the counting margin's boundary: MAX_WORDS=10 allows eleven words and not twelve, in both
        "# A Title\n" + "word " * 11 + "\n\n<!-- asset:svg_wide -->",
        "# A Title\n" + "word " * 12 + "\n\n<!-- asset:svg_wide -->",
    )
    for body in fixtures:
        got = improved(body)["PROBLEM"]
        want = drafted(body)
        assert got.split(":")[0] == want.split(":")[0], (got, want)
        if got:
            assert got == want, (got, want)
    # the twin really ran: no problem for the correct fixture, a budget problem for the long one
    assert improved(fixtures[0])["PROBLEM"] == ""
    assert improved(fixtures[4])["PROBLEM"].startswith("OVER_BUDGET")
    assert improved(fixtures[1])["PROBLEM"] == "MARKERS: svg_wide x2"
    # and the margin is the same in both halves
    assert improved(fixtures[5])["PROBLEM"] == "" and drafted(fixtures[5]) == ""
    assert improved(fixtures[6])["PROBLEM"].startswith("OVER_BUDGET")
    assert drafted(fixtures[6]).startswith("OVER_BUDGET")


LEVELS = ("NONE", "LOW", "MEDIUM", "ADVANCED")


def test_the_audience_levels_agree_with_the_committed_definitions():
    """The enum is three copies by necessity: the definitions file, the graph's const and the
    board default. A new level fails here until every copy carries it (the FORMS pattern)."""
    selector = _js("select_article_to_queue")
    match = re.search(r"const AUDIENCE_LEVELS = \[(.*?)\];", selector)
    assert match, "the selector no longer holds the level enum"
    in_graph = re.findall(r"'([A-Z]+)'", match.group(1))
    assert tuple(in_graph) == LEVELS, in_graph
    definitions = (BASE / "prompts" / "article_audiences.md").read_text(encoding="utf-8")
    assert tuple(re.findall(r"^## (\S+)$", definitions, re.MULTILINE)) == LEVELS
    board = json.loads((BASE / "datasets" / "board_intake.json").read_text(encoding="utf-8"))
    assert board["defaults"]["audience"] == "NONE", "the intake default is not today's reader"


@pytest.mark.skipif(shutil.which("node") is None, reason=NODE_REQUIRED)
def test_a_blank_audience_is_the_general_reader_and_an_unknown_one_is_refused():
    def run(cell):
        return _run_code_node(
            "select_article_to_queue",
            {"validate_categories": [{"row_number": 1, "ENTRY_ID": "e1", "ASSET_TYPES": "svg_wide",
                                      "ARTICLE_STATUS": "", "AUDIENCE": cell}]},
            [],
        )["out"][0]["json"]

    assert run("")["AUDIENCE"] == "NONE"
    assert run(None)["AUDIENCE"] == "NONE"
    assert run(" medium ")["AUDIENCE"] == "MEDIUM"
    done = _run_code_node(
        "select_article_to_queue",
        {"validate_categories": [{"row_number": 1, "ENTRY_ID": "e1", "ASSET_TYPES": "svg_wide",
                                  "ARTICLE_STATUS": "", "AUDIENCE": "EXPERT"}]},
        [],
        expect_error=True,
    )
    assert done.returncode != 0, "a mistyped level was read as NONE"
    assert 'AUDIENCE "EXPERT"' in done.stderr and "ADVANCED" in done.stderr, done.stderr
