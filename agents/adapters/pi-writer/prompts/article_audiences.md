# Audiences

Every article is written for one reader, named by its row's `AUDIENCE`. The level fixes what the article may assume; it never changes the writing rules or the length budget. A blank cell reads as `NONE`.

## NONE

Your reader is smart, busy and new to the subject — an engineer from another field, or a practitioner who has never touched this one. Write so that someone who has never seen it can follow, without writing down to them. Explaining the subject is the job; sounding impressive is not. Explain every term the first time it appears.

## LOW

Your reader knows the field and is new to this subject: a backend engineer reading about data engineering, a data engineer reading about this project. The field's basics need no introduction — name Kafka and move on — but the subject's own words do: name a custom resource, a controller, a sidecar and say what it is for. Explain what this thing adds, not what its category is.

## MEDIUM

Your reader is a practitioner in the subject's area: they work in this space, not on this project. Explain only what is specific to this thing — its own model, its own constraints, the choices that differ from what they already use. The area's basics and the usual vocabulary are assumed; spending sentences on them wastes the reader's time.

## ADVANCED

Your reader works with this daily: they know the vocabulary, the defaults and the usual failure modes. No orientation at all — no definition, no "what is X", no introduction to the category. Spend the article on the depth: the trade-offs, the internals, the numbers, and the parts that still surprise someone who uses it every day.
