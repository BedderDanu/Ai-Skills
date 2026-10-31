#!/usr/bin/env python3
"""
validate_artifact.py - Run structural gates against a produced artifact.

HARD FAIL. Exit 0 = pass, exit 1 = fail, exit 2 = error.

Every check here is one where the check IS the thing meant. There is no
proxy in between, so gaming a check requires satisfying it. A required
section is either present or absent; a word cap is either respected or
not; a forbidden phrase is either there or it isn't.

Headings inside fenced code blocks are not headings: a `# comment` in a
shell example does not start a section.

DELIBERATELY ABSENT: readability formulas, grade-level scores, sentence
length limits, vocabulary difficulty indices. Those are proxies. They
measure syllables and sentence length, not conceptual load, syntactic
embedding, or cultural presupposition. Blocking on them teaches the
writer to chop sentences, which strips the connectives that made logical
relationships explicit - producing text that scores easier and reads
harder. Use scan_prose.py for those signals, advisory only.

Do not add a readability gate to this file.

Usage:
    python -I -X utf8 validate_artifact.py <artifact> --config <gates.json>
    python -I -X utf8 validate_artifact.py <artifact> --config <gates.json> --json
"""

import argparse
import os
import json
import re
import sys
from pathlib import Path


class Result:
    def __init__(self):
        self.checks = []

    def add(self, name, passed, detail):
        self.checks.append({"check": name, "passed": passed, "detail": detail})

    @property
    def failed(self):
        return [c for c in self.checks if not c["passed"]]

    @property
    def ok(self):
        return not self.failed


HEADING = re.compile(r"^ {0,3}(#{1,6})[ \t]+(.*?)(?:[ \t]+#+)?[ \t]*$")
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")


def sections(text):
    """Return [(title_lower, body_start, body_end)] for markdown ATX headings.

    Offsets index into `text`. A section's body runs to the next heading
    of the same or higher level, so it includes its subsections. Lines
    inside fenced code blocks are never headings. A closing run of #s is
    stripped only when a space precedes it, so "## Using C#" keeps its
    title.
    """
    found = []
    fence = None
    pos = 0
    for line in text.splitlines(keepends=True):
        f = FENCE.match(line.rstrip("\r\n"))
        if f:
            marker, rest = f.group(1), f.group(2)
            if fence is None:
                fence = marker
            elif (marker[0] == fence[0] and len(marker) >= len(fence)
                  and not rest.strip()):
                fence = None
        elif fence is None:
            m = HEADING.match(line.rstrip("\r\n"))
            if m:
                level = len(m.group(1))
                for s in found:
                    if s[4] and s[0] >= level:
                        s[3], s[4] = pos, False
                found.append([level, m.group(2).strip().lower(),
                              pos + len(line), len(text), True])
        pos += len(line)
    return [(title, start, end) for _, title, start, end, _ in found]


def heading_blocks(text):
    """Map heading title -> body text beneath it. Repeated headings merge."""
    blocks = {}
    for title, start, end in sections(text):
        body = text[start:end].strip()
        blocks[title] = (blocks[title] + "\n" + body).strip() if title in blocks else body
    return blocks


def word_count(text):
    return len(re.findall(r"\b[\w'-]+\b", text))


def check_required_sections(text, spec, res):
    blocks = heading_blocks(text)
    for title in spec:
        key = title.strip().lower()
        if key not in blocks:
            res.add(f"section present: '{title}'", False, "heading not found")
        elif not blocks[key]:
            res.add(f"section present: '{title}'", False, "heading found but body is empty")
        else:
            res.add(f"section present: '{title}'", True,
                    f"{word_count(blocks[key])} words")


def check_max_words(text, limit, res):
    n = word_count(text)
    res.add("word cap", n <= limit, f"{n} words (limit {limit})")


def check_min_words(text, floor, res):
    n = word_count(text)
    res.add("word floor", n >= floor, f"{n} words (minimum {floor})")


def check_required_phrases(text, phrases, res):
    low = text.lower()
    for p in phrases:
        found = p.lower() in low
        res.add(f"required phrase: '{p}'", found,
                "present" if found else "absent")


def check_forbidden_phrases(text, phrases, res):
    low = text.lower()
    for p in phrases:
        hits = [m.start() for m in re.finditer(re.escape(p.lower()), low)]
        if hits:
            line_no = low[:hits[0]].count("\n") + 1
            res.add(f"forbidden phrase absent: '{p}'", False,
                    f"{len(hits)} occurrence(s), first at line {line_no}")
        else:
            res.add(f"forbidden phrase absent: '{p}'", True, "absent")


def check_section_forbidden_phrases(text, spec, res):
    """Phrases that may appear in the document, but not under one heading."""
    blocks = heading_blocks(text)
    for title, phrases in spec.items():
        key = title.strip().lower()
        if key not in blocks:
            res.add(f"section present: '{title}'", False,
                    "heading not found, so its forbidden phrases cannot be checked")
            continue
        low = blocks[key].lower()
        for p in phrases:
            n = low.count(p.lower())
            res.add(f"'{p}' absent from '{title}'", n == 0,
                    "absent" if n == 0 else f"{n} occurrence(s)")


def check_define_before_use(text, spec, res):
    """Each term's first appearance must be inside the definition section."""
    section_title = spec.get("definition_section", "").strip().lower()
    terms = spec.get("terms", [])
    spans = [(s, e) for t, s, e in sections(text) if t == section_title]

    if not spans:
        res.add("definition section present", False,
                f"'{spec.get('definition_section')}' not found")
        return
    res.add("definition section present", True, "found")

    low_all = text.lower()

    for term in terms:
        t = term.lower()
        m = re.search(r"\b" + re.escape(t) + r"\b", low_all)
        if not m:
            res.add(f"defined before use: '{term}'", True, "term not used")
            continue
        first = m.start()
        inside = any(s <= first < e for s, e in spans)
        if inside:
            res.add(f"defined before use: '{term}'", True, "first use is in definitions")
        else:
            line_no = low_all[:first].count("\n") + 1
            res.add(f"defined before use: '{term}'", False,
                    f"used at line {line_no} before being defined")


def check_companion_files(artifact_path, names, res):
    parent = artifact_path.parent
    for name in names:
        exists = (parent / name).exists()
        res.add(f"companion file: '{name}'", exists,
                "found" if exists else f"missing from {parent}")


REJECTED_KEYS = {
    "max_grade_level": "readability score",
    "reading_level": "readability score",
    "flesch_kincaid": "readability score",
    "max_sentence_words": "sentence-length proxy",
    "vocabulary_difficulty": "vocabulary proxy",
}


def run(artifact_path, config):
    res = Result()
    text = artifact_path.read_text(encoding="utf-8", errors="replace")

    for key, why in REJECTED_KEYS.items():
        if key in config:
            print(f"error: '{key}' is a {why} and cannot be a hard gate.\n"
                  f"       Move it to scan_prose.py as an advisory signal.\n"
                  f"       See the module docstring for why.", file=sys.stderr)
            sys.exit(2)

    if "required_sections" in config:
        check_required_sections(text, config["required_sections"], res)
    if "max_words" in config:
        check_max_words(text, config["max_words"], res)
    if "min_words" in config:
        check_min_words(text, config["min_words"], res)
    if "required_phrases" in config:
        check_required_phrases(text, config["required_phrases"], res)
    if "forbidden_phrases" in config:
        check_forbidden_phrases(text, config["forbidden_phrases"], res)
    if "section_forbidden_phrases" in config:
        check_section_forbidden_phrases(text, config["section_forbidden_phrases"], res)
    if "define_before_use" in config:
        check_define_before_use(text, config["define_before_use"], res)
    if "companion_files" in config:
        check_companion_files(artifact_path, config["companion_files"], res)

    return res


def render(res, artifact_path):
    out = [f"STRUCTURAL GATES - {artifact_path}", "=" * 70, ""]
    for c in res.checks:
        mark = "PASS" if c["passed"] else "FAIL"
        out.append(f"  [{mark}] {c['check']}")
        out.append(f"         {c['detail']}")
    out.append("")
    out.append("-" * 70)
    if res.ok:
        out.append(f"PASSED - {len(res.checks)} checks.")
        out.append("")
        out.append("Structural checks only. This says nothing about whether the")
        out.append("artifact is any good. A human still has to read it.")
    else:
        out.append(f"FAILED - {len(res.failed)} of {len(res.checks)} checks.")
    return "\n".join(out)


def _safe_print(s):
    """Print without exploding when the consumer closes the pipe (e.g. | head)."""
    try:
        print(s)
        sys.stdout.flush()
    except BrokenPipeError:
        try:
            os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        except Exception:
            pass
        raise SystemExit(0)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("artifact")
    ap.add_argument("--config", required=True)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    artifact_path = Path(args.artifact)
    config_path = Path(args.config)

    for p in (artifact_path, config_path):
        if not p.exists():
            print(f"error: no such file: {p}", file=sys.stderr)
            return 2

    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"error: bad JSON in {config_path}: {e}", file=sys.stderr)
        return 2

    config = {k: v for k, v in config.items() if not k.startswith("_")}
    res = run(artifact_path, config)

    if args.json:
        _safe_print(json.dumps({"passed": res.ok, "checks": res.checks}, indent=2))
    else:
        _safe_print(render(res, artifact_path))

    return 0 if res.ok else 1


if __name__ == "__main__":
    sys.exit(main())
