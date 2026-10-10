#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPE 1.2 demo case — AI governance: LLM customer-service assistant go-live (EU)
================================================================================
同一项 AI 上线决策，两份材料，一次对照审计：

  CASE A · "看起来可以签字" 的就绪声明 —— 修辞粉饰、证据空洞、
            已证伪前提仍在用、无回退路径、无灰度阶梯
  CASE B · 结构完备的灰度上线方案 —— 假设可证伪、分支可回退（含反事实场景）、
            事实已核验、责任已锚定

演示要回答的只有三个问题：哪里被拦住 · 为什么被拦住 · 链根怎么复算。

确定性：固定 nonce / clock，跨机重跑链根一致（照 verify.py 约定）。
用法: python demo_ai_governance.py
"""

import importlib.util
import os
import sys

# Windows 控制台常为 GBK：缺字形的打印降级为替代字符，而不是中断演示。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    except Exception:
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(HERE, "Second Perspective Engine.py")

# 复现实验用固定值：clock 决定链事件时间戳，nonce 决定审计身份（照 verify.py 约定）
FIXED_CLOCK = 1792022400.0        # 2026-10-15T00:00:00Z
NONCE_CASE_A = "a1f00001"
NONCE_CASE_B = "a1f00002"

ACCOUNT_OWNER = "AI Governance Office / case AI-2026-041"

# ── 被审材料原文（演示用）────────────────────────────────────────────────

A1 = "The assistant resolves at least 80% of first-line tickets without handoff"
A2 = "Personal data is never retained beyond the session"
A3 = "All inference runs on EU-hosted endpoints"

MEMO_CASE_A = (
    "Clearly, the assistant is ready for the EU production launch. "
    "Our pilot results were amazing, and everyone knows the market expects this move. "
    "Undoubtedly the vendor roadmap aligns with our strategy. "
    "Obviously the quality bar is met — deploy now and our leadership position takes care of itself."
)

MEMO_CASE_B = (
    "Proposal: deploy the LLM customer-service assistant for the EU region in a staged rollout, "
    "with verified controls, declared evidence and named rollback paths for every assumption."
)

ORIGIN = "2026-Q3 AI governance board — assistant go-live review"
GOAL = "Serve EU customers with stable CSAT and zero personal-data retention incidents"
DECISION = "Deploy the LLM customer-service assistant to production for the EU region"


def case_a_context():
    """CASE A：修辞 + 空洞 + 问题结构（审计应停住它）。"""
    return {
        "origin": ORIGIN,
        "goal": GOAL,
        "resources": {"compute": {"budget": 100, "committed": 120}},
        "narrative": MEMO_CASE_A,
        "text": MEMO_CASE_A,
        "decision": DECISION,
        "assumptions": [A1, A2, A3],
        "outcome": "EU customers served by the assistant without compliance incidents",
        "branches": [
            {"assumption": A1, "delta_d": "Keep the assistant in shadow mode; route all EU traffic to human agents"},
        ],
        "facts": [
            {"id": "F1", "claim": A1, "evidence": ["pilot-readout-2026-08"]},
            {"id": "F2", "claim": A2, "evidence": []},
            {"id": "F3", "claim": A3, "evidence": ["architecture-review-2026-07"]},
        ],
        "observations": {"F1": True, "F3": False},
        "gray_levels": [],
        "commit_ratio": 1.0,
        "feedback": {A1: "confirmed", A2: "unobserved", A3: "falsified"},
        "conclusions": "Proceed with full production deployment for EU customers.",
        "evidence": [],
    }


def case_b_context():
    """CASE B：同一决策的结构完备版本（审计应放行）。"""
    return {
        "origin": ORIGIN,
        "goal": GOAL,
        "resources": {"compute": {"budget": 100, "committed": 40}},
        "narrative": MEMO_CASE_B,
        "text": MEMO_CASE_B,
        "decision": DECISION,
        "assumptions": [A1, A2, A3],
        "outcome": "EU customers served by the assistant under declared gates and evidence",
        "branches": [
            {"assumption": A1, "delta_d": "Shadow mode + human routing until resolution rate recovers"},
            {"assumption": A2, "delta_d": "Purge session data and escalate to the Data Protection Officer"},
            {"assumption": A3, "delta_d": "Fail over to the EU-only replica and pause non-EU routes"},
            {
                "assumption": "If the CSAT gate is not met in the staged rollout, the EU launch is postponed",
                "delta_d": "Hold the rollout at the current stage and re-run the gate review",
            },
        ],
        "facts": [
            {"id": "F1", "claim": A1, "evidence": ["pilot-readout-2026-08", "QA-report-2026-09"]},
            {"id": "F2", "claim": A2, "evidence": ["DPA-2026-09", "privacy-test-log-2026-09"]},
            {"id": "F3", "claim": A3, "evidence": ["architecture-review-2026-07", "endpoint-audit-2026-09"]},
        ],
        "observations": {"F1": True, "F2": True, "F3": True},
        "gray_levels": [0.01, 0.05, 0.25, 1.0],
        "commit_ratio": 0.05,
        "feedback": {A1: "confirmed", A2: "confirmed", A3: "confirmed"},
        "conclusions": "Proceed with the staged rollout under the declared gates and evidence.",
        "evidence": ["pilot-readout-2026-08", "DPA-2026-09"],
    }


# ── 引擎装载与审计（照 verify.py 约定）──────────────────────────────────

def load_engine():
    spec = importlib.util.spec_from_file_location("spe", ENGINE)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["spe"] = mod          # dataclasses 反查 cls.__module__ 时需要
    spec.loader.exec_module(mod)
    return mod


spe = load_engine()


def run_audit(ctx, nonce):
    acct = spe.ResponsibilityAccount(
        organization="NOHN AI — AI governance case",
        role="third_party_auditor",
        stage="review",
        owner=ACCOUNT_OWNER,
    )
    acct.nonce = nonce                 # 覆盖确定性推导，保证跨运行一致
    eng = spe.SecondPerspectiveEngine(acct)
    eng.set_clock(FIXED_CLOCK)         # 覆盖系统墙钟
    eng.load_core_plugins()
    report = eng.audit(dict(ctx), save_log=True, log_dir=os.path.join(HERE, "logs"))
    return report


# ── 输出 ─────────────────────────────────────────────────────────────────

def banner(title):
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def brief(v, n=90):
    return str(v)[:n]


def show_verdict(report):
    acc = report.get("analysis", {}).get("ACC", {})
    verdict = acc.get("verdict", {})
    cert = acc.get("certificate", {})
    print(f"  VERDICT : {verdict.get('level')} — {verdict.get('summary', '')}")
    print(f"  HALT {verdict.get('halt_count', 0)} · WARN {verdict.get('warn_count', 0)}")
    print(f"  CERT    : {cert.get('audit_id', 'N/A')} · signature {brief(cert.get('signature', ''), 24)}…")
    print(f"  CHAIN   : {report.get('chain_root_hash', '')}")
    return verdict.get("level")


def show_highlights(report):
    analysis = report.get("analysis", {})

    ns = analysis.get("NS", {})
    print(f"  [NS ] narrative stripped: pass={ns.get('pass')} violations={ns.get('violation_count', 0)}")
    core = ns.get("logical_core", "")
    if core:
        print(f"        logical core → {brief(core, 110)}")

    iap = analysis.get("IAP", {})
    flags = iap.get("flags", [])
    print(f"  [IAP] implicit assumptions: pass={iap.get('pass')} flags={iap.get('flag_count', 0)}")
    for f in flags[:6]:
        print(f"        [{f.get('severity')}] {f.get('flag_type')}: {brief(f.get('match', ''), 60)}")

    lch = analysis.get("LCH", {})
    weak = lch.get("weakest_variable") or {}
    print(f"  [LCH] system ΔD = {lch.get('system_delta_d')} · weakest = {brief(weak.get('assumption', 'n/a'), 55)} (ΔD={weak.get('delta_d')})")

    bfc = report.get("fact_check", {})
    print(f"  [BFC] status={bfc.get('status')} · true={bfc.get('true_count', 0)} false={bfc.get('false_count', 0)} undeclared={bfc.get('undeclared_count', 0)}")
    for v in bfc.get("verdicts", [])[:6]:
        binary = v.get("binary")
        val = "true" if binary is True else ("false" if binary is False else "undeclared")
        ev = v.get("evidence", [])
        ev_txt = f"{len(ev)} evidence item(s)" if ev else "no evidence"
        print(f"        {v.get('id')} → {val} · {ev_txt} · {brief(v.get('claim', ''), 60)}")
    for line in bfc.get("remediation", [])[:4]:
        print(f"        → {brief(line, 110)}")

    ccs = analysis.get("CCS", {})
    print(f"  [CCS] causal chain: pass={ccs.get('pass')}")
    for c in ccs.get("checks", []):
        print(f"        [{c.get('severity')}] {c.get('check')}: {brief(c.get('description', ''), 90)}")

    grf = analysis.get("GRF", {})
    print(f"  [GRF] falsified-without-branch: {grf.get('falsified_without_branch', [])}")
    print(f"        unobserved: {grf.get('unobserved', [])}")

    meta = report.get("meta_ledger", {})
    print(f"  [META] status={meta.get('status')} · high-risk bases={meta.get('high_risk_bases', [])}")

    acc = analysis.get("ACC", {})
    resp = acc.get("responsibility", {})
    owner = report.get("responsibility_account", {}).get("owner")
    print(f"  [ACC] anchor={resp.get('anchor_status')} · owner={owner}")


def show_plain(report):
    plain = spe.PlainLanguageRenderer()
    print("\n  — plain-language reading (this is what a board member sees) —")
    for line in plain.humanize_text(report, lang="en").splitlines():
        print(f"  | {line}")


def main():
    print("SPE 1.2 — AI governance demo case: one go-live decision, two structures")
    print(f"fixed clock={FIXED_CLOCK} · nonce A={NONCE_CASE_A} · nonce B={NONCE_CASE_B}")

    banner("CASE A · \"Ready for sign-off\" memo — what the audit stops")
    print("  Material (as submitted):")
    print(f'    "{MEMO_CASE_A}"')
    report_a = run_audit(case_a_context(), NONCE_CASE_A)
    level_a = show_verdict(report_a)
    show_highlights(report_a)
    show_plain(report_a)

    banner("CASE B · Same decision, complete structure — what the audit lets through")
    print("  Material (as submitted):")
    print(f'    "{MEMO_CASE_B}"')
    report_b = run_audit(case_b_context(), NONCE_CASE_B)
    level_b = show_verdict(report_b)
    show_highlights(report_b)
    show_plain(report_b)

    banner("REPRODUCIBILITY — recompute these roots on any machine")
    print(f"  Case A chain root: {report_a.get('chain_root_hash', '')}")
    print(f"  Case B chain root: {report_b.get('chain_root_hash', '')}")
    print("  Same input + same nonce + same clock → same root, offline, no LLM in the loop.")
    print("  Independent check:  python verify.py --root")

    ok = level_a == "AUDIT_HALT" and level_b in ("AUDIT_PASS", "AUDIT_WARN")
    print("\n" + ("[OK] self-check: flawed structure HALTed, governed structure passed."
                  if ok else "[!!] self-check: unexpected verdict combination — inspect output."))


if __name__ == "__main__":
    main()
