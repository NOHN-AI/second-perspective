#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
案例审计：三年战略规划（管理层报告）— 东南亚市场进入
====================================================

被审材料（原文，未增删）：

    公司决定三年内进入东南亚市场，目标海外营收占比达到 20%。
    为此将组建海外事业部，并加大产品本地化投入。
    该战略将显著提升公司长期竞争力。

原则（对应引擎护栏 I-1 非猜测）：
    报告中未出现的前提(A) / 分支(ΔD) / 证据 / 责任人一律不补。
    因此 decision_context 只映射原文可核实的 P / Q / 结论 三类字段。

可复现：固定 nonce 与 clock（沿用 verify.py 约定）。
用法: python case_strategy_audit.py
"""

import importlib.util
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(HERE, "Second Perspective Engine.py")

FIXED_NONCE = "5ea2026a"
FIXED_CLOCK = 1791504000.0  # 2026-10-09T00:00:00Z

REPORT_TEXT = (
    "公司决定三年内进入东南亚市场，目标海外营收占比达到 20%。"
    "为此将组建海外事业部，并加大产品本地化投入。"
    "该战略将显著提升公司长期竞争力。"
)

CONFIG = {
    "allowed_stages": ["pre_decision", "in_decision", "post_decision", "review"],
    "disclaimer": "本审计报告由 SPL Cognitive Audit Engine 生成，仅做结构性审计，不替代人类判断。",
    "custom_fields": {"case": "三年战略规划—东南亚市场进入", "source": "管理层报告"},
}

DECISION_CONTEXT = {
    "narrative": REPORT_TEXT,
    "text": REPORT_TEXT,
    "decision": "三年内进入东南亚市场：组建海外事业部，加大产品本地化投入",
    "outcome": "海外营收占比达到 20%，公司长期竞争力显著提升",
    "conclusions": "该战略将显著提升公司长期竞争力",
    # assumptions / branches / evidence 原报告均未披露 → 按 I-1 不补
}


def load_engine():
    # 必须先写入 sys.modules，否则 dataclasses 反查 cls.__module__ 拿到 None（同 verify.py）
    spec = importlib.util.spec_from_file_location("ca", ENGINE)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["ca"] = mod
    spec.loader.exec_module(mod)
    return mod


ca = load_engine()


def build(owner=None, nonce=FIXED_NONCE):
    acct = ca.ResponsibilityAccount(
        organization="公司",  # 原文唯一给出的责任主体表述
        role="管理层",
        stage="pre_decision",
        owner=owner,
        nonce=nonce,
    )
    eng = ca.CognitiveAuditEngine(acct, CONFIG)
    eng.set_clock(FIXED_CLOCK)
    eng.load_core_plugins()
    return eng


def main():
    print("=" * 68)
    print("案例审计：三年战略规划（管理层报告）")
    print("=" * 68)

    # ---------- A. 静态结构审计（落盘） ----------
    eng = build()
    report = eng.audit(DECISION_CONTEXT, save_log=True, log_dir=os.path.join(HERE, "logs"))
    analysis = report["analysis"]
    ns = analysis.get("NS", {})
    iap = analysis.get("IAP", {})
    lch = analysis.get("LCH", {})
    ccs = analysis.get("CCS", {})
    st = analysis.get("ACC", {})

    print("\n--- 最终裁定（ACC）---")
    v = st.get("verdict", {})
    print(f"Level  : {v.get('level')}")
    print(f"Summary: {v.get('summary')}")
    for h in v.get("halt_items", []):
        print(f"  [HALT] {h}")
    for w in v.get("warn_items", []):
        print(f"  [WARN] {w}")

    print("\n--- 责任锚定（ACC）---")
    resp = st.get("responsibility", {})
    print(f"anchor_status: {resp.get('anchor_status')}")
    if resp.get("warning"):
        print(f"warning: {resp['warning']}")
    rc = analysis.get("RESPONSIBILITY_CLOSURE")
    print(f"engine-level RESPONSIBILITY_CLOSURE: {rc.get('status') if rc else 'closed'}")

    print("\n--- NS 叙事剥离 ---")
    print(f"pass={ns.get('pass')}  violations={ns.get('violation_count')}")
    for vi in ns.get("violations", []):
        print(f"  [{vi['severity']}] {vi['rule_id']}: {vi['description']}")
    print(f"logical_core: {ns.get('logical_core')}")

    print("\n--- IAP 内隐假设 ---")
    for f in iap.get("flags", []):
        print(f"  [{f['severity']}] {f['flag_type']}: {f['description']}")

    print("\n--- LCH 脆弱性 ---")
    print(f"pass={lch.get('pass')}  system_delta_d={lch.get('system_delta_d')}  "
          f"note={lch.get('note', '')}")

    print("\n--- CCS 因果链 ---")
    for c in ccs.get("checks", []):
        print(f"  [{c['severity']}] {c['check']}: {c['result']} — {c['description']}")

    print("\n--- 引擎级静态算子 ---")
    print(f"narrative_meta: {report['narrative_meta']}")
    print(f"implicit      : {report['implicit_assumptions']}")
    print(f"vulnerability : {report['vulnerability']}")

    print("\n--- 审计凭据 ---")
    cert = st.get("certificate", {})
    print(f"audit_id   : {cert.get('audit_id')}")
    print(f"signature  : {cert.get('signature')}")
    v1 = eng.verify_chain()
    print(f"chain_root : {report.get('chain_root_hash')}")
    print(f"verify     : valid={v1['valid']} events={v1['total']}")
    print(f"log        : {report.get('log_path')}")

    # ---------- B. 因果重构（无人工批准 delta） ----------
    print("\n" + "=" * 68)
    print("因果重构：无人工批准 delta → 停在 human gate，不自动修正")
    print("=" * 68)
    eng2 = build()
    r = eng2.reconstruct(dict(DECISION_CONTEXT), max_rounds=5)
    print(f"final_state        = {r['final_state']}")
    print(f"is_true_convergence= {r['is_true_convergence']}")
    print(f"total_rounds       = {r['total_rounds']}")
    print(f"awaiting_human     = {r['awaiting_human']}")
    print(f"session_root_hash  = {r['session_root_hash']}")

    # ---------- C. 引擎一致性探针（合成样本，非本次审计结论） ----------
    print("\n" + "=" * 68)
    print("引擎一致性探针（合成样本，非本次审计结论）")
    print("=" * 68)
    eng3 = build(owner="probe-bot/0", nonce="probe001")
    probe_ctx = {
        "decision": "探针决策P",
        "assumptions": ["探针前提A1"],
        "outcome": "探针结果Q",
        "evidence": ["probe#1"],
    }
    r3 = eng3.reconstruct(probe_ctx, max_rounds=3)
    st3 = r3["final_report"]["analysis"]["ACC"]["verdict"]
    print(f"ACC verdict    = {st3['level']}  halts={st3['halt_items']}")
    print(f"reconstruct 判定 = {r3['final_state']}  is_true_convergence={r3['is_true_convergence']}")


if __name__ == "__main__":
    main()
