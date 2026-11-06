# Design

## Decision: the feedback round is the exception, not a second gate

The ledger's job is to stop the **writer** inventing a command and attributing it to a page. The
person reviewing the draft is a different authority: when they ask for `kind create cluster`, the
command they want is their knowledge, not the model's. Keeping the strict rule on a feedback round
means the only request the lane can honour is one the project's own docs happen to carry, which is
not what the person asked for.

So the exception is narrow and observable:

- it applies only when the round carries human feedback (`HAS_FEEDBACK`);
- the block is counted in `UNVERIFIED` and the count reaches the review message;
- `FIDELITY` becomes `feedback` rather than `checked`, so the provenance is on the item;
- a **ledgered** block that failed still fails. A page that did not answer, a failed dry-run and a
  drifted excerpt are defects in material the draft claims to have read, and feedback does not
  make them true.

Rejected alternative: accept any unverified block always. That restores the placeholder drafts the
authoring change removed (see `add-agent-authored-articles`), and the first draft is exactly where
invention is worst.

## Decision: an unchanged round is an outcome, not a pass

`IMPROVED_TEXT` being non-empty says the model answered, not that it applied anything. Rather than
ask the model whether it changed the draft, the code compares the returned body and title with the
ones it handed over, whitespace-normalised. Equality is `UNCHANGED`.

`select_final_draft` then keeps the base draft and reports `UNCHANGED` with "the feedback was not
applied" when the round was a feedback round. Rejected alternative: retry the improver on an
unchanged answer. The attempt bound exists to recover from a bad model call, and the observed
failure is a model obeying a rule that forbade the edit; retrying the same instruction spends calls
and changes nothing. The next human action is what decides.

## Decision: the count, not the block, reaches the reviewer

The review message already names the improvement outcome. Adding `UNVERIFIED: n` there and the
one-line note in `IMPROVEMENT_NOTE` is enough for the person to see what their feedback introduced.
A list of the blocks would duplicate the draft they can read.

## Verification

Six tests in `agents/n8n/scripts/test_article_sources.py`, red before the code:

- a feedback round accepts a block no source carries and counts it;
- a first-draft edit still rejects that block;
- a feedback round still rejects a ledgered block the page lost;
- an unchanged edit is reported as unchanged;
- an unchanged edit is not an improvement in `select_final_draft`;
- the unverified count reaches the converged draft and its note.

Prompt wording is not tested (see `testing`): the graph's behaviour is.
