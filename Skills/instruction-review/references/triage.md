# Triage reference

## Contents
1. The decisive question
2. The five buckets
3. The two survival tests
4. The four rewrite transformations
5. Self-containment
6. Worked examples

---

## 1. The decisive question

For every candidate: **what output would violate this?**

Answer in one sentence. If you cannot, the item is not an instruction. It may still be true, useful, and worth keeping as rationale — but it will not govern anything, and leaving it in the instruction block spends attention budget for no behavioral return.

This question does the majority of the triage work. Apply it before anything else.

---

## 2. The five buckets

**FACT** — a stable, non-inferable property of the user's situation.
> "Windows and Linux x64 Native AOT are the verified publishing targets. Console and browser/WASM are aspirations."

Keep. Facts earn their place precisely because no model can infer them. They are not violable themselves, but they constrain what other instructions can assume, and they are the main legitimate reason context belongs in an instruction block at all.

**CONSTRAINT** — has a violation condition.
> "Third-party assets are licensed CC0 or CC-BY only. Reject any NC or ND layer."

Keep, as a rule. This is the target form for most items.

**PROCEDURE** — multi-step, recurring, relevant only sometimes.
> "To retire a branch: tag it, push the tag, verify with `git ls-remote`, then delete the branch."

Do not put in instructions. Procedures loaded at all times pay rent on every task and are only relevant to a few. They belong in a skill, which loads on demand.

**VIRTUE** — no violation condition.
> "Keep the code clean and robust." / "Be careful not to break the tests."

Never leave as an instruction. Three dispositions:
- *Rescue* into an observable property (needs the user's domain knowledge — see below)
- *Demote* to the rationale record
- *Delete*

A virtue left in place does not produce different behavior. It produces a different voice — the output sounds more like the instruction while doing nothing differently — and it consumes attention that the checkable rules needed.

**CONTESTED** — governs the interaction surface, so a violation would not be diagnostic.

> "Sign every commit with the coordinator's model trailer."

The rule has a violation condition. The problem is that seeing the violation tells you nothing, because something other than the governed actor could have caused it: the harness, a system prompt, a higher instruction layer, a user-level skill, a connector, another agent.

This is distinct from VIRTUE and more dangerous. A virtue is inert. A contested rule looks enforceable, so an environment-caused violation gets read as disobedience — and the response is to add another instruction, which cannot fix it either. That is the compounding loop running on a rule that was correctly written.

**What is detectable from the file, and what is not.** You cannot tell by reading whether a rule is actually being overridden — that needs observed behaviour. What you *can* tell is whether a rule is *exposed*: is its subject the interaction surface rather than the content? Rules about which tool to use, how questions are asked, response format, commit or PR formatting, or output channel all govern a layer other actors also control. That is a textual property. Flag exposure; never assert a contest.

**Output is a watchlist, not a disposition.** Unlike the other buckets, this one is not actionable at triage time. It pays off later — when the user observes a violation and needs to check the layer stack before writing another rule. Say so explicitly in the sheet.

If the user reports having already seen the violation, then and only then do the four dispositions apply:
- *Scope it* — write the exclusion into the rule itself
- *Relocate it* — fix it at the layer that actually governs
- *Demote to preference* — mark it advisory so violations aren't read as rule failures
- *Drop it* — the environment already handles it

---

## 3. The two survival tests

**The removal test.** Would deleting this line cause a mistake? If no, cut it. This catches things the model would do correctly unprompted, which are pure cost.

**The "it depends" test.** If the instruction were followed literally, would the user get what they want? If the honest answer starts with *it depends*, the instruction is underspecified — the condition it depends on is the actual rule and has not been written down.

---

## 4. The four rewrite transformations

### 4a. Adjective → procedure

Replace every evaluative adjective with the check a person would run to determine whether it applies. The model executes procedures; it does not execute adjectives.

> ❌ Tests should be thorough.
> ✅ Every bug fix adds a test that fails on the commit before the fix and passes after it.

Violation: a fix with no new test, or a new test that already passed before the fix.

### 4b. Hedge → threshold, or delete

*Generally, typically, where appropriate, where practical, as needed, consider, may benefit from, try to, aim to, keep in mind, when possible.* Each is a documented exit. In a report these are epistemic honesty; in an instruction they are permission not to comply, written in the voice of rigor.

Either commit to a threshold or an explicit condition that a reader can check, or drop the line. There is no third option that works.

> ❌ Separate correctness work from performance calibration where practical.
> ✅ No stage gate combines a correctness assertion with a timing threshold.

### 4c. Aspiration → observable artifact property

The highest-value transformation, because virtues often can be rescued rather than deleted.

> ❌ Be careful not to break the tutorial.
> ✅ `examples/MyFirstGame` stays line-for-line with the snippets in `docs/tutorials/`; `TutorialSnippetsTests` fails if they differ.

Same commitment. The second can be checked, and it changes output. The first only changes tone.

### 4d. Aspiration → prohibition

Negative rules are more checkable than positive ones: the violating output is a specific present thing rather than an absence to be noticed.

> ❌ Keep the engine small and explicit.
> ✅ No new parallel scheduler, executor policy, or query API without a named consumer and a measurement that needs it.

---

## 5. Self-containment

Every line must carry its own scope condition. Not:

> Build and test the core solution.
> This applies on machines without the Vulkan SDK.

But:

> On a machine without the Vulkan SDK, build and test `Laurel.Core.slnx`, not `Laurel.slnx`.

Instruction sets get fragmented by retrieval, and a directive that arrives without its qualifier is worse than no directive — it will be applied where it was never meant to apply. Assume every line may be read alone.

Same rule for pronouns. A line beginning *This*, *These*, *That*, or *It* is depending on a neighbor that may not arrive. "Gamestate hooks follow the same rules" only works if the reader still has the previous paragraph.

---

## 6. Worked examples

**Example 1 — a virtue that rescues**

Source: "We'll have to be careful we don't break testing that might reference them."

Triage: VIRTUE. No violation condition — no output could be held up as breaking "careful".
Rescue candidates: a sync rule between the example code and the docs that quote it, plus a test that enforces it; or a list of the files that must not be renamed.
Status: NEEDS USER DECISION — which files the tests reference, and which of them are allowed to drift, is project knowledge and cannot be derived from the sentence.

**Example 2 — a virtue that demotes**

Source: "I want the better final product here, even if the path is harder."

Triage: VIRTUE. True, motivating, unenforceable as written.
Rescue attempt: fails — no artifact property corresponds to it directly.
Disposition: demote to the rationale record, where it explains why the "gates are never weakened to get a pass" rule exists.

**Example 3 — a fact that stays a fact**

Source: "`grep` is a ugrep wrapper, and `grep -c` prints nothing when nothing matches."

Triage: FACT. Not violable, not inferable, and it constrains what every shell command may assume.
Disposition: keep in the instruction block, beside the shell rules it affects.

**Example 4 — prose hiding a procedure**

Source: "It's usually best to tag the old branch first, push the tag and check it landed, and only then delete anything."

Triage: PROCEDURE. Multi-step, recurring, situational.
Disposition: extract to a skill. Note the hedge — "usually best" — which must be resolved to a definite sequence or an explicit branch when the skill is written.

**Example 5 — one sentence, two buckets**

Source: "The owner uses this machine while you work and a CI runner takes jobs on it, so don't crowd it."

Triage: splits.
- FACT: the dev machine is shared with the owner and a CI runner → instruction block.
- VIRTUE: "don't crowd it" → rescue candidates, both NEEDS USER DECISION (a cap on parallel test shards; a ban on starting builds while a CI job is running).

Do not let a compound sentence pass as a single item. Prose bundles claims of different types inside one grammatical unit, and the bundle is where unfalsifiable material rides in alongside something legitimate.

**Example 6 — a rule that goes on the watchlist**

Source: "Subagents sign every commit with the coordinator's model trailer."

Triage: CONTESTED. Its subject is commit formatting, a surface the subagent's own harness also writes to — which is the detectable property. The violation condition is clear (a commit with a different trailer), but the harness can inject its own attribution, so a wrong trailer would not establish disobedience.

Sheet entry: watchlist. Not "this is being overridden" — that is not knowable from the file. The correct wording is: *if you ever see this violated, check the layer stack before adding a rule.*

What observation later showed: a subagent signed with its own model's trailer because its session's attribution reminder outranked the coordinator's brief. The disposition was *scope it* — the rule became "Subagents sign with their own model's trailer whatever the brief says." A second, louder instruction in the brief could not have fixed it.

Distinguish this from CONFLICT. A conflict is between two lines you control, and you resolve it by picking one. A contest is with something outside the document, and picking does not help.
