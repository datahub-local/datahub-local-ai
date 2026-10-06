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
from pathlib import Path

import pytest

WORKFLOWS = Path(__file__).resolve().parents[1] / "workflows"
SHARING = WORKFLOWS / "linked_in_post_sharing.workflow.json"
TYPES = WORKFLOWS.parent / "datasets" / "visual_types.json"

ANIMATED_TYPE = "diagram_animated_linkedin"
AGENT_TYPE = "diagram_agent"
PUBLISH = "send_2_linkedin_omImage"


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

    Two opt-ins share the branch: ANIMATED asks for the deterministic type,
    AGENT asks for the agent-authored type. The asset type is an expression over
    POST_MEDIA, so both must appear and the deterministic one must remain the
    default for a row that is not AGENT.
    """
    connections = _connections(document)
    nodes = _nodes(document)
    assert "execute_visual_studio" in _targets(connections, "switch_post_media")

    values = nodes["execute_visual_studio"]["parameters"]["workflowInputs"]["value"]
    asset_types = values["ASSET_TYPES"]
    assert "POST_MEDIA" in asset_types, "the requested type must follow the row's opt-in"
    assert AGENT_TYPE in asset_types, "AGENT must request the agent-authored type"
    assert ANIMATED_TYPE in asset_types, "the deterministic type must stay the default"
    # No frozen spec: a post has one media asset, so nothing needs keeping in step,
    # and a retry has to be free to re-author. An unset field is omitted from
    # workflowInputs.value while its definition stays in `schema`, so an absent key
    # is the same statement as an empty one.
    assert values.get("SPEC_JSON") in ("", None)
    assert "FEEDBACK" in values


@pytest.mark.parametrize("label,document", list(_copies(SHARING)))
def test_the_media_switch_accepts_both_opt_ins(label, document):
    """AGENT must reach the studio; a blank or STATIC row must not."""
    conditions = _nodes(document)["switch_post_media"]["parameters"]["conditions"]["conditions"]
    left = conditions[0]["leftValue"]
    assert "'ANIMATED'" in left and "'AGENT'" in left
    assert "POST_MEDIA" in left


@pytest.mark.parametrize("label,document", list(_copies(SHARING)))
def test_the_result_resolves_the_requested_type(label, document):
    """check_animation_result must look up the type that was asked for, not a fixed one."""
    js = _nodes(document)["check_animation_result"]["parameters"]["jsCode"]
    assert AGENT_TYPE in js and ANIMATED_TYPE in js
    assert "POST_MEDIA" in js


@pytest.mark.parametrize("label,document", list(_copies(SHARING)))
def test_animation_is_approved_before_it_is_published(label, document):
    """Reachability: the studio's result only reaches the publish node via the gate."""
    connections = _connections(document)
    assert _walk(connections, "execute_visual_studio") >= {"check_animation_result", "convert_animation",
                                                          "notification_sent_animation",
                                                          "notification_accept_animation",
                                                          "switch_user_accept_animation", PUBLISH}
    assert PUBLISH in _targets(connections, "switch_user_accept_animation")
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
    assert failure_output == "notify_animation_fallback"
    assert "execute_image_creator" in _walk(connections, "notify_animation_fallback")
    # It enters the image branch *before* the image's own approval gate, so the
    # substitute is approved as an image rather than silently replacing it.
    assert "notification_accept_image" in _walk(connections, "notify_animation_fallback")


@pytest.mark.parametrize("label,document", list(_copies(SHARING)))
def test_the_publish_node_accepts_either_media(label, document):
    """One publish node, whose binary resolves on whichever path ran."""
    expr = _nodes(document)[PUBLISH]["parameters"]["binaryPropertyName"]
    assert "convert_animation" in expr and "convert_image" in expr
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


def test_the_declared_type_is_inside_the_platform_caps():
    """GIF, at most 500 frames, at most 36,152,320 pixels in total."""
    registry = json.loads(TYPES.read_text())
    entry = next(t for t in registry["types"] if t["id"] == ANIMATED_TYPE)
    assert entry["render"] == "animated"
    assert entry["format"] == "gif"
    assert entry["available"] is True

    budget = entry["budget"]
    width = budget["viewport"]
    height = round(width * 5 / 4)  # the type's aspect is 4:5
    total_pixels = budget["frames"] * width * height
    assert budget["frames"] <= 500
    assert total_pixels <= 36152320, f"{total_pixels} pixels exceeds the platform's GIF cap"


def test_the_agent_type_is_declared_and_inside_the_caps():
    """A GIF produced by the agent, with the same platform cap as the deterministic one."""
    registry = json.loads(TYPES.read_text())
    entry = next(t for t in registry["types"] if t["id"] == AGENT_TYPE)
    assert entry["author"] == "agent"
    assert entry["format"] == "gif"
    assert entry["available"] is True
    assert entry["specTemplate"] is None, "the agent takes the brief, not a content spec"
    assert entry.get("durationSeconds", 0) >= 10

    budget = entry["budget"]
    width = budget["viewport"]
    height = round(width * 5 / 4)
    assert budget["frames"] <= 500
    assert budget["frames"] * width * height <= 36152320


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
