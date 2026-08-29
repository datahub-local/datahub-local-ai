You classify source material for a LinkedIn post generator, so it is never assigned a hook style the content cannot support. Decide two things about the content below.

1. `is_news` — true ONLY if it centers on a specific, datable event: a product release, version launch, feature announcement, funding round, acquisition, published benchmark or similar. False for evergreen material such as opinion pieces, tutorials, best-practice guides or general commentary.
2. `has_hard_number` — true ONLY if it contains at least one concrete, citable figure (benchmark result, cost, latency, throughput, percentage, count) strong enough to open a post with. Vague or rhetorical numbers do not count.

When in doubt answer false: dropping a hook style is safer than forcing one.

Return ONLY:
<output>{"is_news": <true|false>, "has_hard_number": <true|false>}</output>

<content>
{{ CONTENT }}
</content>
