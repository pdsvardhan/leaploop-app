"""Deterministic resume-tailoring engine — JD text -> flex/P5 overrides -> per-JD .tex.

No LLM. Scans the JD for keyword clusters (rules.yaml), picks the best-scoring cluster,
and assembles a per-JD LaTeX file by \\renewcommand-ing the flex macros over the master
(preamble.tex + body.tex). Zero confident match => safe default master (never a wrong CV).

Mirrors the proven Resume/_project/gen_*.py assembly so output is Overleaf-identical.

iter-170 corrections, all measured against the 139 stored JDs that carry real JD text:

* Matching is WORD-AWARE, not substring. `"ai" in jd` fired inside mainstream / domain /
  brainstorming / available (38 JDs) and `"api"` inside capital / rapid (12), which handed
  7% of JDs the wrong variant. A keyword now has to appear as a word, optionally inflected.
* Scoring is DOMAIN-FIRST. Clusters marked `kind: process` describe how a PM works, not what
  they work on, and their keywords are near-universal — "roadmap" appears in 101 of 139 JDs
  and "delivery" in 96 — so agile_delivery won 53% of every JD while bfsi_compliance won none.
  A process cluster is now only in the running when no domain cluster matches at all.
* Keyword hits in the ROLE TITLE count TITLE_WEIGHT times a body hit. "Senior Product Manager,
  Payments" is a stronger signal than one stray "payments" in a benefits paragraph.

`fit_hint` stays a plain count of distinct matched themes — it is a transparency number shown
to the user, never the weighted score used for ranking.
"""
from __future__ import annotations
import argparse, functools, os, re, sys
from pathlib import Path

try:
    import yaml  # PyYAML
except ImportError:
    yaml = None

HERE = Path(__file__).resolve().parent
RULES_PATH = HERE / "rules.yaml"
DEFAULT_RESUME_DIR = Path(os.environ.get("LEAPLOOP_RESUME_DIR", HERE.parent / "resume"))

# A title hit is worth this many body hits.
TITLE_WEIGHT = 3

# Suffixes a keyword may carry and still be the same word: agent/agents/agentic,
# api/apis, analytics, a/b test -> a/b testing. Deliberately short — anything longer
# starts matching unrelated words again, which is the bug this replaced.
_INFLECTIONS = r"(?:s|es|ies|ing|ed|ic|ics)?"


def load_rules(path: Path = RULES_PATH) -> dict:
    if yaml is None:
        raise RuntimeError("PyYAML not installed (pip install pyyaml)")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


# ----------------------------------------------------------------- matching
@functools.lru_cache(maxsize=1024)
def keyword_pattern(kw: str) -> re.Pattern:
    """Word-aware pattern for one keyword. Internal spaces match any whitespace run, so
    'supply chain' still matches 'supply  chain' across a line break."""
    body = re.escape(kw.lower()).replace("\\ ", r"\s+").replace(" ", r"\s+")
    # (?<![a-z0-9]) rather than \b so hyphenated compounds still count: "ai-powered" hits 'ai',
    # but "mainstream" does not.
    return re.compile(r"(?<![a-z0-9])" + body + _INFLECTIONS + r"(?![a-z0-9])")


def matches(kw: str, text: str) -> bool:
    """Case-insensitive on both sides. The internal callers pre-lowercase for speed, but this
    is a public helper and silently returning False for 'Payments' would be a trap."""
    if not text:
        return False
    if not text.islower():
        text = text.lower()
    return keyword_pattern(kw).search(text) is not None


def is_process(cluster: dict) -> bool:
    """A cluster that describes ways of working rather than a domain. Fallback-only."""
    return (cluster.get("kind") or "domain") == "process"


# ----------------------------------------------------------------- scoring
def score_clusters(jd_text: str, rules: dict, title: str = ""):
    """Clusters that matched, best first.

    Sort key: (weighted score, higher-priority). Domain clusters are considered first; process
    clusters only enter the running when nothing domain-specific matched at all.
    """
    jd = (jd_text or "").lower()
    ti = (title or "").lower()
    scored = []
    for c in rules.get("clusters", []):
        hits, score = [], 0.0
        for k in c.get("keywords", []):
            in_title = matches(k, ti)
            if in_title or matches(k, jd):
                hits.append(k)
                score += TITLE_WEIGHT if in_title else 1
        if hits:
            scored.append({"cluster": c, "hits": hits, "score": score,
                           "priority": c.get("priority", 5),
                           "process": is_process(c)})
    pool = [s for s in scored if not s["process"]] or scored
    pool.sort(key=lambda x: (x["score"], -x["priority"]), reverse=True)
    return pool


def choose_cluster(jd_text: str, rules: dict, title: str = ""):
    scored = score_clusters(jd_text, rules, title)
    if not scored:
        return None, []
    return scored[0]["cluster"], scored[0]["hits"]


def detect_gaps(jd_text: str, rules: dict, title: str = "") -> dict:
    """Honest gaps the JD asks for. Word-aware for the same reason scoring is: the substring
    test matched the ml_modeling keyword 'rag' inside average / leverage and flagged a
    fabricated ML-modeling gap on 30 of 139 real JDs."""
    jd = (jd_text or "").lower()
    ti = (title or "").lower()
    out = {}
    for gap, kws in rules.get("honest_gaps", {}).items():
        matched = [k for k in kws if matches(k, jd) or matches(k, ti)]
        if matched:
            out[gap] = matched
    return out


# ----------------------------------------------------------------- assembly
_LATEX_ESCAPES = {
    "\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
    "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def latex_escape(s) -> str:
    """Make a user-typed string safe to drop into LaTeX. Without this a chip value containing
    & % $ # _ produced a compile error instead of a PDF."""
    return "".join(_LATEX_ESCAPES.get(ch, ch) for ch in str(s))


def build_overrides(cluster: dict | None, rules: dict, escape: bool = False) -> str:
    """Assemble the \\renewcommand block. `escape=True` for user-typed override values;
    values that come from rules.yaml are authored LaTeX and are never escaped."""
    esc = latex_escape if escape else (lambda s: s)
    d = rules["default"]
    cl = cluster or {}
    lines = [r"\renewcommand{\flexDescriptor}{%s}" % esc(cl.get("descriptor") or d["descriptor"])]
    p5key = cl.get("p5") or d.get("p5")
    bullet = rules.get("p5_bullets", {}).get(p5key)
    if bullet is None and p5key:
        # Unknown key would have silently dropped the renewcommand and left the preamble
        # default in place, with nothing saying so. Fall back explicitly.
        bullet = rules.get("p5_bullets", {}).get(d.get("p5"))
    if bullet:
        lines.append(r"\renewcommand{\flexHSBCFive}{%s}" % bullet)
    if cl.get("product_add"):
        lines.append(r"\renewcommand{\flexProduct}{%s}" % esc(cl["product_add"]))
    if cl.get("ai_add"):
        lines.append(r"\renewcommand{\flexAINative}{%s}" % esc(cl["ai_add"]))
    if cl.get("domain_add"):
        lines.append(r"\renewcommand{\flexDomain}{%s}" % esc(cl["domain_add"]))
    if cl.get("tools_add"):
        lines.append(r"\renewcommand{\flexTools}{%s}" % esc(cl["tools_add"]))
    if cl.get("edu_ab"):
        lines.append(r"\renewcommand{\flexEduAB}{\eduABbullet}")
    if cl.get("third_project") == "portfolio":
        lines.append(r"\renewcommand{\flexThirdProject}{\projPortfolio}")
    return "\n".join(lines)


def cluster_by_name(name: str, rules: dict) -> dict | None:
    return next((c for c in rules.get("clusters", []) if c.get("name") == name), None)


# Fields the chip editor exposes (map 1:1 onto the flex macros build_overrides emits).
EDITABLE_KEYS = ["descriptor", "p5", "domain_add", "product_add", "ai_add", "tools_add",
                 "edu_ab", "third_project"]
THIRD_PROJECTS = ("vault7a", "portfolio")


def variant_options(rules: dict | None = None) -> list[dict]:
    """[{name, label}] for every selectable variant, default first — the single source for the
    swap-variant control. Previously hardcoded in the API layer, so a cluster added to
    rules.yaml never reached the dropdown and its label fell back to 'Default (safe master)'."""
    rules = rules or load_rules()
    d = rules.get("default", {})
    out = [{"name": "default", "label": d.get("label") or "Default (safe master)"}]
    for c in rules.get("clusters", []):
        out.append({"name": c["name"], "label": c.get("label") or c["name"].replace("_", " ").title()})
    return out


def overrides_for_cluster(name: str, rules: dict | None = None) -> dict:
    """The current editable flex-field values for a cluster name (or 'default'/'custom'),
    with defaults filled in. Used to seed the chip editor."""
    rules = rules or load_rules()
    d = rules["default"]
    cl = cluster_by_name(name, rules) or {}
    return {
        "descriptor": cl.get("descriptor") or d["descriptor"],
        "p5": cl.get("p5") or d.get("p5"),
        "domain_add": cl.get("domain_add") or "",
        "product_add": cl.get("product_add") or "",
        "ai_add": cl.get("ai_add") or "",
        "tools_add": cl.get("tools_add") or "",
        "edu_ab": bool(cl.get("edu_ab", d.get("edu_ab", False))),
        "third_project": cl.get("third_project") or d.get("third_project") or "vault7a",
    }


def p5_options(rules: dict | None = None) -> list[dict]:
    """The available 5th-bullet (P5) options for the chip editor's dropdown."""
    rules = rules or load_rules()
    return [{"key": k, "text": v} for k, v in rules.get("p5_bullets", {}).items()]


MAX_OVERRIDE_LEN = 200


def sanitize_override(raw: dict, rules: dict | None = None,
                      notes: list | None = None) -> dict:
    """Keep only known editable keys from a user-submitted override dict (chip editor).

    Values are stored RAW (escaping happens at render time in build_overrides) so that an
    override survives a round-trip through the editor without accumulating backslashes.
    `p5` and `third_project` are validated against the rules rather than trusted: an unknown
    p5 key used to silently drop the 5th bullet with nothing on screen saying it had.

    Pass `notes` to collect a plain-English line for every value that was rejected, trimmed
    or left to its default. Rejecting silently is the same failure the validation was added
    to fix — the editor reopened showing a value the PDF never used.
    """
    rules = rules or load_rules()
    valid_p5 = set(rules.get("p5_bullets", {}))

    def note(msg):
        if notes is not None:
            notes.append(msg)

    out = {}
    for k in EDITABLE_KEYS:
        if k not in raw or raw[k] in (None, ""):
            if k == "descriptor" and raw.get(k) == "":
                note("The headline descriptor was left empty, so the default is used.")
            continue
        v = raw[k]
        if k == "edu_ab":
            out[k] = bool(v)
        elif k == "p5":
            if v in valid_p5:
                out[k] = v
            else:
                note(f"{v!r} is not one of your confirmed 5th bullets — kept the default one.")
        elif k == "third_project":
            if v in THIRD_PROJECTS:
                out[k] = v
            else:
                note(f"{v!r} is not a known third project — kept the default one.")
        else:
            s = str(v)
            if len(s) > MAX_OVERRIDE_LEN:
                s = s[:MAX_OVERRIDE_LEN]
                note(f"{k} was longer than {MAX_OVERRIDE_LEN} characters and was trimmed.")
            out[k] = s
    return out


def render_tex(jd_text: str, resume_dir: Path = DEFAULT_RESUME_DIR, rules: dict | None = None,
               force_cluster: str | None = None, override: dict | None = None,
               title: str = "") -> dict:
    """Assemble the per-JD .tex string + return metadata (chosen cluster, gaps, fit hint).

    `title` is the role title, scored at TITLE_WEIGHT per hit alongside the JD body.

    `force_cluster` (a cluster name, or 'default' for the safe master) overrides auto-selection
    — used by the Apply-screen swap-variant control. Unknown name falls back to auto-select.

    `override` (a dict of flex fields: descriptor / p5 / domain_add / product_add / ai_add /
    tools_add / edu_ab / third_project) bypasses cluster selection entirely — used by the
    chip editor so the user can hand-tune the flex macros. Still deterministic, still no LLM.
    Override values are user input, so they are LaTeX-escaped on the way in.
    """
    rules = rules or load_rules()
    preamble = (resume_dir / "preamble.tex").read_text(encoding="utf-8")
    body = (resume_dir / "body.tex").read_text(encoding="utf-8")
    escape = False
    if override is not None:
        cluster, hits, token, escape = override, [], "custom", True
    elif force_cluster == "default":
        cluster, hits, token = None, [], "default"
    elif force_cluster:
        cluster = cluster_by_name(force_cluster, rules)
        hits = [k for k in (cluster or {}).get("keywords", [])
                if matches(k, (jd_text or "").lower()) or matches(k, (title or "").lower())] if cluster else []
        if cluster is None:
            cluster, hits = choose_cluster(jd_text, rules, title)
        token = (cluster or {}).get("name", "default")
    else:
        cluster, hits = choose_cluster(jd_text, rules, title)
        token = (cluster or {}).get("name", "default")
    overrides = build_overrides(cluster, rules, escape=escape)
    tex = (
        "\\documentclass[a4paper,10pt]{article}\n"
        + preamble
        + "\n%% ===== per-JD flex overrides (cluster: " + token + ") =====\n"
        + overrides + "\n\n"
        + "\\begin{document}\n"
        + body
        + "\n\\end{document}\n"
    )
    gaps = detect_gaps(jd_text, rules, title)
    return {
        "tex": tex,
        "cluster": token,
        "keyword_hits": hits,
        "fit_hint": len(hits),                 # transparent overlap count, NOT a black-box rank
        "gaps_triggered": list(gaps.keys()),
        "overrides": overrides,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="Tailor the resume to a JD (deterministic).")
    ap.add_argument("--jd", help="path to JD text file, or '-' for stdin")
    ap.add_argument("--text", help="JD text inline (alternative to --jd)")
    ap.add_argument("--title", default="", help="role title (scored at 3x a body hit)")
    ap.add_argument("--resume-dir", default=str(DEFAULT_RESUME_DIR))
    ap.add_argument("--out", help="write the .tex here", default="/tmp/leaploop_cv.tex")
    args = ap.parse_args(argv)

    if args.text:
        jd = args.text
    elif args.jd == "-":
        jd = sys.stdin.read()
    elif args.jd:
        jd = Path(args.jd).read_text(encoding="utf-8")
    else:
        ap.error("provide --jd <file|-> or --text")

    res = render_tex(jd, Path(args.resume_dir), title=args.title)
    Path(args.out).write_text(res["tex"], encoding="utf-8")
    print(f"cluster      : {res['cluster']}")
    print(f"keyword hits : {res['keyword_hits']}")
    print(f"fit hint     : {res['fit_hint']} theme matches")
    print(f"gaps flagged : {res['gaps_triggered'] or 'none'}")
    print(f"wrote tex    : {args.out}  ({len(res['tex'])} bytes)")


if __name__ == "__main__":
    main()
