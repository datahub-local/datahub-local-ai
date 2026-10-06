# Render service samples

Two content specs and the assets they produced, rendered by the live service
(`POST /render`, 1080×1350, 30 fps). They are here so the service's output can be
seen without running it, and so a change to the composition templates can be
compared against a known result.

| Spec | Layout | Asset | Duration | Frames |
| ---- | ------ | ----- | -------- | ------ |
| `flow.json` | `flow` | [`flow.mp4`](flow.mp4) · [`flow.gif`](flow.gif) | 6.0 s | 180 |
| `bars.json` | `bars` | [`bars.mp4`](bars.mp4) · [`bars.gif`](bars.gif) | 5.0 s | 150 |

The specs' `accent` values are deliberately outside the brand ramp; the service
maps a caller accent onto the nearest brand role, so the rendered samples use
brand moss rather than the accent as written. See [`../README.md#brand`](../README.md#brand).

`flow` draws its connectors and steps them one node at a time; `bars` fills each
bar proportionally to the number in the value. The GIFs are 10 fps previews of
the MP4s, not a service output format.

## Re-render a sample

```
curl -s -X POST <service>/render \
  -H 'content-type: application/json' \
  --data-binary @flow.json -o flow.mp4
```

In-cluster the service is
`http://datahub-local-core-automation-render.automation.svc.cluster.local:8080`;
from a workstation, `kubectl -n automation port-forward svc/datahub-local-core-automation-render 8080:8080`.
The service reports the file's real duration and frame count in the `X-HF-*`
response headers, so a re-render can be checked against the table above.
