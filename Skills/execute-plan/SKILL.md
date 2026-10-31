---
name: execute-plan
description: Executes a make-plan plan file on a work branch, stage by stage, logging progress into the plan so an interrupted run can resume. Use when the user invokes /execute-plan with a plan path.
argument-hint: <./path/to/plan-file.md>
disable-model-invocation: true
metadata:
  harness: [codex, claude]
---

# /execute-plan — implement a plan beginning to end

You are responsible for implementing the plan, as described below.

## Hard rules
1. Do not push. Ask the user when a Post-Acceptance item needs the branch pushed.
2. Never commit to the default branch.
3. After Phase 0, stay on `plan/<plan-file-stem>`.

## Phase 0 — Preflight

1. Resolve the argument to a plan file. If just a file name is provided, the default plan file location will either be defined in the project's AGENTS.md or defaulted to `./docs/plans/<plan-file.md>`. If no argument was given or the desired plan file is ambiguous, list the candidates and ask.
2. Read the plan fully.
3. If `Status` is not READY, stop and confirm with the user: DRAFT hasn't finished review, EXECUTING means a run is in flight - engage step 4, EXECUTED/COMPLETE (or an existing completion record) means it already ran.
4. **Resume:** if the branch already exists (`plan/<plan-file-stem>`), or the plan already has a `## Progress Log` with completed stages, ask the user whether to resume. On resume, check out the existing branch, verify the changes the log claims are actually present in the code, and continue from the first incomplete stage — never start over. If the user declines, stop: recovery is handled outside this skill. With no existing branch or Progress Log entries, continue to step 5.
5. Require a clean working tree (`git status`); if it is dirty, tell the user what's there and stop — otherwise later review can't tell plan work from pre-existing edits. Note, if the only uncommitted file is the plan file itself: proceed, and commit it as the first commit on the branch step 6 creates.
6. **New Runs:** Find the default branch (`git symbolic-ref refs/remotes/origin/HEAD`, else ask). Check it out, `git pull` if a remote exists, then `git checkout -b plan/<plan-file-stem>`.

## Phase 1 — Execute

Set the plan's `Status` to `EXECUTING` (committed with the first stage's work).

Work through `## Stages` in order under the `plan/<plan-file-stem>` branch. At your judgement, you may spin up a T3 Code Delegate or a subagent to do the specific execution, as you coordinate across the stages. For each stage:

- Implement what the plan says. Any choice the plan does not specify, or that contradicts it, gets a `Deviation:` line in that stage's Progress Log entry. A stage that cannot be done as written is logged as blocked and skipped, and so is every stage the plan lists as depending on it.
- Consumer migrations named in a stage land in that stage's commit.
- Update the design-of-record docs (see the plan's `## Documentation` section) when the change alters a documented design.
- Run every verification command the stage names and log its actual output summary.
- On a failure, rerun only the failed step, then do one full confirming run.
- AGENTS.md's verification guidance sets when and how often a check runs, never whether a plan gate runs.
- Each verification that cannot run on this machine is added to `## Post-Acceptance verification` as pending, with its exact command and where its result will be recorded. Never report them as unmet gates or run-skipped passes.
- Do not edit a `## Pre-Acceptance criteria` item or a stage's verification command to make it pass. An item you think is wrong is a Deviation for the user to rule on.
- Append the stage's entry to `## Progress Log` as each stage lands, not all at the end: `### Stage <N> — <done\|blocked\|skipped>`, then what you did, files touched, verification output, `Deviation:` lines.
- Commit the stage (including the plan-file log update) with a message on this branch: `Plan: <plan-file-stem> Stage <N>: <Summary of work performed>`

Feel free to engage with T3 Code Delegates, or subagents, for doing more advanced searching if it would seem beneficial. I'd recommend the latest Sonnet or Terra level models for this work.

## Phase 2 — Review

Check every `## Pre-Acceptance criteria` item and log pass/fail with evidence in the `## Progress Log`.
After the last stage, run the full gates as defined in the local AGENTS.md. Fix failures your own work caused before finishing.

### Review-Loop
If the user asked for a review loop (e.g. `review loop with <model>`), invoke the `review-loop` skill on this branch's changes here, before Phase 3.
Include `### Review round: <N> (<model>[ on <effort>])` as a subheader in the `## Progress Log` for this particular review round. Then, include the findings and your assessments.

## Phase 3 — Completion record

Fill in the plan's `## Completion record`:

```markdown
## Completion record
Completed: <date>  Branch: <branch>  Commits: <range or list>
- What was done, per stage, matching what actually landed
- Deviations from the plan and why
- Build/test results as actually observed
- Stages skipped/blocked, if any, and why
```

Set `Status: EXECUTED` and commit. Do **not** mark the plan as complete or move it to a `complete` or `finished` folder, that step waits for a final human approval.

## Finish

Report: the plan path and status, branch name and commit list (from git, not from memory), which stages completed / were skipped (and why), deviations, and gate results, and total review rounds (if review-loop was engaged). Next steps: `/push-plan <path>` (ideally in a fresh session) to finish any post-plan cleanup.
