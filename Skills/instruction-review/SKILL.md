---
name: instruction-review
description: "Reviews instruction-bearing documents for whether an agent can actually follow them. Audits an installed instruction file (CLAUDE.md, AGENTS.md, a SKILL.md, a rules file, a plan or plan template an agent will execute, a voice guide), converts a report or design doc's findings into rules, or designs a new skill or folder structure. Produces a review sheet, never installed instructions. Use when asked to audit, review, tighten or streamline agent instructions or a skill, or to turn notes into rules; not for ordinary writing, code review, or a question about what a file says."
argument-hint: "[convert|audit|design] <file or target>"
---

# Instruction Review

Prose written to be *read* fails when asked to *govern*. A report's job is to be true and persuasive; an instruction's job is to be checkable. Converting one into the other without re-forming it produces instructions that cannot be violated, and therefore cannot be followed — the model treats them as tone rather than procedure, and invents compliance behavior to fill the gap. Output drifts, and because nothing was violated, the drift can't be traced back to any rule.

This skill re-forms prose into checkable instructions, or finds the places where an existing instruction set has already failed this way.

## The hard rule

**Never write into the user's live instructions.** Produce a review document. The user assembles the final block from the rows they approve.

This is the point of the skill, not a formality. When a person reads a clean finished instruction block, they validate its *content* — is this accurate about my situation — and not its *executability*, which is the property that matters. An approved-but-unenforceable block is worse than none, because the approval retires their suspicion. Handing back decisions instead of a draft keeps the human's attention on the axis that fails silently.

If the user asks for a paste-ready block, give them the review document first and offer to assemble the approved rows afterward, in a separate step.

## Where the work goes

These rules hold in whatever project the skill runs in. Where the host project's `CLAUDE.md` or `AGENTS.md` sets a stricter rule on the same point, the project's rule wins.

- **Folder.** Write every triage sheet, findings sheet, structure proposal, draft instruction block and draft skill to the host project's work-item folder: the one its `CLAUDE.md` or `AGENTS.md` names (e.g. `docs/reviews/<item>/`). If it names none, ask before writing, and suggest `design/<item>/`. Name the item folder for the work, not for a document type.
- **File name.** `<source-or-project-name>-<triage|audit|structure|draft>.md`, unless the host project sets its own convention.
- **Source files are read-only.** Never modify the source document or the instruction set under audit. A source document stays intact as the rationale record.
- **Decisions first.** Every sheet or proposal opens with a `Needs user decision` section: a numbered list of the decisions in the file, each with one line of context and the section it comes from. Where a whole section is mostly decisions, one entry names that section and its count.
- **Decisions stay in working documents.** A decision point never goes into an installed reference, index or instruction file; that file states what was decided. When a decision is resolved, strike through the question where it was posed and record the outcome beside it, in the same pass.

## Pick the mode

**CONVERT** — the input is prose. A report, design doc, research summary, review findings, meeting notes, or a run of corrections the user made in conversation. Produces a triage sheet.

**AUDIT** — the input is an existing instruction set. A CLAUDE.md or AGENTS.md, a skill body, a rules file, a plan document an agent will execute, or a plan or review template that other agents follow. Produces a findings sheet.

**DESIGN** — there is no source document to triage or audit. The task is proposing or building folder organization, project instructions, or a skill directly. Produces a structure/instructions/skill proposal — same hard rule as CONVERT and AUDIT: a proposal, not an installed thing.

All three modes share the same underlying tests. Read `references/triage.md` before any of them — it holds the five buckets, the two survival tests, and the rewrite transformations. For AUDIT, also read `references/audit.md`, and `references/skill-spec-checklist.md` when the material is a skill.

**Source type.** Independent of which mode applies, check whether the source (or the thing being designed) is task instructions or a voice/style/tone guide. For the latter, also read `references/voice-audit.md` — it overrides the virtue disposition for tone content specifically, and adds a `Track` column to whichever sheet the mode produces. Everything else about the mode is unchanged.

If the user hands over both a report and the instructions it produced, run AUDIT on the instructions and use the report only to recover intent for items that failed.

## CONVERT workflow

**1. Read the source, then set it aside.**
Do not edit the prose into instructions. Editing guarantees mirroring — the sentence structure, transitions, and hedges survive and you end up with the report in bullet form. Extract claims, then write instructions from scratch. Return to the source only to check for omissions.

**2. Extract every candidate directive.**
Anything in the source that seems like it should govern future work. Over-collect here; triage removes.

**3. Triage each into FACT, CONSTRAINT, PROCEDURE, VIRTUE, or CONTESTED.**
Apply the tests in `references/triage.md`. The decisive question for every item: *what output would violate this?* One sentence, or it does not survive as an instruction.

Then one further question, answerable from the text alone: *does this rule govern the interaction surface rather than the content?* Rules about the interaction surface — which tool, response format, how questions are asked, commit or PR formatting, output channel — govern a layer that other actors also control. Mark those CONTESTED and put them on the watchlist.

**4. Rewrite the survivors.**
Four transformations, in `references/triage.md`. Every rewritten line is self-contained: its scope condition is on the same line, and it does not open on a pronoun that refers to a neighbouring line (`references/triage.md` §5).

**5. Sort into tiers.**
- *Project instructions* — FACTs and CONSTRAINTs only; procedures go to skills, and virtues are rescued, demoted or deleted before anything is presented as final. Order by how bad a silent violation would be, not by how often the rule fires; position is not neutral. Flag a long block as an advisory note. Build a hard length cap when the user asks for one; propose one unprompted only once the same correction has recurred three times.
- *Knowledge files* — exemplars, templates, and the source document itself, retitled as a rationale record.
- *Skills* — every PROCEDURE.
- *The deliverable* — checklists ride with the artifact.

**6. Write the triage sheet.**
Use `assets/triage_sheet_template.md`. Every row carries its bucket, proposed rewrite, violation condition, and destination tier. VIRTUE rows carry a proposed rescue *marked as needing the user's call* — see the division of labor below.

**7. Scaffold what was identified.**
For each PROCEDURE, build a skill folder from `assets/skill_scaffold_template.md`. When the user asks for a gate, generate its config (see Gates).

## DESIGN workflow

There is no source document. The task is building or proposing folder organization, project instructions, or a skill directly.

**1. State the bucket before producing anything.** For each piece of content in the proposal: does it go in project instructions (followed), a knowledge file (consulted), a skill (executed as a repeatable procedure), or the deliverable (a checklist that rides with the artifact)? Say which, and why, before the artifact exists. This is the same test CONVERT and AUDIT apply to existing prose — DESIGN just runs it forward, on content that doesn't exist yet.

**2. Apply the same survival tests.** Proposed content with no violation condition is a virtue, not an instruction, whether it came from a source document or was invented for this proposal. `references/triage.md` applies here unchanged.

**3. If a skill is involved, it passes two independent checks, not one.** Every piece of bundled content is genuinely conditional or genuinely multi-step — nothing that belongs in every task, the same bucket test used to send PROCEDURE items to a skill in CONVERT and AUDIT — *and* the file is packaged correctly per `references/skill-spec-checklist.md`. Keep these separate. A single bundled "is this well-designed" judgment hides which of the two actually failed.

**4. Split what can stand alone.** Put a concern in its own file or skill whenever a task could need it without needing the rest.

**5. Propose test cases with any final assembly.** When an instruction block or skill is assembled, propose concrete cases for the user to try in a fresh conversation before adopting it, not a generic "test this." Every recorded result names how the run was executed (the real target project, a sibling session, or a subagent). A test whose failure case that harness cannot trigger does not count as a pass.

## Division of labor

Decide mechanically, without asking:
- whether a claim has a violation condition
- whether a line contains hedges or evaluative adjectives
- whether an item is procedural
- whether a line is self-contained
- ordering, length, duplication, contradiction

Do **not** decide alone:
- whether a VIRTUE is rescuable into an observable property, and into which one
- whether a watchlisted rule is actually being contested, and how to resolve it
- how to resolve a conflict between two lines
- which bucket an item belongs in, when the tests leave two readings open

Rescuing a virtue requires knowing the user's setting. "Be careful not to break the tutorial" becoming "`examples/MyFirstGame` stays line-for-line with `docs/tutorials/`, enforced by a test" is project knowledge, not a transformation derivable from the text. Propose rescues and resolutions as candidates, show the reasoning, and mark each one **NEEDS USER DECISION**. Never resolve one by inferring what the user probably meant.

Watchlisted rules are the sharpest case: the skill can say a rule is *exposed* to being overridden, never that it *is* being overridden. That second claim needs observed behaviour, which reading a file cannot supply. Asserting it produces confident errors about the user's own environment.

When several virtues need the same missing information, ask once, batched, after the sheet is drafted — not as a blocking question up front.

## Gates

An instruction says *don't*. A gate makes it visible when you did. Gates cost nothing in context — the script runs and only its output enters the window — so unlike instructions they do not compete with each other for adherence.

**Two kinds, and the split is load-bearing.**

*Structural gates — hard fail.* Only where the check IS the thing meant, with no proxy in between: required section present and non-empty, term defined before first use, length cap, placeholder text absent, a phrase kept out of one section, companion file present. Gaming these requires satisfying them, so there is no Goodhart problem. Use `scripts/validate_artifact.py` with a JSON config.

*Prose signals — advisory only, never blocking.* Readability formulas, sentence length, vocabulary difficulty. These are proxies: they measure sentence and syllable length, not conceptual load, syntactic embedding, or cultural presupposition. Hard-failing on them teaches the writer to chop sentences, which strips the connectives that made logical relationships explicit and can make a text measurably easier and actually harder. Use `scripts/scan_prose.py`, which reports located findings and deliberately emits no score. Do not add a score to the scanner, compute one from its output, or describe its results as a grade.

The scanner is calibrated for instruction blocks — one rule per line, no rationale. On documents that legitimately mix explanation with directives, its prose-register and sentence-length signals fire on the explanatory parts, which is noise. Read the unfalsifiable, virtue, and hedge signals there and disregard the rest.

**When to build a gate:** whenever the user asks for one. Propose one unprompted only the third time the user makes the same correction by hand. Not the first — that may be noise. The third is a pattern, and it means the instruction layer cannot hold it.

## Incident handling

When the user reports that something went wrong, do not append a line. Find the line that should have caught it, and report which of three is true as a finding row:

1. It does not exist → propose it.
2. It exists but is unfalsifiable → propose a rewrite. Do not supplement it.
3. It exists and is sound but was ignored → run the four-cause check in `references/audit.md` step 5 (too long, unfalsifiable, buried late, conflicts with an earlier line). When the cause is length, the fix is deletion elsewhere, not addition here.

Nothing is added until something has been inspected. Appending on every incident is what drives the density that degrades adherence to the rules that were already working.

Two edit hazards when the user asks you to apply approved rows:
- **Narrowing a rule can falsify a neighbour** that was consistent with the wider version. After narrowing one, re-read the rules around it, not only the rule being changed.
- **A section that grew during the session can't be replaced by its heading.** Having written its first version doesn't tell you its current extent, so a whole-section replacement anchored on the heading silently deletes everything added since. Re-read the section before replacing it.

## Verify before presenting

Before any triage sheet, findings sheet, or design proposal is shown to the user, a subagent or fresh session that did not write the sheet re-checks every quotation, line reference, and claim about a file against the file itself. Brief it to find errors, not to confirm the sheet — a pass briefed to agree will agree.

Findings it overturns are corrected before presentation, and the sheet's `Verification pass` section records who ran it and what it changed. That last clause is load-bearing. A verification pass whose corrections disappear into a clean final document teaches the user the sheet was right the first time, which is the same failure the hard rule guards against: an approved artifact retires the suspicion that was the only thing checking it.

Applies to all three modes. Not required for conversation, for a known-path lookup, or for a sheet the user has already read and is iterating on.

Citation rules the pass checks:
- A claim that a rule or convention exists in a file cites that file and the section where it appears. If the file wasn't read this session, the claim is marked unverified rather than stated.
- Cite a line number only from a read made after that file's last edit this session; otherwise cite the section heading, which doesn't move.
- In a document that will be read again in a later session (a working document, a plan, a handoff), pair every line citation with a verbatim quote of five or more consecutive words from the cited line, longer if five aren't unique in the file. A one-shot sheet that is acted on in the session that produced it is exempt.

## Test fixtures

**A fixture must not name the thing it tests.** Naming it cues the subject, so the run measures the cue rather than the behaviour, and the result looks like a pass. This is checkable before the run and it is the cheapest test defect to prevent. Auditors make it in their own fixtures too, so check yours.

## Reporting to the user

State what was cut, added or restructured and why, with counts by bucket, before reporting what survived or what is proposed — the deletions are where the value is. State the instance count in a finding's first sentence; anything at n=1 is an observation, not a pattern. Flag any contradiction found between two surviving instructions; those are invisible to the user and produce inconsistent behavior across sessions.

Do not congratulate the source document or apologize for cutting it. The report was the right artifact for the thinking it supported. The error is reuse without re-forming.

## Files

- `references/triage.md` — buckets, tests, transformations, worked examples. Read before any mode.
- `references/audit.md` — AUDIT mode specifics and the findings sheet.
- `references/voice-audit.md` — disposition override for voice/tone/style-guide sources, any mode.
- `references/skill-spec-checklist.md` — skill packaging/format check, used by DESIGN and AUDIT whenever a skill is involved.
- `scripts/scan_prose.py` — advisory signal scanner. No score by design.
- `scripts/validate_artifact.py` — structural gate runner. Hard fail.

Script paths are relative to this skill's folder. Run both as `python -I -X utf8 scripts/<name>.py …`; a Windows console otherwise fails on the scanner's symbols.
- `assets/triage_sheet_template.md` — CONVERT and DESIGN output format, including voice sources.
- `assets/skill_scaffold_template.md` — scaffold for extracted procedures.
- `assets/gates.example.json` — annotated gate config, written for a plan document.
