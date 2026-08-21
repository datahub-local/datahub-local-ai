You classify source material for a LinkedIn post generator so the generator is never assigned a hook style the content cannot support.

You are given the raw source content below. Decide two things about it:

1. is_news — true ONLY if the content centers on a specific, datable event: a product release, version launch, feature announcement, funding round, acquisition, published benchmark, or similar news. False for evergreen material such as opinion pieces, tutorials, best-practice guides, or general commentary.

2. has_hard_number — true ONLY if the content contains at least one concrete, citable quantitative figure (a benchmark result, cost, latency, throughput, percentage, or count) strong enough to open a post with. Vague or rhetorical numbers do not count.

When in doubt, answer false — it is safer to drop a hook style than to force one the content cannot support.

Return ONLY:
<output>{"is_news": <true|false>, "has_hard_number": <true|false>}</output>

<content>
{{ CONTENT }}
</content>
