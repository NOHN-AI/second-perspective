#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
案例审计：投资决策备忘录（建议收购标的公司 A）
================================================

被审材料（原文，未增删）：

    投资决策备忘录：建议收购标的公司 A。理由：①A 公司近三年营收年均增长 20%，
    成长性良好；②本次收购对价对应 PE 15 倍，显著低于行业均值 25 倍，存在估值折让；
    ③按当前盈利水平测算，预计三年可收回投资成本。综上，建议董事会批准本次收购。

映射原则（对应引擎护栏 I-1 非猜测）：
    1. P（决策）/ Q（结果）/ 结论：取自原文可核实的表述。
    2. A（前提）：原文以「理由①②③」形式给出了三条论证依据，如实映射为 A1–A3。
       —— 注意：这三条是「断言式依据」，本身未经证据支撑；不是可证伪的实验前提。
    3. branches（分支 ΔD）/ evidence（证据）/ criteria（评估标准）/ owner（责任人）：
       原文均未披露 —— 一律不补。缺失本身就是本次审计要指出的对象。
    4. 原文没有署名提议人 / 数据责任人 → 责任主体无法闭环（engine 级 BLOCKED）。

可复现：固定 nonce 与 clock（沿用 verify.py / case_strategy_audit.py 约定）。
用法: python case_memo_audit.py
"""

import importlib.util
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(HERE, "Second Perspective Engine.py")

FIXED_NONCE = "b8e42f17"
FIXED_CLOCK = 1791504000.0  # 2026-10-09T00:00:00Z

MEMO_TEXT = (
    "投资决策备忘录：建议收购标的公司 A。"
    "理由：①A 公司近三年营收年均增长 20%，成长性良好；"
    "②本次收购对价对应 PE 15 倍，显著低于行业均值 25 倍，存在估值折让；"
    "③按当前盈利水平测算，预计三年可收回投资成本。"
    "综上，建议董事会批准本次收购。"
)

CONFIG = {
    "allowed_stages": ["pre_decision", "in_decision", "post_decision", "review"],
    "disclaimer": "本审计报告由 SPL Cognitive Audit Engine 生成，仅做结构性审计，不替代人类判断。",
    "custom_fields": {"case": "投资决策备忘录—收购标的公司A", "source": "投资建议书"},
}

DECISION_CONTEXT = {
    "narrative": MEMO_TEXT,
    "text": MEMO_TEXT,
    "decision": "收购标的公司 A",
    "assumptions": [
        "A1：近三年营收年均增长 20% 的成长性在未来可持续",
        "A2：对价 PE 15 倍显著低于行业均值 25 倍，即标的被低估（存在估值折让）",
        "A3：按当前盈利水平测算，三年内可收回投资成本",
    ],
    "outcome": "收购完成，三年收回投资成本，公司价值提升",
    "conclusions": "建议董事会批准本次收购",
    # branches / evidence / criteria / owner 原备忘录均未披露 → 按 I-1 不补
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
        organization="董事会",      # 原文唯一给出的决策主体
        role="投资决策审批",
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
    print("案例审计：投资决策备忘录（建议收购标的公司 A）")
    print("=" * 68)

    # ---------- A. 静态结构审计（落盘） ----------
    eng = build()
    report = eng.audit(DECISION_CONTEXT, save_log=True, log_dir=os.path.join(HERE, "logs"))
    analysis = report["analysis"]
    ns = analysis.get("NS", {})
    iap = analysis.get("IAP", {})
    lch = analysis.get("LCH", {})
    ccs = analysis.get("CCS", {})
    st = analysis.get("STATE", {})

    print("\n--- 最终裁定（STATE）---")
    v = st.get("verdict", {})
    print(f"Level  : {v.get('level')}")
    print(f"Summary: {v.get('summary')}")
    for h in v.get("halt_items", []):
        print(f"  [HALT] {h}")
    for w in v.get("warn_items", []):
        print(f"  [WARN] {w}")

    print("\n--- 责任锚定（STATE）---")
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
          f"coverage={lch.get('has_branch_coverage')}  note={lch.get('note', '')}")
    for fr in lch.get("fragility_report", []):
        print(f"  A{fr['index']+1} delta_d={fr['delta_d']} branch={fr['has_branch_response']} "
              f"— {fr['assumption'][:40]}")

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

    # ---------- C. 机器可读摘要（供视频/海报引用，禁止手改） ----------
    print("\n" + "=" * 68)
    print("FACTS_JSON（供 C:/video/memo_vs_gcae 引用）")
    print("=" * 68)
    facts = {
        "audit_id": cert.get("audit_id"),
        "signature": cert.get("signature"),
        "chain_root_hash": report.get("chain_root_hash"),
        "verdict_level": v.get("level"),
        "verdict_summary": v.get("summary"),
        "halt_count": v.get("halt_count"),
        "warn_count": v.get("warn_count"),
        "halt_items": v.get("halt_items"),
        "warn_items": v.get("warn_items"),
        "anchor_status": resp.get("anchor_status"),
        "responsibility_closure": (rc.get("status") if rc else "closed"),
        "ns_violation_count": ns.get("violation_count"),
        "lch_system_delta_d": lch.get("system_delta_d"),
        "lch_pass": lch.get("pass"),
        "ccs_halt_count": ccs.get("halt_count"),
        "ccs_warn_count": ccs.get("warn_count"),
        "vulnerability": report.get("vulnerability"),
        "implicit_flags": [f.get("type") for f in report.get("implicit_assumptions", {}).get("flags", [])],
        "reconstruct_state": r["final_state"],
        "is_true_convergence": r["is_true_convergence"],
        "session_root_hash": r["session_root_hash"],
        "log_path": report.get("log_path"),
    }
    print(json.dumps(facts, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
