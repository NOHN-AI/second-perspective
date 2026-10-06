#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Decision Structure Language (DSL) — Reference Toolkit
======================================================

Language Standard 2026.1 · Second Perspective Language
Grammar   : ./decision.ebnf          Extension : .spd
Spec doc  : ./grammar.md             Standard  : ./2026.md

本文件一次性交付工艺链的三层能力：

    ┌─ ① 文法  ──────────────────────────────────────┐
    │   decision.ebnf  —— ISO 14977 形式文法           │
    ├─ ② 校验器  check ───────────────────────────────┤
    │   词法 → 语法 → 结构校验 → 约束校验 → 质量警告    │
    ├─ ③ 造词器  gen ─────────────────────────────────┤
    │   依文法生成「形式合法」的决策记录样本             │
    └──────────────────────────────────────────────────┘

设计不变式（与 ./2026.md 第 44-50 行 Constraints 段一致）：

    本语言只描述结构，不产生执行语义。
    校验器不放行 结论 / 建议 / 评分 / 优化引导；
    造词器只造「形式样本」，不造「决定」。

零外部依赖 · 仅标准库 · 确定性（造词器按显式 seed 可复现）

用法：
    python dsl.py check examples/valid_decision.spd
    python dsl.py check examples/*.spd --json --strict
    python dsl.py gen --seed 2026
    python dsl.py gen --seed 2026 --count 5 --out examples/generated/
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
# 元信息
# ──────────────────────────────────────────────────────────────────────

LANG_VERSION = "2026.1"
EXTENSION = ".spd"

# 规范区块顺序（不可颠倒，见 grammar.md §1.1）
PHASE_ORDER: Dict[str, int] = {
    "Decision": 0,
    "Assumption": 1,
    "Dependency": 2,
    "Branch": 3,
}

# ── 行级词法（行导向：一套正则 = 一个产生式） ──

RE_DECISION = re.compile(r"^Decision\s*:\s*(?P<text>.*)$")
RE_ASSUMPTION = re.compile(r"^Assumption\s+(?P<id>\S+)\s*:\s*(?P<text>.*)$")
RE_DEPENDENCY = re.compile(
    r"^Dependency\s*:\s*(?P<src>\S+)\s+(?P<verb>requires|depends\s+on)\s+(?P<dst>\S+)\s*$"
)
RE_BRANCH = re.compile(r"^Branch\s+(?P<id>\S+)\s*:\s*(?P<text>.*)$")

# EBNF: id = letter , { letter | digit | "_" }
RE_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")

# ── L1 约束词库（Constraints · 2026.md 第 44-50 行）──
# 每条规则对应标准中的一行禁令；命中即 ERROR。

CONSTRAINT_RULES: List[Tuple[str, str, List[str]]] = [
    (
        "E301",
        "结论性表述",
        [
            r"结论是", r"综上所述", r"综上", r"由此可见",
            r"因此可以(?:断定|认定|确认|得出)", r"说明该", r"证明了", r"已经证实",
            r"\bconclusion\b", r"\btherefore\b", r"\bthus proving\b",
            r"\bit is clear that\b",
        ],
    ),
    (
        "E302",
        "建议 / 推荐表述",
        [
            r"建议", r"推荐", r"不妨", r"务必",
            r"应当(?:选择|采用|改为|转向)", r"应该(?:选择|采用|改为|转向)",
            r"最好(?:选择|采用|改为)", r"最佳选择",
            r"\brecommend", r"\bshould\b", r"\badvise", r"\bbetter to\b",
        ],
    ),
    (
        "E303",
        "评分 / 排序 / 概率赋值",
        [
            r"评分", r"打分", r"得分", r"排名", r"排序第", r"优先级为",
            r"概率(?:为|是)", r"成功概率", r"胜率", r"置信度(?:为|是)",
            r"\bscore\b", r"\brank(?:ed|ing)?\b", r"\bprobability\b",
        ],
    ),
    (
        "E304",
        "优化引导",
        [
            r"优化方案", r"最优(?:解|方案|选择)", r"最佳实践", r"改进建议",
            r"提升空间", r"更优(?:的)?(?:方案|选择)",
            r"\boptimi[sz]e\b", r"\bbest practice\b", r"\bimprovement plan\b",
        ],
    ),
]

# ── L3 质量警告词库（只警告，不阻断）──

VAGUE_MARKERS: List[str] = [
    r"可能", r"也许", r"或许", r"大概", r"大约", r"似乎", r"应该是",
    r"估计", r"基本上", r"某种程度上", r"大致",
    r"\bmaybe\b", r"\bperhaps\b", r"\bprobably\b", r"\bapproximately\b",
    r"\blikely\b", r"\bpresumably\b",
]

# 可观测阈值：必须同时具备「数字」与「比较词」
RE_DIGIT = re.compile(r"[0-9]")
RE_COMPARISON = re.compile(
    r"[≥≤<>＜＞]|不低于|不超过|不少于|不多于|低于|高于|超过|少于|"
    r"等于|至少|至多|达到|低于|大于|小于|低\s|高\s"
)

# 疑似自明：过短，或落入固定句式
RE_SELF_EVIDENT = re.compile(r"^(?:这是|那是|情况是|事实是|众所周知)")
SELF_EVIDENT_MIN_LEN = 8

# ── 错误码说明表 ──

CODE_TABLE: Dict[str, str] = {
    "E101": "缺少 Decision 块",
    "E102": "Decision 重复",
    "E103": "缺少 Assumption 块",
    "E104": "引用未声明的前提 ID",
    "E105": "ID 重复声明",
    "E106": "依赖图存在环",
    "E107": "前提缺少对应的 Branch",
    "E108": "区块顺序颠倒",
    "E201": "行无法识别（未知关键字）",
    "E202": "ID 格式非法",
    "E203": "文本为空",
    "E204": "缺少冒号或分隔符",
    "E301": "出现结论性表述",
    "E302": "出现建议 / 推荐表述",
    "E303": "出现评分 / 排序 / 概率赋值",
    "E304": "出现优化引导",
    "W401": "假设含模糊限定词",
    "W402": "假设缺少可观测阈值",
    "W403": "假设疑似自明",
}


# ──────────────────────────────────────────────────────────────────────
# 数据模型
# ──────────────────────────────────────────────────────────────────────


@dataclass
class Diagnostic:
    """单条诊断记录（与插件层 violations 结构对齐）。"""

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
    """一个 .spd 文档的抽象语法结构。"""

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
# ① 词法 + 语法：文本 → Document
# ──────────────────────────────────────────────────────────────────────


def _normalize_colon(line: str) -> str:
    """仅把首个全角冒号折半角，避免污染正文中的全角标点。"""
    return line.replace("：", ":", 1)


def _keyword_of(line: str) -> Optional[str]:
    """精确匹配关键字（大小写敏感），要求后接空白或冒号。"""
    for kw in PHASE_ORDER:
        if line.startswith(kw):
            rest = line[len(kw):]
            if rest[:1] in (" ", ":", "：") or rest == "":
                return kw
    return None


def parse(text: str) -> Tuple[Document, List[Diagnostic]]:
    """行导向解析。永不抛异常——所有问题以 Diagnostic 形式回报。"""
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
            continue  # 整行注释，非规范内容，不参与约束扫描

        line = _normalize_colon(line)
        kw = _keyword_of(line)

        # ── 未知关键字 ──
        if kw is None:
            hint = ""
            lowered = line.split(":", 1)[0].strip().lower()
            for known in PHASE_ORDER:
                if lowered == known.lower():
                    hint = f"（关键字大小写错误，应为 '{known}'）"
                    break
            diags.append(
                Diagnostic("E201", "ERROR", lineno, f"行无法识别：{hint or '未知关键字'}", raw)
            )
            continue

        phase = PHASE_ORDER[kw]

        # ── 区块顺序 ──
        if phase < max_phase:
            diags.append(
                Diagnostic(
                    "E108",
                    "ERROR",
                    lineno,
                    f"区块顺序颠倒：{kw} 不得出现在 {prev_kw} 之后",
                    raw,
                )
            )
        max_phase = max(max_phase, phase)
        prev_kw = kw

        # ── 各产生式分派 ──
        if kw == "Decision":
            m = RE_DECISION.match(line)
            if not m:
                diags.append(Diagnostic("E204", "ERROR", lineno, "Decision 缺少冒号", raw))
                continue
            if decision_seen:
                diags.append(Diagnostic("E102", "ERROR", lineno, "Decision 重复声明", raw))
                continue
            body = m.group("text").strip()
            if not body:
                diags.append(Diagnostic("E203", "ERROR", lineno, "Decision 文本为空", raw))
                continue
            doc.decision = body
            doc.decision_line = lineno
            decision_seen = True

        elif kw == "Assumption":
            m = RE_ASSUMPTION.match(line)
            if not m:
                diags.append(
                    Diagnostic("E204", "ERROR", lineno, "Assumption 缺少 ID 或冒号", raw)
                )
                continue
            aid = m.group("id")
            if not RE_ID.match(aid):
                diags.append(
                    Diagnostic("E202", "ERROR", lineno, f"ID 格式非法：'{aid}'", raw)
                )
                continue
            body = m.group("text").strip()
            if not body:
                diags.append(Diagnostic("E203", "ERROR", lineno, f"前提 {aid} 文本为空", raw))
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
                        "Dependency 格式应为 'Dependency: A1 requires A2'",
                        raw,
                    )
                )
                continue
            src, dst = m.group("src"), m.group("dst")
            bad = [x for x in (src, dst) if not RE_ID.match(x)]
            if bad:
                diags.append(
                    Diagnostic("E202", "ERROR", lineno, f"ID 格式非法：{bad[0]}", raw)
                )
                continue
            doc.dependencies.append(
                Dependency(src, re.sub(r"\s+", " ", m.group("verb")), dst, lineno)
            )

        elif kw == "Branch":
            m = RE_BRANCH.match(line)
            if not m:
                diags.append(Diagnostic("E204", "ERROR", lineno, "Branch 缺少 ID 或冒号", raw))
                continue
            bid = m.group("id")
            if not RE_ID.match(bid):
                diags.append(Diagnostic("E202", "ERROR", lineno, f"ID 格式非法：'{bid}'", raw))
                continue
            body = m.group("text").strip()
            if not body:
                diags.append(Diagnostic("E203", "ERROR", lineno, f"分支 {bid} 文本为空", raw))
                continue
            doc.branches.append(Branch(bid, body, lineno))

    return doc, diags


# ──────────────────────────────────────────────────────────────────────
# ② 校验：结构 + 约束 + 质量
# ──────────────────────────────────────────────────────────────────────


def _scan_constraints(lineno: int, label: str, body: str) -> List[Diagnostic]:
    """L1 约束扫描：命中断言/建议/评分/优化引导即 ERROR。"""
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
                        f"{label}出现{title}：'{m.group()}'（违反 2026.md Constraints）",
                        body,
                    )
                )
                break  # 同一规则同一字段只报一次
    return out


def _scan_quality(assumption: Assumption) -> List[Diagnostic]:
    """L3 质量警告：只提示，不阻断。"""
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
                    f"前提 {assumption.id} 含模糊限定词：'{m.group()}'，可证伪性不足",
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
                f"前提 {assumption.id} 缺少可观测阈值（需同时含数字与比较词）",
                body,
            )
        )

    if len(body.strip()) < SELF_EVIDENT_MIN_LEN or RE_SELF_EVIDENT.match(body.strip()):
        out.append(
            Diagnostic(
                "W403",
                "WARN",
                assumption.line,
                f"前提 {assumption.id} 疑似自明，不构成有效边界",
                body,
            )
        )

    return out


def _find_cycles(doc: Document) -> List[List[str]]:
    """依赖图找环（DFS 三色标记）。"""
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
    """完整校验：结构 (E1xx) → 约束 (E3xx) → 质量 (W4xx)。"""
    diags: List[Diagnostic] = list(parse_diags or [])

    # ── L1 结构 ──
    if doc.decision is None:
        diags.append(Diagnostic("E101", "ERROR", 0, "文档缺少 Decision 块"))
    if not doc.assumptions:
        diags.append(Diagnostic("E103", "ERROR", 0, "文档至少需要一条 Assumption"))

    # ID 唯一性
    seen_ids: Dict[str, int] = {}
    for a in doc.assumptions:
        if a.id in seen_ids:
            diags.append(
                Diagnostic(
                    "E105",
                    "ERROR",
                    a.line,
                    f"ID 重复声明：'{a.id}'（首次出现于第 {seen_ids[a.id]} 行）",
                    a.text,
                )
            )
        else:
            seen_ids[a.id] = a.line

    declared = set(seen_ids)

    # 引用完整性
    branch_ids = set()
    for b in doc.branches:
        branch_ids.add(b.id)
        if b.id not in declared:
            diags.append(
                Diagnostic(
                    "E104",
                    "ERROR",
                    b.line,
                    f"Branch 引用未声明的前提 ID：'{b.id}'",
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
                        f"Dependency 引用未声明的前提 ID：'{endpoint}'",
                        f"{d.src} {d.verb} {d.dst}",
                    )
                )

    # 覆盖性：每个前提必须有同 ID 分支
    for a in doc.assumptions:
        if a.id not in branch_ids:
            diags.append(
                Diagnostic(
                    "E107",
                    "ERROR",
                    a.line,
                    f"前提 {a.id} 缺少对应的 Branch（断裂点未标注）",
                    a.text,
                )
            )

    # 无环
    for cyc in _find_cycles(doc):
        diags.append(
            Diagnostic("E106", "ERROR", 0, "依赖图存在环：" + " → ".join(cyc))
        )

    # ── L1 约束（E3xx）──
    if doc.decision is not None:
        diags.extend(_scan_constraints(doc.decision_line, "Decision ", doc.decision))
    for a in doc.assumptions:
        diags.extend(_scan_constraints(a.line, f"前提 {a.id} ", a.text))
    for b in doc.branches:
        diags.extend(_scan_constraints(b.line, f"分支 {b.id} ", b.text))

    # ── L3 质量（W4xx）──
    for a in doc.assumptions:
        diags.extend(_scan_quality(a))

    diags.sort(key=lambda d: (d.line == 0, d.line, d.code))
    return diags


def has_errors(diags: Sequence[Diagnostic]) -> bool:
    return any(d.severity == "ERROR" for d in diags)


# ──────────────────────────────────────────────────────────────────────
# ③ 造词器：依文法生成形式合法的样本
# ──────────────────────────────────────────────────────────────────────
#
# 边界声明：造词器只组合「形式合法」的结构骨架，所有词条均为
# 中立描述性短语，不含结论、建议、评分或优化引导——生成物必须能
# 通过本文件自身的 validate()。这是自洽性约束，由 --self-check 验证。

_DECISION_TEMPLATES: List[str] = [
    "接受{target}作为本季度唯一并行推进项目",
    "将{target}的交付日期锁定在 2026-12-31，不再顺延",
    "在{target}投入 3 人全职编制，冻结其他新增立项",
    "以{target}为唯一验证场景，暂停其他方向的投入",
    "对{target}启用固定报价，不再逐单议价",
    "把{target}的验收口径固定为 3 项可测指标",
]

_TARGETS: List[str] = [
    "张江科学城试点",
    "华东区渠道试点",
    "自建推理集群",
    "第三方合规审计",
    "开源自托管方案",
    "边缘推理节点",
]

# 前提与分支按索引严格对齐：ASSUMPTION[i] ↔ BRANCH[i]
_ASSUMPTION_POOL: List[Tuple[str, str, str]] = [
    ("目标客户的年度 AI 预算", "≥", "500 万元"),
    ("对方的采购合规审核周期", "≤", "8 周"),
    ("我方单位算力成本相对对方自建成本的优势", "≥", "30%"),
    ("对方现有技术团队规模", "≥", "20 人"),
    ("试点期内的月均调用量", "≥", "1000 万次"),
    ("对方的采购决策链长度", "≤", "2 级"),
    ("供应商的交付准时率", "≥", "95%"),
]

_BRANCH_POOL: List[str] = [
    "预算规模不足，项目降级为单点 PoC，不进入年度框架",
    "审核周期超限，交付节点整体后移一级，验证范围收窄",
    "算力成本优势不成立，成本叙事作废，资源投入上修",
    "技术团队需外部补齐，交付周期上修 6 周",
    "调用量未达阈值，容量规划回退，集群规模砍半",
    "决策链过长，立项节点后移，试点改为观察期",
    "交付准时率不达标，备份供应商启用，主链路降权",
]


def generate_document(seed: int = 2026) -> str:
    """生成一份形式合法的 .spd 文本（同 seed 完全可复现）。"""
    rng = random.Random(seed)

    k = rng.choice([3, 4, 5])
    picked = rng.sample(range(len(_ASSUMPTION_POOL)), k)
    decision = rng.choice(_DECISION_TEMPLATES).format(target=rng.choice(_TARGETS))

    assumptions = [
        (f"A{i + 1}", f"{_ASSUMPTION_POOL[j][0]} {_ASSUMPTION_POOL[j][1]} {_ASSUMPTION_POOL[j][2]}")
        for i, j in enumerate(picked)
    ]
    branches = [(f"A{i + 1}", _BRANCH_POOL[j]) for i, j in enumerate(picked)]

    deps: List[Tuple[str, str, str]] = []
    for i in range(1, k):
        if rng.random() < 0.6:
            deps.append((f"A{i + 1}", rng.choice(["requires", "depends on"]), "A1"))

    lines: List[str] = [
        f"# 由 dsl.py 造词器生成 · Language Standard {LANG_VERSION} · seed={seed}",
        "# 生成物为形式合法的结构样本，不含结论与推荐类表述",
        "",
        f"Decision: {decision}",
        "",
    ]
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
            print(f"[SKIP] {name} — 文件不存在")
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
            print("       合规：结构完整、无约束冲突、无质量警告")
        print()

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))

    return worst


def cmd_gen(args: argparse.Namespace) -> int:
    if args.count < 1:
        print("用法错误：--count 必须 ≥ 1")
        return 2

    texts = [generate_document(args.seed + i) for i in range(args.count)]

    if args.count > 1 and args.out:
        out_dir = Path(args.out)
        out_dir.mkdir(parents=True, exist_ok=True)
        written = []
        for i, t in enumerate(texts, start=1):
            p = out_dir / f"generated_{args.seed + i - 1:04d}{EXTENSION}"
            p.write_text(t, encoding="utf-8")
            written.append(p)
        print(f"已生成 {len(written)} 份样本 → {out_dir}")
        for p in written:
            print(f"  {p}")
    elif args.count > 1:
        print("用法错误：--count > 1 时必须指定 --out 目录（单文件只允许一条 Decision）")
        return 2
    elif args.out:
        p = Path(args.out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(texts[0], encoding="utf-8")
        print(f"已写入 {p}")
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
            print(f"[SELF-CHECK PASS] {len(texts)} 份生成物均通过自身校验器（0 error / 0 warning）")
        else:
            return 1

    return 0


def cmd_grammar(_: argparse.Namespace) -> int:
    ebnf = Path(__file__).with_name("decision.ebnf")
    if ebnf.is_file():
        sys.stdout.write(_read_text(ebnf))
        return 0
    print(f"未找到文法文件：{ebnf}", file=sys.stderr)
    return 2


def cmd_codes(args: argparse.Namespace) -> int:
    if args.code:
        key = args.code.upper()
        if key in CODE_TABLE:
            print(f"{key}  {CODE_TABLE[key]}")
            return 0
        print(f"未知错误码：{args.code}", file=sys.stderr)
        return 2
    print(f"Decision Structure Language {LANG_VERSION} — 诊断码总表\n")
    for code in sorted(CODE_TABLE):
        level = "ERROR" if code.startswith("E") else "WARN "
        print(f"  {code}  [{level}]  {CODE_TABLE[code]}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="dsl.py",
        description=f"决策结构语言参考工具链 v{LANG_VERSION}（第二视角语言 · Language Standard 2026）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例：\n"
            "  python dsl.py check examples/valid_decision.spd\n"
            "  python dsl.py check examples/*.spd --json\n"
            "  python dsl.py gen --seed 2026 --count 5 --out examples/generated/ --self-check\n"
            "  python dsl.py codes E302\n"
        ),
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    pc = sub.add_parser("check", help="校验 .spd 文件的语法、结构与约束合规性")
    pc.add_argument("files", nargs="+", help="待校验文件")
    pc.add_argument("--json", action="store_true", help="输出 JSON（便于接入 CI）")
    pc.add_argument("--strict", action="store_true", help="严格模式：警告也视为失败")
    pc.set_defaults(func=cmd_check)

    pg = sub.add_parser("gen", help="造词器：依文法生成形式合法的样本")
    pg.add_argument("--seed", type=int, default=2026, help="随机种子（默认 2026）")
    pg.add_argument("--count", type=int, default=1, help="生成份数（>1 需 --out 目录）")
    pg.add_argument("--out", default=None, help="输出文件或目录")
    pg.add_argument("--self-check", action="store_true", help="生成后立即用自身校验器复检")
    pg.set_defaults(func=cmd_gen)

    pgr = sub.add_parser("grammar", help="打印 EBNF 形式文法")
    pgr.set_defaults(func=cmd_grammar)

    pcd = sub.add_parser("codes", help="查询诊断码含义")
    pcd.add_argument("code", nargs="?", help="错误码，省略则打印全表")
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
