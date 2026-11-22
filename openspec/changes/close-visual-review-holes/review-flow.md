# Review flow

## Today, as execution 17510 showed it

```mermaid
flowchart TD
    A["Composer authors and renders"] --> B["Stills: 8 uniform offsets + final frame"]
    B --> C["One vision call:<br/>all stills + the whole brief"]
    C --> D{"JSON verdict"}
    D -->|"ok"| E["STATUS: COMPLETE<br/>posted for approval"]
    D -->|"fix, round < 3"| A
    D -->|"fix, round = 3"| E
    D -->|"unreadable"| E

    style E fill:#f8d7da,stroke:#b02a37,color:#000
```

Findings have no id, no severity and no memory, so each round is a fresh opinion. A `fix`
verdict is still an approvable asset, and an empty answer is read as a pass.

## After the change

```mermaid
flowchart TD
    A["Composer authors and renders"] --> B["Adapter: hyperframes check --json<br/>layout, motion, contrast, craft"]
    B --> C["Adapter: ffmpeg signals<br/>freeze, black, cuts"]
    C --> D["Stills by detected scene<br/>+ settled frame"]
    D --> E["Critic:<br/>stills + brief + open ledger"]
    B -->|"check errors"| L[("Ledger")]
    E --> F["Critic answer:<br/>resolved ids + ranked findings"]
    F --> G["parse_verdict:<br/>merge, rank, mark seen"]
    L --> G
    G --> H{"open findings?"}
    H -->|"none"| I["NEEDS_REVIEW = false<br/>approvable"]
    H -->|"new or open,<br/>round < budget"| J["Correction brief<br/>ordered by severity"]
    H -->|"stalled or budget hit"| K["NEEDS_REVIEW = true"]
    H -->|"unreadable"| K
    J --> A
    K --> M["Slack approval names<br/>every open finding"]
    I --> N["Slack approval"]
```

## The ledger across turns

```mermaid
sequenceDiagram
    participant C as Composer
    participant V as Critic
    participant L as Ledger
    participant H as Human

    Note over L: round 0 — open: []
    C->>V: render + stills + brief
    V->>L: F1 arrow has no head (sev 1)<br/>F2 four labels (sev 2)
    L-->>C: fix F1, F2 (severity order)
    C->>V: correction render
    V->>L: resolved: F1<br/>F2 still present (seen = 2)
    Note over L: F2 is stalled
    L-->>H: NEEDS_REVIEW, F2 named
    Note over H: approving posts it anyway
```

`seen` is the number of reviews that reported the same id. A finding seen twice survived a
correction turn, so it stops spending cycles and goes to a person instead of round three.

## Connectors as data

```mermaid
flowchart LR
    D["connectors.json<br/>id, from, to, head"] --> H["HFConnectors.draw()"]
    H --> R["from.getBoundingClientRect()"]
    H --> T["to.getBoundingClientRect()"]
    R --> S["line from edge to edge"]
    T --> S
    S --> P["head placed on the target's edge"]
    H --> M["data-hf-connectors = ok / error:ids"]
    M --> G["adapter reads the settled DOM"]
```

The composer no longer computes arrow coordinates. A head cannot point at nothing because the
target's own box decides where it lands; a missing endpoint is recorded as an error instead of
rendering as a line into space.

## Where each gate runs

```mermaid
flowchart LR
    subgraph Pod["pi-render session pod"]
        R["render out.mp4"] --> K["check + ffmpeg + DOM"]
        K --> S["stills + check + signals + connectors"]
    end
    S --> W["n8n: ledger + budget"]
    W --> V["gateway: vision critic"]
    V --> W
    W --> SL["Slack approval"]
```

The pod owns what only it can see (the artifact and the browser); n8n owns the decision and its
memory; the critic only judges what a still can show.
