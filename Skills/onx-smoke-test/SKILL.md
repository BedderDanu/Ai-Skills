---
name: onx-smoke-test
description: Black-box test an onX (Order Network eXchange) MCP server and produce a findings report. Checks the advertised tool schemas against the Commerce Operations Foundation reference, then calls every tool over HTTP - protocol edge cases, a minimal call per query tool, filters and pagination built from real data, every returned record validated against the spec entity schemas, and optionally the create/update/fulfill/return/cancel flow - and writes a report plus a full request/response trace. Use this whenever someone wants to test, validate, certify, smoke-test, debug, or check conformance of an onX, OMS, fulfillment, WMS, or logistics MCP server, asks which onX tools are broken or missing, mentions the mcp-reference-server repo, or gives you an MCP endpoint URL for a commerce/logistics system - even if they do not say "onX", "conformance", or "smoke test".
disable-model-invocation: true
argument-hint: <server-url> [mutate]
compatibility: Python 3.9+ (standard library only), git on PATH, outbound HTTPS to the target server and github.com. Runs the server probes over HTTP; in a sandbox without egress only the declaration tier is possible.
---

# onX smoke test

Usage: `/onx-smoke-test <server-url> [mutate]`

- `$0` is the MCP Streamable-HTTP endpoint, including any `?x-api-key=` query parameter.
- `$1` is the mode. `mutate` (or `write`/`yes`) exercises the five action tools, which
  creates, updates, fulfils, returns and cancels orders on that server. Anything else, or
  nothing, is read-only.

Everything runs from one script. Do not re-implement the probing by hand; the value of
the skill is that every run does the same calls in the same order and cites the same
trace numbers.

## 1. Confirm the target

If no URL was given, ask for it. If `mutate` was requested, say in one line what that
will do (create orders prefixed `ONX-<timestamp>`, update and cancel them, and cancel
`--order-id` if one is passed) and that it must only be pointed at staging or a
disposable tenant. If the user has already said the environment is safe, that is
enough; do not ask again.

## 2. Run the driver in the background

```bash
python "${CLAUDE_SKILL_DIR}/scripts/smoke_test.py" "$0" $1
```

Run it with `run_in_background: true`. A full run makes 150 to 200 tool calls and takes
10 to 30 minutes depending on the server's latency; it prints a progress line every 20
calls and at each tier boundary, so you can read the output file to see where it is.
Wait for the completion notification. Do not poll in a loop, and do not start a second
run while one is in flight: two concurrent mutation runs interfere with each other.

The driver clones the reference spec into `~/.onx-smoke-test/mcp-reference-server` on
first use (set `ONX_SPEC_DIR` or `ONX_SPEC_REF` to override) and writes to
`./onx-reports/<host>-<timestamp>/`:

| file | what it is |
|---|---|
| `smoke-test.md` | the findings report, grouped by severity then tool |
| `smoke-test.json` | the same findings plus one row per call |
| `smoke-test.trace.jsonl` | every request body and raw response, in order, with timing |
| `conformance.md` | the L0 declaration report with a reproducible fingerprint |

Useful extra flags, passed through after the mode: `--sku` and `--location` when the
query tools return no data to harvest from, `--order-id <id>` to exercise
update/fulfill/return/cancel on an existing open order when create-sales-order cannot
produce one, `--token` for bearer auth, `--header K=V`, `--offline` to skip the spec
refresh.

If the driver exits immediately with `cannot list tools`, the host is unreachable from
this machine. Try one `curl` to the URL to tell "server down" from "sandbox has no
egress"; in a sandbox the fallback at the end of this file applies.

## 3. Read the report and write the summary

Read `smoke-test.md` in full before writing anything. Then report in this shape:

**Verdict line.** Counts from the report, and the tier they come from, e.g. "12 of 12
tools match the reference schemas, but at runtime: 29 bugs, 9 spec deviations, 2 blocked,
over 169 calls". A server can serve the spec's schemas byte for byte and still crash on
its simplest legal call, so never let a clean declaration tier read as "it works".

**What the run found**, as a ranked list, worst first. Group related findings into one
bullet: "every query tool crashes when `arguments` is omitted" is one bullet, not six.
Lead each bullet with the behaviour in bold, then the evidence. The severities mean:

- BUG: crashed, leaked an exception ("Cannot read property … of null"), ignored a filter,
  accepted invalid input, or returned data that contradicts an earlier call.
- SPEC: response shape deviates from the reference (typo'd keys such as `updatedAd`,
  required fields absent, values outside the schema's range).
- BLOCKED: the environment stopped the check (API key without write permission, no
  order to run the flow against). Say what unblocks it.
- WARN: nulls where the spec wants the field omitted, latency over the spec ceiling,
  backend errors leaked verbatim, no default page size.

**Blocked and skipped.** What could not be tested and the one thing that unblocks it.

**How to rerun**, as one command in a `bash` block, and the report folder path.

Keep record contents out of the summary. Counts, keys, ids, error text and trace
numbers are fine; customer names, emails and addresses are not, because `get-customers`
and orders carry personal data even on staging.

## 4. Help debug from the trace

Every finding cites `trace #N`. The trace is often the only debugging surface a low-code
or hosted implementation has, so when the user asks about a finding, pull the exact
request and response for that `seq` rather than describing it from memory:

```bash
python -c "import json; [print(json.dumps(json.loads(l), indent=1)) for l in open('onx-reports/<folder>/smoke-test.trace.jsonl') if json.loads(l)['seq']==N]"
```

Patterns worth naming when you see them, because the fix is usually obvious once named:

- **"must have X argument" for a spec-shaped payload.** The implementation reads its
  arguments one nesting level off (top level instead of under `order`, or the reverse).
  The driver probes both shapes and says which one the server accepts.
- **`{}` crashes but `{pageSize: n}` works.** No default page size is applied, the whole
  table is fetched, and one bad row (a null address, a null linked entity) kills
  serialisation. The report bisects to the record position and names the record before
  it so the row can be found in the backend.
- **Same crash text across action tools** (`'reduce' of undefined`, `'orderItems' of
  undefined`). One shared step, usually the order lookup or line-item mapping, fails
  before any tool-specific logic runs. Fix it once.
- **Leaked GraphQL or REST errors on malformed ids.** The server passes user input
  straight to the backend query. Validating id format, or catching the backend's type
  error and returning an empty list, removes the 15-second round trips too.
- **Typo'd output keys.** `values` for `value`, `returntotal` for `returnTotal`. A
  compliant client silently drops the field.

## Known spec gaps, so you do not fail a server for them

As of commit `3038a3f` on `develop`: the spec says stdio MUST be the primary transport
(a hosted server has none); the error model document and the reference server disagree
on error shape (structured `code`/`retryable` versus MCP `isError` plus text), so report
which one the server uses without calling either a violation; no output schema is bound
to any tool, so the driver takes the binding from the reference server's adapter
interface (`get-orders` returns `Order[]`, etc.) and says so; `statuses` and `outcomes`
have no published vocabulary, which is why the driver only filters on values the server
itself returned; and the reference server wraps results as `{"success": true,
"orders": [...]}` while the spec text never mandates it, so a bare array is INFO, not
SPEC.

## Fallback: the server is unreachable from bash

Agent sandboxes usually restrict egress to a package allowlist, so a host that the MCP
connector reaches fine is invisible to `curl`. Only the declaration tier is possible
then: load every tool from the connector so its `inputSchema` enters context, transcribe
them exactly (a mangled pattern or a parameter sitting beside `type` instead of under
`properties` is the finding, so do not tidy), write a `{"tools": [...]}` file, and run

```bash
python "${CLAUDE_SKILL_DIR}/scripts/onx_conformance.py" --spec <spec>/schemas --live live_tools.json --caveat "Live schemas transcribed from connector context, not fetched over HTTP."
```

For a liveness sample, call each query tool once through the connector with
`{"pageSize": 2}` and report structurally: counts, keys, error text. Never call a
mutating tool through the connector unless the user said so in chat, and say plainly in
the report that runtime coverage was partial.
