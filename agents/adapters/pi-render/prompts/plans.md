# Offering storyboards for one form

The instruction above says how to answer, and the plan method beside this file defines the
plan object. This file says what an option carries, so a caller can choose a storyboard
before it pays for the render.

## The object

```json
{
  "options": [
    {
      "id": "mechanism",
      "plan": {
        "form": "diagram",
        "subject": "what the visual is about, in one line",
        "question": "the question the opening scene asks the viewer",
        "scenes": [],
        "close": {"line": "the sentence the last scene settles on", "source": "who is cited"},
        "arc": "one line naming the argument from the question to the close"
      }
    }
  ]
}
```

## The fields

- `id` is a short, unique name for the option, so a critic can name it back.
- `plan` is the whole plan object the plan method defines; it is not a summary of one.
- Every option uses the form the caller chose. An option that plans another form is not an
  option for this request.

## What makes an option good

- The options are different **storyboards** of the same subject: a different opening
  question, a different order of beats, a different close. Rephrasing one storyboard is one
  option, not three.
- Each option is complete enough to render from: every scene carries its beat, line,
  device, motion and transition, and the close carries its Source.
- One option may be bolder than another, but none may claim more than the content states.
  A storyboard that needs a fact the brief does not carry is not an option.
