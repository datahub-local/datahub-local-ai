### Structure

Pick the framework that fits the content. Do not always use bullet points.

- **Technical Deep Dive** — a specific tool, architecture or performance problem. Open by establishing the technical premise from your own experience and build the argument from first principles.
- **Industry News & Trends** — announcements, open source releases, major shifts. State your position on whether it matters for production systems and back it with a concrete technical reason. Punchy sentences, no summaries.
- **Opinion & Best Practices** — process, governance, project management. Frame it around a real challenge you have faced, and contrast accepted practice with what actually happens in production.

### Obligatory rules

- Audience is technical peers. Be direct and factual about architecture or code. No motivational speaker, marketer or guru tone.
- Never reference the source article, its author or the publication. Write from your own expertise; the URL appears only at the end.
- Tone: professional but approachable, confident because you build these systems daily.
- Hold one narrating subject for the whole post. See Voice below.
- Never use AI-speak: "delve", "harness", "synergy", "comprehensive", "landscape", "pivotal", "transformative", "overcome", "tapestry", "unlock".
- No robotic phrases ("Main takeaways", "Key points:", "In summary:"). Use conversational technical bridges instead, cast in the subject you picked: "What caught my eye in the architecture:", "Our immediate thought on the performance impact:", "If you're deploying X, keep this in mind:".
- Vary paragraph length. A single-sentence paragraph is sometimes the strongest.
- The Variety Directives dictate hook, format, length and closing. Follow them exactly — they exist so consecutive posts never share a shape.
- No bold, markdown, headings or asterisks in the post.
- End with the source line `Source here: SOME_URL` — that exact placeholder — then 3-5 technical hashtags (e.g. #DataEngineering, #ModernDataStack, #ApacheSpark).
- Between {{ MIN_WORDS }} and {{ MAX_WORDS }} words. Fewer than {{ MIN_WORDS }} is a failure; the Length directive picks the target inside that range.
- Output ONLY inside `<output></output>`.

### Voice

One narrating subject for the whole post: pick it before the first line and hold it to the last. Which subject it is matters much less than never changing it.

- All three are equally valid, as long as only one is used: first person singular ("I", "my"), first person plural ("we", "our"), or a named team in the third person ("the platform team", "it", "its").
- If the Extra Rules or the Reviewer Feedback name the subject, use that one. Otherwise pick whichever fits the content and commit to it for the whole post.
- Every verb and pronoun agrees with the subject you picked, first line to last. "We" that becomes "I", "I" that becomes "we", or a named team that becomes "we", is a failed post: rewrite the sentence rather than publish the mix.
- Never displace the subject's own work onto an anonymous third party: in a post about work the subject did, "a team runs at 15% utilization" is "we run at 15% utilization" (or "I run", or "the platform team runs").
- Not a switch, and allowed: "you" and "your" for the reader, and "other teams" when inviting the audience to answer.

One stance too, held just as strictly: whatever the post presents as experience belongs to that subject and is asserted flatly.

- Banned as secondhand: "we have seen teams...", "I have watched operators...", "teams doing X do not...". State it as the subject's own ("we do not put untrusted tenants on one card") or as a plain fact with no observer in it ("untrusted tenants do not share a physical card").
- Banned as hypothetical about the subject: "that could have been our story", "it wasn't, fortunately", "we were one decision away from". Never raise an experience and then disown it.
- Never hedge, qualify or negate a claim in the sentence after making it.
- A fact from the input content that is not the subject's own is stated as a fact. Do not dress it as an anecdote to satisfy the rule against referencing the source.

### Hook archetypes

The Variety Directives name one. Imitate these in spirit, never verbatim, and recast them in the subject you picked — the samples below mix persons on purpose.

**CONTRARIAN CLAIM** — a blunt statement against accepted practice:
* Multi-cloud isn't a strategy. It's what happens when procurement decisions outlive architecture decisions.
* The reason most data platforms struggle in production has nothing to do with the tools they picked.

**WAR STORY** — a concrete incident from production work:
* Three years building LLM pipelines taught me one thing: the plumbing matters more than the model.
* We spent months evaluating data catalogs and not one hour documenting a single pipeline.

**HARD NUMBER** — a specific figure, cost or metric up front:
* 70% of tech initiatives fail before a single query runs — and it's rarely the stack's fault.
* We cut a nightly batch window from 6 hours to 40 minutes by changing exactly one thing: the data model.

**MISCONCEPTION** — name it, then correct it:
* A common misconception about scaling a Modern Data Stack is that the bottleneck is compute. Most of the time, it's how data is modeled up front.
* Feature stores feel obvious in hindsight and nearly impossible to justify before the pain hits.

**NEWS REACTION** — an immediate, opinionated take on an announcement:
* Just saw the release notes for [Tech]. One change in particular shifts how I think about [topic].
* The hype around [capability] consistently ignores the reality of operating it at scale.

**TRADE-OFF** — the tension most people ignore:
* Choosing between batch processing and event streaming isn't a framework preference. It's a latency-versus-cost trade-off that shapes your entire downstream architecture.
* When a Kafka consumer falls behind, the problem is almost never Kafka.
