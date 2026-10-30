---
name: make-plan
description: Grill the user about a piece of work until every design decision is settled, then create a planning document. Default to ./docs/plans
argument-hint: <plan location> <description of the work to plan>
disable-model-invocation: true
metadata:
  harness: [codex, claude]
  prefers: "request_user_input or AskUserQuestion tool available"
---

# /make-plan - grill until settled, then write the plan

The arguments plus whatever the user said in conversation are the request being planned. If no description was provided, ask for one and stop until you have it.  Treat the first argument as the plan location only if it contains `/` or `\` or ends in `.md`; otherwise it is part of the description. If the plan location ends with .md, use that as the file name for the plan (see Phase 2). Do not start executing the plan.

## Phase 1 - Grill

Interview the user relentlessly until you reach a shared understanding. Map the work as a **design tree**: every decision branches into the decisions that hang off it.

Work the tree in **rounds**. The **frontier** is every decision whose prerequisites are already settled: the questions you can ask *now* without guessing at answers you haven't heard yet. Ask the whole frontier in one round with the `AskUserQuestion` or `request_user_input` tool (Use whichever tool is available, within its own limits; skip fields it doesn't support). A frontier larger than 4 questions is split across consecutive calls; that's fine, since frontier questions are independent. For each question:
 - Keep `question` short and self-contained (name the subsystem or file it concerns).
 - Give 2–4 options; put your recommendation first with `(Recommended)` and its rationale in the `description`.
 - Cumulative scope (`a`, `a+b`, `a+b+c`) is single-select with one option per tier; independent components use `multiSelect: true`.
 - Put longer detail (API sketches, file paths, code) in an option's `preview`, not the question.
 - If a decision has more than 4 options, split it into two questions across rounds rather than cramming.
 - If the question is difficult to represent as an `AskUserQuestion` or `request_user_input` style format (when the answer can't be expressed as a choice among 2–4 options or if the tools are unavailable for some reason), fall back to the below free form question format:

❓ **Q1** - **<question title>**: <question body, might be multiple paragraphs, including multiple choices>
➡️ <your recommended answer>

---

❓ **Q2** - **<question title>**: <question body, might be multiple paragraphs, including multiple choices>
➡️ <your recommended answer>

Each round the user answers reshapes the tree: settled decisions push the frontier outward and unblock questions that depended on them. Recompute the frontier and ask the next round. A question whose answer depends on another question still open in this round belongs to a *later* round, not this one. Ask the tool questions first; put the round's prose-format questions in your message after the dialogs return.

Read the information from the Repo to get answers to questions before going back to the user: `AGENTS.md`, the guide/plan docs it names for any subsystem the work touches, and the actual code, so questions are grounded in real file paths and API names. Never ask the user anything you could look up yourself; ask only genuine **decisions** - scope boundaries, trade-offs, acceptance criteria, ordering constraints. Feel free to engage with T3 Code Delegates, or subagents, for doing more advanced searching if it would seem beneficial. I'd recommend the latest Sonnet or Terra level models for this work.

The grilling is done when the frontier is empty: every branch visited, nothing left silently assumed. Confirm the shared understanding with the user before writing anything (Provide a plan summary and ask for confirmation).

## Phase 2 - Write the plan

Write the plan to `<plan location>/<kebab-case-topic>.md`, if a plan location wasn't provided default to `./docs/plans/<kebab-case-topic>.md`. Use the filename provided if a specific name was included in the `<plan location>` argument. If the name is taken, read the existing file first - if it's a prior version of the same plan, update it in place; otherwise pick a more specific name. Never overwrite an unrelated plan.

Document Structure (the other plan skills parse it, so keep the headings exact):
```markdown
# <Title>

Status: DRAFT
Created: <today>
Draft Review rounds: 0

## Original request
<The user's request plus every decision from the grilling, restated completely.
Every requirement, constraint, and example belongs here, in full sentences -
this section must let someone reconstruct what was asked and decided without
the conversation. Do not summarize away details. State any assumptions made
in place of unasked questions.>

## Design
<The approach: affected projects/files, new/changed APIs, how it respects the
repo's contracts. Call out the alternatives you rejected and why.>

## Documentation
<A list of the project documentation that would need to be updated alongside
the updated design files.>

## Seams
<One bullet per other subsystem or module this change touches or is touched by,
stating what happens at that boundary and which test or stage covers it.>

## Stages
<Numbered, independently verifiable stages. Each stage names its files, its
consumer migrations, and how to verify it (build/test/testbed command). Note 
dependencies between stages explicitly.>

## Pre-Acceptance criteria
<Checkable statements that define `done`, including documentation updates. 
Only evidence the local machine can produce before a push belongs here: builds, 
tests, local native fixtures, performance metrics, etc. These are the criteria
you can check yourself, on this machine, without getting any outside assistance.>

## Post-Acceptance verification
<Acceptance evidence that does require outside assistance: Compile and execution
checks on different operating systems, repository automated CI, human usability
verification, etc. One row per item with the exact command, the marker/exit expected, 
and where the result is appended (A docs/verification record placed in this section, either
as part of the planning or added as an amendment as part of the /execute-plan skill. For any human 
verification, include how to perform it, what counts as passing, and where the result is 
recorded). These are never completion gates and never blocking review findings; a missing
result is recorded as pending, not as a pass. Write `none` if the plan has no Post-Acceptance items.>

## Risks & Open questions
<Known unknowns, decisions deferred to execution time, things that could
invalidate the plan.>

## Completion record
(filled in by /execute-plan when the work lands)
```

## Review-Loop
If the user asked for a review loop (e.g. `review-loop with <model>`), invoke the `review-loop` skill on the plan file after writing it, before Finish. 
Each review round increments `Draft Review rounds` (the review-loop skill also calls this out; don't double-count review rounds).

## Finish

End with: the plan file path, a 3–6 sentence summary, a command to kick off project execution in a new thread (/execute-plan `<plan-file-path>`)
