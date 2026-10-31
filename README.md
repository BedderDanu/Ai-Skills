# Ai-Skills
A collection of skills I've written and used.

In theory, designed around any skill running out of any harness.

I use T3 Code, so these are written to assume that Codex can call Claude, etc.

USAGE:
 - make-plan: A modification of the matt pocock grilling skill at https://github.com/mattpocock/skills/blob/main/skills/productivity/grilling/SKILL.md, but it asks questions about your current thread, and then saves the result in a "plan.md" field.
 - execute-plan: Have a model look at the plan file that was created with make-plan, and attempt to carry the plan's work all the way to the end. It doesn't attempt to push or merge. It logs its progress notes, so that if the thread is interrupted it can be restarted from where it left off.
 - push-plan: Create a PR for the work that landed with the plan. Assists with babysitting the CI, making corrections as necessary. Only merges if you ask it to merge along with the push-plan request.
 - review-loop: Ask a specific model to review the work that was done in the repository, and provide feedback to the main model's thread.  Designed to be combined with the other skills above. For example, from Claude Opus, run something to the effect of "/make-plan lets redo the splash page to make it more business professional. Once we're done grilling review loop with GPT Sol." or "/execute-plan ./docs/plans/splash-page-redesign.md, and then review loop with Claude Sonnet"
 - instruction-review: Look at a skill or an agent's guidance file (AGENTS.md, CLAUDE.md, etc.) and reviews it for duplicate guidance, conflicting direction, and unclear instructions, and then offers sections to be rewritten, cut, or clarified. 
