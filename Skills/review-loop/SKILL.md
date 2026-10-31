---
name: review-loop
description: Runs an iterative review of the current change or plan by a delegated reviewer model. Use when the user says "review loop". Example "/execute-plan ./docs/plans/example.md and review loop with Claude Fable 5.1"
argument-hint: <model> [target]
disable-model-invocation: false
metadata:
  harness: [codex, claude]
  requires: "T3 Code delegation, or some other way to call the provided model as a subagent from the current running harness."
---

# /review-loop

You own the code. The provided model will review it. Fix what it gets right, push back on what is wrong, and stop when you either agree, the changes are all nits, or the review budget ends. The Goal is the smallest change that meets the intent. Review makes things correct, not bigger or longer.

## Budget

- Default: 3 rounds total. Round 1 is a full review. Further rounds check changes and open findings.
- Extend past 3 rounds only while the count of open `Blocker` + `Should` findings drops each round; hard stop at 5. If it doesn't drop, stop and tell the user.
- Stop early if a round returns only nits. Declined nits, comments, document formatting, or other simple changes do not need a review round.
- One primary reviewer only. The reviewer may spin up its own assistant model for testing or fact finding to assist it, but no secondary reviewers

## 1. Scope

If the project is tracked by git, run `git status --short`. Do not stash, discard, or include unrelated changes. Limit the review to the change paths if they cleanly separate.
If there is no clean listing of changed files, provide the reviewer with your list of files you edited as part of your change, and let it know the scope of the change you were trying to make.

If the invoking skill names a base, use it. Find the base after `git fetch origin`:

 - PR: `gh pr view <n> --json baseRefName,headRefOid`. Check out the branch only if clean. Confirm `HEAD` is the PR head, or ahead only by this change. Base: `git merge-base HEAD origin/<baseRefName>`
 - Local: `git merge-base HEAD origin/<default-branch>`. No Remote: a base the user names, or `HEAD` for uncommitted changes only.

The change is base to working tree in those paths, with untracked files. Use one diff command for all rounds. State intent and out-of-scope in 1-2 sentences.
Before round 1, run covering checks; record results and `git diff --shortstat <base>`. 
Do not send code this change breaks; note missing or pre-failing checks in the brief.

## 2. Start Reviewer
If using T3 Code delegation, call `orchestrator_capabilities`. Pick the specific model that was provided in the arguments. 
If a general name was provided, try to find and use the latest version of that model (for example, Fable could match to Claude Fable 5.1; Sol could match to GPT-6.1-Sol). 
If a model wasn't provided, use the same model as the currently running thread. 
If a model was provided but can't be matched, end the review rounds early with a note that the model couldn't be found. 
Don't hardcode an ID. 
Record provider, model, and effort if exposed. 
Use `delegate_task` every round (`role: "review"`, `mode: "async"`, `isolation: "shared"`). Save the `taskId`, use a new `clientRequestId` per round.
`childThreadId` is storage, not the next target.
Do not use `t3_thread_send`, `create_threads`, or `t3_thread_launch` for reviews.

If T3 tools are not available, try to see if another tool is providing that model in some way. If a model can be reached, follow that method's guidance to run the review. Don't substitute the model if you cannot reach it: report back the blocker.

Round 1 Brief (T3 delegates don't get history), assumes git:
```
Review Only. Do not edit, commit, push, comment on PRs, or Start subagents with jobs beyond simple factfinding or local testing.
Repo: <absolute path>; Base: <sha>; Intent:<intent>; Out of Scope: <scope>; Checks: <results>
See: git diff <base> [-- <paths>]; git status --short (read untracked).
Read surrounding code. Find bugs, broken callers, mismatch with intent. Skip style unless it hides a bug. Hold to the smallest change. Flag Code, tests, or Guards the intent does not need. Other paths, rare cases, small performance, extra compatibility are nits.
`Blocker` means intended case is wrong. `Should` is a real bug callers will hit. `Nit` is the rest.
Reply: 
VERDICT: [APPROVE|CHANGES]
S1 [Blocker|Should|Nit] <file>:<line> <claim>. Recommended Fix: <suggestion> (use stable IDs)
```

If the reviewed work is not tracked via git, or if the reviewed medium is prose instead of code (for example, reviewing a plan.md document) you may modify or simplify the prompt as appropriate. Follow its intent for the medium you are reviewing. (For example, review-loop against a 3d model would require a different prompt, but should still be able to reply with Blockers, Shoulds, and Nits.)

## 3. Answer Findings

Keep a ledger in your working notes, one line per finding ID with its status.

Check each finding and severity yourself. Another Path, rare case, or small cost is a nit, regardless of the delegates label.
 - Agree: Apply the smallest fix. Prefer to delete or narrow over a new lock, helper, or option. Fix the case that happened. Add one focused test that fails without the fix, if the intent needs it.
 - Disagree: State Why, with evidence (file:line, test, output, etc.)
 - Nit: Apply the correction if you agree, or List as follow up.
 - Out of Scope: Decline in one line, List as follow up.

Update the Ledger. If working with a plan document via make-plan or execute-plan, update the plan document as appropriate:
 - increment `Draft Review rounds` after each round if reviewing the plan itself. Note that this is a restatement of the rule inside of make-plan, don't double-count review rounds.
 - Include `### Review round: <N> (<model>[ on <effort>])` as a subheader in the `## Progress Log` for this particular review round if reviewing work that landed from execute-plan. Then, include the findings and your assessments. Note that this is a restatement of the rule inside of execute-plan, don't double-write review round ledger entries.
Re-run checks and `git diff --shortstat <base>`. If review grew the diff, cut first. Don't just agree to end the loop.

For prose, skip tests and checks; measure size by line count.

## 4. Next Round

Start one if budget remains and a `Blocker` or `Should` is open, code behavior changed, or approval does not cover the current behavior.
Use a fresh `delegate_task` in T3, or follow up the same native ID.
Send the round 1 brief, the ledger [`fixed:`|`disagree:`|`declined: <evidence>`], the same base diff, and the change since last round.
Ask the reviewer to review only the open IDs and the code changed since the last round, and to mark each old ID `resolved` or `still open: <reason>`.
New findings continue numbering from the last round.

## 5. Stop and Ship

Agreed: APPROVE on the current behavior diff. No `blocker` or `should` is open. You yourself have no concerns as well. If this is an approval of a plan, mark the plan as `Status: READY`.
Stuck: An item stays disputed after two rounds, or budget ends. Show both sides in a brief 2-3 lines each. Let the user decide how to proceed.
Budget end is not approval.

Do not push during the loop. Push after agreement only if the user asked to push, ship, or update a PR.
If you create a PR or push to a PR, include the blurb `review-loop: <N> rounds with <model>`, Add ` on <effort>` only if the effort level is known.

Report: Rounds, Model, what was changed, diff size before/after, fixed and declined findings with reasons, usage if exposed (else don't say), and if we pushed or not.
