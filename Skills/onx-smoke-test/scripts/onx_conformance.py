#!/usr/bin/env python3
"""
onX MCP conformance checker.

Compares an MCP server's advertised tools against the onX reference
tool-input schemas and emits a report with a reproducible fingerprint.

  # from a captured tools/list dump (the usual path)
  ./onx_conformance.py --spec ./schemas --live ./live_tools.json

  # straight from a reachable server
  ./onx_conformance.py --spec ./schemas --server https://host/mcp/messages --token $TOK

Outputs <prefix>.md and <prefix>.json. Exit 0 if every onX-named tool
conforms, 1 otherwise.
"""
import argparse, datetime, hashlib, json, re, subprocess, sys, urllib.error, urllib.request
from pathlib import Path

# Bump when the rules below change. Folded into the fingerprint so that an
# identical spec + identical tools under different rules yields a different
# run_id -- otherwise a rule change silently produces a "matching" report.
CHECKER_VERSION = "1.0.0"
PROTOCOL_VERSION = "2025-06-18"

# JSON Schema keywords, used to tell a real keyword from a parameter that has
# been mistakenly hoisted up next to `type`.
KEYWORDS = {
    "$schema", "$id", "$ref", "$defs", "$comment", "definitions", "type",
    "properties", "required", "additionalProperties", "title", "description",
    "default", "enum", "const", "format", "pattern", "items", "prefixItems",
    "minItems", "maxItems", "uniqueItems", "minimum", "maximum",
    "exclusiveMinimum", "exclusiveMaximum", "minLength", "maxLength",
    "multipleOf", "oneOf", "anyOf", "allOf", "not", "if", "then", "else",
    "examples", "deprecated", "readOnly", "writeOnly", "patternProperties",
    "propertyNames", "nullable",
}


def canon(obj):
    """Key-sorted compact JSON so hashes track meaning, not formatting."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def sha(b, n=16):
    return hashlib.sha256(b).hexdigest()[:n]


def params(schema):
    """
    Return (params, envelope).

    An MCP inputSchema must nest its parameters under `properties`. When they
    sit as siblings of `type` instead, JSON Schema treats them as unknown
    keywords and ignores them -- the tool advertises no parameters at all,
    even though the server may still honour them at runtime. Detect that here
    rather than silently reporting zero params.
    """
    if not isinstance(schema, dict):
        return {}, "invalid"
    if "properties" in schema:
        return schema["properties"], "nested"
    hoisted = {k: v for k, v in schema.items()
               if k not in KEYWORDS and isinstance(v, dict)}
    return hoisted, ("hoisted" if hoisted else "empty")


# --------------------------------------------------------------- MCP client

class McpClient:
    """Minimal Streamable-HTTP MCP client: initialize -> tools/list."""

    def __init__(self, url, token=None, timeout=30):
        self.url, self.token, self.timeout = url, token, timeout
        self.session_id, self._id = None, 0

    def _post(self, method, params=None, notify=False):
        self._id += 1
        body = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            body["params"] = params
        if not notify:
            body["id"] = self._id
        headers = {"Content-Type": "application/json",
                   "Accept": "application/json, text/event-stream",
                   "MCP-Protocol-Version": PROTOCOL_VERSION,
                   # Cloudflare-fronted hosts reject urllib's default agent with a 403
                   "User-Agent": f"onx-conformance/{CHECKER_VERSION}"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        req = urllib.request.Request(self.url, data=json.dumps(body).encode(),
                                     headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                if r.headers.get("Mcp-Session-Id"):
                    self.session_id = r.headers["Mcp-Session-Id"]
                raw, ctype = r.read().decode(), r.headers.get("Content-Type", "")
        except urllib.error.HTTPError as e:
            sys.exit(f"HTTP {e.code} from {self.url}\n{e.read().decode()[:400]}")
        except urllib.error.URLError as e:
            sys.exit(f"cannot reach {self.url}: {e.reason}")
        if notify or not raw.strip():
            return None
        if "text/event-stream" in ctype:
            for line in raw.splitlines():
                if line.startswith("data:"):
                    msg = json.loads(line[5:].strip())
                    if "result" in msg or "error" in msg:
                        return msg
            sys.exit("no JSON-RPC message in SSE stream")
        return json.loads(raw)

    def tools(self):
        init = self._post("initialize", {
            "protocolVersion": PROTOCOL_VERSION, "capabilities": {},
            "clientInfo": {"name": "onx-conformance", "version": CHECKER_VERSION}})
        if init and "error" in init:
            sys.exit(f"initialize failed: {init['error']}")
        self._post("notifications/initialized", notify=True)
        out, cursor = [], None
        while True:
            res = self._post("tools/list", {"cursor": cursor} if cursor else {})
            if "error" in res:
                sys.exit(f"tools/list failed: {res['error']}")
            out.extend(res["result"].get("tools", []))
            cursor = res["result"].get("nextCursor")
            if not cursor:
                return out


# ------------------------------------------------------------------- checks

def check_tool(name, spec, live):
    sp, _ = params(spec)
    lp, envelope = params(live)

    pattern_drift = []
    for k in sorted(set(sp) & set(lp)):
        s_pat, l_pat = sp[k].get("pattern"), lp[k].get("pattern")
        if s_pat and l_pat and s_pat != l_pat:
            i = next((i for i, (a, b) in enumerate(zip(s_pat, l_pat)) if a != b),
                     min(len(s_pat), len(l_pat)))
            pattern_drift.append({
                "param": k, "offset": i,
                "spec": s_pat[max(0, i - 8):i + 8],
                "live": l_pat[max(0, i - 8):i + 8]})

    type_drift = [
        {"param": k, "spec": sp[k].get("type"), "live": lp[k].get("type")}
        for k in sorted(set(sp) & set(lp))
        if sp[k].get("type") != lp[k].get("type")]

    s_req = set(spec.get("required", []) or [])
    l_req = set(live.get("required", []) or [])

    r = {
        "envelope": envelope,
        "additionalProperties": "additionalProperties" in live,
        "spec_param_count": len(sp),
        "live_param_count": len(lp),
        "missing_params": sorted(set(sp) - set(lp)),
        "extra_params": sorted(set(lp) - set(sp)),
        "pattern_drift": pattern_drift,
        "type_drift": type_drift,
        "required_drift": (None if s_req == l_req
                           else {"spec": sorted(s_req), "live": sorted(l_req)}),
        "placeholder_enums": sorted(
            k for k, v in lp.items()
            if re.search(r"\b(various|TBD|TODO|N/A)\b", v.get("description", ""), re.I)
            and "enum" not in v and "enum" not in v.get("items", {})),
    }
    # Extra params and missing additionalProperties are divergence worth
    # reporting but not necessarily defects -- they may be deliberate local
    # extensions. Only spec violations fail the tool.
    r["pass"] = (envelope == "nested" and not r["missing_params"]
                 and not pattern_drift and not type_drift
                 and r["required_drift"] is None)
    return r


# ------------------------------------------------------------------- report

def render(meta, coverage, results, spec_hashes, live_hashes):
    L, w = [], lambda s="": L.append(s)
    shared = coverage["implemented"]
    npass = sum(1 for n in shared if results[n]["pass"])

    w("# onX MCP Conformance Report")
    w()
    w(f"**Run ID `{meta['run_id']}`** · {meta['generated']} · checker v{meta['checker_version']}")
    w()
    w("## Verdict")
    w()
    w(f"**{npass} of {len(shared)}** onX-named tools conform. "
      f"{len(coverage['missing'])} spec tools unimplemented; "
      f"{len(coverage['extra'])} live tools outside the spec.")
    w()
    if shared:
        w("| tool | envelope | addlProps | spec | live | missing | verdict |")
        w("|---|---|---|---:|---:|---|---|")
        for n in shared:
            r = results[n]
            w(f"| `{n}` | {r['envelope']} | {'yes' if r['additionalProperties'] else 'no'} "
              f"| {r['spec_param_count']} | {r['live_param_count']} "
              f"| {', '.join(f'`{p}`' for p in r['missing_params']) or '—'} "
              f"| {'PASS' if r['pass'] else '**FAIL**'} |")
        w()
        w("## Findings")
        w()
        for n in shared:
            r = results[n]
            if r["pass"] and not r["extra_params"]:
                continue
            w(f"### `{n}`")
            if r["envelope"] == "hoisted":
                w("- **Malformed envelope.** Parameters sit as siblings of `type` rather than "
                  "under `properties`, so JSON Schema ignores them as unknown keywords and a "
                  "compliant client sees a parameterless tool. The server may still honour them "
                  "at runtime, which is what makes this easy to miss.")
            elif r["envelope"] in ("empty", "invalid"):
                w(f"- **No usable inputSchema** (envelope: {r['envelope']}).")
            if not r["additionalProperties"]:
                w("- No top-level `additionalProperties`; strict-mode clients reject.")
            if r["missing_params"]:
                w(f"- Missing spec parameters: {', '.join(f'`{p}`' for p in r['missing_params'])}")
            if r["extra_params"]:
                w(f"- Parameters not in spec: {', '.join(f'`{p}`' for p in r['extra_params'])}")
            for d in r["pattern_drift"]:
                w(f"- `{d['param']}`: `pattern` diverges at char {d['offset']} — "
                  f"spec `{d['spec']}` vs live `{d['live']}`. Still compiles, so no schema "
                  "validator flags it.")
            for d in r["type_drift"]:
                w(f"- `{d['param']}`: type `{d['spec']}` in spec, `{d['live']}` live.")
            if r["required_drift"]:
                w(f"- `required` differs — spec {r['required_drift']['spec']}, "
                  f"live {r['required_drift']['live']}.")
            if r["placeholder_enums"]:
                w(f"- Placeholder descriptions with no `enum`: "
                  f"{', '.join(f'`{p}`' for p in r['placeholder_enums'])}. The model has to "
                  "guess valid values and fails silently when it guesses wrong.")
            w()
    w("## Coverage")
    w()
    w(f"**Unimplemented ({len(coverage['missing'])}):** "
      + (", ".join(f"`{n}`" for n in coverage["missing"]) or "none"))
    w()
    w(f"**Outside the spec ({len(coverage['extra'])}):** "
      + (", ".join(f"`{n}`" for n in coverage["extra"]) or "none"))
    w()
    if meta.get("caveats"):
        w("## Caveats")
        w()
        for c in meta["caveats"]:
            w(f"- {c}")
        w()
    w("## Fingerprint")
    w()
    w("```json")
    w(json.dumps({k: v for k, v in meta.items() if k != "caveats"}, indent=2))
    w("```")
    w()
    w("`run_id` = sha256 over key-sorted compact JSON of: checker version, spec repo and "
      "commit, per-file spec hashes, the full live tool inventory, and per-tool live schema "
      "hashes — truncated to 24 hex chars. Identical inputs reproduce it; any change to the "
      "spec, the served tools, or the checker rules changes it. It is a checksum, not a "
      "signature: it detects drift, it does not attest to who ran it.")
    w()
    w("### Spec tool-inputs")
    w()
    w("| file | sha256[:16] |")
    w("|---|---|")
    for n, h in spec_hashes.items():
        w(f"| `{n}.json` | `{h}` |")
    w()
    w("### Live tool schemas")
    w()
    w("| tool | sha256[:16] |")
    w("|---|---|")
    for n, h in live_hashes.items():
        w(f"| `{n}` | `{h}` |")
    return "\n".join(L) + "\n"


# --------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--spec", required=True, help="path to the onX schemas/ directory")
    ap.add_argument("--live", help="JSON file: tools/list result, or a bare array of tools")
    ap.add_argument("--server", help="MCP endpoint URL (alternative to --live)")
    ap.add_argument("--token", help="bearer token for --server")
    ap.add_argument("--out", default="onx-conformance-report", help="output prefix")
    ap.add_argument("--caveat", action="append", default=[],
                    help="note to include in the report; repeatable")
    args = ap.parse_args()

    spec_dir = Path(args.spec)
    tool_dir = spec_dir / "tool-inputs" if (spec_dir / "tool-inputs").is_dir() else spec_dir
    spec_docs = {f.stem: json.loads(f.read_text()) for f in sorted(tool_dir.glob("*.json"))}
    if not spec_docs:
        sys.exit(f"no *.json under {tool_dir}")

    if args.live:
        raw = json.loads(Path(args.live).read_text())
        tools = raw.get("tools", raw) if isinstance(raw, dict) else raw
    elif args.server:
        tools = McpClient(args.server, args.token).tools()
    else:
        sys.exit("need --live or --server")
    live_docs = {t["name"]: t.get("inputSchema", {}) for t in tools}

    def git(*a):
        try:
            return subprocess.check_output(["git", "-C", str(spec_dir), *a],
                                           stderr=subprocess.DEVNULL).decode().strip()
        except Exception:
            return None

    shared = sorted(set(spec_docs) & set(live_docs))
    coverage = {"spec_total": len(spec_docs), "live_total": len(live_docs),
                "implemented": shared,
                "missing": sorted(set(spec_docs) - set(live_docs)),
                "extra": sorted(set(live_docs) - set(spec_docs))}
    results = {n: check_tool(n, spec_docs[n], live_docs[n]) for n in shared}

    spec_hashes = {n: sha(canon(d)) for n, d in sorted(spec_docs.items())}
    # Hash every live schema, not only the onX-named ones -- otherwise a change
    # to a local-only tool leaves the fingerprint untouched.
    live_hashes = {n: sha(canon(d)) for n, d in sorted(live_docs.items())}

    run_id = sha(canon({
        "checker_version": CHECKER_VERSION,
        "spec_repo": git("config", "--get", "remote.origin.url"),
        "spec_commit": git("rev-parse", "HEAD"),
        "spec_files": spec_hashes,
        "live_tool_inventory": sorted(live_docs),
        "live_schemas": live_hashes,
    }), 24)

    meta = {
        "run_id": run_id,
        "generated": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "checker_version": CHECKER_VERSION,
        "spec_repo": git("config", "--get", "remote.origin.url"),
        "spec_commit": git("rev-parse", "HEAD"),
        "spec_commit_date": git("log", "-1", "--format=%cI"),
        "spec_ref": git("rev-parse", "--abbrev-ref", "HEAD"),
        "live_source": args.server or args.live,
        "live_tools_total": len(live_docs),
        "caveats": args.caveat,
    }

    Path(f"{args.out}.md").write_text(
        render(meta, coverage, results, spec_hashes, live_hashes))
    Path(f"{args.out}.json").write_text(json.dumps(
        {"meta": meta, "coverage": coverage, "results": results,
         "spec_hashes": spec_hashes, "live_hashes": live_hashes}, indent=2))

    npass = sum(1 for n in shared if results[n]["pass"])
    print(f"run_id {run_id}")
    print(f"{npass}/{len(shared)} conform · {len(coverage['missing'])} unimplemented "
          f"· {len(coverage['extra'])} outside spec")
    print(f"wrote {args.out}.md and {args.out}.json")
    return 0 if npass == len(shared) else 1


if __name__ == "__main__":
    sys.exit(main())
