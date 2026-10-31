# Skill spec checklist

## Contents
1. Frontmatter fields
2. Naming
3. Description
4. Body and references
5. Packaging

Use this whenever DESIGN or AUDIT involves a skill — proposing one, or checking one that already exists. This is a packaging/format check, separate from the bucket test that decides whether this content belongs in a skill at all. A skill can pass one and fail the other; check both, and don't let a pass on one stand in for the other.

---

## 1. Frontmatter fields

| Field | Required | Constraint |
|---|---|---|
| `name` | Yes | Max 64 chars. Lowercase letters, numbers, hyphens only. No leading/trailing or doubled hyphens. Must match the parent directory name. Cannot contain "anthropic" or "claude". |
| `description` | Yes | Max 1024 chars, non-empty, no XML tags. Third person. Must say what it does *and* when to use it. |
| `license` | No | |
| `compatibility` | No | Max 500 chars. Most skills don't need it. |
| `metadata` | No | Free-form map. Version goes here — it is not a top-level field. |
| `allowed-tools` | No | Space-separated pre-approved tools. Experimental. |

Harness-specific fields (for example Claude Code's `argument-hint` and `disable-model-invocation`) are allowed. Check them against that harness's docs, not this table.

Secondary sources sometimes show a lowercase `skill.md` filename, a capitalized name with spaces, a 200-character description limit, a `dependencies` field, or a `## Metadata` markdown heading in place of YAML frontmatter. All five contradict the specification; follow the spec.

## 2. Naming

Check the proposed or existing `name` against the frontmatter constraints above.

Violation: the name doesn't match its parent directory, contains a doubled/leading/trailing hyphen, exceeds 64 characters, uses anything but lowercase letters/numbers/hyphens, or contains "anthropic" or "claude".

## 3. Description

Third person, always — "Generates database migrations," not "I can help you build" or "You can use this to." Must name what the skill does *and* when to use it, including words a user would actually type (the literal task names, not just a category label).

Violation: first- or second-person phrasing, a description that only says what it does with no "when to use" clause (or vice versa), over 1024 characters, or vague language that could describe several skills ("helps with documents").

## 4. Body and references

Body under 500 lines, target under 5,000 tokens. References stay one level deep from `SKILL.md` — a reference file may not itself point to another reference file. Any reference file over 100 lines carries a table of contents at the top, because an agent may preview it with a partial read.

Violation: body over the line/token target, a reference-of-a-reference chain, or a reference file over 100 lines with no table of contents.

## 5. Packaging

`SKILL.md` sits at the root of the skill folder, with optional `scripts/`, `references/`, `assets/` alongside it. When the skill is uploaded as a ZIP, the skill folder itself is the archive root — not nested inside an extra subfolder. When a project mirrors skills for a second harness (for example `.claude/skills/` copied to `.agents/skills/`), the mirror matches its source.

Violation: `SKILL.md` not at the folder root, a ZIP with an added nesting level between the archive root and the skill folder, or a mirror that differs from its source.
