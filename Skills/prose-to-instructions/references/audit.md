# Audit reference

For instruction sets that already exist and are already in use. The buckets, tests, and transformations are the same as in the base triage pass; this file covers only what is different when the material has history.

## What is different

A live instruction set has three properties a fresh report does not:

1. **Someone is relying on it.** Deletions have to be justified individually, not in bulk.
2. **It accreted.** Lines were added at different times by different reasoning, and some now contradict.
3. **The user has evidence.** They know which outputs went wrong. That evidence is more valuable than any static analysis — ask for it.

Open by asking what has actually gone wrong lately. A single real failure locates the problem faster than scanning the whole block.

## Sequence

**1. Inventory.** Count lines, count distinct directives, note the order. Report the count plainly. Instruction-following degrades as density rises, and models show measurable bias toward earlier instructions — so both the total and the ordering are findings in themselves.

**1b. If the material is a skill, run the packaging check.** Read `skill-spec-checklist.md` and check naming, frontmatter, description, body length, and file structure. This is separate from the bucket-test classification in steps 3–4b below — a skill can pass one and fail the other. Do this whether or not anything else in the audit turns up a problem.

**2. Run the scanner.** `scripts/scan_prose.py <file>` for located signals. It is advisory. Its output is a list of places to look, not a verdict, and it emits no score by design. Do not compute one from it.

**3. Classify every line** into FACT, CONSTRAINT, PROCEDURE, or VIRTUE — the four buckets classified inline here — plus three buckets specific to audit:

- **DEAD** — refers to something that no longer exists, or a problem already fixed
- **DUPLICATE** — covered by another line
- **CONFLICT** — contradicts another line you control

CONTESTED is the fifth universal bucket, carried over from the base triage pass, but it isn't tagged inline with these — it gets its own dedicated pass in step 4b, because it's the one bucket audit can't confirm by reading alone.

**4. Cross-check for contradiction.** This is the highest-value step and the scanner cannot do it. Two lines added six months apart pointing in different directions produce behavior that varies by session, which the user experiences as unreliability rather than as a rule problem. They will not find these by reading, because each line looks correct alone.

**4b. Build the watchlist.** Flag every rule whose subject is the
interaction surface rather than the content. This is the one finding the
audit cannot confirm, because confirming it needs observed behaviour and
the audit only reads a file. Report exposure, not override.

If the user says a specific rule is being disobeyed, that is observation,
and the layer stack becomes checkable: profile preferences, account-level
skills, global instructions. Cowork skills are account-scoped with no
per-project scoping, so a skill built for one project can act in another.
Raise this as a candidate cause; do not assert it.

**5. Test the ignored ones.** For any rule the user says is being ignored, check in order: is the block too long, is the line unfalsifiable, is it buried late in the ordering, does it conflict with an earlier line. Report which. "It is being ignored because it cannot be violated" is a different fix from "it is being ignored because it is line 60 of 80."

**6. Write the findings sheet.**

## Findings sheet format

```markdown
# Audit: <source>

Lines: N | Distinct directives: N | Est. tokens: N

## Needs user decision (N)
Every virtue rescue and every conflict resolution: one line of context each, and the section it comes from.

## Cut (N)
| Line | Text | Why | Risk if kept |

## Rewrite (N)
| Line | Current | Problem | Proposed | Violation condition |

## Move to skill (N)
| Line(s) | Procedure | Proposed skill name |

## Conflicts (N)
| Lines | The contradiction | Which to keep — NEEDS USER DECISION |

## Watchlist (N)
Rules governing the interaction surface. Not defects. If you ever see one
violated, check the layer stack before writing another rule.

| Line | Rule | Layer that could also control this |

## Reorder
Proposed order, highest-stakes first, with reasoning.

## Keep as-is (N)
Line numbers only. No commentary needed.
```

## Blind spots that look like clean results

Each of these fails silently: the audit reads as complete because the missing thing leaves no trace on the page.

- **A subtraction list inherits its plan's blind spots.** An audit that works only from a list built from a prior plan can't surface anything that list already classified as protected. Read the material itself, not only the list.
- **A never-fired mechanism has three causes that look the same from outside:** no population yet, the population is gone, or it is preventing what it was built to prevent. Only the third is a reason to keep it. The count can't tell them apart; the recorded origin incident can, so find it before proposing a cut.
- **An open-decision list built without opening the artifacts** will contain items the artifacts already answer. An unread file and an unmade decision look the same from the list. Open each artifact before listing its decision as open.
- **An ownership or routing table can name a destination that doesn't exist.** A row reads as settled whether or not its target has any content. Check that each destination exists and is populated.
- **Parallel subagents can each settle the same interface differently** (for example, where a reconciliation line lives). A parallel rewrite needs a fixed interface list in every brief and one consistency pass across the outputs afterwards.

## Deletion discipline

Never delete on suspicion alone. Each cut carries a stated reason and a stated risk. The user has to be able to disagree with any single row without discarding the whole audit.

Three cuts are safe to propose confidently:
- **DEAD** — the referenced thing is verifiably gone
- **DUPLICATE** — another line covers it, cited by number
- **Redundant with default behavior** — the model would do this unprompted. State the claim so the user can test it by deleting the line and watching.

Everything else is a proposal.

## What not to do

**Do not rewrite the file.** Same rule as CONVERT: produce the sheet, let the user apply it. An audit that returns a cleaned file gets approved on content and never checked for executability, which is the failure the skill exists to prevent.

**Do not treat length as the only problem.** A short block of unfalsifiable virtues is worse than a long block of checkable rules. Density is one finding among several; report form and density separately.

**Do not add anything.** Audit removes, rewrites, relocates, and reorders. If the user wants new coverage, that is CONVERT mode on a new source, run separately.
