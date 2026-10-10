#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Decision Structure Language (DSL) — Reference Toolkit
======================================================

Language Standard 2026.2 · Second Perspective Language
Grammar   : ./decision.ebnf          Extension : .spd
Spec doc  : ./grammar.md             Standard  : ./2026.md

This file delivers all three layers of the toolchain at once:

    +-- (1) Grammar ---------------------------------+
    |   decision.ebnf - ISO 14977 formal grammar     |
    +-- (2) Validator  check ------------------------+
    |   lexer -> parser -> structural -> constraints |
    |        -> quality advisories                   |
    +-- (3) Sample generator  gen -------------------+
    |   emits FORM-VALID decision records            |
    +------------------------------------------------+

Design invariant (mirrors the Constraints section of ./2026.md):

    This language describes structure only; it carries no execution
    semantics. The validator rejects conclusions, recommendations,
    ranking/scoring and optimisation guidance. The generator emits
    form-valid SAMPLES only -- never ADVICE.

Zero external dependencies · standard library only · deterministic
(the generator is reproducible given an explicit seed).

NOTE ON BILINGUAL LEXICONS. The constraint and quality lexicons below
deliberately contain BOTH English and Chinese terms. They are functional
data, not documentation prose: dropping either language would silently
disable violation detection for that language's inputs. All human-facing
text in this file is English; all detection capability is bilingual.

Usage:
    python dsl.py check examples/valid_decision.en.spd
    python dsl.py check examples/*.spd --json --strict
    python dsl.py gen --seed 2026
    python dsl.py gen --seed 2026 --lang zh --count 5 --out samples/
    python dsl.py grammar
    python dsl.py codes E302

Copyright (c) 2026 Shanghai Linming Junhua Technology Co., Ltd.
              and NOHN AI TECHNOLOGY PTE. LTD.
All rights reserved.  Dual-track license — see ../../LICENSE.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

# ──────────────────────────────────────────────────────────────────────
# Metadata
# ──────────────────────────────────────────────────────────────────────

LANG_VERSION = "2026.2"
EXTENSION = ".spd"

# Normative block order (see grammar.md §1.1). Permutation raises E108.
PHASE_ORDER: Dict[str, int] = {
    "Decision": 0,
    "Assumption": 1,
    "Dependency": 2,
    "Branch": 3,
}

# ── Line-level lexer: one regex per production ──

RE_DECISION = re.compile(r"^Decision\s*:\s*(?P<text>.*)$")
RE_ASSUMPTION = re.compile(r"^Assumption\s+(?P<id>\S+)\s*:\s*(?P<text>.*)$")
RE_DEPENDENCY = re.compile(
    r"^Dependency\s*:\s*(?P<src>\S+)\s+(?P<verb>requires|depends\s+on)\s+(?P<dst>\S+)\s*$"
)
RE_BRANCH = re.compile(r"^Branch\s+(?P<id>\S+)\s*:\s*(?P<text>.*)$")

# EBNF: id = letter , { letter | digit | "_" }
RE_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")

# ── L2 constraint lexicon (Constraints, ./2026.md lines 44-50) ──
# One rule per prohibited line of the standard. A hit is an ERROR.
# Bilingual by design — see the module docstring.

CONSTRAINT_RULES: List[Tuple[str, str, List[str]]] = [
    (
        "E301",
        "conclusion-bearing wording",
        [
            # Chinese
            r"结论是", r"综上所述", r"综上", r"由此可见",
            r"因此可以(?:断定|认定|确认|得出)", r"说明该", r"证明了", r"已经证实",
            # English
            r"\bconclusion\b", r"\btherefore\b", r"\bthus proving\b",
            r"\bit is clear that\b", r"\bthis proves\b",
        ],
    ),
    (
        "E302",
        "recommendation wording",
        [
            # Chinese
            r"建议", r"推荐", r"不妨", r"务必",
            r"应当(?:选择|采用|改为|转向)", r"应该(?:选择|采用|改为|转向)",
            r"最好(?:选择|采用|改为)", r"最佳选择",
            # English
            r"\brecommend", r"\bshould\b", r"\badvise", r"\bbetter to\b",
            r"\bwe ought to\b", r"\bpreferable to\b",
        ],
    ),
    (
        "E303",
        "ranking / scoring / probability assignment",
        [
            # Chinese
            r"评分", r"打分", r"得分", r"排名", r"排序第", r"优先级为",
            r"概率(?:为|是)", r"成功概率", r"胜率", r"置信度(?:为|是)",
            # English
            r"\bscore\b", r"\brank(?:ed|ing)?\b", r"\bprobability\b",
            r"\bwin rate\b", r"\bconfidence level\b", r"\btop-ranked\b",
        ],
    ),
    (
        "E304",
        "optimisation guidance",
        [
            # Chinese
            r"优化方案", r"最优(?:解|方案|选择)", r"最佳实践", r"改进建议",
            r"提升空间", r"更优(?:的)?(?:方案|选择)",
            # English
            r"\boptimi[sz]e\b", r"\bbest practice\b", r"\bimprovement plan\b",
            r"\bopportunity for improvement\b",
        ],
    ),
]

# ── L3 quality lexicon (advisory only) ──

VAGUE_MARKERS: List[str] = [
    # Chinese
    r"可能", r"也许", r"或许", r"大概", r"大约", r"似乎", r"应该是",
    r"估计", r"基本上", r"某种程度上", r"大致",
    # English
    r"\bmaybe\b", r"\bperhaps\b", r"\bprobably\b", r"\bapproximately\b",
    r"\blikely\b", r"\bpresumably\b", r"\broughly\b", r"\bsomewhat\b",
]

# Observable threshold: both a number AND a comparison must be present
RE_DIGIT = re.compile(r"[0-9]")
RE_COMPARISON = re.compile(
    r"[≥≤<>＜＞]|不低于|不超过|不少于|不多于|低于|高于|超过|少于|"
    r"等于|至少|至多|达到|大于|小于|低\s|高\s|"
    r"\bno less than\b|\bno more than\b|\bat least\b|\bat most\b|"
    r"\bgreater than\b|\bless than\b|\bexceeds?\b|\bbelow\b|\babove\b|"
    r"\bequals?\b|\bwithin\b",
    re.IGNORECASE,
)

# Self-evidence heuristic: too short, or a fixed opening formula
RE_SELF_EVIDENT = re.compile(
    r"^(?:this is|that is|it is|这是|那是|情况是|事实是|众所周知)", re.IGNORECASE
)
SELF_EVIDENT_MIN_LEN = 8

# Placeholder-branch heuristic (W404): the declared failure response carries no
# executable action — pure marker words, ellipsis, or a same-as-above reference.
RE_PLACEHOLDER_BRANCH = re.compile(
    r"^(?:tbd|tba|todo|xxx|n/?a|placeholder|lorem.*|待定|待补|占位|同上|同下|略|…+|。*|-*|_*)$",
    re.IGNORECASE,
)

# ── Diagnostic code index ──

CODE_TABLE: Dict[str, str] = {
    "E101": "Missing Decision block",
    "E102": "Duplicate Decision block",
    "E103": "Missing Assumption block",
    "E104": "Reference to an undeclared assumption id",
    "E105": "Duplicate id declaration",
    "E106": "Cycle in the dependency graph",
    "E107": "Assumption without a matching Branch",
    "E108": "Block order violated",
    "E201": "Unrecognised line (unknown keyword)",
    "E202": "Invalid identifier format",
    "E203": "Empty text",
    "E204": "Missing colon or separator",
    "E301": "Conclusion-bearing statement",
    "E302": "Recommendation statement",
    "E303": "Scoring / ranking / probability assignment",
    "E304": "Optimisation guidance",
    "W401": "Assumption contains a vague qualifier",
    "W402": "Assumption lacks an observable threshold",
    "W403": "Assumption looks self-evident",
    "W404": "Branch response is a placeholder (no executable action)",
}


# ──────────────────────────────────────────────────────────────────────
# Data model
# ──────────────────────────────────────────────────────────────────────


@dataclass
class Diagnostic:
    """A single diagnostic record (aligned with the plugin-layer violation shape)."""

    code: str
    severity: str  # ERROR | WARN
    line: int
    message: str
    excerpt: str = ""

    def to_dict(self) -> Dict[str, object]:
        return {
            "rule_id": self.code,
            "severity": self.severity,
            "line": self.line,
            "description": self.message,
            "excerpt": self.excerpt,
        }


@dataclass
class Assumption:
    id: str
    text: str
    line: int


@dataclass
class Dependency:
    src: str
    verb: str
    dst: str
    line: int


@dataclass
class Branch:
    id: str
    text: str
    line: int


@dataclass
class Document:
    """Abstract syntax structure of one .spd document."""

    decision: Optional[str] = None
    decision_line: int = 0
    assumptions: List[Assumption] = field(default_factory=list)
    dependencies: List[Dependency] = field(default_factory=list)
    branches: List[Branch] = field(default_factory=list)

    @property
    def assumption_ids(self) -> List[str]:
        return [a.id for a in self.assumptions]

    def summary(self) -> str:
        return (
            f"1 decision · {len(self.assumptions)} assumptions · "
            f"{len(self.dependencies)} dependencies · {len(self.branches)} branches"
        )


# ──────────────────────────────────────────────────────────────────────
# (1) Lexer + parser: text -> Document
# ──────────────────────────────────────────────────────────────────────


def _normalize_colon(line: str) -> str:
    """Fold only the first full-width colon, so body punctuation stays intact."""
    return line.replace("：", ":", 1)


def _keyword_of(line: str) -> Optional[str]:
    """Exact keyword match (case-sensitive); requires a trailing space or colon."""
    for kw in PHASE_ORDER:
        if line.startswith(kw):
            rest = line[len(kw):]
            if rest[:1] in (" ", ":", "：") or rest == "":
                return kw
    return None


def parse(text: str) -> Tuple[Document, List[Diagnostic]]:
    """Line-oriented parse. Never raises — every problem is reported as a Diagnostic."""
    doc = Document()
    diags: List[Diagnostic] = []

    max_phase = -1
    prev_kw: Optional[str] = None
    decision_seen = False

    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.rstrip()
        if not line.strip():
            continue
        if line.lstrip().startswith("#"):
            continue  # whole-line comment: non-normative, excluded from constraint scanning

        line = _normalize_colon(line)
        kw = _keyword_of(line)

        # ── Unknown keyword ──
        if kw is None:
            hint = ""
            lowered = line.split(":", 1)[0].strip().lower()
            for known in PHASE_ORDER:
                if lowered == known.lower():
                    hint = f" (keyword case mismatch — expected '{known}')"
                    break
            diags.append(
                Diagnostic(
                    "E201", "ERROR", lineno, f"unrecognised line: {hint or 'unknown keyword'}", raw
                )
            )
            continue

        phase = PHASE_ORDER[kw]

        # ── Block order ──
        if phase < max_phase:
            diags.append(
                Diagnostic(
                    "E108",
                    "ERROR",
                    lineno,
                    f"block order violated: {kw} may not appear after {prev_kw}",
                    raw,
                )
            )
        max_phase = max(max_phase, phase)
        prev_kw = kw

        # ── Production dispatch ──
        if kw == "Decision":
            m = RE_DECISION.match(line)
            if not m:
                diags.append(Diagnostic("E204", "ERROR", lineno, "Decision is missing ':'", raw))
                continue
            if decision_seen:
                diags.append(
                    Diagnostic("E102", "ERROR", lineno, "duplicate Decision block", raw)
                )
                continue
            body = m.group("text").strip()
            if not body:
                diags.append(
                    Diagnostic("E203", "ERROR", lineno, "Decision text is empty", raw)
                )
                continue
            doc.decision = body
            doc.decision_line = lineno
            decision_seen = True

        elif kw == "Assumption":
            m = RE_ASSUMPTION.match(line)
            if not m:
                diags.append(
                    Diagnostic("E204", "ERROR", lineno, "Assumption is missing an id or ':'", raw)
                )
                continue
            aid = m.group("id")
            if not RE_ID.match(aid):
                diags.append(
                    Diagnostic("E202", "ERROR", lineno, f"invalid identifier: '{aid}'", raw)
                )
                continue
            body = m.group("text").strip()
            if not body:
                diags.append(
                    Diagnostic("E203", "ERROR", lineno, f"assumption {aid} text is empty", raw)
                )
                continue
            doc.assumptions.append(Assumption(aid, body, lineno))

        elif kw == "Dependency":
            m = RE_DEPENDENCY.match(line)
            if not m:
                diags.append(
                    Diagnostic(
                        "E204",
                        "ERROR",
                        lineno,
                        "Dependency must read 'Dependency: A1 requires A2'",
                        raw,
                    )
                )
                continue
            src, dst = m.group("src"), m.group("dst")
            bad = [x for x in (src, dst) if not RE_ID.match(x)]
            if bad:
                diags.append(
                    Diagnostic("E202", "ERROR", lineno, f"invalid identifier: {bad[0]}", raw)
                )
                continue
            doc.dependencies.append(
                Dependency(src, re.sub(r"\s+", " ", m.group("verb")), dst, lineno)
            )

        elif kw == "Branch":
            m = RE_BRANCH.match(line)
            if not m:
                diags.append(
                    Diagnostic("E204", "ERROR", lineno, "Branch is missing an id or ':'", raw)
                )
                continue
            bid = m.group("id")
            if not RE_ID.match(bid):
                diags.append(
                    Diagnostic("E202", "ERROR", lineno, f"invalid identifier: '{bid}'", raw)
                )
                continue
            body = m.group("text").strip()
            if not body:
                diags.append(
                    Diagnostic("E203", "ERROR", lineno, f"branch {bid} text is empty", raw)
                )
                continue
            doc.branches.append(Branch(bid, body, lineno))

    return doc, diags


# ──────────────────────────────────────────────────────────────────────
# (2) Validation: structural + constraints + quality
# ──────────────────────────────────────────────────────────────────────


def _scan_constraints(lineno: int, label: str, body: str) -> List[Diagnostic]:
    """L2 scan: a conclusion, recommendation, ranking or optimisation hit is an ERROR."""
    out: List[Diagnostic] = []
    for code, title, patterns in CONSTRAINT_RULES:
        for pat in patterns:
            m = re.search(pat, body, re.IGNORECASE)
            if m:
                out.append(
                    Diagnostic(
                        code,
                        "ERROR",
                        lineno,
                        f"{label} carries {title}: '{m.group()}' (violates 2026.md Constraints)",
                        body,
                    )
                )
                break  # one report per rule per field
    return out


def _scan_branch_quality(branch: Branch) -> List[Diagnostic]:
    """L3 advisories for branch responses: warn only, never block (W404)."""
    out: List[Diagnostic] = []
    body = branch.text.strip()
    if RE_PLACEHOLDER_BRANCH.match(body):
        out.append(
            Diagnostic(
                "W404",
                "WARN",
                branch.line,
                f"branch {branch.id} response is a placeholder — "
                f"declares no executable action (avoid falsely 'anchored' claims)",
                branch.text,
            )
        )
    return out


def _scan_quality(assumption: Assumption) -> List[Diagnostic]:
    """L3 advisories: warn only, never block."""
    out: List[Diagnostic] = []
    body = assumption.text

    for pat in VAGUE_MARKERS:
        m = re.search(pat, body, re.IGNORECASE)
        if m:
            out.append(
                Diagnostic(
                    "W401",
                    "WARN",
                    assumption.line,
                    f"assumption {assumption.id} contains a vague qualifier: "
                    f"'{m.group()}' — not falsifiable",
                    body,
                )
            )
            break

    if not (RE_DIGIT.search(body) and RE_COMPARISON.search(body)):
        out.append(
            Diagnostic(
                "W402",
                "WARN",
                assumption.line,
                f"assumption {assumption.id} has no observable threshold "
                f"(needs both a number and a comparison)",
                body,
            )
        )

    if len(body.strip()) < SELF_EVIDENT_MIN_LEN or RE_SELF_EVIDENT.match(body.strip()):
        out.append(
            Diagnostic(
                "W403",
                "WARN",
                assumption.line,
                f"assumption {assumption.id} looks self-evident — not a valid boundary",
                body,
            )
        )

    return out


def _find_cycles(doc: Document) -> List[List[str]]:
    """Cycle detection over the dependency graph (DFS, three-colour marking)."""
    graph: Dict[str, List[str]] = {}
    for dep in doc.dependencies:
        graph.setdefault(dep.src, []).append(dep.dst)

    WHITE, GRAY, BLACK = 0, 1, 2
    color: Dict[str, int] = {n: WHITE for n in graph}
    stack: List[str] = []
    cycles: List[List[str]] = []
    seen_signatures = set()

    def dfs(node: str) -> None:
        color[node] = GRAY
        stack.append(node)
        for nxt in graph.get(node, []):
            if color.get(nxt, WHITE) == WHITE:
                dfs(nxt)
            elif color.get(nxt) == GRAY:
                path = stack[stack.index(nxt):] + [nxt]
                sig = tuple(sorted(set(path)))
                if sig not in seen_signatures:
                    seen_signatures.add(sig)
                    cycles.append(path)
        stack.pop()
        color[node] = BLACK

    for node in list(graph):
        if color.get(node, WHITE) == WHITE:
            dfs(node)
    return cycles


def validate(doc: Document, parse_diags: Optional[List[Diagnostic]] = None) -> List[Diagnostic]:
    """Full validation: structural (E1xx) -> constraints (E3xx) -> quality (W4xx)."""
    diags: List[Diagnostic] = list(parse_diags or [])

    # ── L1 structural ──
    if doc.decision is None:
        diags.append(Diagnostic("E101", "ERROR", 0, "document is missing a Decision block"))
    if not doc.assumptions:
        diags.append(
            Diagnostic("E103", "ERROR", 0, "document requires at least one Assumption")
        )

    # id uniqueness
    seen_ids: Dict[str, int] = {}
    for a in doc.assumptions:
        if a.id in seen_ids:
            diags.append(
                Diagnostic(
                    "E105",
                    "ERROR",
                    a.line,
                    f"duplicate identifier: '{a.id}' (first declared on line {seen_ids[a.id]})",
                    a.text,
                )
            )
        else:
            seen_ids[a.id] = a.line

    declared = set(seen_ids)

    # reference integrity
    branch_ids = set()
    for b in doc.branches:
        branch_ids.add(b.id)
        if b.id not in declared:
            diags.append(
                Diagnostic(
                    "E104",
                    "ERROR",
                    b.line,
                    f"Branch references an undeclared assumption id: '{b.id}'",
                    b.text,
                )
            )
    for d in doc.dependencies:
        for endpoint in (d.src, d.dst):
            if endpoint not in declared:
                diags.append(
                    Diagnostic(
                        "E104",
                        "ERROR",
                        d.line,
                        f"Dependency references an undeclared assumption id: '{endpoint}'",
                        f"{d.src} {d.verb} {d.dst}",
                    )
                )

    # coverage: every assumption needs a branch with the same id
    for a in doc.assumptions:
        if a.id not in branch_ids:
            diags.append(
                Diagnostic(
                    "E107",
                    "ERROR",
                    a.line,
                    f"assumption {a.id} has no matching Branch (failure path unlabelled)",
                    a.text,
                )
            )

    # acyclicity
    for cyc in _find_cycles(doc):
        diags.append(
            Diagnostic("E106", "ERROR", 0, "dependency cycle detected: " + " -> ".join(cyc))
        )

    # ── L2 constraints (E3xx) ──
    if doc.decision is not None:
        diags.extend(_scan_constraints(doc.decision_line, "Decision", doc.decision))
    for a in doc.assumptions:
        diags.extend(_scan_constraints(a.line, f"assumption {a.id}", a.text))
    for b in doc.branches:
        diags.extend(_scan_constraints(b.line, f"branch {b.id}", b.text))

    # ── L3 quality (W4xx) ──
    for a in doc.assumptions:
        diags.extend(_scan_quality(a))
    for b in doc.branches:
        diags.extend(_scan_branch_quality(b))

    diags.sort(key=lambda d: (d.line == 0, d.line, d.code))
    return diags


def has_errors(diags: Sequence[Diagnostic]) -> bool:
    return any(d.severity == "ERROR" for d in diags)


# ──────────────────────────────────────────────────────────────────────
# (3) Generator: emits form-valid samples
# ──────────────────────────────────────────────────────────────────────
#
# BOUNDARY DECLARATION. The generator only recombines form-valid structural
# skeletons. Every phrase is a neutral descriptive fragment — no conclusion,
# recommendation, ranking or optimisation wording. The output MUST pass this
# file's own validate(). That self-consistency requirement is exercised by
# --self-check.
#
# Two vocabulary sets are provided so the tool can emit either an English or
# a Chinese sample. Assumption[i] is index-aligned with Branch[i] in both.

_VOCAB: Dict[str, Dict[str, object]] = {
    "en": {
        "header": [
            "# Generated by dsl.py sample generator - Language Standard {ver} - seed={seed}",
            "# Form-valid structural sample only: no conclusions, no recommendations",
        ],
        "templates": [
            "Accept {target} as this quarter's only parallel workstream",
            "Lock the delivery date for {target} to 2026-12-31 with no slippage",
            "Commit 3 full-time headcount to {target} and freeze all new initiatives",
            "Use {target} as the only validation scenario and pause all other directions",
            "Apply fixed pricing to {target} instead of case-by-case negotiation",
            "Fix the acceptance criteria for {target} at 3 measurable indicators",
        ],
        "targets": [
            "the Zhangjiang pilot",
            "the East-China channel pilot",
            "the self-built inference cluster",
            "the third-party compliance audit",
            "the open-source self-hosted option",
            "the edge inference node",
        ],
        "assumptions": [
            ("The target account's annual AI budget", ">=", "CNY 5,000,000"),
            ("Their procurement compliance review cycle", "<=", "8 weeks"),
            ("Our unit compute cost advantage over their self-built option", ">=", "30%"),
            ("Their existing engineering headcount", ">=", "20 people"),
            ("Average monthly inference volume during the pilot", ">=", "10 million calls"),
            ("The depth of their procurement decision chain", "<=", "2 levels"),
            ("The supplier's on-time delivery rate", ">=", "95%"),
        ],
        "branches": [
            "Budget falls short - the project degrades to a single PoC and leaves the annual framework",
            "Review overruns - delivery milestones shift by one tier and validation narrows",
            "Cost advantage fails - the cost narrative is voided and resource commitment is revised up",
            "Engineering must be backfilled externally - delivery slips by 6 weeks",
            "Volume misses the threshold - capacity planning rolls back and the cluster is halved",
            "Decision chain is too deep - the approval node shifts and the pilot becomes an observation window",
            "On-time delivery misses the threshold - the backup supplier activates and the main route de-rates",
        ],
    },
    "zh": {
        "header": [
            "# 由 dsl.py 造词器生成 · Language Standard {ver} · seed={seed}",
            "# 生成物为形式合法的结构样本，不含结论与推荐类表述",
        ],
        "templates": [
            "接受{target}作为本季度唯一并行推进项目",
            "将{target}的交付日期锁定在 2026-12-31，不再顺延",
            "在{target}投入 3 人全职编制，冻结其他新增立项",
            "以{target}为唯一验证场景，暂停其他方向的投入",
            "对{target}启用固定报价，不再逐单议价",
            "把{target}的验收口径固定为 3 项可测指标",
        ],
        "targets": [
            "张江科学城试点",
            "华东区渠道试点",
            "自建推理集群",
            "第三方合规审计",
            "开源自托管方案",
            "边缘推理节点",
        ],
        "assumptions": [
            ("目标客户的年度 AI 预算", "≥", "500 万元"),
            ("对方的采购合规审核周期", "≤", "8 周"),
            ("我方单位算力成本相对对方自建成本的优势", "≥", "30%"),
            ("对方现有技术团队规模", "≥", "20 人"),
            ("试点期内的月均调用量", "≥", "1000 万次"),
            ("对方的采购决策链长度", "≤", "2 级"),
            ("供应商的交付准时率", "≥", "95%"),
        ],
        "branches": [
            "预算规模不足，项目降级为单点 PoC，不进入年度框架",
            "审核周期超限，交付节点整体后移一级，验证范围收窄",
            "算力成本优势不成立，成本叙事作废，资源投入上修",
            "技术团队需外部补齐，交付周期上修 6 周",
            "调用量未达阈值，容量规划回退，集群规模砍半",
            "决策链过长，立项节点后移，试点改为观察期",
            "交付准时率不达标，备份供应商启用，主链路降权",
        ],
    },
}


def generate_document(seed: int = 2026, lang: str = "en") -> str:
    """Generate one form-valid .spd document (fully reproducible for a given seed)."""
    vocab = _VOCAB.get(lang) or _VOCAB["en"]
    rng = random.Random(seed)

    templates = vocab["templates"]          # type: ignore[index]
    targets = vocab["targets"]              # type: ignore[index]
    pool_assumptions = vocab["assumptions"]  # type: ignore[index]
    pool_branches = vocab["branches"]        # type: ignore[index]

    k = rng.choice([3, 4, 5])
    picked = rng.sample(range(len(pool_assumptions)), k)  # type: ignore[arg-type]
    decision = rng.choice(templates).format(target=rng.choice(targets))  # type: ignore[arg-type]

    assumptions = [
        (
            f"A{i + 1}",
            f"{pool_assumptions[j][0]} {pool_assumptions[j][1]} {pool_assumptions[j][2]}",  # type: ignore[index]
        )
        for i, j in enumerate(picked)
    ]
    branches = [(f"A{i + 1}", pool_branches[j]) for i, j in enumerate(picked)]  # type: ignore[index]

    deps: List[Tuple[str, str, str]] = []
    for i in range(1, k):
        if rng.random() < 0.6:
            deps.append((f"A{i + 1}", rng.choice(["requires", "depends on"]), "A1"))

    lines: List[str] = [
        h.format(ver=LANG_VERSION, seed=seed) for h in vocab["header"]  # type: ignore[union-attr]
    ]
    lines += ["", f"Decision: {decision}", ""]
    for aid, atext in assumptions:
        lines.append(f"Assumption {aid}: {atext}")
    lines.append("")
    for src, verb, dst in deps:
        lines.append(f"Dependency: {src} {verb} {dst}")
    if deps:
        lines.append("")
    for bid, btext in branches:
        lines.append(f"Branch {bid}: {btext}")

    return "\n".join(lines) + "\n"


# ──────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def cmd_check(args: argparse.Namespace) -> int:
    worst = 0
    payload: List[Dict[str, object]] = []

    for name in args.files:
        path = Path(name)
        if not path.is_file():
            print(f"[SKIP] {name} — file not found")
            worst = max(worst, 2)
            continue

        doc, parse_diags = parse(_read_text(path))
        diags = validate(doc, parse_diags)
        errors = [d for d in diags if d.severity == "ERROR"]
        warns = [d for d in diags if d.severity == "WARN"]

        failed = bool(errors) or (args.strict and bool(warns))
        worst = max(worst, 1 if failed else 0)

        if args.json:
            payload.append(
                {
                    "file": str(path),
                    "language_version": LANG_VERSION,
                    "pass": not failed,
                    "summary": doc.summary(),
                    "error_count": len(errors),
                    "warning_count": len(warns),
                    "diagnostics": [d.to_dict() for d in diags],
                }
            )
            continue

        print(f"[{'FAIL' if failed else 'PASS'}] {path}")
        print(f"       {doc.summary()}")
        for d in diags:
            mark = "x" if d.severity == "ERROR" else "!"
            loc = f"line {d.line}" if d.line else "doc"
            print(f"       {mark} {d.code}  {loc:<10} {d.message}")
        if not diags:
            print("       conforming: structure complete, no constraint conflicts, no advisories")
        print()

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))

    return worst


def cmd_gen(args: argparse.Namespace) -> int:
    if args.count < 1:
        print("usage error: --count must be >= 1")
        return 2

    texts = [generate_document(args.seed + i, args.lang) for i in range(args.count)]

    if args.count > 1 and args.out:
        out_dir = Path(args.out)
        out_dir.mkdir(parents=True, exist_ok=True)
        written = []
        for i, t in enumerate(texts, start=1):
            p = out_dir / f"generated_{args.lang}_{args.seed + i - 1:04d}{EXTENSION}"
            p.write_text(t, encoding="utf-8")
            written.append(p)
        print(f"generated {len(written)} sample(s) -> {out_dir}")
        for p in written:
            print(f"  {p}")
    elif args.count > 1:
        print("usage error: --count > 1 requires --out DIRECTORY "
              "(a single file may hold only one Decision)")
        return 2
    elif args.out:
        p = Path(args.out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(texts[0], encoding="utf-8")
        print(f"written to {p}")
    else:
        sys.stdout.write(texts[0])

    if args.self_check:
        bad = 0
        for t in texts:
            doc, pd = parse(t)
            ds = validate(doc, pd)
            errs = [d for d in ds if d.severity == "ERROR"]
            warns = [d for d in ds if d.severity == "WARN"]
            if errs or warns:
                bad += 1
                print(f"[SELF-CHECK FAIL] {len(errs)} error / {len(warns)} warning")
                for d in ds:
                    print(f"  {d.code} line {d.line}: {d.message}")
        if bad == 0:
            print(f"[SELF-CHECK PASS] {len(texts)} generated document(s) cleared by the "
                  f"validator in this file (0 error / 0 warning)")
        else:
            return 1

    return 0


def cmd_grammar(_: argparse.Namespace) -> int:
    ebnf = Path(__file__).with_name("decision.ebnf")
    if ebnf.is_file():
        sys.stdout.write(_read_text(ebnf))
        return 0
    print(f"grammar file not found: {ebnf}", file=sys.stderr)
    return 2


def cmd_codes(args: argparse.Namespace) -> int:
    if args.code:
        key = args.code.upper()
        if key in CODE_TABLE:
            print(f"{key}  {CODE_TABLE[key]}")
            return 0
        print(f"unknown diagnostic code: {args.code}", file=sys.stderr)
        return 2
    print(f"Decision Structure Language {LANG_VERSION} — diagnostic code index\n")
    for code in sorted(CODE_TABLE):
        level = "ERROR" if code.startswith("E") else "WARN "
        print(f"  {code}  [{level}]  {CODE_TABLE[code]}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="dsl.py",
        description=(
            f"Decision Structure Language reference toolchain v{LANG_VERSION} "
            f"(Second Perspective Language · Language Standard 2026)"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python dsl.py check examples/valid_decision.en.spd\n"
            "  python dsl.py check examples/*.spd --json\n"
            "  python dsl.py gen --seed 2026 --count 5 --out examples/generated/ --self-check\n"
            "  python dsl.py gen --seed 2026 --lang zh\n"
            "  python dsl.py codes E302\n"
        ),
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    pc = sub.add_parser("check", help="validate grammar, structure and constraint conformance")
    pc.add_argument("files", nargs="+", help="files to validate")
    pc.add_argument("--json", action="store_true", help="emit JSON (for CI integration)")
    pc.add_argument("--strict", action="store_true", help="treat warnings as failures")
    pc.set_defaults(func=cmd_check)

    pg = sub.add_parser("gen", help="sample generator: emit form-valid documents")
    pg.add_argument("--seed", type=int, default=2026, help="random seed (default 2026)")
    pg.add_argument("--count", type=int, default=1, help="number of documents (>1 needs --out)")
    pg.add_argument("--out", default=None, help="output file or directory")
    pg.add_argument("--lang", choices=["en", "zh"], default="en", help="sample language (default en)")
    pg.add_argument("--self-check", action="store_true",
                    help="re-validate the generated output immediately")
    pg.set_defaults(func=cmd_gen)

    pgr = sub.add_parser("grammar", help="print the EBNF grammar")
    pgr.set_defaults(func=cmd_grammar)

    pcd = sub.add_parser("codes", help="look up a diagnostic code")
    pcd.add_argument("code", nargs="?", help="diagnostic code; omit to print the whole index")
    pcd.set_defaults(func=cmd_codes)

    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
