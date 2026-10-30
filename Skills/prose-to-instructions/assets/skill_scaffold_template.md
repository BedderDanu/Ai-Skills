# Skill scaffold

Use for each PROCEDURE identified in triage or audit. Produce the folder,
fill what the source supports, and mark gaps explicitly rather than
inventing steps.

## Folder

```
<skill-name>/
├── SKILL.md
├── scripts/          (only if a deterministic check exists)
├── references/       (only if SKILL.md would exceed ~500 lines)
└── assets/           (templates the procedure fills in)
```

Create only the directories that have contents.

## SKILL.md template

```markdown
---
name: <kebab-case-name>
description: <What it does, then when to use it. Include the phrases the
user would actually say — including indirect ones. Skills under-trigger,
so be generous with the trigger contexts.>
---

# <Title>

<One paragraph: what problem this procedure solves and why the steps are
in this order. Explaining the reason makes the steps generalise to
situations the source didn't anticipate; a bare list doesn't.>

## Steps

1. <Imperative. One action.>
2. <Imperative. One action.>

## Checks before finishing

- [ ] <Observable. Someone else could verify it without asking you.>
- [ ] <Observable.>

## Gaps

<Anything the source hedged or left undefined. Name it here rather than
guessing — an invented step is worse than a flagged hole.>
```

## Rules for filling it

**Resolve every hedge.** Source prose says "usually start by checking the
standard." A procedure cannot contain *usually*. Either the step is
unconditional, or there is a named branch with a stated condition. If the
source doesn't say which, list it under Gaps and ask.

**One action per step.** If a step contains "and", check whether it is two
steps. Compound steps get partially completed and read as done.

**Checks must be observable by someone else.** "Confirm the task is
appropriately scoped" is not a check. "Confirm no task exceeds four
steps" is.

**Scripts only where the check is the thing meant.** A script that
verifies a required section exists belongs here. A script that scores
readability does not — see `scripts/validate_artifact.py` for why.

**Keep the description pushy.** Skills under-trigger more often than they
over-trigger. Include indirect phrasings, not just the obvious ones.

## Before handing it over

Run the skill's own SKILL.md through `scripts/scan_prose.py`. A skill
about writing checkable instructions that is itself full of hedges and
virtue words has failed its own test, and so has any other skill built
this way.
