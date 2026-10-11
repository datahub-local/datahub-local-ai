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
    for source, types in _connections(document).items():
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
    assert _walk(connections, "execute_visual_studio") >= {"check_animation_result", "convert_animation",
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
    assert "convert_animation" in left and "CONTENT_TYPE" in left and "video/mp4" in left
    # The image and GIF path is unchanged: the same node, chosen by the same binary.
    expr = nodes[PUBLISH]["parameters"]["binaryPropertyName"]
    assert "convert_animation" in expr and "convert_image" in expr
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
