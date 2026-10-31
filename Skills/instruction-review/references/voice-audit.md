# Voice audit reference

For voice, tone, brand-voice, and style guides — material whose job is to shape how something sounds, not just what it says. The buckets, survival tests, and rewrite transformations are the same ones used elsewhere in this skill. This file covers the one place voice material behaves differently: the virtue disposition.

## Why this file exists

Ordinary instructions: a VIRTUE left in place produces a different voice, not different behavior — inert cost, no payoff, which is exactly why the standard triage disposes of every virtue (rescue, demote, delete). A voice guide inverts that. Voice is the deliverable here, not the residue. Running the standard disposition on a style guide strips out the content it exists to carry.

## Split every line into a track first

**MECHANICAL** — banned words or phrases, formatting habits, sentence-opener bans, sign-off structure, any convention with a literal violation condition. Treat exactly like an ordinary CONSTRAINT: the standard rewrite transformations and survival tests apply unchanged.

**TONE** — descriptors of feel, warmth, register, personality: "sounds like you," "warm but not chatty," "confident, not salesy." These do not get the standard VIRTUE disposition — see below.

State the track on every line in the sheet. A line can't be both, and can't be neither — if it's neither, it hasn't actually been triaged yet.

## The revised disposition for TONE lines

A TONE line with no violation condition gets one of two dispositions, not three:

- **Rescue into an example pair** — two or three sentences that hit the tone next to two or three that don't. Checkable by demonstration even though there's no single violation condition; the same technique used to teach the rules in this skill's own reference files.
- **Demote to rationale**, exactly as in ordinary triage, when no example pair captures it either.

There is no third disposition here. Do not rescue a TONE line into a numeric threshold as the default move.

## The Goodhart guard

A TONE line rescued into a number — contractions per paragraph, exclamation points per email — can be satisfied while the actual voice is missed: the writer hits the metric and still doesn't sound like anyone. This is the same failure mode this skill already refuses to run on readability scores: advisory only, never a gate. Propose a numeric rescue for a TONE line only if the user explicitly confirms that number is what they mean, and mark it NEEDS USER DECISION regardless of how they answer. A tone row never produces a proposed gate for this reason — only a mechanical row can.

## Sheet format

Every mode adds one column, `Track` (Mechanical / Tone), and nothing else:

- **AUDIT:** to the Rewrite and Cut tables in the findings sheet.
- **CONVERT and DESIGN:** to the Constraints and Cut tables in `assets/triage_sheet_template.md`, plus a Track line on every Virtue entry. DESIGN applies the same rules to a voice guide written from scratch.

## Worked example

Source: "Keep it warm and conversational, never salesy."

- MECHANICAL: nothing extractable as written — would apply if the source named actual banned words (e.g., "unlock," "leverage," "seamless").
- TONE: "warm and conversational, never salesy" — VIRTUE, no violation condition.

Rescue candidate:
> Warm: "Here's what I'd try first."
> Salesy: "Unlock your team's full potential today."

Status: NEEDS USER DECISION — the specific pair depends on the user's own sense of their voice and isn't derivable from the adjective alone.
