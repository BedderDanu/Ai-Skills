#!/usr/bin/env python3
"""
onX smoke test driver. One command, one report folder.

  python smoke_test.py URL [mutate|read-only] [options]

Does three things:
  1. fetches (or refreshes) the onX reference spec into a cache directory
  2. runs onx_conformance.py   -> <out>/conformance.md   (L0 declaration, fingerprinted)
  3. runs onx_exercise.py      -> <out>/smoke-test.md    (protocol, liveness, contract, mutation)

Mutation tools are only exercised when the second argument is one of
mutate / write / yes / true. Anything else, or nothing, means read-only.

Environment:
  ONX_SPEC_DIR   where to clone the spec (default ~/.onx-smoke-test/mcp-reference-server)
  ONX_SPEC_REF   branch or tag to check out (default develop)
"""
import argparse, datetime, os, re, subprocess, sys
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
SPEC_REPO = "https://github.com/commerce-operations-foundation/mcp-reference-server.git"
MUTATE_WORDS = {"mutate", "write", "yes", "true", "--mutate", "mutations"}


def log(msg):
    print(f"[{datetime.datetime.now():%H:%M:%S}] {msg}", flush=True)


def ensure_spec(spec_dir: Path, ref: str, offline: bool):
    if not (spec_dir / ".git").is_dir():
        if offline:
            sys.exit(f"spec not found at {spec_dir} and --offline given")
        log(f"cloning onX reference spec ({ref}) into {spec_dir}")
        spec_dir.parent.mkdir(parents=True, exist_ok=True)
        subprocess.check_call(["git", "clone", "--depth", "1", "--branch", ref, SPEC_REPO, str(spec_dir)])
    elif not offline:
        log(f"refreshing onX reference spec ({ref})")
        r = subprocess.run(["git", "-C", str(spec_dir), "fetch", "--depth", "1", "origin", ref],
                           capture_output=True, text=True)
        if r.returncode == 0:
            subprocess.run(["git", "-C", str(spec_dir), "reset", "--hard", "FETCH_HEAD"],
                           capture_output=True, text=True)
        else:
            log(f"spec refresh failed ({r.stderr.strip()[:120]}); using the cached copy")
    sha = subprocess.run(["git", "-C", str(spec_dir), "rev-parse", "--short", "HEAD"],
                         capture_output=True, text=True).stdout.strip()
    log(f"spec commit {sha}")
    return sha


def run(cmd, stream=True):
    """Run a child process, streaming its output so progress is visible."""
    log("running: " + " ".join(re.sub(r"(x-api-key=|token=)[^&\"']+", r"\1***", c) for c in cmd))
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                         encoding="utf-8", errors="replace")
    for line in p.stdout:
        print("   " + line.rstrip(), flush=True)
    return p.wait()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url", help="MCP Streamable-HTTP endpoint (include the api key query param if the server uses one)")
    ap.add_argument("mode", nargs="?", default="read-only",
                    help="'mutate' to exercise create/update/fulfill/return/cancel; default read-only")
    ap.add_argument("--token", help="bearer token, if the server uses Authorization instead of a URL key")
    ap.add_argument("--header", action="append", default=[], help="extra header K=V; repeatable")
    ap.add_argument("--sku", help="SKU that exists in the backend (else harvested from query results)")
    ap.add_argument("--location", help="locationId for fulfil/return (else harvested)")
    ap.add_argument("--order-id", help="existing open order to exercise the action tools on if create fails")
    ap.add_argument("--out-dir", help="report folder (default ./onx-reports/<host>-<timestamp>)")
    ap.add_argument("--page", type=int, default=2, help="pageSize used for probes")
    ap.add_argument("--timeout", type=int, default=120, help="per-request timeout in seconds")
    ap.add_argument("--offline", action="store_true", help="do not fetch or refresh the spec")
    ap.add_argument("--caveat", action="append", default=[], help="note to include in the report; repeatable")
    args = ap.parse_args()

    mutate = args.mode.strip().lower() in MUTATE_WORDS
    host = urlparse(args.url).hostname or "server"
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M")
    out = Path(args.out_dir) if args.out_dir else Path("onx-reports") / f"{host}-{stamp}"
    out.mkdir(parents=True, exist_ok=True)
    spec_dir = Path(os.environ.get("ONX_SPEC_DIR") or Path.home() / ".onx-smoke-test" / "mcp-reference-server")
    ref = os.environ.get("ONX_SPEC_REF", "develop")

    log(f"target {host}  mode {'MUTATE (creates/updates/cancels orders)' if mutate else 'read-only'}  reports -> {out}")
    sha = ensure_spec(spec_dir, ref, args.offline)
    schemas = str(spec_dir / "schemas")
    common_auth = (["--token", args.token] if args.token else [])

    # L0 declaration with the reproducible fingerprint
    rc0 = run([sys.executable, str(HERE / "onx_conformance.py"), "--spec", schemas, "--server", args.url,
               *common_auth, "--out", str(out / "conformance"),
               *[a for c in args.caveat for a in ("--caveat", c)]])
    if rc0 not in (0, 1):
        log(f"onx_conformance.py exited {rc0}; continuing with the runtime exercise")

    # runtime exercise
    cmd = [sys.executable, str(HERE / "onx_exercise.py"), "--server", args.url, "--spec", schemas,
           "--out", str(out / "smoke-test"), "--page", str(args.page), "--timeout", str(args.timeout),
           *common_auth]
    for h in args.header:
        cmd += ["--header", h]
    if mutate:
        cmd.append("--mutate")
    for k in ("sku", "location", "order_id"):
        if getattr(args, k):
            cmd += [f"--{k.replace('_', '-')}", getattr(args, k)]
    for c in args.caveat + [f"Driver: smoke_test.py, spec {ref}@{sha}, mode {'mutate' if mutate else 'read-only'}."]:
        cmd += ["--caveat", c]
    rc1 = run(cmd)

    log("done")
    print()
    print(f"REPORT      {out / 'smoke-test.md'}")
    print(f"FINDINGS    {out / 'smoke-test.json'}")
    print(f"TRACE       {out / 'smoke-test.trace.jsonl'}")
    print(f"L0 REPORT   {out / 'conformance.md'}")
    print(f"EXIT        exercise={rc1} conformance={rc0}")
    return rc1


if __name__ == "__main__":
    sys.exit(main())
