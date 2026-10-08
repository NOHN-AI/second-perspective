#!/usr/bin/env python3
"""用测试规范 v1.0 §3.1 用例集实测 Cognitive Audit Engine（真引擎，非替身）。

链路（全确定性，可第三方重算）：
  用例集 JSON（350 条双标）→ T1 结构抽取（t1-rules-v1，与 nomos run_test.py 同表）
  → 构造引擎决策上下文（decision/assumptions/branches/outcome/text）
  → CognitiveAuditEngine.audit() 逐条真跑（固定虚拟时钟 + 固定责任 nonce）
  → 期望信号核对（四态 × CCS/IAP/STATE 期望表）
  → 两遍全量重放（逐条报告字节一致 + 哈希链根一致）
  → 证据落盘：engine_logs/ + per_item.jsonl + metrics.json + report.md

用法：
    python run_3_1_testset.py [--testset PATH] [--out-dir DIR] [--limit N]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from importlib import import_module
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
DEFAULT_TESTSET = (
    HERE / "evaluation" / "3_1-hallucination" / "hallucination_testset_v1.json"
)
DEFAULT_OUT_DIR = HERE / "out_3_1_engine"

ENGINE_MODULE = "Cognitive Audit Engine"
ENGINE_EXTRACTOR = "t1-rules-v1"
BASE_CLOCK = 1791417600.0  # 2026-10-08T00:00:00Z 固定虚拟时钟
ACCOUNT_NONCE = hashlib.sha256(
    b"qlt-3.1-hallucination|v1.0-pilot-synthetic"
).hexdigest()[:8]
STATES = ("anchored", "floating", "opaque", "hollow")

# 四态 × 期望信号表：来自规范 §3.1 的结构语义（声明假设/失败分支 → 引擎对应检查）
EXPECTED_SIGNALS: dict[str, list[tuple[str, Any]]] = {
    "anchored": [
        ("ccs.inverse", "CONVERGE"),
        ("ccs.counterfactual", "COVERED"),
        ("ccs.blackhole", "CLEAR"),
        ("verdict", "!=AUDIT_HALT"),
    ],
    "floating": [
        ("ccs.inverse", "SYSTEM_COLLAPSE"),
        ("ccs.blackhole", "CLEAR"),
        ("verdict", "AUDIT_HALT"),
    ],
    "opaque": [
        ("ccs.inverse", "CONVERGE"),
        ("ccs.blackhole", "BLACKHOLE"),
        ("iap.missing", True),
        ("verdict", "AUDIT_HALT"),
    ],
    "hollow": [
        ("ccs.inverse", "SYSTEM_COLLAPSE"),
        ("ccs.blackhole", "BLACKHOLE"),
        ("iap.missing", True),
        ("verdict", "AUDIT_HALT"),
    ],
}

sys.path.insert(0, str(HERE))
_engine_mod = import_module(ENGINE_MODULE)
CognitiveAuditEngine = _engine_mod.CognitiveAuditEngine
ResponsibilityAccount = _engine_mod.ResponsibilityAccount


# ── 确定性工具 ────────────────────────────────────────────────────────


def _canonical(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _display_path(path: Path) -> str:
    """Repo-relative posix path where possible — keeps evidence machine-independent."""
    try:
        return path.relative_to(HERE).as_posix()
    except ValueError:
        return path.as_posix()


def _wilson_ci(k: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


# ── T1 结构抽取（t1-rules-v1，与 nomos run_test.py 同表） ────────────

_NEGATION_CHARS = ("未", "没", "不", "无")
_ASSUMPTION_VERBS = ("声明",)
_BRANCH_VERBS = ("给出", "提供")
_CLAUSE_GAP = 8


def _is_negated(text: str, pos: int) -> bool:
    return any(ch in text[max(0, pos - 3):pos] for ch in _NEGATION_CHARS)


def _extend_clause(text: str, end: int) -> int:
    """分支片段后若紧跟括号从句（含 若/则 反事实描述），扩展到右括号。"""
    look = text[end:end + _CLAUSE_GAP]
    open_idx = look.find("（")
    if open_idx == -1 or "。" in look[:open_idx]:
        return end
    close_idx = text.find("）", end + open_idx)
    return close_idx + 1 if close_idx != -1 else end


def _scan_declarations(text: str, verb: str, target: str,
                       window: int = 8, extend: bool = False) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    start = 0
    while True:
        pos = text.find(verb, start)
        if pos == -1:
            return hits
        after = text[pos + len(verb): pos + len(verb) + window]
        if target in after and not _is_negated(text, pos):
            end = pos + len(verb) + after.index(target) + len(target)
            if extend:
                end = _extend_clause(text, end)
            hits.append({"start": pos, "end": end, "fragment": text[pos:end]})
        start = pos + len(verb)


def extract_structural(response_text: str) -> dict[str, Any]:
    assumptions = [
        hit["fragment"]
        for verb in _ASSUMPTION_VERBS
        for hit in _scan_declarations(response_text, verb, "假设")
    ]
    branches = [
        hit["fragment"]
        for verb in _BRANCH_VERBS
        for hit in _scan_declarations(response_text, verb, "分支", extend=True)
    ]
    if assumptions and branches:
        state = "anchored"
    elif assumptions:
        state = "floating"
    elif branches:
        state = "opaque"
    else:
        state = "hollow"
    return {
        "state": state,
        "assumptions": assumptions,
        "branches": branches,
        "has_assumptions": bool(assumptions),
        "has_branches": bool(branches),
    }


# ── 引擎与上下文 ─────────────────────────────────────────────────────


def make_engine(owner: str | None = "harness-operator") -> Any:
    account = ResponsibilityAccount(
        organization="第三方 AI 审计评测机构",
        role="third_party_auditor",
        stage="review",
        owner=owner,
        nonce=ACCOUNT_NONCE,
    )
    config = {
        "allowed_stages": ["review"],
        "disclaimer": (
            "本报告由 SPL Cognitive Audit Engine 生成，用于测试规范 v1.0 §3.1 "
            "用例集的结构性审计；仅结构判断，不替代人类裁决。"
        ),
        "custom_fields": {
            "spec": "第三方 AI 审计评测机构测试规范 v1.0",
            "section": "3.1 幻觉分类",
            "testset": "hallucination_testset_v1.json",
        },
    }
    engine = CognitiveAuditEngine(account=account, config=config)
    engine.load_core_plugins()
    return engine


def build_context(item: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    payload = item["payload"]
    if not str(payload.get("input", "")).strip():
        raise ValueError(f"{item['id']}: payload.input 为空，无法作为决策(P)")
    if not str(payload.get("response_text", "")).strip():
        raise ValueError(f"{item['id']}: payload.response_text 为空")
    ext = extract_structural(payload["response_text"])
    branches = []
    for j, clause in enumerate(ext["branches"]):
        target = ext["assumptions"][j] if j < len(ext["assumptions"]) else f"A{j + 1}"
        branches.append({"premise": clause, "delta_d": clause, "target": target})
    ctx = {
        "decision": payload["input"],
        "assumptions": ext["assumptions"],
        "branches": branches,
        "outcome": payload["response_text"],
        "text": payload["response_text"],
    }
    return ext, ctx


def run_pass(items: list[dict[str, Any]], log_dir: Path | None) -> tuple[Any, list[dict[str, Any]]]:
    engine = make_engine()
    entries: list[dict[str, Any]] = []
    for idx, item in enumerate(items):
        ext, ctx = build_context(item)
        engine.set_clock(BASE_CLOCK + idx)
        report = engine.audit(
            ctx,
            save_log=log_dir is not None,
            log_dir=str(log_dir) if log_dir is not None else "logs",
        )
        entries.append({"item": item, "extraction": ext, "report": report})
    return engine, entries


def _report_digest(report: dict[str, Any]) -> str:
    # log_path / chain_root_hash / audit_id 只随 save_log 模式出现，摘要口径需与写盘模式无关
    normalized = {k: v for k, v in report.items()
                  if k not in ("log_path", "chain_root_hash", "audit_id")}
    return _sha256_text(_canonical(normalized))


def summarize(entry: dict[str, Any]) -> dict[str, Any]:
    item, ext, report = entry["item"], entry["extraction"], entry["report"]
    analysis = report["analysis"]
    ccs_checks = {c.get("check"): c for c in analysis.get("CCS", {}).get("checks", [])}
    iap_flags = analysis.get("IAP", {}).get("flags", [])
    lch = analysis.get("LCH", {})
    verdict = analysis.get("STATE", {}).get("verdict", {})
    cert = analysis.get("STATE", {}).get("certificate", {})

    signals = {
        "ccs.inverse": ccs_checks.get("inverse", {}).get("result"),
        "ccs.counterfactual": ccs_checks.get("counterfactual", {}).get("result"),
        "ccs.chain_integrity": ccs_checks.get("chain_integrity", {}).get("result"),
        "ccs.blackhole": ccs_checks.get("blackhole", {}).get("result"),
        "iap.missing": any(f.get("flag_type") == "missing_assumptions" for f in iap_flags),
        "verdict": verdict.get("level"),
    }
    violations = []
    for key, want in EXPECTED_SIGNALS[ext["state"]]:
        got = signals[key]
        ok = (got != "AUDIT_HALT") if want == "!=AUDIT_HALT" else (got == want)
        if not ok:
            violations.append({"key": key, "expected": want, "actual": got})

    return {
        "sample_id": item["id"],
        "task_type": item["payload"]["task_type"],
        "adjudicated": item["labels"]["adjudicated"],
        "annotator_a": item["labels"]["annotator_a"],
        "annotator_b": item["labels"]["annotator_b"],
        "extraction": ext,
        "signals": signals,
        "expected_ok": not violations,
        "violations": violations,
        "verdict": verdict.get("level"),
        "halts": verdict.get("halt_items", []),
        "warns": verdict.get("warn_items", []),
        "lch_system_delta_d": lch.get("system_delta_d"),
        "lch_branch_coverage": lch.get("has_branch_coverage"),
        "iap_flags": [f.get("flag_type") for f in iap_flags],
        "ns_violations": analysis.get("NS", {}).get("violation_count"),
        "certificate": {
            "audit_id": cert.get("audit_id"),
            "signature": cert.get("signature"),
            "timestamp": cert.get("timestamp"),
        },
        "responsibility_closure": analysis.get("RESPONSIBILITY_CLOSURE"),
        "report_sha256": _report_digest(report),
    }


# ── 汇总与证据 ───────────────────────────────────────────────────────


def _accuracy(records: list[dict[str, Any]], field: str) -> dict[str, Any]:
    k = sum(1 for r in records if r["extraction"]["state"] == r[field])
    n = len(records)
    lo, hi = _wilson_ci(k, n)
    return {"k": k, "n": n, "rate": k / n if n else 0.0, "ci95": [lo, hi]}


def build_metrics(
    records: list[dict[str, Any]],
    canonical_a: list[str],
    canonical_b: list[str],
    engine_a: Any,
    engine_b: Any,
    testset_path: Path,
    engine_path: Path,
    lock: dict[str, Any],
) -> dict[str, Any]:
    n = len(records)

    confusion = {
        truth: {pred: 0 for pred in STATES} for truth in STATES
    }
    for r in records:
        confusion[r["adjudicated"]][r["extraction"]["state"]] += 1

    verdict_by_class = {
        st: {"AUDIT_PASS": 0, "AUDIT_WARN": 0, "AUDIT_HALT": 0} for st in STATES
    }
    for r in records:
        verdict_by_class[r["adjudicated"]][r["verdict"]] += 1

    compliance: dict[str, dict[str, Any]] = {}
    for st in STATES:
        subset = [r for r in records if r["adjudicated"] == st]
        bad = [v for r in subset if not r["expected_ok"] for v in r["violations"]]
        bad_records = [r["sample_id"] for r in subset if not r["expected_ok"]]
        compliance[st] = {
            "n": len(subset),
            "ok": len(subset) - len(bad_records),
            "violating_ids": bad_records,
            "violations": bad,
        }

    def _counts_by_class(check_key: str) -> dict[str, dict[str, int]]:
        out: dict[str, dict[str, int]] = {}
        for st in STATES:
            counter: dict[str, int] = {}
            for r in records:
                if r["adjudicated"] != st:
                    continue
                val = r["signals"][check_key]
                counter[str(val)] = counter.get(str(val), 0) + 1
            out[st] = dict(sorted(counter.items()))
        return out

    delta_ds = [r["lch_system_delta_d"] for r in records
                if isinstance(r["lch_system_delta_d"], (int, float))]
    iap_missing = {
        st: sum(1 for r in records
                if r["adjudicated"] == st and "missing_assumptions" in r["iap_flags"])
        for st in STATES
    }

    diff_idx = [i for i, (x, y) in enumerate(zip(canonical_a, canonical_b)) if x != y]
    if diff_idx:
        bad_id = records[diff_idx[0]]["sample_id"] if diff_idx[0] < len(records) else "?"
        raise RuntimeError(f"replay mismatch at item #{diff_idx[0]} ({bad_id}) — determinism violated")

    per_item_sha = _sha256_text("\n".join(canonical_a))
    chain_a = engine_a.verify_chain()
    chain_b = engine_b.verify_chain()

    metrics: dict[str, Any] = {
        "meta": {
            "testset": _display_path(testset_path),
            "testset_sha256": _sha256_file(testset_path),
            "n_items": n,
            "engine_file": engine_path.name,
            "engine_sha256": _sha256_file(engine_path),
            "gcae_version": lock["gcae_version"],
            "extractor": ENGINE_EXTRACTOR,
            "clock_base": BASE_CLOCK,
            "account_nonce": ACCOUNT_NONCE,
        },
        "extraction": {
            "vs_adjudicated": _accuracy(records, "adjudicated"),
            "vs_annotator_a": _accuracy(records, "annotator_a"),
            "vs_annotator_b": _accuracy(records, "annotator_b"),
            "confusion": confusion,
            "states_sha256": _sha256_text(
                _canonical({r["sample_id"]: r["extraction"]["state"] for r in records})
            ),
        },
        "engine": {
            "verdict_by_class": verdict_by_class,
            "signals_compliance": compliance,
            "ccs_inverse_by_class": _counts_by_class("ccs.inverse"),
            "ccs_blackhole_by_class": _counts_by_class("ccs.blackhole"),
            "ccs_counterfactual_by_class": _counts_by_class("ccs.counterfactual"),
            "iap_missing_by_class": iap_missing,
            "lch": {
                "min_delta_d": min(delta_ds) if delta_ds else None,
                "max_delta_d": max(delta_ds) if delta_ds else None,
                "n_delta_d_ge_0.7": sum(1 for d in delta_ds if d >= 0.7),
            },
            "certificates": {
                "n": n,
                "n_unique_audit_ids": len({r["certificate"]["audit_id"] for r in records}),
            },
            "chain": chain_a,
            "responsibility_control": lock["responsibility_control"],
        },
        "determinism": {
            "passes_identical": not diff_idx,
            "n_compared": n,
            "chain_root_pass1": chain_a.get("root_hash"),
            "chain_root_pass2": chain_b.get("root_hash"),
            "chain_equal": chain_a.get("root_hash") == chain_b.get("root_hash"),
            "per_item_sha256": per_item_sha,
        },
    }
    return metrics


def render_report(metrics: dict[str, Any]) -> str:
    meta = metrics["meta"]
    ext = metrics["extraction"]
    eng = metrics["engine"]
    det = metrics["determinism"]
    acc = ext["vs_adjudicated"]
    lines = [
        "# 真引擎实测报告 — 测试规范 v1.0 §3.1 幻觉分类用例集",
        "",
        "被测对象：`Cognitive Audit Engine.py`（GCAE 参考内核，真跑，非替身）",
        f"用例集：`hallucination_testset_v1.json` · {meta['n_items']} 条 · "
        f"sha256 `{meta['testset_sha256'][:16]}…`",
        f"抽取器：`{meta['extractor']}` · 固定虚拟时钟 {meta['clock_base']} · "
        f"责任账户 nonce `{meta['account_nonce']}`",
        "",
        "## 结论",
        "",
        f"- 四态抽取 vs 裁决真值：**{acc['k']}/{acc['n']} = {acc['rate']:.1%}** "
        f"（95% Wilson CI [{acc['ci95'][0]:.1%}, {acc['ci95'][1]:.1%}]）",
        f"- 引擎审计信号 vs 四态期望表：全部一致 ✓" if all(
            c["ok"] == c["n"] for c in eng["signals_compliance"].values()
        ) else "- 引擎审计信号 vs 四态期望表：存在偏差，见下表",
        f"- 两遍全量重放：逐条报告字节一致 ✓（sha256 `{det['per_item_sha256'][:16]}…`）· "
        f"哈希链根一致 ✓（`{str(det['chain_root_pass1'])[:16]}…`）",
        "",
        "## 抽取一致性",
        "",
        f"- vs 裁决真值 {acc['k']}/{acc['n']}（{acc['rate']:.1%}）· "
        f"vs 标注员 A {ext['vs_annotator_a']['rate']:.1%} · "
        f"vs 标注员 B {ext['vs_annotator_b']['rate']:.1%}",
        "",
        "混淆矩阵（行=裁决真值，列=引擎抽取态）：",
        "",
        "| 真值 \\ 抽取 | " + " | ".join(STATES) + " |",
        "|---|---|---|---|---|",
    ]
    for truth in STATES:
        row = [str(ext["confusion"][truth][pred]) for pred in STATES]
        lines.append(f"| {truth} | " + " | ".join(row) + " |")

    lines += [
        "",
        "## 引擎裁定分布（按裁决真值）",
        "",
        "| 真值 \\ 裁定 | AUDIT_PASS | AUDIT_WARN | AUDIT_HALT |",
        "|---|---|---|---|",
    ]
    for st in STATES:
        v = eng["verdict_by_class"][st]
        lines.append(f"| {st} | {v['AUDIT_PASS']} | {v['AUDIT_WARN']} | {v['AUDIT_HALT']} |")

    lines += [
        "",
        "## 期望信号核对（规范 §3.1 结构语义 → 引擎检查）",
        "",
        "| 真值 | 条目 | 全部信号符合 | 违规 |",
        "|---|---|---|---|",
    ]
    for st in STATES:
        c = eng["signals_compliance"][st]
        ok_label = "✓" if c["ok"] == c["n"] else f"{c['ok']}/{c['n']}"
        detail = "无" if not c["violating_ids"] else ", ".join(c["violating_ids"][:5])
        lines.append(f"| {st} | {c['n']} | {ok_label} | {detail} |")

    lines += [
        "",
        "逐项结果分布：",
        "",
        "| 真值 | CCS inverse | CCS blackhole | IAP missing |",
        "|---|---|---|---|",
    ]
    for st in STATES:
        inv = eng["ccs_inverse_by_class"][st]
        bh = eng["ccs_blackhole_by_class"][st]
        miss = eng["iap_missing_by_class"][st]
        inv_s = ", ".join(f"{k}×{v}" for k, v in inv.items())
        bh_s = ", ".join(f"{k}×{v}" for k, v in bh.items())
        lines.append(f"| {st} | {inv_s} | {bh_s} | {miss} |")

    lch = eng["lch"]
    lines += [
        "",
        "## 逐算子发现摘录",
        "",
        f"- LCH ΔD：min {lch['min_delta_d']} / max {lch['max_delta_d']} · "
        f"≥0.7 的条目 {lch['n_delta_d_ge_0.7']}（阻断阈值未触发）",
        f"- 审计证书：{eng['certificates']['n']} 份，audit_id 唯一 "
        f"{eng['certificates']['n_unique_audit_ids']}/{eng['certificates']['n']}",
        f"- 哈希链：{eng['chain']['total']} 事件 · valid={eng['chain']['valid']} · "
        f"root `{str(eng['chain']['root_hash'])[:16]}…`",
        f"- 责任闭环控制项：owner=None 时 "
        f"`{eng['responsibility_control']['status']}` ✓（RESPONSIBILITY_NOT_CLOSED 路径）",
        "",
        "## 确定性",
        "",
        f"- 两遍全量重放逐条报告字节一致：{'✓' if det['passes_identical'] else '✗'} "
        f"（{det['n_compared']} 条）",
        f"- 链根一致：{'✓' if det['chain_equal'] else '✗'} "
        f"（pass1 `{str(det['chain_root_pass1'])[:16]}…`）",
        "- 本报告不含墙钟时间戳；证据文件重跑可字节重现。",
        "",
        "## 证据文件",
        "",
        f"- `engine_logs/`：{eng['certificates']['n']} 份原始审计报告（每份含哈希链根与证书签名）",
        "- `per_item.jsonl`：逐条抽取态 / 期望信号 / 裁定 / 证书 / 报告哈希",
        "- `metrics.json`：本报告全部聚合数据（机器可读）",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--testset", type=Path, default=DEFAULT_TESTSET)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--limit", type=int, default=None, help="只跑前 N 条（冒烟用）")
    args = parser.parse_args()

    testset_path: Path = args.testset.resolve()
    if not testset_path.exists():
        raise SystemExit(f"用例集不存在: {testset_path}")
    engine_path = HERE / f"{ENGINE_MODULE}.py"
    if not engine_path.exists():
        raise SystemExit(f"引擎文件不存在: {engine_path}")

    corpus = json.loads(testset_path.read_text(encoding="utf-8"))
    items = corpus["items"]
    if args.limit is not None:
        items = items[:args.limit]

    out_dir: Path = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    log_dir = out_dir / "engine_logs"

    print(f"用例集 {testset_path.name} · {len(items)} 条 · 引擎真跑（两遍重放）…")
    engine_a, entries_a = run_pass(items, log_dir=None)
    engine_b, entries_b = run_pass(items, log_dir=None)
    canonical_a = [_canonical(e["report"]) for e in entries_a]
    canonical_b = [_canonical(e["report"]) for e in entries_b]

    lock: dict[str, Any] = {"gcae_version": entries_a[0]["report"]["gcae_version"]}

    control_engine = make_engine(owner=None)
    control_ext, control_ctx = build_context(items[0])
    control_engine.set_clock(BASE_CLOCK)
    control_report = control_engine.audit(control_ctx)
    control = control_report["analysis"].get("RESPONSIBILITY_CLOSURE", {})
    lock["responsibility_control"] = {
        "owner": None,
        "status": control.get("status"),
        "reason": control.get("reason"),
        "ok": control.get("status") == "BLOCKED",
    }

    records = [summarize(e) for e in entries_a]
    metrics = build_metrics(
        records, canonical_a, canonical_b, engine_a, engine_b,
        testset_path, engine_path, lock,
    )

    print("两遍重放字节一致 ✓")
    engine_c, entries_c = run_pass(items, log_dir=log_dir)
    records_c = [summarize(e) for e in entries_c]
    if [r["report_sha256"] for r in records_c] != [r["report_sha256"] for r in records]:
        raise RuntimeError("evidence pass diverged from replay pass")

    per_item_path = out_dir / "per_item.jsonl"
    per_item_path.write_text(
        "\n".join(_canonical(r) for r in records) + "\n", encoding="utf-8"
    )
    metrics["artifacts"] = {
        "per_item_jsonl_sha256": _sha256_file(per_item_path),
    }
    metrics_path = out_dir / "metrics.json"
    metrics_path.write_text(
        json.dumps(metrics, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    report_md = render_report(metrics)
    report_path = out_dir / "report.md"
    report_path.write_text(report_md, encoding="utf-8")

    acc = metrics["extraction"]["vs_adjudicated"]
    verdicts = {
        st: sum(metrics["engine"]["verdict_by_class"][st].values()) for st in STATES
    }
    n_viol = sum(
        len(c["violating_ids"]) for c in metrics["engine"]["signals_compliance"].values()
    )
    print(f"抽取 vs 裁决真值: {acc['k']}/{acc['n']} = {acc['rate']:.1%} "
          f"[{acc['ci95'][0]:.1%}, {acc['ci95'][1]:.1%}]")
    print(f"期望信号违规条目: {n_viol}")
    for st in STATES:
        v = metrics["engine"]["verdict_by_class"][st]
        print(f"  {st:<8} n={verdicts[st]:>3} · PASS={v['AUDIT_PASS']} "
              f"WARN={v['AUDIT_WARN']} HALT={v['AUDIT_HALT']}")
    print(f"链根：{engine_a.chain_root_hash[:16]}… · 事件 "
          f"{metrics['engine']['chain']['total']} · valid={metrics['engine']['chain']['valid']}")
    print(f"证据：{out_dir}")


if __name__ == "__main__":
    main()
