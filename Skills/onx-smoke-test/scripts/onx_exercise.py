#!/usr/bin/env python3
"""
onX MCP runtime exerciser.

Black-box tests an onX MCP server over Streamable HTTP, in four tiers:

  L0  protocol + declaration   initialize / tools/list / error codes, and the
                               advertised inputSchemas vs the spec (delegates
                               to onx_conformance.py when --spec is given)
  L1  liveness                 one minimal call per query tool
  L2  contract                 filters, pagination, negative inputs, and every
                               returned record validated against the spec's
                               entity schemas
  L3  mutation (--mutate)      create -> read -> update -> fulfill -> return
                               -> cancel, with echo checks on what comes back

Everything the server was sent and everything it answered goes to a JSONL
trace, so a low-code implementation can be debugged from inputs and outputs
alone.

  python onx_exercise.py --server URL --spec ./mcp-reference-server/schemas
  python onx_exercise.py --server URL --spec ./schemas --mutate --sku ABC-123

Exit code: 0 no BUG/SPEC findings, 1 otherwise, 2 could not reach the server.
"""
import argparse, datetime, difflib, json, re, sys, time, urllib.error, urllib.request
from pathlib import Path

VERSION = "0.3.0"
PROTOCOL_VERSION = "2025-06-18"
UA = f"onx-exercise/{VERSION}"

QUERY_TOOLS = ["get-products", "get-product-variants", "get-orders", "get-customers",
               "get-fulfillments", "get-returns", "get-inventory"]
ACTION_TOOLS = ["create-sales-order", "update-order", "fulfill-order", "create-return",
                "cancel-order"]
# tool -> (entity schema file stem, key used by the reference envelope)
ENTITY = {
    "get-products": ("product", "products"),
    "get-product-variants": ("product-variant", "productVariants"),
    "get-orders": ("order", "orders"),
    "get-customers": ("customer", "customers"),
    "get-fulfillments": ("fulfillment", "fulfillments"),
    "get-returns": ("return", "returns"),
    "get-inventory": ("inventory", "inventory"),
    "create-sales-order": ("order", "order"),
    "update-order": ("order", "order"),
    "cancel-order": ("order", "order"),
    "fulfill-order": ("fulfillment", "fulfillment"),
    "create-return": ("return", "return"),
}
# spec response-time ceilings (docs/specification/mcp-server-spec.md, "Response Time Targets")
LATENCY_MAX_MS = {"query": 1000, "action": 5000, "init": 2000}
SYSTEM_FIELDS = {"id", "createdAt", "updatedAt", "tenantId"}

ERROR_KINDS = [
    ("permission", re.compile(r"permission|forbidden|not authori[sz]ed|unauthori[sz]ed", re.I)),
    ("unhandled", re.compile(r"cannot read propert|of undefined|of null|is not a function|"
                             r"NullReference|Object reference not set|TypeError|"
                             r"Unhandled|stack trace|at [\w.]+ \(", re.I)),
    ("backend_leak", re.compile(r"Failed to perform Rest request|graphql|\"extensions\"|"
                                r"Status: (BadRequest|InternalServerError|NotFound)", re.I)),
    ("not_found", re.compile(r"not found|does not exist|no such", re.I)),
    ("validation", re.compile(r"required|invalid|must have|must be|missing|expected|malformed", re.I)),
]


# ----------------------------------------------------------------- utilities

def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def progress(msg):
    """Progress lines go to stdout unbuffered so a backgrounded run can be watched."""
    print(f"[{datetime.datetime.now():%H:%M:%S}] {msg}", flush=True)


def trunc(s, n=300):
    s = s if isinstance(s, str) else json.dumps(s, default=str)
    return s if len(s) <= n else s[:n] + f"… [+{len(s) - n} chars]"


def strip_index(path):
    return re.sub(r"\[\d+\]", "[]", path)


def deep_get(obj, path):
    for p in path:
        if isinstance(obj, dict) and p in obj:
            obj = obj[p]
        elif isinstance(obj, list) and isinstance(p, int) and p < len(obj):
            obj = obj[p]
        else:
            return None, False
    return obj, True


# ------------------------------------------------------- minimal JSON Schema

TYPE_CHECK = {
    "string": lambda v: isinstance(v, str),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "null": lambda v: v is None,
}


def validate(inst, schema, path="$"):
    """
    Dependency-free validator for the subset of JSON Schema the onX entity
    schemas use: type, enum, pattern, min/max, minLength, properties,
    required, additionalProperties, items. Yields (path, kind, message).

    kind is one of: null (a null where the spec wants a value), type,
    required, enum, pattern, range, extra (unknown key), near_miss (unknown
    key that looks like a typo of a known key).
    """
    if not isinstance(schema, dict):
        return
    types = schema.get("type")
    if types is not None:
        types = types if isinstance(types, list) else [types]
        if inst is None and "null" not in types:
            yield path, "null", f"null (spec wants {'/'.join(types)}; omit the field instead)"
            return
        if not any(TYPE_CHECK.get(t, lambda v: True)(inst) for t in types):
            yield path, "type", f"is {type(inst).__name__}, spec wants {'/'.join(types)}: {trunc(inst, 60)}"
            return
    if "enum" in schema and inst not in schema["enum"]:
        yield path, "enum", f"{trunc(inst, 40)} not in {schema['enum']}"
    if isinstance(inst, str):
        if "pattern" in schema and not re.search(schema["pattern"], inst):
            yield path, "pattern", f"{trunc(inst, 60)!r} does not match spec pattern"
        if "minLength" in schema and len(inst) < schema["minLength"]:
            yield path, "range", f"shorter than minLength {schema['minLength']}"
    if isinstance(inst, (int, float)) and not isinstance(inst, bool):
        if "minimum" in schema and inst < schema["minimum"]:
            yield path, "range", f"{inst} < minimum {schema['minimum']}"
        if "exclusiveMinimum" in schema and inst <= schema["exclusiveMinimum"]:
            yield path, "range", f"{inst} <= exclusiveMinimum {schema['exclusiveMinimum']}"
        if "maximum" in schema and inst > schema["maximum"]:
            yield path, "range", f"{inst} > maximum {schema['maximum']}"
    if isinstance(inst, dict):
        props = schema.get("properties", {})
        for k in schema.get("required", []):
            if k not in inst:
                yield f"{path}.{k}", "required", "required by spec but absent"
        for k, v in inst.items():
            if k in props:
                yield from validate(v, props[k], f"{path}.{k}")
            elif props:
                addl = schema.get("additionalProperties", True)
                near = difflib.get_close_matches(k, list(props), n=1, cutoff=0.75)
                near = [n for n in near if n != k]
                if near:
                    yield f"{path}.{k}", "near_miss", f"unknown key; spec has `{near[0]}` (typo?)"
                elif addl is False:
                    yield f"{path}.{k}", "extra", "not in spec and additionalProperties is false"
                elif isinstance(addl, dict):
                    yield from validate(v, addl, f"{path}.{k}")
    if isinstance(inst, list) and isinstance(schema.get("items"), dict):
        for i, v in enumerate(inst):
            yield from validate(v, schema["items"], f"{path}[{i}]")


# --------------------------------------------------------------- MCP client

class Client:
    def __init__(self, url, headers, timeout, trace_path, trace_max):
        self.url, self.timeout = url, timeout
        self.headers = {"Content-Type": "application/json",
                        "Accept": "application/json, text/event-stream",
                        "MCP-Protocol-Version": PROTOCOL_VERSION,
                        "User-Agent": UA, **headers}
        self.session_id, self.seq = None, 0
        self.trace = open(trace_path, "w", encoding="utf-8")
        self.trace_max = trace_max
        self.calls = []  # every tools/call: dict(seq, tool, args, ms, kind, ...)

    def raw_post(self, body_bytes, label):
        self.seq += 1
        headers = dict(self.headers)
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        req = urllib.request.Request(self.url, data=body_bytes, headers=headers, method="POST")
        t0 = time.time()
        status, raw, ctype, err = None, "", "", None
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                status, ctype = r.status, r.headers.get("Content-Type", "")
                if r.headers.get("Mcp-Session-Id"):
                    self.session_id = r.headers["Mcp-Session-Id"]
                raw = r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            status, raw = e.code, e.read().decode("utf-8", "replace")
            ctype = e.headers.get("Content-Type", "")
        except Exception as e:  # URLError, timeout, ...
            err = f"{type(e).__name__}: {e}"
        ms = int((time.time() - t0) * 1000)
        msg = None
        if raw.strip():
            try:
                if "text/event-stream" in ctype:
                    for line in raw.splitlines():
                        if line.startswith("data:"):
                            m = json.loads(line[5:].strip())
                            if "result" in m or "error" in m:
                                msg = m
                else:
                    msg = json.loads(raw)
            except ValueError:
                msg = None
        rec = {"seq": self.seq, "label": label, "at": now_iso(), "ms": ms, "http": status,
               "request": body_bytes.decode("utf-8", "replace"),
               "response": raw if len(raw) <= self.trace_max else raw[:self.trace_max] + "…",
               "transport_error": err}
        self.trace.write(json.dumps(rec) + "\n")
        self.trace.flush()
        return {"seq": self.seq, "ms": ms, "http": status, "raw": raw, "msg": msg, "err": err}

    def rpc(self, method, params=None, label=None, notify=False):
        body = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            body["params"] = params
        if not notify:
            body["id"] = self.seq + 1
        return self.raw_post(json.dumps(body).encode(), label or method)

    def call(self, tool, args, label=None, omit_arguments=False):
        """tools/call, with the result decoded and classified."""
        params = {"name": tool} if omit_arguments else {"name": tool, "arguments": args}
        r = self.rpc("tools/call", params, label or tool)
        c = classify(r)
        c.update(seq=r["seq"], tool=tool, args=args, ms=r["ms"], http=r["http"])
        self.calls.append(c)
        if len(self.calls) % 20 == 0:
            progress(f"{len(self.calls)} tool calls so far (last: {label or tool}, {r['ms']} ms)")
        return c


def classify(r):
    """
    Turn a raw tools/call response into:
      kind: ok | empty | error | jsonrpc_error | http_error | transport | unparseable
      error_kind: permission | unhandled | backend_leak | not_found | validation | other
      data: the decoded payload (list or dict) when parseable
      envelope: bare | success | entity | text
    """
    out = {"kind": "ok", "error_kind": None, "error_text": None, "data": None,
           "envelope": None, "text": None}
    if r["err"]:
        out.update(kind="transport", error_text=r["err"])
        return out
    if r["http"] and r["http"] >= 400:
        out.update(kind="http_error", error_text=f"HTTP {r['http']}: {trunc(r['raw'], 200)}")
        return out
    m = r["msg"]
    if not isinstance(m, dict):
        out.update(kind="unparseable", error_text=trunc(r["raw"], 200))
        return out
    if "error" in m:
        e = m["error"]
        out.update(kind="jsonrpc_error", error_text=f"{e.get('code')} {e.get('message')}",
                   jsonrpc_code=e.get("code"))
        return out
    res = m.get("result", {})
    text = None
    for c in res.get("content", []) or []:
        if c.get("type") == "text":
            text = c.get("text")
            break
    out["text"] = text
    if res.get("isError"):
        out.update(kind="error", error_text=text or json.dumps(res)[:200])
        out["error_kind"] = next((k for k, rx in ERROR_KINDS if rx.search(text or "")), "other")
        return out
    data = res.get("structuredContent")
    if data is None and text is not None:
        try:
            data = json.loads(text)
        except ValueError:
            out.update(envelope="text", data=None)
            return out
    out["data"] = data
    if isinstance(data, list):
        out["envelope"] = "bare"
        if not data:
            out["kind"] = "empty"
    elif isinstance(data, dict):
        if "success" in data:
            out["envelope"] = "success"
            if data.get("success") is False:
                out.update(kind="error", error_text=json.dumps(data.get("error"))[:300],
                           error_kind="domain")
        else:
            out["envelope"] = "entity"
    return out


def records(c, tool):
    """Extract the entity list (or single entity as a 1-list) from a call result."""
    d = c.get("data")
    key = ENTITY.get(tool, (None, None))[1]
    if isinstance(d, list):
        return d
    if isinstance(d, dict):
        if key and key in d:
            v = d[key]
            return v if isinstance(v, list) else [v]
        # single entity returned bare
        if "id" in d or "sku" in d:
            return [d]
        for v in d.values():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                return v
    return []


# ------------------------------------------------------------------ findings

class Findings:
    SEV = ["BUG", "SPEC", "BLOCKED", "WARN", "INFO", "PASS"]

    def __init__(self):
        self.items = []
        self.schema_agg = {}   # (tool, kind, path, msg) -> counts, aggregated across calls
        self.lat = {}          # tool -> [(ms, ceiling, seq)]

    def add(self, sev, tool, check, detail, seq=None):
        self.items.append({"severity": sev, "tool": tool, "check": check,
                           "detail": detail, "seq": seq})

    def schema(self, tool, kind, path, msg, occurrences, n_records, seq, check):
        a = self.schema_agg.setdefault((tool, kind, path, msg),
                                       {"occ": 0, "records": 0, "calls": 0, "seq": seq, "check": check})
        a["occ"] += occurrences
        a["records"] += n_records
        a["calls"] += 1

    def latency(self, tool, ms, ceiling, seq):
        self.lat.setdefault(tool, []).append((ms, ceiling, seq))

    def finalize(self):
        """Fold the aggregated output-schema and latency observations into items."""
        null_by_tool = {}
        for (tool, kind, path, msg), a in self.schema_agg.items():
            if kind == "null":
                null_by_tool.setdefault(tool, []).append((path, a))
                continue
            sev = {"near_miss": "SPEC", "required": "SPEC", "type": "SPEC", "pattern": "SPEC",
                   "enum": "SPEC", "range": "SPEC", "extra": "INFO"}.get(kind, "WARN")
            self.add(sev, tool, "output schema",
                     f"{path}: {msg} ({a['occ']} occurrence(s) across {a['records']} records in "
                     f"{a['calls']} call(s); first seen in {a['check']})", a["seq"])
        for tool, lst in null_by_tool.items():
            paths = ", ".join(sorted(p for p, _ in lst))
            seq = min(a["seq"] for _, a in lst)
            self.add("WARN", tool, "output schema",
                     f"null where the spec wants a value (omit the field instead): {trunc(paths, 500)}", seq)
        for tool, lst in self.lat.items():
            over = [(ms, seq) for ms, ceil, seq in lst if ms > ceil]
            if not over:
                continue
            ms_sorted = sorted(ms for ms, _, _ in lst)
            worst = max(over)
            self.add("WARN", tool, "latency",
                     f"{len(over)} of {len(lst)} calls exceeded the spec ceiling of {lst[0][1]} ms; "
                     f"p50 {ms_sorted[len(ms_sorted) // 2]} ms, max {worst[0]} ms (trace #{worst[1]})")

    def count(self, sev):
        return sum(1 for f in self.items if f["severity"] == sev)


def report_call(F, c, tool, check, expect="ok"):
    """
    Common outcome handling. expect: "ok" (data expected), "empty_ok" (empty
    acceptable), "error" (a *clean* error is the correct answer).
    Returns True when the call can be used for further checks.
    """
    k = c["kind"]
    if k in ("transport", "http_error", "unparseable"):
        F.add("BUG", tool, check, f"{k}: {c['error_text']}", c["seq"])
        return False
    if k == "jsonrpc_error":
        F.add("BUG" if expect != "error" else "PASS", tool, check,
              f"JSON-RPC error {c['error_text']}", c["seq"])
        return False
    if k == "error":
        ek = c["error_kind"]
        if ek == "permission":
            F.add("BLOCKED", tool, check, f"API key lacks permission: {trunc(c['error_text'], 160)}", c["seq"])
        elif ek == "unhandled":
            F.add("BUG", tool, check, f"unhandled exception leaked: {trunc(c['error_text'], 200)}", c["seq"])
        elif expect == "error":
            sev = "WARN" if ek == "backend_leak" else "PASS"
            F.add(sev, tool, check, f"rejected ({ek}): {trunc(c['error_text'], 200)}", c["seq"])
        else:
            sev = "WARN" if ek == "backend_leak" else "BUG"
            F.add(sev, tool, check, f"error ({ek}): {trunc(c['error_text'], 200)}", c["seq"])
        return False
    if expect == "error":
        F.add("BUG", tool, check, "accepted input that the spec says is invalid "
              f"(returned {len(records(c, tool))} records)", c["seq"])
        return True
    if k == "empty":
        F.add("WARN" if expect == "ok" else "PASS", tool, check, "returned no records", c["seq"])
        return True
    return True


def check_entities(F, c, tool, schema, check, max_per_call=8):
    """Validate every returned record against the entity schema; aggregate."""
    recs = records(c, tool)
    if not recs or not schema:
        return recs
    agg = {}
    for rec in recs:
        for path, kind, msg in validate(rec, schema, "$"):
            # required/near-miss messages are stable; pattern/type/range messages
            # embed the offending value, so key those on path only
            key = (kind, strip_index(path), msg if kind in ("near_miss", "required") else "")
            a = agg.setdefault(key, {"n": 0, "example": msg})
            a["n"] += 1
    for (kind, path, _), a in agg.items():
        F.schema(tool, kind, path, a["example"] if kind != "null" else "", a["n"], len(recs), c["seq"], check)
    return recs


# ----------------------------------------------------------------- harvest

class Harvest:
    """Identifiers pulled out of live results, used to build later calls."""

    def __init__(self):
        self.skus, self.location_ids = [], []
        self.orders, self.customers, self.products, self.variants = [], [], [], []
        self.fulfillments, self.returns, self.inventory = [], [], []

    def take(self, tool, recs):
        store = {"get-orders": self.orders, "get-customers": self.customers,
                 "get-products": self.products, "get-product-variants": self.variants,
                 "get-fulfillments": self.fulfillments, "get-returns": self.returns,
                 "get-inventory": self.inventory}.get(tool)
        if store is not None:
            for r in recs:
                if isinstance(r, dict) and r not in store:
                    store.append(r)
        for r in recs:
            if not isinstance(r, dict):
                continue
            for li in (r.get("lineItems") or r.get("returnLineItems") or []):
                if isinstance(li, dict) and li.get("sku"):
                    self._add(self.skus, li["sku"])
            if r.get("sku"):
                self._add(self.skus, r["sku"])
            if r.get("locationId"):
                self._add(self.location_ids, r["locationId"])

    @staticmethod
    def _add(lst, v):
        if v and v not in lst:
            lst.append(v)

    def ids(self, recs, key="id"):
        return [r[key] for r in recs if isinstance(r, dict) and r.get(key)]

    def first_field(self, recs, key):
        return next((r[key] for r in recs if isinstance(r, dict) and r.get(key)), None)


# ------------------------------------------------------------- the tiers

def tier_protocol(cli, F, live_tools):
    t = "protocol"
    r = cli.rpc("initialize", {"protocolVersion": PROTOCOL_VERSION, "capabilities": {},
                               "clientInfo": {"name": "onx-exercise", "version": VERSION}}, "initialize")
    init = (r["msg"] or {}).get("result") if r["msg"] else None
    if not init:
        F.add("BUG", t, "initialize", f"no result: {trunc(r['raw'] or r['err'], 200)}", r["seq"])
        return None
    F.latency("initialize", r["ms"], LATENCY_MAX_MS["init"], r["seq"])
    if "tools" not in (init.get("capabilities") or {}):
        F.add("SPEC", t, "initialize", "capabilities does not declare `tools`", r["seq"])
    if not init.get("serverInfo", {}).get("version"):
        F.add("SPEC", t, "initialize", "serverInfo.version missing (spec requires semver)", r["seq"])
    F.add("INFO", t, "initialize", f"server {init.get('serverInfo', {}).get('name')} "
          f"v{init.get('serverInfo', {}).get('version')} protocol {init.get('protocolVersion')}", r["seq"])
    cli.rpc("notifications/initialized", notify=True, label="notifications/initialized")

    r = cli.rpc("ping", label="ping")
    if not (r["msg"] and "result" in r["msg"]):
        F.add("WARN", t, "ping", f"no result: {trunc(r['raw'] or r['err'], 120)}", r["seq"])

    r = cli.rpc("no/such/method", label="unknown method")
    code = ((r["msg"] or {}).get("error") or {}).get("code")
    if code != -32601:
        F.add("SPEC", t, "unknown method", f"expected JSON-RPC -32601, got {code or trunc(r['raw'], 100)}", r["seq"])

    r = cli.raw_post(b'{"jsonrpc":"2.0","id":1,"method":', "parse error")
    code = ((r["msg"] or {}).get("error") or {}).get("code") if r["msg"] else None
    if code != -32700:
        F.add("SPEC", t, "malformed JSON", f"expected JSON-RPC -32700 parse error, got HTTP {r['http']}: {trunc(r['raw'], 120)}", r["seq"])

    c = cli.call("no-such-tool", {}, "unknown tool")
    if c["kind"] != "jsonrpc_error" or c.get("jsonrpc_code") not in (-32602, -32601):
        F.add("SPEC", t, "unknown tool", f"expected JSON-RPC -32602/-32601, got {c['kind']}: {trunc(c['error_text'] or '', 120)}", c["seq"])

    missing = [n for n in QUERY_TOOLS + ACTION_TOOLS if n not in live_tools]
    extra = sorted(set(live_tools) - set(QUERY_TOOLS + ACTION_TOOLS))
    if missing:
        F.add("SPEC", t, "tools/list", f"standard tools not advertised: {', '.join(missing)}")
    if extra:
        F.add("INFO", t, "tools/list", f"tools outside the spec: {', '.join(extra)}")
    return init


def tier_declaration(F, spec_dir, live):
    """L0 declaration: delegate to onx_conformance.check_tool if it is importable."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        import onx_conformance as oc
    except ImportError:
        F.add("WARN", "declaration", "checker", "onx_conformance.py not found next to this script; L0 skipped")
        return
    tool_dir = spec_dir / "tool-inputs" if (spec_dir / "tool-inputs").is_dir() else spec_dir
    for f in sorted(tool_dir.glob("*.json")):
        name = f.stem
        if name not in live:
            continue
        r = oc.check_tool(name, json.loads(f.read_text()), live[name].get("inputSchema", {}))
        if r["pass"]:
            F.add("PASS", name, "inputSchema vs spec", "matches reference schema")
        else:
            bits = []
            if r["envelope"] != "nested":
                bits.append(f"envelope {r['envelope']}")
            if r["missing_params"]:
                bits.append(f"missing {r['missing_params']}")
            if r["type_drift"]:
                bits.append(f"type drift {r['type_drift']}")
            if r["required_drift"]:
                bits.append(f"required drift {r['required_drift']}")
            if r["pattern_drift"]:
                bits.append(f"pattern drift {[d['param'] for d in r['pattern_drift']]}")
            F.add("SPEC", name, "inputSchema vs spec", "; ".join(bits))
        if r["extra_params"]:
            F.add("INFO", name, "inputSchema vs spec", f"extra params {r['extra_params']}")


def latency(F, c, tool, kind):
    F.latency(tool, c["ms"], LATENCY_MAX_MS[kind], c["seq"])


def tier_liveness(cli, F, H, schemas, live, page, sku_hint):
    for tool in QUERY_TOOLS:
        if tool not in live:
            continue
        if tool == "get-inventory":
            skus = ([sku_hint] if sku_hint else []) + H.skus
            if not skus:
                F.add("WARN", tool, "L1 minimal", "no SKU harvested from other tools and no --sku given; skipped")
                continue
            args = {"skus": skus[:1]}
        else:
            args = {"pageSize": page}
        c = cli.call(tool, args, f"L1 {tool}")
        latency(F, c, tool, "query")
        if report_call(F, c, tool, "L1 minimal"):
            recs = check_entities(F, c, tool, schemas.get(ENTITY[tool][0]), "L1")
            H.take(tool, recs)
            if c["envelope"] == "bare":
                F.add("INFO", tool, "L1 envelope",
                      "returns a bare JSON array; the reference server wraps results as "
                      f"{{\"success\": true, \"{ENTITY[tool][1]}\": [...]}}", c["seq"])
            if recs and len(recs) > page and tool != "get-inventory":
                F.add("BUG", tool, "L1 pageSize", f"asked for {page}, got {len(recs)}", c["seq"])
            elif recs:
                F.add("PASS", tool, "L1 minimal", f"{len(recs)} record(s)", c["seq"])


def paginate_checks(cli, F, H, tool, schema, page):
    """pageSize/skip semantics, default page, and crash bisection."""
    a = cli.call(tool, {"pageSize": page, "skip": 0}, f"L2 {tool} page0")
    b = cli.call(tool, {"pageSize": page, "skip": page}, f"L2 {tool} page1")
    ok_a = report_call(F, a, tool, "L2 pagination page0", "empty_ok")
    ok_b = report_call(F, b, tool, "L2 pagination page1", "empty_ok")
    if ok_a and ok_b:
        ra, rb = records(a, tool), records(b, tool)
        H.take(tool, ra + rb)
        ia, ib = set(H.ids(ra)), set(H.ids(rb))
        if ia & ib:
            F.add("BUG", tool, "L2 pagination", f"page0 and page1 overlap on ids {sorted(ia & ib)[:3]}", b["seq"])
        elif ra and rb:
            both = cli.call(tool, {"pageSize": page * 2, "skip": 0}, f"L2 {tool} page0+1")
            if report_call(F, both, tool, "L2 pagination page0+1", "empty_ok"):
                ib2 = H.ids(records(both, tool))
                if ib2 != H.ids(ra) + H.ids(rb):
                    F.add("WARN", tool, "L2 pagination", "ordering is not stable across page sizes "
                          "(pageSize 2n != page0 + page1); skip-based paging will drop or repeat records", both["seq"])
                else:
                    F.add("PASS", tool, "L2 pagination", "skip/pageSize consistent and stably ordered", both["seq"])
    # no-argument call: the schema says every filter is optional, so {} is legal
    d = cli.call(tool, {}, f"L2 {tool} no args")
    if d["kind"] == "error":
        report_call(F, d, tool, "L2 no-argument call ({})")
        if d["error_kind"] == "unhandled":
            F.add("BUG", tool, "L2 default pageSize",
                  "{} crashes while {pageSize: n} works; the server is probably fetching the whole "
                  "table without applying the spec default pageSize=10 and hitting a bad record", d["seq"])
    else:
        n = len(records(d, tool))
        if n > 10:
            F.add("WARN", tool, "L2 default pageSize", f"{{}} returned {n} records; spec default is 10", d["seq"])
        else:
            F.add("PASS", tool, "L2 default pageSize", f"{{}} returned {n} record(s)", d["seq"])
    # omitted arguments object entirely
    e = cli.call(tool, {}, f"L2 {tool} arguments omitted", omit_arguments=True)
    if e["kind"] == "error" and e["error_kind"] == "unhandled":
        F.add("BUG", tool, "L2 arguments omitted", f"tools/call without `arguments` crashes: {trunc(e['error_text'], 120)}", e["seq"])
    # large page + bisect if it crashes
    big = cli.call(tool, {"pageSize": 50, "skip": 0}, f"L2 {tool} pageSize 50")
    if big["kind"] == "error" and big["error_kind"] == "unhandled":
        F.add("BUG", tool, "L2 pageSize 50", f"crashes: {trunc(big['error_text'], 120)}", big["seq"])
        bisect_crash(cli, F, tool, 0, 50)
    elif big["kind"] not in ("error", "jsonrpc_error"):
        recs = records(big, tool)
        H.take(tool, recs)
        check_entities(F, big, tool, schema, "L2 pageSize 50")
        if len(recs) > 50:
            F.add("BUG", tool, "L2 pageSize 50", f"got {len(recs)} records", big["seq"])
        # walk further pages until a crash or empty, bounded (200 records)
        for k in range(1, 4):
            nxt = cli.call(tool, {"pageSize": 50, "skip": 50 * k}, f"L2 {tool} pageSize 50 skip {50*k}")
            if nxt["kind"] == "error" and nxt["error_kind"] == "unhandled":
                F.add("BUG", tool, f"L2 page skip {50*k}", f"crashes: {trunc(nxt['error_text'], 120)}", nxt["seq"])
                bisect_crash(cli, F, tool, 50 * k, 50)
                break
            if nxt["kind"] != "ok":
                break
            check_entities(F, nxt, tool, schema, f"L2 page skip {50*k}")
            H.take(tool, records(nxt, tool))


def bisect_crash(cli, F, tool, skip, size):
    """Narrow a crashing page down to one record position and name its neighbour."""
    while size > 1:
        half = size // 2
        left = cli.call(tool, {"pageSize": half, "skip": skip}, f"bisect {tool} {skip}+{half}")
        if left["kind"] == "error" and left["error_kind"] == "unhandled":
            size = half
            continue
        right = cli.call(tool, {"pageSize": size - half, "skip": skip + half}, f"bisect {tool} {skip+half}+{size-half}")
        if right["kind"] == "error" and right["error_kind"] == "unhandled":
            skip, size = skip + half, size - half
            continue
        F.add("INFO", tool, "L2 crash bisect", f"page {skip}+{size} fails but both halves succeed; crash is page-size dependent", right["seq"])
        return
    prev = cli.call(tool, {"pageSize": 1, "skip": max(0, skip - 1)}, f"bisect {tool} neighbour")
    pr = records(prev, tool)
    nb = f"{pr[0].get('id')} / externalId {pr[0].get('externalId')}" if pr else "n/a"
    F.add("BUG", tool, "L2 crash bisect",
          f"the single record at skip={skip} (default ordering) cannot be serialised; "
          f"the record just before it is {nb}", prev["seq"])


def filter_checks(cli, F, H, tool, schema, page):
    """Build every filter the spec allows from harvested data and check it is honoured."""
    E = ENTITY[tool][0]

    def run(check, args, match=None, expect="ok"):
        c = cli.call(tool, args, f"L2 {tool} {check}")
        latency(F, c, tool, "query")
        if not report_call(F, c, tool, f"L2 {check}", expect):
            return None
        recs = check_entities(F, c, tool, schema, f"L2 {check}")
        H.take(tool, recs)
        if match and recs:
            bad = [r for r in recs if not match(r)]
            if bad:
                F.add("BUG", tool, f"L2 {check}", f"filter not applied: {len(bad)} of {len(recs)} records do not match "
                      f"(e.g. {trunc({k: bad[0].get(k) for k in list(bad[0])[:6]}, 160)})", c["seq"])
            else:
                F.add("PASS", tool, f"L2 {check}", f"{len(recs)} record(s), all match", c["seq"])
        return recs

    def within(r, field, lo=None, hi=None):
        v = r.get(field)
        return isinstance(v, str) and (lo is None or v >= lo) and (hi is None or v <= hi)

    base = {"get-orders": H.orders, "get-customers": H.customers, "get-products": H.products,
            "get-product-variants": H.variants, "get-fulfillments": H.fulfillments,
            "get-returns": H.returns, "get-inventory": H.inventory}[tool]
    sample = base[0] if base else None
    unknown_id = fake_id(H)

    if tool == "get-inventory":
        skus = H.skus[:3]
        if not skus:
            return
        run("skus (several)", {"skus": skus}, lambda r: r.get("sku") in skus)
        if H.location_ids:
            loc = H.location_ids[0]
            run("skus + locationIds", {"skus": skus[:1], "locationIds": [loc]},
                lambda r: r.get("sku") in skus and r.get("locationId") == loc)
        run("unknown sku", {"skus": ["__onx_no_such_sku__"]}, expect="empty_ok")
        run("missing required skus", {}, expect="error")
        run("wrong type skus", {"skus": "not-an-array"}, expect="error")
        return

    if not sample:
        F.add("WARN", tool, "L2 filters", "no records harvested, most filter checks skipped")
        if tool == "get-product-variants" and H.skus:
            got = run("skus known to inventory/orders", {"skus": H.skus[:3]}, None, "empty_ok")
            if got is not None and not got:
                F.add("BUG", tool, "L2 skus known to inventory/orders",
                      f"no variants for SKUs that inventory or orders report: {H.skus[:3]}; "
                      "the tool appears to return nothing at all", None)
    else:
        ids = H.ids(base)[:2]
        if ids:
            run("ids", {"ids": ids}, lambda r: r.get("id") in ids)
        ext = H.ids(base, "externalId")[:2]
        if ext and tool == "get-orders":
            run("externalIds", {"externalIds": ext}, lambda r: r.get("externalId") in ext)
        if tool == "get-orders":
            names = H.ids(base, "name")[:1]
            if names:
                run("names", {"names": names}, lambda r: r.get("name") in names)
            run("includeLineItems=false", {"ids": ids[:1], "includeLineItems": False})
            li = run("includeLineItems=true", {"ids": ids[:1], "includeLineItems": True})
            if li and not any(r.get("lineItems") for r in li):
                F.add("WARN", tool, "L2 includeLineItems=true", "order came back with no lineItems", None)
        if tool in ("get-orders", "get-returns"):
            sts = sorted({r.get("status") for r in base if r.get("status")})[:2]
            if sts:
                run("statuses", {"statuses": sts, "pageSize": page}, lambda r: r.get("status") in sts)
            run("statuses unknown value", {"statuses": ["__onx_no_such_status__"], "pageSize": page}, expect="empty_ok")
        if tool == "get-returns":
            outs = sorted({r.get("outcome") for r in base if r.get("outcome")})[:2]
            if outs:
                run("outcomes", {"outcomes": outs, "pageSize": page}, lambda r: r.get("outcome") in outs)
            rn = H.ids(base, "returnNumber")[:1]
            if rn:
                run("returnNumbers", {"returnNumbers": rn}, lambda r: r.get("returnNumber") in rn)
            oids = H.ids(base, "orderId")[:1]
            if oids:
                run("orderIds", {"orderIds": oids}, lambda r: r.get("orderId") in oids)
        if tool == "get-fulfillments":
            oids = H.ids(base, "orderId")[:1] or H.ids(H.orders)[:1]
            if oids:
                run("orderIds", {"orderIds": oids}, lambda r: r.get("orderId") in oids, "empty_ok")
        if tool == "get-customers":
            emails = H.ids(base, "email")[:1]
            if emails:
                run("emails", {"emails": emails}, lambda r: r.get("email") in emails)
        if tool == "get-product-variants":
            skus = H.ids(base, "sku")[:2] or H.skus[:2]
            if skus:
                run("skus", {"skus": skus}, lambda r: r.get("sku") in skus)
            pids = H.ids(base, "productId")[:1] or H.ids(H.products)[:1]
            if pids:
                run("productIds", {"productIds": pids}, lambda r: r.get("productId") in pids, "empty_ok")
        if tool == "get-products":
            skus = H.skus[:2]
            if skus:
                run("skus", {"skus": skus}, None, "empty_ok")
        # date windows, from a real record's timestamps
        for fld in ("createdAt", "updatedAt"):
            v = sample.get(fld)
            if isinstance(v, str) and len(v) >= 19:
                lo = v[:19] + "Z" if not v.endswith("Z") else v
                run(f"{fld}Min={fld}Max=record", {f"{fld}Min": lo, f"{fld}Max": lo, "pageSize": page},
                    lambda r, f=fld, lo=lo: within(r, f, lo[:19], lo[:19] + ".999Z"), "empty_ok")
                run(f"{fld}Min window", {f"{fld}Min": lo, "pageSize": page},
                    lambda r, f=fld, lo=lo: within(r, f, lo[:19]))
                run(f"{fld}Max window", {f"{fld}Max": lo, "pageSize": page},
                    lambda r, f=fld, lo=lo: within(r, f, None, lo[:19] + ".999Z"))
        run("createdAtMin far future", {"createdAtMin": "2999-01-01T00:00:00Z", "pageSize": page}, expect="empty_ok")
        if ids:
            got = run("ids unknown (well-formed) value", {"ids": [unknown_id]}, None, "empty_ok")
            if got:
                F.add("BUG", tool, "L2 ids unknown value", f"ids=[{unknown_id}] returned {len(got)} records", None)
            run("ids malformed value", {"ids": ["__onx_not_an_id__"]}, None, "empty_ok")
    # negative inputs, independent of data
    run("wrong type pageSize", {"pageSize": "ten"}, expect="error")
    run("bad date format", {"createdAtMin": "yesterday", "pageSize": page}, expect="error")
    run("unknown extra argument", {"pageSize": 1, "__onx_bogus": True}, None, "empty_ok")


def tier_contract(cli, F, H, schemas, live, page):
    for tool in QUERY_TOOLS:
        if tool not in live:
            continue
        schema = schemas.get(ENTITY[tool][0])
        if tool != "get-inventory":
            paginate_checks(cli, F, H, tool, schema, page)
        filter_checks(cli, F, H, tool, schema, page)


# ----------------------------------------------------------------- mutation

def address(**over):
    a = {"address1": "425 Washington Blvd", "address2": "Suite 100", "city": "Jersey City",
         "company": "onX Conformance", "country": "US", "email": "onx-conformance@example.com",
         "firstName": "Conform", "lastName": "Tester", "phone": "+1-555-010-0100",
         "stateOrProvince": "NJ", "zipCodeOrPostalCode": "07310"}
    a.update(over)
    return a


def order_payload(run_id, sku, maximal=True):
    li = {"sku": sku, "quantity": 2}
    if maximal:
        li.update(id=f"LI-{run_id}", unitPrice=10.5, unitDiscount=0.5, totalPrice=20.0,
                  name="Conformance item", customFields=[{"name": "li-run", "value": run_id}])
    o = {"externalId": run_id, "lineItems": [li]}
    if maximal:
        o.update(name=run_id, currency="USD", orderSource="onx-conformance",
                 orderNote="created by onx_exercise.py", tags=["onx-conformance"],
                 status="pending", paymentStatus="paid",
                 customer={"id": f"CUST-{run_id}", "externalId": f"CUST-{run_id}",
                           "createdAt": "2026-01-01T00:00:00Z", "updatedAt": "2026-01-01T00:00:00Z",
                           "tenantId": "onx", "email": "onx-conformance@example.com",
                           "firstName": "Conform", "lastName": "Tester", "phone": "+1-555-010-0100",
                           "type": "individual", "status": "active"},
                 shippingAddress=address(), billingAddress=address(address1="1 Billing Way"),
                 shippingCarrier="UPS", shippingClass="Ground", shippingCode="03",
                 shippingNote="leave at door", shippingPrice=5.0, giftNote="enjoy",
                 incoterms="DAP", subTotalPrice=20.0, orderDiscount=0.0, orderTax=1.6,
                 totalPrice=26.6, discounts=[], payments=[], refunds=[],
                 customFields=[{"name": "runId", "value": run_id}])
    return o


def echo_check(F, tool, check, sent, got, seq, path="", ignore=SYSTEM_FIELDS):
    """Compare each leaf we sent with the entity that came back."""
    if not isinstance(got, dict):
        F.add("WARN", tool, check, "no entity in response to compare against", seq)
        return
    mism, missing, soft = [], [], []
    for k, v in sent.items():
        if k in ignore:
            continue
        p = f"{path}{k}"
        if k not in got:
            missing.append(p)
        elif isinstance(v, dict) and isinstance(got[k], dict):
            echo_check(F, tool, check, v, got[k], seq, p + ".", set())
        elif isinstance(v, list):
            if v and isinstance(v[0], dict) and isinstance(got[k], list):
                for i, item in enumerate(v):
                    if i < len(got[k]) and isinstance(got[k][i], dict):
                        echo_check(F, tool, check, item, got[k][i], seq, f"{p}[{i}].", set())
                    else:
                        missing.append(f"{p}[{i}]")
            elif got[k] != v:
                mism.append(f"{p}: sent {trunc(v, 40)} got {trunc(got[k], 40)}")
        elif got[k] != v:
            if isinstance(v, str) and isinstance(got[k], str) and v.lower() == got[k].lower():
                soft.append(f"{p}: {v!r} -> {got[k]!r}")
            elif isinstance(v, (int, float)) and isinstance(got[k], (int, float)) and abs(v - got[k]) < 1e-6:
                pass
            else:
                mism.append(f"{p}: sent {trunc(v, 40)} got {trunc(got[k], 40)}")
    if path == "":
        if mism:
            F.add("WARN", tool, f"{check} - echo", "values changed: " + "; ".join(mism[:8]), seq)
        if missing:
            F.add("INFO", tool, f"{check} - echo", "sent but absent in response: " + ", ".join(missing[:12]), seq)
        if soft:
            F.add("INFO", tool, f"{check} - echo", "case-normalised: " + "; ".join(soft[:6]), seq)
        if not (mism or missing or soft):
            F.add("PASS", tool, f"{check} - echo", "every field sent came back unchanged", seq)
    else:
        # nested: fold into parent's lists by re-raising through F (simple approach)
        for m in mism:
            F.add("WARN", tool, f"{check} - echo", f"value changed: {m}", seq)
        for m in missing:
            F.add("INFO", tool, f"{check} - echo", f"sent but absent: {m}", seq)
        for m in soft:
            F.add("INFO", tool, f"{check} - echo", f"case-normalised: {m}", seq)


def entity_of(c, tool):
    recs = records(c, tool)
    return recs[0] if recs else None


def fake_id(H):
    """An id that is well-formed for this backend but does not exist."""
    real = (H.ids(H.orders) or H.ids(H.products) or H.ids(H.returns))[:1]
    if real and re.fullmatch(r"[0-9a-fA-F-]{36}", real[0]):
        return "00000000-0000-4000-8000-000000000000"
    return "onx-no-such-id"


def tier_mutation(cli, F, H, schemas, live, sku, location, existing_order_id=None):
    run_id = f"ONX-{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    sku = sku or (H.skus[0] if H.skus else None)
    if not sku:
        F.add("WARN", "mutation", "setup", "no SKU available (pass --sku); L3 skipped")
        return
    location = location or (H.location_ids[0] if H.location_ids else None)
    S = lambda t: schemas.get(ENTITY[t][0])

    def act(tool, args, check, expect="ok"):
        c = cli.call(tool, args, f"L3 {tool} {check}")
        latency(F, c, tool, "action")
        ok = report_call(F, c, tool, f"L3 {check}", expect)
        if ok and expect != "error":
            check_entities(F, c, tool, S(tool), f"L3 {check}")
            if c["envelope"] == "bare":
                F.add("INFO", tool, f"L3 {check} envelope",
                      f"reference server returns {{\"success\": true, \"{ENTITY[tool][1]}\": {{...}}}}", c["seq"])
        return c if ok else None

    # negatives first: they must not crash regardless of permissions
    if "cancel-order" in live:
        act("cancel-order", {"orderId": fake_id(H)}, "unknown orderId", "error")
        act("cancel-order", {"orderId": "not-a-well-formed-id"}, "malformed orderId", "error")
        act("cancel-order", {}, "missing required orderId", "error")
    if "fulfill-order" in live:
        act("fulfill-order", {"orderId": fake_id(H), "lineItems": [{"sku": sku, "quantity": 1}],
                              "trackingNumbers": ["ONX-NO-SUCH"]}, "unknown orderId", "error")
        act("fulfill-order", {"orderId": fake_id(H)}, "missing required lineItems/trackingNumbers", "error")
    if "update-order" in live:
        act("update-order", {"id": fake_id(H), "updates": {"orderNote": "x"}}, "unknown id", "error")
    if "create-return" in live:
        act("create-return", {"return": {"orderId": fake_id(H), "outcome": "refund",
                                         "returnLineItems": [{"orderLineItemId": "x", "sku": sku,
                                                              "quantityReturned": 1, "returnReason": "defective"}]}},
            "unknown orderId", "error")
    if "create-sales-order" in live:
        act("create-sales-order", {"order": {"externalId": f"{run_id}-NOLINES"}}, "missing required lineItems", "error")
        act("create-sales-order", {}, "missing required order", "error")

    if "create-sales-order" not in live:
        return

    # create: minimal spec-legal payload, then maximal
    minimal = order_payload(f"{run_id}-MIN", sku, maximal=False)
    c = act("create-sales-order", {"order": minimal}, "create minimal (spec-required fields only)")
    if c is None:
        # a very common low-code mistake: reading arguments at the wrong nesting level
        flat = cli.call("create-sales-order", minimal, "L3 create-sales-order flat probe")
        if flat["kind"] not in ("error", "jsonrpc_error"):
            F.add("SPEC", "create-sales-order", "L3 argument shape",
                  "accepts the order fields at the top level of `arguments` but rejects them under "
                  "`order`, which is what the advertised inputSchema and the spec require", flat["seq"])
    full = order_payload(run_id, sku, maximal=True)
    c = act("create-sales-order", {"order": full}, "create maximal (every spec field)")
    order = entity_of(c, "create-sales-order") if c else None
    order_id = order.get("id") if isinstance(order, dict) else None
    if c and order:
        echo_check(F, "create-sales-order", "L3 create maximal", full, order, c["seq"])

    # read back by externalId (works even if create returned nothing useful)
    if "get-orders" in live:
        g = cli.call("get-orders", {"externalIds": [run_id], "includeLineItems": True}, "L3 get-orders by externalId")
        if report_call(F, g, "get-orders", "L3 read back created order", "ok"):
            recs = records(g, "get-orders")
            if recs:
                if not order_id:
                    order_id = recs[0].get("id")
                echo_check(F, "get-orders", "L3 read back created order", full, recs[0], g["seq"])
            elif order_id:
                F.add("BUG", "get-orders", "L3 read back created order",
                      f"order {order_id} was created but externalIds=[{run_id}] finds nothing", g["seq"])
    if not order_id and existing_order_id:
        g = cli.call("get-orders", {"ids": [existing_order_id], "includeLineItems": True}, "L3 get-orders --order-id")
        recs = records(g, "get-orders") if report_call(F, g, "get-orders", "L3 read --order-id") else []
        if recs:
            order_id = existing_order_id
            lis = recs[0].get("lineItems") or []
            if lis and isinstance(lis[0], dict) and lis[0].get("sku"):
                sku = lis[0]["sku"]
            F.add("WARN", "mutation", "L3 flow",
                  f"create-sales-order produced no order; exercising update/fulfill/return/cancel on "
                  f"existing order {order_id} (status {recs[0].get('status')!r}) as requested with --order-id")
        else:
            F.add("BLOCKED", "mutation", "L3 flow", f"--order-id {existing_order_id} not found via get-orders")
    if not order_id:
        F.add("BLOCKED", "mutation", "L3 flow",
              "create-sales-order produced no order, so update/fulfill/return/cancel were not exercised. "
              "Fix create first, or pass --order-id <existing open order> to exercise the rest.")
        return
    if order_id != existing_order_id:
        F.add("INFO", "mutation", "L3 flow", f"created order id {order_id} (externalId {run_id})")

    # update
    if "update-order" in live:
        upd = {"orderNote": "updated by onx_exercise.py", "tags": ["onx-conformance", "updated"],
               "shippingAddress": address(address1="789 Updated St", city="Updated City"),
               "shippingCarrier": "FedEx", "shippingClass": "Express"}
        c = act("update-order", {"id": order_id, "updates": upd}, "update")
        if c:
            ent = entity_of(c, "update-order")
            if ent:
                echo_check(F, "update-order", "L3 update", upd, ent, c["seq"])
            g = cli.call("get-orders", {"ids": [order_id]}, "L3 get-orders after update")
            if report_call(F, g, "get-orders", "L3 read after update") and records(g, "get-orders"):
                echo_check(F, "get-orders", "L3 read after update", upd, records(g, "get-orders")[0], g["seq"])

    # fulfill
    ful_id = None
    if "fulfill-order" in live:
        ful = {"orderId": order_id, "lineItems": [{"sku": sku, "quantity": 2}],
               "trackingNumbers": [f"1Z{run_id.replace('-', '')}"], "shippingCarrier": "UPS",
               "shippingClass": "Ground", "shippingCode": "03", "shippingNote": "conformance",
               "shippingPrice": 5.0, "expectedShipDate": "2026-09-08T00:00:00Z",
               "expectedDeliveryDate": "2026-09-12T00:00:00Z", "shipByDate": "2026-09-09T00:00:00Z",
               "status": "shipped", "tags": ["onx-conformance"], "shippingAddress": address(),
               "customFields": [{"name": "runId", "value": run_id}], "giftNote": "", "incoterms": "DAP"}
        if location:
            ful["locationId"] = location
        c = act("fulfill-order", ful, "fulfill")
        if c:
            ent = entity_of(c, "fulfill-order")
            if ent:
                ful_id = ent.get("id")
                echo_check(F, "fulfill-order", "L3 fulfill", ful, ent, c["seq"])
            if "get-fulfillments" in live:
                g = cli.call("get-fulfillments", {"orderIds": [order_id]}, "L3 get-fulfillments by orderId")
                if report_call(F, g, "get-fulfillments", "L3 read back fulfillment"):
                    recs = records(g, "get-fulfillments")
                    if recs:
                        check_entities(F, g, "get-fulfillments", S("get-fulfillments"), "L3 read back fulfillment")
                        echo_check(F, "get-fulfillments", "L3 read back fulfillment", ful, recs[0], g["seq"])
                        if ful_id and ful_id not in H.ids(recs):
                            F.add("BUG", "get-fulfillments", "L3 read back fulfillment",
                                  f"fulfill-order returned id {ful_id} but get-fulfillments does not list it", g["seq"])
            g = cli.call("get-orders", {"ids": [order_id]}, "L3 get-orders after fulfill")
            if report_call(F, g, "get-orders", "L3 read after fulfill") and records(g, "get-orders"):
                st = records(g, "get-orders")[0].get("status")
                F.add("INFO", "get-orders", "L3 status after fulfill", f"order status is now {st!r}", g["seq"])

    # return
    if "create-return" in live:
        g = cli.call("get-orders", {"ids": [order_id], "includeLineItems": True}, "L3 get-orders for line item id")
        li_id = None
        if records(g, "get-orders"):
            lis = records(g, "get-orders")[0].get("lineItems") or []
            li_id = lis[0].get("id") if lis and isinstance(lis[0], dict) else None
        ret = {"orderId": order_id, "externalId": f"RET-{run_id}", "returnNumber": f"RET-{run_id}",
               "outcome": "refund", "status": "requested",
               "returnLineItems": [{"orderLineItemId": li_id or f"LI-{run_id}", "sku": sku,
                                    "quantityReturned": 1, "returnReason": "defective",
                                    "unitPrice": 10.5, "refundAmount": 10.0, "restockFee": 0.5,
                                    "name": "Conformance item"}],
               "totalQuantity": 1, "returnMethod": {"provider": "UPS", "methodType": "label",
                                                    "address": address()},
               "returnShippingAddress": address(), "locationId": location or "",
               "returnTotal": 10.5, "refundAmount": 10.0, "refundMethod": "original",
               "restockingFee": 0.5, "customerNote": "conformance return", "internalNote": "onx_exercise",
               "tags": ["onx-conformance"], "customFields": [{"name": "runId", "value": run_id}]}
        if not location:
            ret.pop("locationId")
        c = act("create-return", {"return": ret}, "create return")
        if c:
            ent = entity_of(c, "create-return")
            if ent:
                echo_check(F, "create-return", "L3 create return", ret, ent, c["seq"])
            if "get-returns" in live:
                g = cli.call("get-returns", {"orderIds": [order_id]}, "L3 get-returns by orderId")
                if report_call(F, g, "get-returns", "L3 read back return") and records(g, "get-returns"):
                    check_entities(F, g, "get-returns", S("get-returns"), "L3 read back return")
                    echo_check(F, "get-returns", "L3 read back return", ret, records(g, "get-returns")[0], g["seq"])

    # cancel: a fresh order that has not been fulfilled, then the fulfilled one (should refuse or handle)
    if "cancel-order" in live:
        oid2 = None
        if order_id != existing_order_id:
            o2 = order_payload(f"{run_id}-CANCEL", sku, maximal=False)
            c2 = act("create-sales-order", {"order": o2}, "create for cancel")
            oid2 = (entity_of(c2, "create-sales-order") or {}).get("id") if c2 else None
            if not oid2:
                g = cli.call("get-orders", {"externalIds": [f"{run_id}-CANCEL"]}, "L3 get-orders cancel target")
                oid2 = (records(g, "get-orders") or [{}])[0].get("id")
        else:
            oid2 = existing_order_id  # cancel the --order-id order last
        if oid2:
            can = {"orderId": oid2, "reason": "customer_request", "notifyCustomer": False,
                   "notes": "cancelled by onx_exercise.py"}
            c = act("cancel-order", can, "cancel")
            if c:
                ent = entity_of(c, "cancel-order")
                st = ent.get("status") if ent else None
                if st and "cancel" not in str(st).lower():
                    F.add("BUG", "cancel-order", "L3 cancel", f"returned order status {st!r}, expected a cancelled state", c["seq"])
                g = cli.call("get-orders", {"ids": [oid2]}, "L3 get-orders after cancel")
                if report_call(F, g, "get-orders", "L3 read after cancel") and records(g, "get-orders"):
                    st2 = records(g, "get-orders")[0].get("status")
                    if st2 and "cancel" not in str(st2).lower():
                        F.add("BUG", "get-orders", "L3 read after cancel", f"status is {st2!r} after cancel-order", g["seq"])
                    else:
                        F.add("PASS", "get-orders", "L3 read after cancel", f"status {st2!r}", g["seq"])
                act("cancel-order", can, "cancel twice", "error")
        if order_id != existing_order_id:
            act("cancel-order", {"orderId": order_id, "reason": "customer_request",
                                 "lineItems": [{"sku": sku, "quantity": 1}]}, "partial cancel of fulfilled order", "empty_ok")


# -------------------------------------------------------------------- report

def render(meta, F, cli):
    L = []
    w = L.append
    w("# onX MCP Runtime Exercise Report")
    w("")
    w(f"**{meta['server']}** | {meta['generated']} | onx_exercise v{VERSION} | "
      f"spec {meta.get('spec_commit') or 'n/a'} | tiers {', '.join(meta['tiers'])}")
    w("")
    counts = {s: F.count(s) for s in Findings.SEV}
    w("## Verdict")
    w("")
    w(f"**{counts['BUG']} bugs, {counts['SPEC']} spec deviations, {counts['BLOCKED']} blocked, "
      f"{counts['WARN']} warnings, {counts['INFO']} notes, {counts['PASS']} passes** "
      f"over {len(cli.calls)} tool calls.")
    w("")
    w("- **BUG**: the server crashed, leaked an exception, ignored a filter, or accepted invalid input.")
    w("- **SPEC**: the response or schema deviates from the onX reference.")
    w("- **BLOCKED**: the environment (credentials, permissions) prevented the check.")
    w("- **WARN**: worth a look, not necessarily wrong (nulls, latency, leaked backend errors).")
    w("")
    # per-tool table
    tools = []
    for f in F.items:
        if f["tool"] not in tools:
            tools.append(f["tool"])
    w("| tool | BUG | SPEC | BLOCKED | WARN | PASS | calls | p50 ms | max ms |")
    w("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for t in tools:
        fs = [f for f in F.items if f["tool"] == t]
        ms = sorted(c["ms"] for c in cli.calls if c["tool"] == t)
        p50 = ms[len(ms) // 2] if ms else ""
        w(f"| `{t}` | " + " | ".join(str(sum(1 for f in fs if f['severity'] == s))
                                     for s in ("BUG", "SPEC", "BLOCKED", "WARN", "PASS"))
          + f" | {len(ms)} | {p50} | {ms[-1] if ms else ''} |")
    w("")
    for sev in ("BUG", "SPEC", "BLOCKED", "WARN"):
        fs = [f for f in F.items if f["severity"] == sev]
        if not fs:
            continue
        w(f"## {sev} ({len(fs)})")
        w("")
        cur = None
        for f in fs:
            if f["tool"] != cur:
                cur = f["tool"]
                w(f"### `{cur}`")
            ref = f" _(trace #{f['seq']})_" if f.get("seq") else ""
            w(f"- **{f['check']}**: {f['detail']}{ref}")
        w("")
    w("## INFO and PASS")
    w("")
    w("<details><summary>expand</summary>")
    w("")
    for f in F.items:
        if f["severity"] in ("INFO", "PASS"):
            ref = f" _(#{f['seq']})_" if f.get("seq") else ""
            w(f"- {f['severity']} `{f['tool']}` **{f['check']}**: {f['detail']}{ref}")
    w("")
    w("</details>")
    w("")
    w("## How to read the trace")
    w("")
    w(f"`{meta['trace']}` holds one JSON object per line for every request sent, in order, with "
      "`seq`, the exact request body, the raw response, HTTP status and elapsed ms. Findings cite "
      "`seq`. To see one call:")
    w("")
    w("```bash")
    w(f"python -c \"import json,sys; [print(json.dumps(json.loads(l), indent=1)) for l in open('{meta['trace']}') if json.loads(l)['seq']==SEQ]\"")
    w("```")
    w("")
    if meta.get("caveats"):
        w("## Caveats")
        w("")
        for c in meta["caveats"]:
            w(f"- {c}")
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--server", required=True, help="MCP Streamable-HTTP endpoint URL")
    ap.add_argument("--spec", help="path to mcp-reference-server/schemas (enables L0 declaration and output validation)")
    ap.add_argument("--token", help="bearer token")
    ap.add_argument("--header", action="append", default=[], help="extra header, K=V; repeatable")
    ap.add_argument("--mutate", action="store_true", help="run L3: create/update/fulfill/return/cancel. Staging only.")
    ap.add_argument("--sku", help="a SKU that exists in the backend (else harvested from query results)")
    ap.add_argument("--location", help="a locationId for fulfil/return (else harvested)")
    ap.add_argument("--order-id", help="existing open order to run update/fulfill/return/cancel against "
                                       "when create-sales-order cannot produce one (it WILL be cancelled)")
    ap.add_argument("--page", type=int, default=2, help="pageSize used for probes (default 2)")
    ap.add_argument("--timeout", type=int, default=120)
    ap.add_argument("--only", help="comma-separated tiers to run: protocol,declaration,liveness,contract,mutation")
    ap.add_argument("--out", default="onx-exercise-report", help="output prefix")
    ap.add_argument("--trace-max-chars", type=int, default=200000)
    ap.add_argument("--caveat", action="append", default=[])
    args = ap.parse_args()

    tiers = args.only.split(",") if args.only else ["protocol", "declaration", "liveness", "contract"] + (["mutation"] if args.mutate else [])
    headers = dict(h.split("=", 1) for h in args.header)
    if args.token:
        headers["Authorization"] = f"Bearer {args.token}"
    trace_path = f"{args.out}.trace.jsonl"
    cli = Client(args.server, headers, args.timeout, trace_path, args.trace_max_chars)
    F = Findings()

    schemas, spec_commit = {}, None
    if args.spec:
        sd = Path(args.spec)
        for f in sd.glob("*.json"):
            schemas[f.stem] = json.loads(f.read_text())
        try:
            import subprocess
            spec_commit = subprocess.check_output(["git", "-C", str(sd), "rev-parse", "--short", "HEAD"],
                                                  stderr=subprocess.DEVNULL).decode().strip()
        except Exception:
            pass

    # tools/list first; nothing works without it
    r = cli.rpc("tools/list", {}, "tools/list")
    if not (r["msg"] and "result" in r["msg"]):
        print(f"cannot list tools: {r['err'] or trunc(r['raw'], 300)}", file=sys.stderr)
        return 2
    live = {t["name"]: t for t in r["msg"]["result"].get("tools", [])}
    print(f"{len(live)} tools advertised: {', '.join(sorted(live))}")

    if "protocol" in tiers:
        progress("tier: protocol")
        tier_protocol(cli, F, live)
    if "declaration" in tiers and args.spec:
        progress("tier: declaration (inputSchema vs spec)")
        tier_declaration(F, Path(args.spec), live)
    H = Harvest()
    if "liveness" in tiers:
        progress("tier: liveness (one minimal call per query tool)")
        tier_liveness(cli, F, H, schemas, live, args.page, args.sku)
    if "contract" in tiers:
        progress("tier: contract (filters, pagination, negatives, output schemas); this is the long one")
        tier_contract(cli, F, H, schemas, live, args.page)
    if "mutation" in tiers:
        progress("tier: mutation (create/update/fulfill/return/cancel)")
        tier_mutation(cli, F, H, schemas, live, args.sku, args.location, args.order_id)
    progress("writing reports")
    cli.trace.close()
    F.finalize()

    meta = {"server": re.sub(r"([?&](x-api-key|token|key)=)[^&]+", r"\1***", args.server),
            "generated": now_iso(), "version": VERSION, "tiers": tiers, "spec_commit": spec_commit,
            "trace": trace_path, "caveats": args.caveat, "tools_advertised": sorted(live)}
    Path(f"{args.out}.md").write_text(render(meta, F, cli), encoding="utf-8")
    Path(f"{args.out}.json").write_text(json.dumps({"meta": meta, "findings": F.items,
                                                    "calls": [{k: v for k, v in c.items() if k not in ("data", "text")} for c in cli.calls]},
                                                   indent=1, default=str), encoding="utf-8")
    for s in Findings.SEV:
        print(f"{s:8}{F.count(s)}")
    print(f"wrote {args.out}.md, {args.out}.json, {trace_path}")
    return 1 if (F.count("BUG") or F.count("SPEC")) else 0


if __name__ == "__main__":
    sys.exit(main())
