# Design

## Context

See `proposal.md` for the gap and `specs/visual-studio/spec.md` for the behaviour
contract. Everything below was read off this repository's own exports and tests; each
path and line is where the claim comes from, because the whole change turns on which
copies of the vocabulary exist and which branch reads which field.

- `linked_in_post_sharing.workflow.json`, node `execute_visual_studio`, sends exactly
  `CONTENT` (`$('execute_post_creator').item.json.text`), `ASSET_TYPES`
  (the literal `animation_linkedin_video`), `FEEDBACK`, `FORCE`
  (`$('select_article_to_post').item.json.VISUAL_FORM || 'auto'`), `SCENES` and
  `SESSION_ID` (`lips-<row_number>`). No `EXTRA_PROMPT`.
- The same workflow's `check_animation_result` locates the asset by name:
  `const want = 'animation_linkedin_video'`, then `STATUS === 'RENDERED' && S3_KEY`.
  The type name is therefore a consumer contract, not only a registry id.
- `visual_studio.workflow.json`, node `normalize_input`: line 8 holds
  `const FORCES = ['auto', 'diagram', …, 'launch']`; lines 9-10 throw
  `unknown FORCE: <value> (expected one of …)` for anything outside it.
- `visual_studio.workflow.json`, node `parse_registry`: line 17 carries
  `FORM: t.form || ''` onto each asset, so a type's declared form travels with the
  request.
- `visual_studio.workflow.json`, node `build_author_brief`: line 31 is
  `const force = String(a.FORM || req.FORCE || 'auto')` — the type's form is honoured
  ahead of the caller's, which is the behaviour the spec never stated. Line 24 accepts
  `mp4` in its format whitelist, and line 62 samples only `gif`/`webp`, so a new mp4 type
  needs nothing new in the brief.
- `content_feed_curator.workflow.json`, nodes `parse_judge` and `parse_judge_backfill`:
  each holds `const FORMS = ['auto', 'diagram', …, 'launch']` — two more copies of the
  same enum, pre-clamped so the judge cannot write a value the studio would refuse.
- The three copies are asserted equal to `prompts/visual_forms.md` offline:
  `test_hook_registry.py::_forms()` reads `normalize_input`'s `const FORCES`, and
  `test_the_form_vocabulary_is_one_file` compares it with the vocabulary file and with
  both curator arrays; `test_visual_studio_graph.py` asserts the studio half again.
- `test_visual_studio_registry.py::test_the_registry_declares_the_expected_types`
  asserts the id list **exactly and in order**, so a new type fails that case until it is
  added — which is the point. `test_a_type_may_pin_the_form_it_means` already reads
  `svg_wide`'s `form` and asserts it is one the vocabulary defines, so a misspelled form
  is caught offline rather than reaching the composer as prose.
- `test_every_animated_video_declares_the_floor_and_a_scene_minimum` is parametrized
  over three named ids (`animation`, `animation_linkedin_video`, `deck`), so a new mp4
  type is **not** automatically bound by the 30 s floor — D4 is a deliberate choice, and
  the change adds its own assertion rather than inheriting one.
- `openspec/specs/visual-studio/spec.md`: the registry requirement (lines 9-23) lists
  nine types and omits `image_wide` and `svg_wide`; the trigger requirement (lines 61-78)
  enumerates `FORCE` without `tiles`; and no requirement anywhere covers a type pinning
  its form, although `build_author_brief:31` implements it and `svg_wide` relies on it.

## Gate findings

- **The automated lane cannot carry free text to the studio.** Verified from the export
  above: six inputs, and `EXTRA_PROMPT` is not one of them. `Visual Studio Test` carries
  none either, so the ad-hoc route is the studio's own `/webhook/visual-studio`. A form
  is the only channel that reaches the composer on the publishing lane.
- **Adding a form is not a prompt push.** The vocabulary is duplicated into the graph in
  three places (Context), so this change is a registry edit *and* a graph edit *and* a
  live apply. The wording in the repository's own notes — that the registry and the
  prompts are live on push — is true of the *definitions* and not of the enum.
- **A missed copy fails loudly, twice over.** `normalize_input` throws naming the value,
  and the curator's arrays are pre-clamped, so a row set to `tiles` before the apply
  fails rather than silently producing a default-shaped asset. The offline tests catch
  the omission before either.
- **The type name is load-bearing in a branch.** `check_animation_result` matches
  `animation_linkedin_video` by name, which is why the feed keeps that type and takes the
  look from `VISUAL_FORM` (D5) rather than gaining a new type name.
- **The registry's own spec is out of date.** `image_wide`/`svg_wide` and the form
  precedence are implemented and unspecified; this change corrects both in its delta
  rather than adding a third undocumented behaviour beside them.

## Goals / Non-Goals

**Goals:**
- Make a generative-pattern look requestable as a form, on both the studio's own webhook
  and the publishing lane, with no new node and no new parameter.
- Make it requestable as an asset type for a caller that wants the frame fixed.
- Keep one vocabulary: the definition in one committed file, the enum consistent across
  the graph, asserted offline.

**Non-Goals:**
- Repointing `linked_in_post_sharing` to a new type name, or changing
  `check_animation_result`.
- Adding a colour, a typeface or any other brand value; the referenced preview's palette
  is not adopted (D7).
- Taking a dependency on OpenDesign, `html-video`, or their template gallery. Their
  gallery is a catalog of upstream HyperFrames `registry/examples` forks and per-template
  manifests; it is a discovery surface, and none of it is needed to author this look.
- Teaching the composer a composition template. The form is a definition; the composition
  is the composer's, as every other form is.

## Decisions

### D1. Two levers, split by what each can express

The look is a **form** (`tiles`), chosen per request and per row; the frame is a **type**
(`tiles`/`tiles_wide`), chosen by a caller. A node, a parameter or a per-request template
would restate the vocabulary in the graph, which the `visual-studio` spec's form-vocabulary
requirement forbids, and would give the composer a second place to be told what shape to
build.

*Alternatives considered:* an `EXTRA_PROMPT`-only recipe — rejected, it does not exist on
the publishing lane and it is not a durable definition. A new hook with `visual.form:
tiles` — rejected for now: the hook registry classifies the *subject* an article is about,
and this is a *shape*, so a hook would pin one look to one intent class (see open
questions).

### D2. The name is `tiles`

It has to read as `FORCE=tiles`, as a `VISUAL_FORM` cell, and as `visual_types.json`'s
`form` value. `truchet` names the inventor's construction rather than what is built;
`pattern` is too broad to distinguish from `retro`'s pixel grid; `generative` names the
method, not the picture. The vocabulary's own rule is "build the definition, not the
name", and `tiles` is what the composer builds.

### D3. Two ids, a wide pair, not one type for all video

A registry type declares one frame, and the wide pair is the established shape
(`image`/`image_wide`, `svg`/`svg_wide`). One id cannot serve a 4:5 feed post and a 16:9
hero, and a caller that wants the feed's frame must not have to be handed a viewport it
then crops.

Declared values:

| id | aspect | viewport | format | fps | frames | durationSeconds | secondsPerScene |
|---|---|---|---|---|---|---|---|
| `tiles` | `4:5` | 1080 | mp4 | 30 | 360 | 12 | *(none)* |
| `tiles_wide` | `16:9` | 1280 | mp4 | 30 | 360 | 12 | *(none)* |

Both are `author: agent`, `render: video`, `brandKind: diagrammatic`, `form: tiles`,
`available: true`.

### D4. A tiling has no scenes, and 12 s is its length

A pattern loop is not a sequence: there is no per-scene floor to give, and a caller's
`SCENES` must not stretch it into three panels. So neither type declares
`secondsPerScene`, following the GIF type's precedent (which declares none for the
platform's cap rather than for shape). The 30 s floor in the registry test belongs to the
story-shaped types; frames follow the declared rate, so the clip's length is a data value
that a future tuning changes without an image change.

12 s: long enough for a staggered draw-on across a field plus a readable hold of the HUD,
short enough that the screenshot-capture render stays cheap. It is the value most likely
to be revised, and it is one registry field.

*Alternatives considered:* 30 s to match `animation` — rejected, the floor is a story
requirement and 900 frames of a tiled field buys nothing. Declaring `secondsPerScene` —
rejected, see above.

### D5. The feed keeps its type and takes the look from the row

`animation_linkedin_video` stays the requested type on the publishing lane; the row's
`VISUAL_FORM=tiles` becomes `FORCE=tiles` on the request the lane already makes. The type
name is matched by name in `check_animation_result`, so repointing the lane would be a
graph edit whose failure mode is "the branch looks for an asset the run did not produce",
and it would buy nothing: the look arrives through `FORCE` either way.

The new ids are for a caller that chooses the frame — the studio's own webhook, and
`Visual Studio Test`.

### D6. Adding a form is a registry + graph change, applied

`prompts/visual_forms.md` gains the definition; `normalize_input`'s `FORCES`,
`parse_judge`'s `FORMS` and `parse_judge_backfill`'s `FORMS` gain the name. The exports are
the backup's output, so the graph half is live only after a field-level apply, guarded by
`--require-edge` and read back. The offline tests assert the four lists agree, so the
omission is caught before the apply and the run-time failure is loud rather than silent.

### D7. The brand owns the palette

The reference preview is another product's artwork and its green is that product's
palette. A `tiles` asset is a diagrammatic type: it uses `brand.json`'s dark or light
scheme and the brand's typefaces, and this change adds neither a colour nor a typeface.
Reaching that exact green would be a brand edit under `test_brand.py`'s single-copy rule,
and it is out of scope.

### D8. The spec drift is corrected here, not deferred

The delta restates the registry requirement with `image_wide`, `svg_wide` and the tiling
pair, states the trigger contract's enum with `tiles`, and adds the missing requirement
that a type may pin the form it means. A spec that under-describes current behaviour
cannot gate a change to that behaviour, and the two omissions were both found by reading
the code this change touches.

## Risks

- **The graph edit is an apply against a running automation.** A `PUT` is field-level and
  the workflow is re-activated only if `active` flips, but an activation attempt that
  fails validation leaves the workflow deactivated (the repository has been bitten by
  this). Mitigation: `--set` on the three code nodes only, `--require-edge` guards for the
  edges the change assumes, a dry run first, then re-read `activeVersion`, confirm
  `active`, and diff the export against live.
- **A pattern look is only as good as the definition.** The form's text is prose and the
  picture is the only test; a generic grid would satisfy the words and miss the visual.
  The composer's `STORYBOARD` report names the form it used, which is what makes a bad
  first run diagnosable.
- **`tiles` pinned on a type is a variety cost, deliberately.** A caller that requests
  `tiles` for everything stops getting the composer's own choices — that is what pinning a
  form means, and why the general animated types are left alone.
- **12 s may be wrong.** It is the value most likely to be revised; it is a registry
  field, not an image.

## Open questions

- **Whether a hook should pin `tiles`.** Deliberately not done: hooks classify subjects,
  and this is a shape. `[UNVERIFIED]` whether the judge ever picks `tiles` unprompted; the
  look is reachable by `FORCE` and by a `VISUAL_FORM` cell regardless, which is what the
  change is for.
- **Whether the HUD's counters read as content or as decoration.** The preview carries a
  timecode, a frame count, a tile count and a tempo; the definition names the naming of
  the pattern and its seed and leaves the rest to the composer under the existing rules
  (seed literal, no clock, single paused timeline). `[UNVERIFIED]` until a live run.
- **Whether a 4:5 frame needs a different tile count than 16:9** to read at the same
  density. A form-level question the composer answers; not a registry field.
- **Whether the composer honours the deterministic seed visibly** — the same seed
  producing the same field across two runs is the property the authoring contract asks
  for, and it has not been measured for this form. `[UNVERIFIED]`.

## Definition of done

- `openspec validate --all` passes with this change present.
- `prompts/visual_forms.md` defines `tiles`; the three graph arrays name it; the offline
  vocabulary tests pass; and `test_visual_studio_registry.py`'s id-list case fails without
  `tiles`/`tiles_wide` and passes with them, with a new case holding their form, duration
  and frame arithmetic.
- The studio serves the form end to end: a request with `ASSET_TYPES=tiles_wide` and
  `FORCE=tiles` renders an mp4 whose brief names the form and carries the vocabulary, and
  the run's `STORYBOARD` names the form it used.
- The graph is applied and live: both workflows re-read, `active` confirmed, the export
  diffed against live, and a `VISUAL_FORM=tiles` row reaches the composer with
  `FORCE=tiles`.
- Every `[UNVERIFIED]` above is either resolved or still marked as such.
