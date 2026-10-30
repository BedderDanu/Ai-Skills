#!/usr/bin/env python3
"""
scan_prose.py - Locate places where prose is likely to fail as instruction.

ADVISORY ONLY. This script reports located findings. It does not score,
grade, rank, or pass/fail anything, and that is deliberate.

Every signal here is a PROXY. Hedge counts and sentence lengths do not
measure whether an instruction is enforceable; they measure surface
features that often co-occur with unenforceability. A line can trip four
signals and be perfectly good. A line can trip none and be unfalsifiable
garbage. Only a human reading the line with their own context can tell.

If you aggregate this output into a number, you have built a target, and
the way to hit the target is to delete hedge words rather than to write
checkable rules. Do not do it.

CALIBRATION: written for instruction blocks - one rule per line, no
rationale. Pointed at a document that legitimately mixes explanation with
directives (a SKILL.md, a policy doc), the long_sentence and
prose_register signals will fire on the explanatory paragraphs, which is
noise rather than a finding. Rationale prose is supposed to read like
prose. On those documents, attend to unfalsifiable/virtue/hedge inside
the directive sections and ignore the rest.

Note also that a markdown paragraph counts as one "line" here. That is
correct for instruction blocks and misleading for prose.

Usage:
    python scan_prose.py <file> [--json]
"""

import argparse
import os
import json
import re
import sys
from pathlib import Path

# --- Signal vocabularies -------------------------------------------------

HEDGES = [
    "generally", "typically", "usually", "often", "where appropriate",
    "when appropriate", "as appropriate", "as needed", "if needed",
    "where possible", "when possible", "if possible", "where relevant",
    "when relevant", "if relevant", "consider", "may benefit", "might want",
    "could benefit", "try to", "aim to", "strive", "keep in mind",
    "be mindful", "ideally", "preferably", "wherever feasible",
    "to the extent", "as much as possible", "generally speaking",
]

# Evaluative adjectives that describe a quality without naming a check.
VIRTUE_WORDS = [
    "appropriate", "effective", "engaging", "meaningful", "robust",
    "thoughtful", "high-quality", "quality", "strong", "good", "best",
    "proper", "relevant", "rigorous", "authentic", "responsive",
    "compelling", "polished", "professional", "seamless", "intuitive",
    "clean", "elegant", "solid", "sound", "reasonable", "sensible",
    "helpful", "useful", "clear", "concise", "comprehensive",
]

# Sentence openers that almost never produce a violation condition.
UNFALSIFIABLE_OPENERS = [
    r"^\s*be\s+\w+",
    r"^\s*remember\s+(that|to)\b",
    r"^\s*keep\s+in\s+mind\b",
    r"^\s*focus\s+on\b",
    r"^\s*prioriti[sz]e\b",
    r"^\s*emphasi[sz]e\b",
    r"^\s*bear\s+in\s+mind\b",
    r"^\s*make\s+sure\s+(it|they|things)\s+(are|is)\b",
    r"^\s*ensure\s+\w+\s+is\s+(clear|good|appropriate|effective|strong)\b",
    r"^\s*aim\s+(for|to)\b",
]

# Transitions that mark reading-prose register rather than rule register.
PROSE_MARKERS = [
    "however", "furthermore", "moreover", "additionally", "in addition",
    "that said", "importantly", "notably", "on the other hand",
    "as such", "therefore", "consequently", "in other words",
    "it is worth noting", "it should be noted", "as mentioned",
]

# Line-initial pronouns: the scope condition may live in a neighbouring line.
DANGLING_OPENERS = [
    r"^\s*this\b", r"^\s*these\b", r"^\s*that\b", r"^\s*those\b",
    r"^\s*it\s+(is|should|must|can|will)\b", r"^\s*they\s+(are|should|must)\b",
    r"^\s*such\b", r"^\s*doing so\b", r"^\s*the above\b", r"^\s*the former\b",
    r"^\s*the latter\b",
]

LONG_SENTENCE_WORDS = 25
COMPOUND_CLAUSE_MARKERS = [" and also ", " as well as ", "; ", " while also "]

CATEGORY_PROMPTS = {
    "hedge": "Commit to a threshold, or delete the line.",
    "virtue": "Replace the adjective with the procedure a person would run to check it.",
    "unfalsifiable": "Name the output that would violate this. If you can't, it isn't an instruction.",
    "prose_register": "Reading-prose connective. Rules don't need transitions.",
    "dangling": "Scope condition may be in a neighbouring line. Make the line self-contained.",
    "long_sentence": "Long enough to be carrying more than one directive. Check whether it splits.",
    "compound": "Possibly two or more claims in one grammatical unit. Split and triage separately.",
}


def split_lines(text):
    """Yield (line_number, raw_line) for non-empty, non-heading lines."""
    for i, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        yield i, stripped


def strip_markers(line):
    """Remove list bullets and numbering so openers match at position 0."""
    return re.sub(r"^\s*(?:[-*+\u2022]|\d+[.)])\s*", "", line)


def find_phrases(line_lower, phrases):
    hits = []
    for p in phrases:
        pattern = r"\b" + re.escape(p) + r"\b" if p.isalpha() else re.escape(p)
        if re.search(pattern, line_lower):
            hits.append(p)
    return hits


def find_patterns(body_lower, patterns):
    return [p for p in patterns if re.search(p, body_lower)]


def word_count(line):
    return len(re.findall(r"\b[\w'-]+\b", line))


def scan(text):
    findings = []
    directive_lines = 0

    for lineno, line in split_lines(text):
        body = strip_markers(line)
        low = body.lower()
        directive_lines += 1
        hit = {}

        for cat, phrases in (("hedge", HEDGES),
                             ("virtue", VIRTUE_WORDS),
                             ("prose_register", PROSE_MARKERS)):
            found = find_phrases(low, phrases)
            if found:
                hit[cat] = found

        for cat, patterns in (("unfalsifiable", UNFALSIFIABLE_OPENERS),
                              ("dangling", DANGLING_OPENERS)):
            if find_patterns(low, patterns):
                hit[cat] = ["line opens with an unverifiable/dependent construction"]

        wc = word_count(body)
        if wc > LONG_SENTENCE_WORDS:
            hit["long_sentence"] = [f"{wc} words"]

        compound = [m.strip() for m in COMPOUND_CLAUSE_MARKERS if m in low]
        if compound:
            hit["compound"] = compound

        if hit:
            findings.append({
                "line": lineno,
                "text": body,
                "signals": hit,
            })

    return {
        "directive_lines": directive_lines,
        "lines_with_signals": len(findings),
        "findings": findings,
    }


def render(result, path):
    out = []
    out.append(f"ADVISORY SCAN - {path}")
    out.append("=" * 70)
    out.append("")
    out.append("These are proxies, not verdicts. No score is produced, on purpose.")
    out.append("Read each flagged line and decide for yourself. A flagged line may")
    out.append("be fine; an unflagged line may be unenforceable.")
    out.append("")
    out.append(f"Directive-bearing lines : {result['directive_lines']}")
    out.append(f"Lines with any signal   : {result['lines_with_signals']}")
    out.append("")

    if not result["findings"]:
        out.append("No surface signals found. This does NOT mean the instructions")
        out.append("are enforceable. Apply the violation-condition test by hand.")
        return "\n".join(out)

    by_cat = {}
    for f in result["findings"]:
        for cat in f["signals"]:
            by_cat.setdefault(cat, []).append(f)

    for cat in ["unfalsifiable", "virtue", "hedge", "dangling",
                "compound", "long_sentence", "prose_register"]:
        items = by_cat.get(cat)
        if not items:
            continue
        out.append("-" * 70)
        out.append(f"{cat.upper().replace('_', ' ')}  ({len(items)} lines)")
        out.append(f"  -> {CATEGORY_PROMPTS[cat]}")
        out.append("")
        for f in items:
            matches = ", ".join(f["signals"][cat])
            snippet = f["text"] if len(f["text"]) <= 100 else f["text"][:97] + "..."
            out.append(f"  L{f['line']}: {snippet}")
            out.append(f"          [{matches}]")
        out.append("")

    out.append("-" * 70)
    out.append("Position note: models show bias toward earlier instructions.")
    out.append("Check that the highest-stakes rules are near the top.")
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
    ap.add_argument("file", help="File to scan (markdown or plain text)")
    ap.add_argument("--json", action="store_true", help="Emit JSON instead of a report")
    args = ap.parse_args()

    path = Path(args.file)
    if not path.exists():
        print(f"error: no such file: {path}", file=sys.stderr)
        return 2

    text = path.read_text(encoding="utf-8", errors="replace")
    result = scan(text)

    if args.json:
        result["_warning"] = ("Advisory proxies only. No score is emitted by "
                              "design. Do not aggregate these counts into one.")
        _safe_print(json.dumps(result, indent=2))
    else:
        _safe_print(render(result, path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
