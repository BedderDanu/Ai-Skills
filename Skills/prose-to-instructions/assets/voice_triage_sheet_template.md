# Voice triage: <source document name>

**Source:** `<path>` — unmodified, kept as rationale record
**Extracted:** N candidates → N mechanical, N tone → N survive as instructions, N → skills, N cut

> This is a review document, not an instruction block. Nothing here is
> installed. Approve rows individually; rows marked NEEDS USER DECISION
> cannot be resolved without your knowledge of your own voice.

---

## Needs user decision (N)

Numbered: one line of context per decision and the section it comes from. Where a whole section is mostly decisions (Virtues, Contradictions), one entry names it and its count.

1. 

---

## Facts — proposed for the instruction block

Stable properties of your situation that no model can infer.

| # | Proposed line | From (source ¶) | Keep? |
|---|---------------|-----------------|-------|
| F1 | | | |

---

## Constraints — proposed for the instruction block

| # | Proposed line | Track | Violation condition | From | Keep? |
|---|---------------|-------|----------------------|------|-------|
| C1 | | Mechanical | *what output would break this* | | |

Proposed order (highest-stakes first):
1.
2.

---

## Procedures — proposed as skills

| # | Procedure | Trigger | Proposed skill name | Build? |
|---|-----------|---------|---------------------|--------|
| P1 | | | | |

---

## Virtues — NEEDS USER DECISION

No violation condition as written. Every row is tracked Mechanical or Tone, and the rescue shape differs by track:

- **Mechanical virtue** (an adjective with no violation condition — "keep it professional"): rescue into a checkable threshold or property, same as ordinary triage.
- **Tone virtue** (a feel/register descriptor — "sound warm"): rescue into an example pair, not a threshold. A numeric proxy is proposed only if you explicitly confirm it's what you mean — see the Goodhart guard in `voice-audit.md`.

Choose per row: **rescue as proposed / rescue differently / demote to rationale / delete.**

### V1 — "<original text>"
- **Track:** Mechanical / Tone
- **Why it fails:** no output could be held up as breaking this
- **Rescue candidate:** *<threshold, if Mechanical>* or *<example pair, if Tone>*
- **Would be violated by / distinguished by:** <specific output, or the contrast between the pair>
- **What I'd need from you:** <the missing specifics>
- **Your call:**

---

## Watchlist

Rules whose subject is the interaction surface rather than the content — unchanged from the base template regardless of track.

| # | Rule | Layer that could also control this |
|---|------|------------------------------------|
| W1 | | |

---

## Cut

| Text | Track | Bucket | Why cut |
|------|-------|--------|---------|
| | | | *redundant with default behaviour / no violation condition and no rescue / duplicate of #X* |

---

## Contradictions found

| Items | The conflict | NEEDS USER DECISION |
|-------|--------------|---------------------|

---

## Proposed gates

**Structural (hard fail)** — mechanical-track rows only:

| Gate | What it checks | Config key |
|------|-----------------|------------|

**Advisory (never blocks)**:

| Signal | What it surfaces |
|--------|-------------------|

A tone row never produces a row in either table above. If a tone row is tempting you toward a gate — a "voice compliance score," a contraction count — that's the Goodhart guard, not a real gate; take it back to the Virtues section instead.

---

## Assembly

Once rows are approved: Facts (in order), then Constraints (in order) into the instruction block. Procedures go to skills. Mechanical-track rescues that were thresholds go in as constraints. Tone-track example pairs go to the knowledge file as calibration material, not into a hard instruction line.

I'll assemble it on request — as a separate step, after your decisions.
