---
name: onx-conformance
description: Validate an MCP server's tools against the onX commerce/logistics reference schemas and produce a conformance report with a reproducible fingerprint. Use this whenever someone asks about onX conformance, wants to check or validate MCP tools or tool schemas against a spec, mentions the mcp-reference-server repo, asks which onX tools are implemented or missing, or wants a conformance/coverage report for a fulfillment, order, or logistics MCP server — even if they don't say "onX" or "conformance" by name.
disable-model-invocation: true
---

# onX MCP Conformance

Compares the tools an MCP server actually advertises against the onX reference
tool-input schemas, and writes a report that records exactly what was compared.

The report is meant to be shared and cited, so it carries a fingerprint: a hash
over the spec commit, every spec file, the live tool inventory, and every live
tool schema. Two people running this against the same inputs get the same run
ID; if anything moved, they don't.

## The one thing that trips people up

**The live tool schemas usually cannot be fetched over HTTP from the sandbox.**

Agent sandboxes typically restrict outbound network access to a package-manager
allowlist, so a local MCP server, an ngrok tunnel, or an internal preview host
is unreachable from `bash` even though the MCP *connector* is working fine in
the conversation.

The connector's tool definitions are the source. When a tool is loaded, its full
`inputSchema` is visible in context. Transcribe those schemas into a JSON file
and pass it with `--live`. Do not try to curl the server first and then fall
back — check reachability once, and expect to transcribe.

Preserve the schema **exactly**, including anything that looks like a mistake. A
mangled regex or a parameter sitting in the wrong place is the finding. Silently
tidying it up while transcribing destroys the result.

## Workflow

### 1. Get the spec

```bash
git clone --depth 1 --branch develop \
  https://github.com/commerce-operations-foundation/mcp-reference-server.git
```

Schemas live in `schemas/tool-inputs/`. Keep the clone — the checker reads the
git metadata for the fingerprint, and without it the report cannot say which
revision it validated against.

The spec declares no version of its own, so the commit SHA is the only
identifier. If the user mentions a newer or private spec revision, ask which
ref to use and note it as a caveat.

### 2. Get the live tools

Load every tool from the target MCP server so their schemas enter context. Tool
search is usually keyword-based and returns a handful at a time, so several
queries with different keywords are normally needed. Compare what has loaded
against the server's full tool list and keep going until they match, or until
it's clear a tool can't be reached — an uninspected tool is a caveat, not a
silent omission.

Then write a `tools/list`-shaped file:

```json
{"tools": [
  {"name": "get-orders", "description": "...", "inputSchema": { ... }}
]}
```

A bare array works too. If the server *is* reachable, skip all of this and pass
`--server URL --token TOKEN` instead — that path is strictly better, because the
hashes then fingerprint a real capture rather than a transcription.

### 3. Run the checker

```bash
python3 scripts/onx_conformance.py \
  --spec mcp-reference-server/schemas \
  --live live_tools.json \
  --caveat "Live schemas transcribed from connector context, not fetched over HTTP."
```

Writes `onx-conformance-report.md` and `.json`. Exit 0 if every onX-named tool
conforms, 1 otherwise. Add a `--caveat` for anything that qualifies the result —
uninspected tools, a spec ref that isn't the default branch, transcription.

### 4. Report back

Lead with the verdict — how many conform, what's unimplemented, what's outside
the spec — then the per-tool findings. Present the report file.

Read the coverage numbers for shape, not just totals. "5 of 12 implemented"
means something different when the 7 missing are all mutations than when they're
scattered; say which it is.

## What gets checked

A tool **fails** on spec violations: a malformed envelope, missing spec
parameters, a `type` that differs, `required` that differs, or a `pattern` that
diverges from the spec's.

Extra parameters and a missing `additionalProperties` are reported but do not
fail — they're often deliberate local extensions. Say so in the writeup rather
than presenting them as defects.

Three findings are worth understanding, because they're the ones that hide:

**Hoisted parameters.** An MCP `inputSchema` must nest parameters under
`properties`. When they sit as siblings of `type`, JSON Schema treats them as
unknown keywords and ignores them, so a compliant client sees a *parameterless
tool* — while the server still honours the parameters at runtime. It works in
the client you tested and breaks in the next one. Nothing in a normal schema
validation catches this, because the schema is valid; it just doesn't say what
its author thought.

**Pattern drift.** A `pattern` that differs from the spec's but still compiles
is invisible to every JSON Schema validator — only a byte-diff against the
reference finds it. The checker reports the divergence offset so the corruption
can be located.

**Placeholder descriptions.** A `statuses` parameter described as "various" with
no `enum` leaves the model guessing at valid values, and a wrong guess returns
an empty result rather than an error. Usually the finding with the largest
effect on real agent accuracy, and the easiest to overlook because the schema is
technically fine.

## Fingerprint

`run_id` = sha256, truncated to 24 hex chars, over key-sorted compact JSON of:
checker version, spec repo and commit, per-file spec hashes, the full live tool
inventory, and per-tool live schema hashes.

The checker version is included deliberately: without it, changing a rule would
produce different findings under an unchanged ID. Bump `CHECKER_VERSION` in the
script whenever the rules change.

Be straight about what this is. It's a checksum, not a signature — it proves two
runs saw identical inputs, not who ran them or that the report wasn't edited
afterward. The timestamp is excluded from the hash so the ID stays reproducible,
which also means it can't distinguish two runs on different days. If someone
needs the report to be evidence rather than a record, that needs signing, and
the live side needs a real HTTP capture.
