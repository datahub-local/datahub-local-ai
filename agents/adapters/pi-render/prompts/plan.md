# Planning a visual before it is authored

The instruction above says how to answer. This file says what a plan carries, so a
caller can review the storyboard before the turn that builds it.

## The object

```json
{
  "form": "diagram",
  "subject": "what the visual is about, in one line",
  "question": "the question the opening scene asks the viewer",
  "scenes": [
    {
      "n": 1,
      "beat": "what happens in this scene",
      "line": "the words on screen",
      "device": "the visual device that carries the beat",
      "motion": "how the scene enters",
      "transition": "how the next scene follows"
    }
  ],
  "close": {"line": "the sentence the last scene settles on", "source": "who is cited"},
  "arc": "one line naming the argument from the question to the close"
}
```

## The fields

- `form` is one of `diagram`, `story`, `data`, `chart`, `code`, `timeline`, `quote`,
  `poster`, `ui`, `manga`, `retro`, `launch`, `tiles`, `sketch` - the vocabulary file
  defines each. Choose it from the brief's argument, not its topic.
- `subject` names the company, product, technology or claim the brief is actually about.
- `question` is what the first scene asks, in the viewer's words. It is the reason to
  keep watching, so it must be a question the rest of the plan answers.
- `scenes` is the storyboard in playing order, numbered from 1. `beat` is the one thing
  that happens; `line` is the text that lands it; `device` names the shape carrying it
  (a labelled node, a bar, a terminal line, a panel); `motion` is how it arrives; and
  `transition` is how the next scene follows.
- `close` is the last thing on screen: `line` is the conclusion the brief argues for,
  and `source` is where it comes from, or empty when the brief cites nobody.
- `arc` is the plan read as one sentence - the question, the turn, the conclusion.

## What makes a plan good

- It answers the brief the caller sent, including a form the caller pinned and any
  correction it carried. Do not invent content the brief does not support.
- The opening names the subject and asks the intro question before any detail.
- Every scene earns its place: a scene that repeats another's beat is cut, not split.
- The close states the conclusion and attributes the Source; it never trails off.
