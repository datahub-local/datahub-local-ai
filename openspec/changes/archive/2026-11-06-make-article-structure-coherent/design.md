# Design

## Decision: coherence is a gate check, not a code count

The defect is semantic: a step names an object the article never created. No count in a Code node can
see it, and the one count that suggests itself — heading numbering — would pass the cancelled draft,
which numbers 1 to 6 with an unnumbered close. A gate that the example passes is not a gate.

So the reviewer carries it. `article_review.md` already runs before the human sees a draft and its
explanation is what the drafting retry receives; adding four concrete checks there means an
incoherent draft is re-drafted with "step 5 uses `quickstart-demo`, which no earlier step created"
in the prompt. That is the existing retry path, not a new one.

Rejected: a structure reviewer before the drafting gate. It duplicates the gate's retry and spends a
model call on every draft, including coherent ones.

## Decision: keep numbering, make it one sequence

The owner asked for numbered sections on a retry, so numbering is wanted for walk-throughs. What went
wrong is that a numbered step held an alternative install as `### 3.1`, which reads as a required
step. The rule is sequence integrity: all steps numbered, no gap, no duplicate, no sub-step, and the
close unnumbered. An article that is not a walk-through numbers nothing.

## Decision: name continuity is the concrete rule

"Be coherent" is not actionable. "Every name a later step uses is one an earlier step created" is, it
names the failure the owner saw, and it is what stops a writer from stitching two pages' examples:
the ensemble section and the quickstart section each name their own objects, and pasting both into one
path produces a command that cannot work.

## Decision: the article's tells do not go in the shared style file

`agents/n8n/prompts/ai_speak.md` is injected into the LinkedIn lane. The tells added here are
long-form structural ones; putting them in that file would change the LinkedIn gate for a decision
made about articles. They go in `article_writer_system.md`. The article lane's own AI-speak list is
inlined there too, because the prompt now lives in the writer adapter and the image cannot fetch a
file from `agents/n8n`; the article gate reads the same rules file as `RULES`, so the drafter and the
gate still read one copy. The LinkedIn lane keeps its own list. The move is recorded in
`move-the-article-prompt-to-the-writer`.

## What was taken from the three references

- *great-writer*: one core outcome stress-tested before prose, asymmetric section weight, one
  load-bearing analogy, the swap test, and "no draft without a skeleton". The skeleton here is the
  shape; the stress test is the one-outcome line.
- *humanizer*: the structural tells — one-line closers, not-X-but-Y, staged openers, straw-man
  defences, forced triads, bold decoration, heading repeated under itself, text about the text,
  significance close.
- *Karpathy*: exact specificity over adjectives, short paragraphs, results inline rather than in a
  separate section, and a close that points forward instead of recapping. His first-person
  "I built it" is not adopted: the lane did not run the software, and a first-person claim would be a
  fabrication.

## Verification

Prompt wording is not tested (`testing`): there is no production change a test can name, and a test
over a prompt string duplicates the file. The observable outcome is the next live draft, which is
`[UNVERIFIED]` until a run.
