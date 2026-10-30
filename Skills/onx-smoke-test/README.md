# onx-smoke-test

A Claude Code skill that black-box tests an onX (Order Network eXchange) MCP server
against the Commerce Operations Foundation reference and writes a findings report.

```
/onx-smoke-test https://host/path/to/mcp?x-api-key=...            # read-only
/onx-smoke-test https://host/path/to/mcp?x-api-key=... mutate     # also exercises the action tools
```

## Install

Copy this folder to one of:

- `~/.claude/skills/onx-smoke-test/` (personal, every project)
- `<repo>/.claude/skills/onx-smoke-test/` (shared with everyone who clones the repo)

Requirements: Python 3.9+ (standard library only), `git` on PATH (to fetch the spec),
and outbound HTTPS to the server and to github.com. The first run clones
`commerce-operations-foundation/mcp-reference-server` into
`~/.onx-smoke-test/`; later runs refresh it.

The scripts also work without Claude:

```bash
python scripts/smoke_test.py "https://host/mcp?x-api-key=..." mutate --sku ABC-123
```

## What it does

| tier | check | script |
|---|---|---|
| L0 declaration | advertised `inputSchema` matches the reference, with a reproducible fingerprint | `onx_conformance.py` |
| L0 protocol | initialize, ping, unknown method/tool, malformed JSON, all 12 tools advertised | `onx_exercise.py` |
| L1 liveness | one minimal call per query tool | `onx_exercise.py` |
| L2 contract | every filter the schema allows, built from harvested data and verified; pagination; negative inputs; every record validated against the spec entity schemas | `onx_exercise.py` |
| L3 mutation (`mutate`) | negatives, then create (minimal and maximal) → read back → update → fulfill → get-fulfillments → return → get-returns → cancel → cancel twice, with echo checks | `onx_exercise.py` |

Output goes to `./onx-reports/<host>-<timestamp>/`:

- `smoke-test.md` findings by severity (BUG, SPEC, BLOCKED, WARN, INFO, PASS) and tool
- `smoke-test.json` the same plus one row per call
- `smoke-test.trace.jsonl` every request and raw response, in order; findings cite `seq`
- `conformance.md` the L0 report with `run_id`

A full run is 150 to 200 tool calls and takes 10 to 30 minutes at typical hosted
latency.

## Notes for implementers

- `mutate` creates real orders (externalId `ONX-<timestamp>-…`), updates, fulfils,
  returns and cancels them. Staging or disposable tenants only.
- Cloudflare-fronted hosts reject Python's default user agent with 403; the scripts set
  their own. If you write ad-hoc probes, set `User-Agent`.
- Known spec gaps (transport, error shape, unbound output schemas, missing status
  vocabularies) are listed in `SKILL.md` and are reported as notes rather than failures.

## Files

```
onx-smoke-test/
├── SKILL.md                 instructions Claude follows
├── README.md                this file
└── scripts/
    ├── smoke_test.py        driver: fetch spec, run both checkers, print paths
    ├── onx_exercise.py      runtime exerciser (tiers L0 protocol through L3)
    └── onx_conformance.py   declaration checker with reproducible fingerprint (OCF original)
```
