---
name: push-plan
description: Pushes an executed plan's branch, opens its pull request, drives CI to green, marks the plan COMPLETE, and squash-merges only when asked. Use when the user asks to "push the plan" or "push the plan and merge", or invokes /push-plan after /execute-plan.
argument-hint: <./path/to/plan-file.md> [merge]
metadata:
  harness: [codex, claude]
  requires: "git, gh, or some other git based archiving tool"
---

# /push-plan — publish an executed plan

You are responsible for getting an executed plan's branch merge-ready in the primary source control system, and merging it when asked.
Examples below use git and gh (GitHub). Where the repository's AGENTS.md or tooling sets a different convention, follow it. If the remote is not GitHub and no convention is documented, stop and ask.

`<plan-file-stem>` is the plan's file name without `.md` and without a `.complete` suffix. It stays the same after step 3 renames the file.

## Hard rules
1. Start only when the user's own message in this session asks to push this plan. Never start it because another skill's instructions say to.
2. Push only `plan/<plan-file-stem>`. Never commit to or push the default branch.
3. Never force-push.
4. Merge only when the request says merge. Never pass `--admin`, and never bypass a required review or check.
5. Do not edit CI configuration, or delete, skip, or loosen a test or change its expected value, without the user's approval (see step 2).

## 0. Preflight

1. Derive `<plan-file-stem>` from the argument. With no argument, use the current branch if it is `plan/<stem>`; otherwise list the plans with `Status: EXECUTED` or `COMPLETE` and ask. `gh auth status --hostname github.com` must succeed. Read the default branch with `gh repo view --json defaultBranchRef -q .defaultBranchRef.name`.
2. Look for an existing PR: `gh pr list --head plan/<plan-file-stem> --state all --json number,state,url,headRefOid`. If there are several, use the most recent.
   - Merged: go to step 5, then Finish.
   - Closed without merging: ask the user before opening another.
   - Open: record its number; step 1 reuses it.
3. If `git worktree list` shows `plan/<plan-file-stem>` checked out in another worktree, work in that worktree. Otherwise check the branch out here. The working tree must be clean (`git status --porcelain` prints nothing) before a checkout and in the tree you work in; if it is dirty, list what's there and stop. Exception: if the only change is to the plan file (a step 3 interrupted before its commit), read the plan (item 4) and continue at step 3.
4. Resolve the plan file the same way /execute-plan does. Also look for `<plan-file-stem>.complete.md` beside it or in a `complete/` or `finished/` subfolder. Read the plan fully.
5. `Status` decides the entry point:
   - `EXECUTED`: continue.
   - `COMPLETE`: an earlier run reached step 3. If `git rev-parse HEAD` differs from the PR's `headRefOid`, the `Complete` commit wasn't pushed: continue at step 3 item 6. If the head commit is `Plan: <plan-file-stem> Complete [skip ci]`, CI was green before it. Otherwise read the PR head's checks as in step 2, and send a failure to step 2's failure handling. Once CI is green, go to step 4 if merge was requested, or report and stop.
   - Anything else: stop and tell the user. The plan has not finished /execute-plan.
6. If the `## Progress Log` has any `### Stage <N> — blocked` or `### Stage <N> — skipped` entry, list those stages and ask the user to confirm before step 1. On confirmation, continue and include them in the PR body; otherwise stop.

## 1. Create the PR

1. `git push -u origin plan/<plan-file-stem>`. If the push is rejected, stop and report.
2. Write the PR body to `<pr-body-file>`, a temporary file outside the repo (`mktemp`), built from the plan:
   - The `## Completion record` summary and the stage list.
   - The plan file path.
   - Any blocked or skipped stages the user accepted in preflight.
   - Every `## Post-Acceptance verification` item still marked pending.
   - If the `## Progress Log` has `### Review round` entries: `review-loop: <N> rounds with <model>[ on <effort>]`, using the model and effort in the round headings.
3. With no open PR: `gh pr create --base <default-branch> --head plan/<plan-file-stem> --title "<the plan's # heading>" --body-file <pr-body-file>`. With an open PR: `gh pr edit <n> --body-file <pr-body-file>`. Record the PR number and URL.
4. Check `gh pr view <n> --json mergeable -q .mergeable`. `UNKNOWN` means GitHub is still computing; check once more, and if it's still `UNKNOWN`, continue (step 4 checks again). `CONFLICTING` means the default branch moved underneath the plan: stop and tell the user. Resolving it (rebase or merge) is their call.

## 2. Review CI

After a push, confirm that `gh pr view <n> --json headRefOid -q .headRefOid` equals `git rev-parse HEAD` before reading any checks, re-checking until it does; otherwise you read the previous commit's checks. Then wait for the checks, for at most 60 minutes. If your harness offers a PR-watching tool, use it. Otherwise run `timeout 60m gh pr checks <n> --watch --interval 30` (or the platform's equivalent of `timeout`). If your shell limits a command's run time below that, run the watch in the background or repeat shorter watches until the 60 minutes are up. Do not read the result from the exit code. Read `gh pr checks <n> --json name,bucket,state,link`:
- Every check's `bucket` is `pass` or `skipping`: CI is green. Go to the Review-loop subsection, then step 3.
- Any `bucket` is `fail` or `cancel`: go to "On a failure".
- Checks still `pending` when the time limit ends (a required check that never starts stays pending): report them and stop.
- "no checks reported": if the repo has no CI configuration (`.github/workflows/` or the repo's equivalent), the project has no PR CI; note that for the report and go to step 3. If CI configuration exists, check once more after a minute. If there are still no checks, tell the user CI did not start and stop.

On a failure:
1. Take each failing check's `link`. If one is not a GitHub Actions run (`…/actions/runs/<run-id>…`), report the check and its link to the user and stop. Otherwise read `gh run view <run-id> --log-failed`.
2. If the log points at nothing the branch changed (a network timeout, runner error, or registry outage), or the check was cancelled, rerun that run once with `gh run rerun <run-id> --failed`, then wait again. A run whose `gh run view <run-id> --json attempt` is above 1 has already been rerun. A rerun is not a correction. A second failure of the same run is a real failure.
3. If the fix would edit CI configuration (`.github/workflows/**` or the repo's equivalent), or delete, skip, or loosen a test or change its expected value, stop. Show the user the failing log excerpt and the proposed change, and wait for approve or deny. On deny, tell the user what is still failing and stop.
4. Otherwise fix the code. Append `### CI Correction <N> — <done|blocked>` to the plan's `## Progress Log`: the failing check and run URL, the cause, the fix, and the files touched. Commit the fix and the log entry together as `Plan: <plan-file-stem> CI Correction <N>: <summary>`, push, and wait again.
5. After three CI Corrections since the last `blocked` entry without a green run, or when a failure can't be fixed, mark the last `CI Correction` entry `blocked`. Commit it as `Plan: <plan-file-stem> CI Correction <N>: blocked`, push, tell the user what is failing, and stop.

### Review-loop
Run this only if the user asked for a review loop, at least one CI Correction landed, and no `### Review round` entry follows the latest `CI Correction` entry in the `## Progress Log`. Once CI is green, invoke the `review-loop` skill and name its base: the parent of the first `CI Correction` commit since the last review round. That is `<sha>^`, where `<sha>` comes from `git log --format=%H --fixed-strings --grep='Plan: <plan-file-stem> CI Correction <N>:' origin/<default-branch>..HEAD`. Log each round as `### Review round: <N> (<model>[ on <effort>])` in the `## Progress Log`, continuing the existing numbering. Commit review fixes together with their log entries as `Plan: <plan-file-stem> Review round <N>: <summary>`. If the loop ends agreed, push and wait for CI again (step 2). If it ends stuck, stop and let the user decide, as review-loop says.

## 3. Final PR update

Once CI is green on the current head, or the project has no PR CI, do each item below that an earlier run hasn't already done:
1. Set `Status: COMPLETE`. The user's push-plan request is the human approval that /execute-plan's Phase 3 waits for.
2. In `## Post-Acceptance verification`, record the CI result (pass and run URL) in each row that names CI. Leave every other pending row as pending.
3. Add `PR: <url>` to the `## Completion record`.
4. `git mv` the plan to `<plan-file-stem>.complete.md`: into the plan folder's `complete/` or `finished/` subfolder if it has one, otherwise in place.
5. Stage the plan and commit as `Plan: <plan-file-stem> Complete`. Add ` [skip ci]` to the subject only when both of these hold, checked before committing:
   - `git diff --cached --stat` lists nothing but the plan file (or its rename).
   - `gh pr checks <n> --required` lists no required checks. With none, it prints "no required checks reported" and exits 1; that counts as none.
6. Push. If the commit has no skip token, wait for CI as in step 2. A failure goes to step 2's failure handling; green continues here.
7. Rebuild `<pr-body-file>` (the plan's new path, the current review-loop count, the pending Post-Acceptance items) and run `gh pr edit <n> --body-file <pr-body-file>`.

Then go to step 4 if merge was requested, otherwise Finish.

## 4. Merge (only when requested)

1. Read `gh pr view <n> --json mergeStateStatus,reviewDecision,headRefOid`:
   - `CLEAN` or `HAS_HOOKS`: merge.
   - `UNKNOWN`: GitHub is still computing. Check once more, and if it's still `UNKNOWN`, report and stop.
   - `BLOCKED` only because a required review or check is pending (`reviewDecision` is `REVIEW_REQUIRED`, or `gh pr checks <n> --required` shows a `pending` bucket): offer to run item 2's command with `--auto` added. On the user's yes, run it, report that auto-merge is enabled, and stop.
   - Anything else (`BEHIND` the base, `DIRTY` with conflicts, `UNSTABLE` with a failing non-required check, `BLOCKED` for another reason): stop and report it.
2. Write `<merge-body-file>` with the plan title, the plan's current path, and the PR URL, without a skip token. Squash merge with an explicit message, so the commits' text (including any `[skip ci]`) does not end up in the default branch's commit:
   `gh pr merge <n> --squash --match-head-commit <headRefOid> --subject "<PR title> (#<n>)" --body-file <merge-body-file>`
3. Confirm with `gh pr view <n> --json state,mergeCommit` that `state` is `MERGED`, and record the merge commit SHA for the report. If gh reports the PR was added to a merge queue, report it as queued and stop. Rerunning push-plan after it merges does the cleanup.

## 5. Local system cleanup (after a confirmed merge only)

Without a merge, list what could be cleaned up in the report and remove nothing. After a merge confirmed in step 4 or in preflight:
1. `git worktree list`. The first entry is the main working tree; skip it. For each other worktree on `plan/<plan-file-stem>` whose `git -C <path> status --porcelain` prints nothing, run `git worktree remove <path>`, then `git worktree prune`. Leave the worktree this session runs in and any worktree your harness created, and name them in the report.
2. If the main working tree is on `plan/<plan-file-stem>`, run `git checkout <default-branch> && git pull --ff-only` there. Otherwise leave it. If the pull fails, report it and leave it.
3. `git branch -D plan/<plan-file-stem>`, but only when `git rev-parse plan/<plan-file-stem>` equals the merged PR's `headRefOid` and no remaining worktree has the branch checked out. Otherwise skip it and say why in the report, because local commits the PR never had would be lost. `-D` is needed because git doesn't recognise a squash-merged branch as merged, and it is safe only because the merge was confirmed.
4. If `git ls-remote --exit-code --heads origin plan/<plan-file-stem>` finds the branch (some repos delete it on merge), run `git push origin --delete plan/<plan-file-stem>`. Then `git fetch --prune`.

Delete nothing except this plan's worktrees and branches.

## Finish

Report:
- PR URL and the final state of each check.
- CI Corrections and review rounds, and what they changed.
- Blocked or skipped stages the user accepted.
- The plan's `Status` and its path now.
- Merged (with the merge commit SHA), queued, or not merged.
- What was cleaned up, and what was left and why.
- Every `## Post-Acceptance verification` item still pending.
