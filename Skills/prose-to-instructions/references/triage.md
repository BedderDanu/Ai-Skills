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
> "Many upperclassmen are at a 7th–8th grade math level."

Keep. Facts earn their place precisely because no model can infer them. They are not violable themselves, but they constrain what other instructions can assume, and they are the main legitimate reason context belongs in an instruction block at all.

**CONSTRAINT** — has a violation condition.
> "No handout exceeds two pages."

Keep, as a rule. This is the target form for most items.

**PROCEDURE** — multi-step, recurring, relevant only sometimes.
> "When building a lesson: check the standard, draft the task, write the worked example, then generate the exit ticket."

Do not put in instructions. Procedures loaded at all times pay rent on every task and are only relevant to a few. They belong in a skill, which loads on demand.

**VIRTUE** — no violation condition.
> "Be equity-aware." / "Materials should be engaging."

Never leave as an instruction. Three dispositions:
- *Rescue* into an observable property (needs the user's domain knowledge — see below)
- *Demote* to the rationale record
- *Delete*

A virtue left in place does not produce different behavior. It produces a different voice — the output sounds more like the instruction while doing nothing differently — and it consumes attention that the checkable rules needed.

**CONTESTED** — governs the interaction surface, so a violation would not
be diagnostic.

> "Never use the multiple-choice widget."

The rule has a violation condition. The problem is that seeing the
violation tells you nothing, because something other than the governed
actor could have caused it: the surface, a higher instruction layer, an
account-level skill, a connector, a collaborator.

This is distinct from VIRTUE and more dangerous. A virtue is inert. A
contested rule looks enforceable, so an environment-caused violation gets
read as disobedience — and the response is to add another instruction,
which cannot fix it either. That is the compounding loop running on a
rule that was correctly written.

**What is detectable from the file, and what is not.** You cannot tell by
reading whether a rule is actually being overridden — that needs observed
behaviour. What you *can* tell is whether a rule is *exposed*: does its
subject is the interaction surface rather than the content? Rules about
which widget, prose versus table, how many questions at a time, output
channel, or response format all govern a layer other actors also control.
That is a textual property. Flag exposure; never assert a contest.

**Output is a watchlist, not a disposition.** Unlike the other buckets,
this one is not actionable at triage time. It pays off later — when the
user observes a violation and needs to check the layer stack before
writing another rule. Say so explicitly in the sheet.

If the user reports having already seen the violation, then and only then
do the four dispositions apply:
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

> ❌ Materials should be scaffolded and accessible.
> ✅ Every student-facing handout includes a vocabulary box defining terms above grade level, placed before first use of the term.

Violation: a handout with no box, or a term used before it is defined.

### 4b. Hedge → threshold, or delete

*Generally, typically, where appropriate, as needed, consider, may benefit from, try to, aim to, keep in mind, when possible.* Each is a documented exit. In a report these are epistemic honesty; in an instruction they are permission not to comply, written in the voice of rigor.

Either commit to a number or drop the line. There is no third option that works.

> ❌ Try to keep tasks reasonably short where appropriate.
> ✅ No independent task exceeds four steps.

### 4c. Aspiration → observable artifact property

The highest-value transformation, because virtues often can be rescued rather than deleted.

> ❌ Culturally responsive framing is appropriate.
> ✅ Examples must not assume: international travel, home internet, a parent who attended college, or access to a private vehicle.

Same commitment. The second can be checked, and it changes output. The first only changes tone.

### 4d. Aspiration → prohibition

Negative rules are more checkable than positive ones: the violating output is a specific present thing rather than an absence to be noticed.

> ❌ Don't assume math proficiency above 7th–8th grade.
> ✅ No student-facing task may require multi-step solving for a variable, operations on unlike denominators, or scientific notation. If one does, a fully worked example appears immediately before it.

---

## 5. Self-containment

Every line must carry its own scope condition. Not:

> Use short sentences.
> This applies to student-facing material only.

But:

> In student-facing material, no sentence exceeds 20 words.

Instruction sets get fragmented by retrieval, and a directive that arrives without its qualifier is worse than no directive — it will be applied where it was never meant to apply. Assume every line may be read alone.

Same rule for pronouns. A line beginning *This*, *These*, *That*, or *It* is depending on a neighbor that may not arrive.

---

## 6. Worked examples

**Example 1 — a virtue that rescues**

Source: "Given the student population, culturally responsive and equity-aware framing is appropriate throughout."

Triage: VIRTUE. No violation condition — no output could be held up as breaking it.
Rescue candidate: a forbidden-assumptions list.
Status: NEEDS USER DECISION — the specific exclusions depend on the setting and cannot be derived from the text.

**Example 2 — a virtue that demotes**

Source: "Students benefit from feeling that mistakes are a normal part of learning."

Triage: VIRTUE. True, motivating, unenforceable as written.
Rescue attempt: fails — no artifact property corresponds to it directly.
Disposition: demote to the rationale record, where it explains why the low-stakes-entry rule exists.

**Example 3 — a fact that stays a fact**

Source: "Roughly 10–25% of students have an IEP or 504."

Triage: FACT. Not violable, not inferable, constrains what other rules may assume.
Disposition: keep in the instruction block, near the top.

**Example 4 — prose hiding a procedure**

Source: "It's usually best to start by looking at the standard, then think about what the task should be, then work out an example before writing any assessment."

Triage: PROCEDURE. Multi-step, recurring, situational.
Disposition: extract to a skill. Note the hedge — "usually best" — which must be resolved to a definite sequence or an explicit branch when the skill is written.

**Example 5 — one sentence, two buckets**

Source: "Because many students are still developing academic vocabulary, keep language simple and support it visually."

Triage: splits.
- FACT: many students are developing academic vocabulary → instruction block.
- VIRTUE: "keep language simple and support it visually" → two rescue candidates, both NEEDS USER DECISION (a sentence-length cap; a required-visual rule with a defined trigger).

Do not let a compound sentence pass as a single item. Prose bundles claims of different types inside one grammatical unit, and the bundle is where unfalsifiable material rides in alongside something legitimate.

**Example 6 — a rule that goes on the watchlist**

Source: "Ask questions in prose, numbered. Never the multiple-choice widget."

Triage: CONTESTED. Its subject is the interaction surface, not the
content — which is the detectable property. The violation condition is
clear (a widget appears), but a surface can supply that widget on its own,
so its appearance would not establish disobedience.

Sheet entry: watchlist. Not "this is being overridden" — that is not
knowable from the file. The correct wording is: *if you ever see this
violated, check the layer stack before adding a rule.*

Distinguish this from CONFLICT. A conflict is between two lines you
control, and you resolve it by picking one. A contest is with something
outside the document, and picking does not help.
