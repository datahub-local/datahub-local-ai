"""Guard the animated-media branch of LinkedIn Post Sharing.

The studio returns an animated infographic as a data URL, the post must carry it
only once a human has approved it, and a post must never be blocked because the
animation could not be produced. Those are properties of the graph, so they are
asserted here, offline, against the committed export.

Both copies of every graph are checked -- the exports carry their nodes twice, at
the top level and inside ``activeVersion``, and a fix applied to one copy is a
live bug.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

WORKFLOWS = Path(__file__).resolve().parents[1] / "workflows"
SHARING = WORKFLOWS / "linked_in_post_sharing.workflow.json"
TYPES = WORKFLOWS.parent / "datasets" / "visual_types.json"

ANIMATED_TYPE = "animation_linkedin_video"
GIF_TYPE = "animation_linkedin"
AGENT_TYPE = "animation"
PUBLISH = "send_2_linkedin_omImage"
VIDEO_REGISTER = "linkedin_register_video"
VIDEO_POST = "linkedin_post_video"


def _copies(path):
    """Yield (label, document) for both copies of a workflow export.

    A missing ``activeVersion`` means the live workflow is deactivated -- the
    backup would commit exactly that, and this test file says so loudly in
    ``test_the_export_has_a_published_version``; here it yields an empty graph so
    the other assertions still report what is missing instead of erroring.
    """
    data = json.loads(path.read_text())
    yield "top level", data
    yield "activeVersion", data.get("activeVersion") or {"nodes": [], "connections": {}}


def _nodes(document):
    return {node["name"]: node for node in document["nodes"]}


def _connections(document):
    return document["connections"]


def _main(connections, source):
    return (connections.get(source) or {}).get("main") or []


def _targets(connections, source, output=None):
    main = _main(connections, source)
    outputs = [main[output]] if output is not None else main
    return [edge["node"] for branch in outputs for edge in (branch or [])]


def _walk(connections, start):
    """Every node reachable from start, following every output."""
    seen, queue = set(), [start]
    while queue:
        node = queue.pop()
        for nxt in _targets(connections, node):
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    return seen


@pytest.mark.parametrize("label,document", list(_copies(SHARING)))
def test_static_rows_still_take_the_image_path(label, document):
    """A row that does not opt in must not change behaviour."""
    connections = _connections(document)
    # The text approval used to call the image creator directly; now it goes
    # through the media switch, whose other output is still the image creator.
    assert "switch_post_media" in _targets(connections, "switch_user_accept")
    assert "execute_image_creator" in _targets(connections, "switch_post_media")


@pytest.mark.parametrize("label,document", list(_copies(SHARING)))
def test_animated_rows_call_the_studio_for_the_declared_type(label, document):
    """The animation comes from the studio, asked for by type, with no frozen spec.

    Both animated opt-ins (ANIMATED and AGENT) are composer-authored, and LinkedIn
    now publishes video, so both request the ``animation_linkedin_video`` type. The
    type is fixed here rather than following POST_MEDIA: the deterministic path is
    retired, so the opt-in now only decides *whether* media is animated.
    """
    connections = _connections(document)
    nodes = _nodes(document)
    assert "execute_visual_studio" in _targets(connections, "switch_post_media")

    values = nodes["execute_visual_studio"]["parameters"]["workflowInputs"]["value"]
    assert values["ASSET_TYPES"] == ANIMATED_TYPE, "the LinkedIn branch must ask for the video type"
    # No frozen spec: a post has one media asset, so nothing needs keeping in step,
    # and a retry has to be free to re-author.
    assert values.get("SPEC_JSON") in ("", None)
    assert "FEEDBACK" in values


@pytest.mark.parametrize("label,document", list(_copies(SHARING)))
def test_the_animation_keeps_one_session_across_a_retry(label, document):
    """A retry must edit the composition it already produced, not author a new one.

    The session id is derived from the article, so it is the same on the first
    request and on the retry (one call node serves both), and it must not depend on
    the execution that produced the asset.
    """
    inputs = _nodes(document)["execute_visual_studio"]["parameters"]["workflowInputs"]
    session = inputs["value"].get("SESSION_ID")
    assert session, "the studio call must name a session so a retry continues it"
    assert "$execution" not in session, "the id must not depend on the run"
    assert "row_number" in session, "the id is derived from the article"
    assert any(f.get("id") == "SESSION_ID" for f in inputs["schema"])


@pytest.mark.parametrize("label,document", list(_copies(SHARING)))
def test_the_studio_scene_count_is_sent_as_a_string(label, document):
    """The sub-workflow's trigger declares its inputs as strings and validates them.

    The curator writes SCENES with ``String(...)``, but the sheet column is numeric, so
    the read returns a number. Execution 12971 failed at the call boundary with
    ``Invalid input for 'SCENES' [item 0]: 'SCENES' expects a string but we got '5'`` —
    before the studio's own ``normalize_input`` could stringify it. The mapping must
    coerce, or any row with a real scene count breaks the call. (The webhook and form
    paths are not schema-validated, which is why only this caller hit it.)
    """
    inputs = _nodes(document)["execute_visual_studio"]["parameters"]["workflowInputs"]
    scenes = inputs["value"]["SCENES"]
    assert "String(" in scenes, f"SCENES must be coerced to a string, got {scenes!r}"


@pytest.mark.parametrize("label,document", list(_copies(SHARING)))
def test_the_media_switch_accepts_both_opt_ins(label, document):
    """AGENT must reach the studio; a blank or STATIC row must not."""
    conditions = _nodes(document)["switch_post_media"]["parameters"]["conditions"]["conditions"]
    left = conditions[0]["leftValue"]
    assert "'ANIMATED'" in left and "'AGENT'" in left
    assert "POST_MEDIA" in left


@pytest.mark.parametrize("label,document", list(_copies(SHARING)))
def test_image_rejection_still_reaches_its_retry(label, document):
    """Routing the image approval through the media decision point must not drop
    its rejection branch.

    ``switch_user_accept_image`` now has two consumers of its approve output; its
    reject output must still reach the image's own retry form, or a rejected still
    image dead-ends and that retry node becomes unreachable.
    """
    connections = _connections(document)
    assert len(_main(connections, "switch_user_accept_image")) == 2, "both outputs stay wired"
    assert "if_video_publish" in _targets(connections, "switch_user_accept_image", 0)
    assert "notification_retry_or_cancel_image" in _targets(connections, "switch_user_accept_image", 1)


@pytest.mark.parametrize("label,document", list(_copies(SHARING)))
def test_no_node_is_orphaned(label, document):
    """A graph edit that rewires a source must not leave its old target stranded.

    Every node that is not a trigger or a sticky note must have an inbound edge;
    an orphan is a branch a person can reach in the form but that goes nowhere.
    """
    document_nodes = _nodes(document)
    inbound = set()
    for types in _connections(document).values():
        for branches in types.values():
            for branch in branches or []:
                for edge in branch or []:
                    inbound.add(edge["node"])
    orphans = sorted(
        name
        for name, node in document_nodes.items()
        if name not in inbound
        and "trigger" not in node["type"].lower()
        and "webhook" not in node["type"].lower()
        and node["type"] != "n8n-nodes-base.stickyNote"
    )
    assert orphans == [], f"nodes nothing calls: {orphans}"


@pytest.mark.parametrize("label,document", list(_copies(SHARING)))
def test_the_result_resolves_the_requested_type(label, document):
    """check_animation_result must look up the type that was asked for."""
    js = _nodes(document)["check_animation_result"]["parameters"]["jsCode"]
    assert ANIMATED_TYPE in js


@pytest.mark.parametrize("label,document", list(_copies(SHARING)))
def test_animation_is_approved_before_it_is_published(label, document):
    """Reachability: the studio's result only reaches the publish node via the gate."""
    connections = _connections(document)
    assert _walk(connections, "execute_visual_studio") >= {"check_animation_result", "presign_animation",
                                                          "animation_url", "download_animation",
                                                          "notification_sent_animation",
                                                          "notification_accept_animation",
                                                          "switch_user_accept_animation",
                                                          "if_video_publish", PUBLISH}
    # One decision point after the approval chooses the path by the asset's media type.
    assert "if_video_publish" in _targets(connections, "switch_user_accept_animation")
    assert PUBLISH in _targets(connections, "if_video_publish")
    # And the gate's rejection goes to the animation's own retry form, not the image's.
    assert "notification_retry_or_cancel_animation" in _targets(connections, "switch_user_accept_animation")


@pytest.mark.parametrize("label,document", list(_copies(SHARING)))
def test_the_result_branches_on_the_asset_not_the_run(label, document):
    """The studio's run status is PARTIAL when a requested type is unavailable."""
    js = _nodes(document)["check_animation_result"]["parameters"]["jsCode"]
    assert "RENDERED" in js
    assert "RUN_STATUS ===" not in js and "RUN_STATUS ==" not in js, "the run status is not a failure signal"
    assert "ASSET_STATUS" in js or "a.STATUS" in js


@pytest.mark.parametrize("label,document", list(_copies(SHARING)))
def test_a_failed_animation_falls_back_to_the_image_and_says_so(label, document):
    """A post is never blocked on the animation."""
    connections = _connections(document)
    failure_output = _targets(connections, "if_animation_ok")[1]
    assert failure_output == "notify_animation_failed"
    assert "execute_image_creator" in _walk(connections, "notify_animation_failed")
    # It enters the image branch *before* the image's own approval gate, so the
    # substitute is approved as an image rather than silently replacing it.
    assert "notification_accept_image" in _walk(connections, "notify_animation_failed")


@pytest.mark.parametrize("label,document", list(_copies(SHARING)))
def test_a_failed_animation_offers_one_bounded_choice(label, document):
    """The failure is reported with a choice, and the report cannot hold the post.

    An unanswered form resumes with the node's own input -- ``SlackV2.execute`` ends
    ``putExecutionToWait(waitTill); return [this.getInputData()]`` -- and this build of
    ``n8n-nodes-base`` carries no ``timedOut`` marker, so an expiry is only visible as
    the *absence* of ``data``. The branch therefore has to treat "no answer" as the
    still, which is what the bounded wait is for: an unbounded form would park the
    publish until someone answered it.
    """
    connections = _connections(document)
    nodes = _nodes(document)
    form = nodes["notify_animation_failed"]
    assert form["type"] == "n8n-nodes-base.slack"
    assert form["parameters"]["operation"] == "sendAndWait"
    assert form["parameters"]["responseType"] == "customForm"
    assert form["webhookId"], "a sendAndWait node needs a webhook to receive the answer"
    assert form.get("credentials", {}).get("slackApi"), "the form has no Slack credential"

    limit = form["parameters"]["options"]["limitWaitTime"]["values"]
    assert limit["limitType"] == "afterTimeInterval"
    assert int(limit["resumeAmount"]) > 0, "an unbounded wait holds the post"
    assert limit["resumeUnit"] in ("minutes", "hours")

    # Both answers are offered, and the actions the switch tests for are the ones the
    # form can send.
    actions = [
        option["option"]
        for field in form["parameters"]["formFields"]["values"]
        if field["fieldLabel"] == "Action"
        for option in field["fieldOptions"]["values"]
    ]
    assert len(actions) == 2
    condition = nodes["if_animation_retry"]["parameters"]["conditions"]["conditions"][0]
    assert condition["leftValue"] == "={{ $json.data.Action }}"
    assert condition["rightValue"] == actions[0], "the retry branch tests an action the form cannot send"

    # True (the retry action) re-authors; everything else -- the other answer and the
    # absent answer of an expired form -- takes the still.
    retry, still = _targets(connections, "if_animation_retry")
    assert _targets(connections, "if_animation_retry", 0) == ["build_retry_feedback"]
    assert _targets(connections, "if_animation_retry", 1) == ["execute_image_creator"]
    assert still == "execute_image_creator"
    assert retry == "build_retry_feedback"


@pytest.mark.parametrize("label,document", list(_copies(SHARING)))
def test_a_retry_carries_the_failure_reason_and_reuses_the_session(label, document):
    """A re-author is asked against the reason it failed, in the same thread.

    The reason is built by ``build_retry_feedback`` and read back by the studio node,
    so a *rejected* animation keeps passing only the reviewer's own feedback: a
    guarded read of the earlier failure would leak into a later rejection.
    """
    connections = _connections(document)
    nodes = _nodes(document)

    assert _targets(connections, "build_retry_feedback") == ["execute_visual_studio"]
    js = nodes["build_retry_feedback"]["parameters"]["jsCode"]
    assert "$('check_animation_result').last()" in js, "the reason must be the latest check"
    assert "ERROR" in js
    assert "data.Feedback" in js, "the reviewer's note is dropped"

    studio = nodes["execute_visual_studio"]["parameters"]["workflowInputs"]["value"]
    assert "build_retry_feedback" in studio["FEEDBACK"], "the failure reason does not reach the request"
    assert "build_retry_feedback').isExecuted" in studio["FEEDBACK"], (
        "the failure feedback must be read only when that branch ran"
    )
    assert "notification_retry_or_cancel_animation" in studio["FEEDBACK"], (
        "the rejection path's own feedback was replaced rather than composed"
    )
    assert studio["SESSION_ID"] == "=lips-{{ $('select_article_to_post').item.json.row_number }}"


@pytest.mark.parametrize("label,document", list(_copies(SHARING)))
def test_no_path_re_authors_a_failed_animation_without_an_answer(label, document):
    """The failure side reaches the studio only through the bounded form.

    The studio also has its own retry (a rejection), so this asserts the *new* edge
    and not the absence of the node: the only predecessor of the failure-feedback
    builder is the form's decision.
    """
    connections = _connections(document)
    assert "if_animation_ok" in [
        source
        for source, ports in connections.items()
        if any(
            edge["node"] == "notify_animation_failed"
            for branch in (ports.get("main") or [])
            for edge in (branch or [])
        )
    ], "the failure form is reachable from something other than the result check"


@pytest.mark.parametrize("label,document", list(_copies(SHARING)))
def test_the_publish_node_accepts_either_media(label, document):
    """One publish node, whose binary resolves on whichever path ran."""
    expr = _nodes(document)[PUBLISH]["parameters"]["binaryPropertyName"]
    assert "download_animation" in expr and "convert_image" in expr
    assert "isExecuted" in expr, "a node that did not run cannot be referenced directly"


@pytest.mark.parametrize("label,document", list(_copies(SHARING)))
def test_animation_retry_re_authors_and_cancel_does_not_publish(label, document):
    """Retry loops back to the studio; Cancel retires the row."""
    connections = _connections(document)
    assert "switch_user_retry_animation" in _targets(connections, "notification_retry_or_cancel_animation")
    retry, cancel = _targets(connections, "switch_user_retry_animation")
    assert retry == "execute_visual_studio"
    assert cancel == "update_status_cancelled"
    # Cancel must not reach the publish node.
    assert PUBLISH not in _walk(connections, "update_status_cancelled")


@pytest.mark.parametrize("label,document", list(_copies(SHARING)))
def test_a_cancelled_post_is_not_reported_as_an_error(label, document):
    """The cancel is the only path that posts; a failure raises instead.

    Cancel writes ``ERROR=CANCELLED``, so the notice has to name the cancel: a
    cancelled post reported as an error reads as a failure that never happened.
    A real failure must not go through this node at all -- it raises, so n8n
    records the run as an error and keeps it.
    """
    connections = _connections(document)
    for retry in ("switch_user_retry", "switch_user_retry_image", "switch_user_retry_animation"):
        assert _targets(connections, retry, 1) == ["update_status_cancelled"], retry
    assert _targets(connections, "set_error_cancelled") == ["send_error_notification"]
    assert _targets(connections, "update_status_error") == ["stop_and_error"]
    text = _nodes(document)["send_error_notification"]["parameters"]["text"]
    assert "CANCELLED" in text, "the notification does not distinguish a cancel"
    assert "Canceled" in text, "a cancelled post is still reported as an error"


def test_the_gif_type_is_still_inside_the_platform_caps():
    """The GIF type stays available and inside the cap: at most 500 frames, 36,152,320 pixels."""
    registry = json.loads(TYPES.read_text())
    entry = next(t for t in registry["types"] if t["id"] == GIF_TYPE)
    assert entry["render"] == "video"
    assert entry["format"] == "gif"
    assert entry["available"] is True

    budget = entry["budget"]
    width = budget["viewport"]
    height = round(width * 5 / 4)  # the type's aspect is 4:5
    total_pixels = budget["frames"] * width * height
    assert budget["frames"] <= 500
    assert total_pixels <= 36152320, f"{total_pixels} pixels exceeds the platform's GIF cap"


def test_the_agent_types_are_declared():
    """The LinkedIn branch asks for the video type; the GIF type remains the capped fallback."""
    registry = json.loads(TYPES.read_text())
    entry = next(t for t in registry["types"] if t["id"] == AGENT_TYPE)
    assert entry["author"] == "agent"
    assert entry["format"] == "mp4"
    assert entry["available"] is True
    assert entry.get("durationSeconds", 0) > 0

    video = next(t for t in registry["types"] if t["id"] == ANIMATED_TYPE)
    assert video["author"] == "agent"
    assert video["render"] == "video"
    assert video["format"] == "mp4"
    assert video["aspect"] == "4:5"
    assert "holdSeconds" not in video

    gif = next(t for t in registry["types"] if t["id"] == GIF_TYPE)
    budget = gif["budget"]
    width = budget["viewport"]
    height = round(width * 5 / 4)
    assert budget["frames"] <= 500
    assert budget["frames"] * width * height <= 36152320


@pytest.mark.parametrize("label,document", list(_copies(SHARING)))
def test_the_publish_choice_is_the_asset_media_type(label, document):
    """One decision point, keyed on the asset's own content type, not the type name."""
    nodes = _nodes(document)
    left = nodes["if_video_publish"]["parameters"]["conditions"]["conditions"][0]["leftValue"]
    # The media type is read from the check, not from the download: a file response
    # carries no JSON of its own, so asking the download node would always fall through
    # to the image path.
    assert "download_animation" in left and "check_animation_result" in left
    assert "CONTENT_TYPE" in left and "video/mp4" in left
    # The image and GIF path is unchanged: the same node, chosen by the same binary.
    expr = nodes[PUBLISH]["parameters"]["binaryPropertyName"]
    assert "download_animation" in expr and "convert_image" in expr
    assert nodes[PUBLISH]["parameters"]["shareMediaCategory"] == "IMAGE"


@pytest.mark.parametrize("label,document", list(_copies(SHARING)))
def test_a_video_asset_takes_the_api_path(label, document):
    """The node cannot upload video, so a video goes through the LinkedIn API directly."""
    connections = _connections(document)
    nodes = _nodes(document)
    assert _walk(connections, "if_video_publish") >= {
        "linkedin_video_register_request",
        VIDEO_REGISTER,
        "linkedin_video_upload",
        "linkedin_video_post_body",
        VIDEO_POST,
        "linkedin_video_urn",
        "send_published_notification_a",
    }
    # registerUpload, then the signed PUT, then ugcPosts as VIDEO.
    assert "registerUpload" in nodes[VIDEO_REGISTER]["parameters"]["url"]
    assert "uploadUrl" in nodes["linkedin_video_upload"]["parameters"]["url"]
    assert "binaryData" == nodes["linkedin_video_upload"]["parameters"]["contentType"]
    body = nodes["linkedin_video_post_body"]["parameters"]["jsCode"]
    assert "shareMediaCategory: 'VIDEO'" in body
    assert "ugcPosts" in nodes[VIDEO_POST]["parameters"]["url"]
    # The published link resolves from whichever path ran.
    assert "linkedin_video_urn" in nodes["send_published_notification_a"]["parameters"]["text"]
    assert "linkedin_video_urn" in nodes["update_status_published_a"]["parameters"]["columns"]["value"]["LINKEDIN_URL"]


@pytest.mark.parametrize("label,document", list(_copies(SHARING)))
def test_the_video_api_nodes_carry_the_linkedin_credential(label, document):
    """n8n refuses to publish a workflow with unconfigured nodes."""
    nodes = _nodes(document)
    for name in (VIDEO_REGISTER, VIDEO_POST):
        creds = nodes[name].get("credentials") or {}
        assert "linkedInOAuth2Api" in creds, f"{label}: {name} has no LinkedIn credential"
        assert nodes[name]["parameters"]["authentication"] == "predefinedCredentialType"


CREDENTIALS = {
    "n8n-nodes-base.slack": "slackApi",
    "n8n-nodes-base.googleSheets": "googleSheetsOAuth2Api",
    "n8n-nodes-base.linkedIn": "linkedInOAuth2Api",
}


@pytest.mark.parametrize("label,document", list(_copies(SHARING)))
def test_every_node_that_needs_a_credential_has_one(label, document):
    """n8n refuses to publish a workflow with unconfigured nodes.

    Adding the animated branch without its four Slack credentials left the
    workflow unable to be re-activated: "Cannot publish workflow: 4 nodes have
    configuration issues ... Missing required credential: slackApi". A PUT that
    only edits the draft leaves the workflow running its previous version, so
    this is invisible until something republishes it -- and then the scheduled
    entry point is deactivated instead. Cloning a node's parameters is not
    cloning the node.
    """
    missing = []
    for node in document["nodes"]:
        credential = CREDENTIALS.get(node["type"])
        if credential and credential not in (node.get("credentials") or {}):
            missing.append(f"{node['name']} ({node['type']})")
    assert not missing, f"nodes without their required credential: {missing}"


def test_the_export_has_a_published_version():
    """The published graph is what runs, and a deactivated workflow has none.

    Adding the animated branch without its Slack credentials made n8n refuse to
    publish, which left the workflow deactivated until the credentials were
    applied. A backup taken in that window would have committed
    ``"activeVersion": null`` -- an export that looks fine until you notice the
    schedule runs nothing.
    """
    data = json.loads(SHARING.read_text())
    assert data.get("activeVersion"), (
        "the sharing export carries no activeVersion: the live workflow is deactivated "
        "and nothing it triggers would run"
    )
    assert data.get("active"), "the export says the workflow is inactive"


@pytest.mark.parametrize("label,document", list(_copies(SHARING)))
def test_the_animation_is_located_by_key_and_downloaded(label, document):
    """The studio no longer carries the render, so the publish path signs and fetches it.

    A data URL here would mean the studio had gone back to carrying a 60 MB asset in
    its own execution record, and the store call would have no reason to exist.
    """
    nodes = _nodes(document)
    js = nodes["check_animation_result"]["parameters"]["jsCode"]
    assert "S3_KEY" in js and "a.IMAGE" not in js
    assert "temp_retrieve" in nodes["presign_animation"]["parameters"]["jsonBody"]
    assert "check_animation_result" in nodes["presign_animation"]["parameters"]["jsonBody"]
    assert "URL" in nodes["animation_url"]["parameters"]["jsCode"]
    download = nodes["download_animation"]
    assert download["type"] == "n8n-nodes-base.httpRequest"
    assert download["parameters"]["options"]["response"]["response"]["outputPropertyName"] == "data"
    assert "$json.URL" in download["parameters"]["url"]


@pytest.mark.parametrize("label,document", list(_copies(SHARING)))
def test_a_post_failure_reports_its_reason(label, document):
    """Without ``errorType`` the node throws a generic stop and the reason is lost."""
    stop = _nodes(document)["stop_and_error"]
    assert stop["parameters"].get("errorType") == "errorMessage"
    assert "$json.ERROR" in stop["parameters"]["errorMessage"]


def _eval_expression(expression, cell):
    """Run an n8n expression body with ``$()`` stubbed to one sheet row."""
    body = expression.strip()
    assert body.startswith("={{") and body.endswith("}}"), expression
    body = body[3:-2]
    script = (
        "const $ = () => ({ item: { json: { MAX_WORDS: process.argv[1] } } });\n"
        f"process.stdout.write(JSON.stringify({body}));\n"
    )
    done = subprocess.run(["node", "-e", script, cell], capture_output=True, text=True, check=False)
    assert done.returncode == 0, f"{expression} threw on {cell!r}: {done.stderr.strip()[:300]}"
    return json.loads(done.stdout)


@pytest.mark.parametrize("label,document", list(_copies(SHARING)))
def test_a_prose_max_words_cell_falls_back_instead_of_failing_the_run(label, document):
    """``MAX_WORDS`` is a person's cell, and ``.toNumber()`` throws on prose.

    Row 126 of ``content_queue`` was hand-queued with a column shift, so the cell
    held an instruction; ``toNumber()`` raised ``cannot convert to number`` and the
    ``|| 300`` beside it could never run, because the throw happens first
    (execution 15351, 2026-10-30).
    """
    value = _nodes(document)["execute_post_creator"]["parameters"]["workflowInputs"]["value"]
    expression = value["MAX_WORDS"]
    assert _eval_expression(expression, "Use the five questions as the spine.") == 300
    assert _eval_expression(expression, "") == 300
    assert _eval_expression(expression, "1200") == 1200
