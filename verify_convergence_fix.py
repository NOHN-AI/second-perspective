#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
收敛逻辑回归验证 — extract_risk_set 插件口径归一化（最小修复）
================================================================================

修复前的实测缺陷（case_strategy_audit.py 探针复现）：
    ConvergenceChecker.extract_risk_set 只读插件结果的 'status' 字段，
    而五算子插件输出的是 'pass' / 'halt_count'（无 status）。
    后果：责任已闭环时，插件级 HALT 对收敛判定不可见 ——
    STATE verdict = AUDIT_HALT 而 reconstruct 判定 = NO_GAIN / is_true_convergence=True。

修复口径（Second Perspective Engine.py · extract_risk_set）：
    status 缺失时归一化：
        halt_count > 0  → BLOCKED    （结构性阻断；CCS 属 T1，允许阻断）
        pass is False   → HIGH_RISK  （信号级风险；T2 算子不得阻断）

本脚本 6 个场景覆盖收敛五状态 + awaiting_human：
    S1 插件级 HALT 可见性（修复回归点）      → BLOCKED            （修复前：NO_GAIN/True）
    S2 干净输入                              → NO_GAIN（真收敛）
    S3 战略报告案例：静态审计复现 + 链根比对 → BLOCKED + 链根不变
    S4 有风险且无批准 delta                  → DIVERGED + awaiting_human
    S5 风险逐轮变化跑满预算                  → BUDGET_EXHAUSTED（非收敛）
    S6 风险不变且已人工推进                  → FIXED_POINT（真收敛）

用法: python verify_convergence_fix.py
退出码: 0 = 全部符合预期；1 = 存在偏差。
"""

import importlib.util
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(HERE, "Second Perspective Engine.py")

FIXED_CLOCK = 1791504000.0  # 2026-10-09T00:00:00Z
BASE_NONCE = "vcf00001"
OWNER = "回归机器人/工号001"

RESULTS = []


def record(cid, name, ok, detail):
    RESULTS.append(ok)
    print(f"  {'[PASS]' if ok else '[FAIL]'}  {cid}  {name}")
    for line in detail.splitlines():
        print(f"          {line}")


def load_engine():
    spec = importlib.util.spec_from_file_location("ca", ENGINE)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["ca"] = mod
    spec.loader.exec_module(mod)
    return mod


ca = load_engine()


def build(nonce=BASE_NONCE, owner=OWNER, org="回归验证", role="third_party_auditor",
          stage="review", config=None):
    acct = ca.ResponsibilityAccount(organization=org, role=role, stage=stage,
                                    owner=owner, nonce=nonce)
    eng = ca.CognitiveAuditEngine(acct, config or {"allowed_stages": ["review", "pre_decision"]})
    eng.set_clock(FIXED_CLOCK)
    eng.load_core_plugins()
    return eng


# ── 修复回归点样本：P/A/Q 在位、无分支、无显式缺陷文本 ──
#    加上原点/目标，使唯一的 HALT 来自 CCS（假设无回退路径），保持探针的隔离性。
S1_CTX = {
    "origin": "探针原点",
    "goal": "探针目标稳态",
    "decision": "探针决策P",
    "assumptions": ["探针前提A1"],
    "outcome": "探针结果Q",
    "evidence": ["probe#1"],
}

# ── 干净样本：全字段齐备，算子全部通过 ──
#    SPE 1.0 起新增 ⊙ORI / ⊞TPG / ⇄GRF 三项，缺 origin 会被 ORI 判 ORIGIN_VACUUM 阻断、
#    缺灰度梯度会被 GRF 判 NO_GRAY_LADDER 信号 —— 那两项都是**预期行为**，不是本脚本要测的东西。
#    故此处补齐 origin / goal / gray_levels / commit_ratio，让「干净」二字在九算子口径下依然成立。
CLEAN_CTX = {
    "origin": "服务B上线原点",
    "goal": "服务B在生产环境稳定运行",
    "gray_levels": [0.01, 0.1, 1.0],
    "commit_ratio": 0.1,
    "decision": "部署服务B到生产环境",
    "assumptions": ["服务B通过了全部集成测试"],
    "outcome": "服务B在生产环境稳定运行",
    "branches": [{"assumption": "服务B通过了全部集成测试", "delta_d": "回滚到上一版本"}],
    "text": "部署服务B到生产环境。",
    "evidence": ["doc#456"],
}

# ── 战略报告案例（与 case_strategy_audit.py 完全一致的常量和配置） ──
STRATEGY_TEXT = (
    "公司决定三年内进入东南亚市场，目标海外营收占比达到 20%。"
    "为此将组建海外事业部，并加大产品本地化投入。"
    "该战略将显著提升公司长期竞争力。"
)
STRATEGY_CONFIG = {
    "allowed_stages": ["pre_decision", "in_decision", "post_decision", "review"],
    "disclaimer": "本审计报告由 SPL Cognitive Audit Engine 生成，仅做结构性审计，不替代人类判断。",
    "custom_fields": {"case": "三年战略规划—东南亚市场进入", "source": "管理层报告"},
}
STRATEGY_CTX = {
    "narrative": STRATEGY_TEXT,
    "text": STRATEGY_TEXT,
    "decision": "三年内进入东南亚市场：组建海外事业部，加大产品本地化投入",
    "outcome": "海外营收占比达到 20%，公司长期竞争力显著提升",
    "conclusions": "该战略将显著提升公司长期竞争力",
}
# 金标链根。它固定的是「同一输入 + 同一 nonce + 同一 clock 下链根可复现」，
# 不是某一版报告的形状 —— 所以报告结构每次升级，这个值都必须重算，而不是被解释掉。
#
# 重算历史（每次都伴随一次结构升级，代价必须付清）：
#   ① v2.0 → SPE 1.0        报告结构整体改变
#   ② SPE 1.0 → 十算子 + 元因果账本 + 版本谱系
#      报告新增 lineage / meta_ledger / topology.time_order，
#      算子清单由 9 项变 10 项（META）；
#      拓扑指纹亦因 edges 元组新增声明时序 t 而改变。
#      本次同步把 S3 的期望值重算为上面的常量。
STRATEGY_ROOT_EXPECTED = "3862cc1f8131a3df5c3a23cc6aedf561a067b039da74ddabe910ffd7e071bdf5"


def main():
    print("=" * 68)
    print("收敛逻辑回归验证 — extract_risk_set 插件口径归一化（最小修复）")
    print("=" * 68)

    # ---------- S1 插件级 HALT 可见性 ----------
    eng = build()
    r = eng.reconstruct(dict(S1_CTX), max_rounds=3)
    verdict = r["final_report"]["analysis"]["STATE"]["verdict"]
    ok = r["final_state"] == "BLOCKED" and not r["is_true_convergence"]
    record("S1", "插件级 HALT 可见性（修复回归点）", ok,
           f"STATE verdict = {verdict['level']} (halts={verdict['halt_items']})\n"
           f"reconstruct   = {r['final_state']} / is_true_convergence={r['is_true_convergence']}\n"
           f"（修复前实测为 NO_GAIN / True，与 AUDIT_HALT 自相矛盾；修复后阻断可见）")

    # ---------- S2 干净输入 → NO_GAIN ----------
    eng = build()
    r = eng.reconstruct(dict(CLEAN_CTX), max_rounds=3)
    verdict = r["final_report"]["analysis"]["STATE"]["verdict"]
    ok = r["final_state"] == "NO_GAIN" and r["is_true_convergence"]
    record("S2", "干净输入 → NO_GAIN（真收敛）", ok,
           f"STATE verdict = {verdict['level']} / rounds={r['total_rounds']}\n"
           f"reconstruct   = {r['final_state']} / is_true_convergence={r['is_true_convergence']}")

    # ---------- S3 战略报告案例复现（链根不变 = 修复对报告零影响） ----------
    acct = ca.ResponsibilityAccount(organization="公司", role="管理层", stage="pre_decision",
                                    owner=None, nonce="5ea2026a")
    eng = ca.CognitiveAuditEngine(acct, STRATEGY_CONFIG)
    eng.set_clock(FIXED_CLOCK)
    eng.load_core_plugins()
    report = eng.audit(dict(STRATEGY_CTX))
    root = eng.chain_root_hash
    verdict = report["analysis"]["STATE"]["verdict"]
    r = eng.reconstruct(dict(STRATEGY_CTX), max_rounds=5)
    ok = (root == STRATEGY_ROOT_EXPECTED and verdict["level"] == "AUDIT_HALT"
          and r["final_state"] == "BLOCKED" and not r["is_true_convergence"])
    record("S3", "战略报告案例：静态审计复现 + 收敛阻断", ok,
           f"chain_root    = {root}\n"
           f"expected      = {STRATEGY_ROOT_EXPECTED}\n"
           f"STATE verdict = {verdict['level']} / reconstruct = {r['final_state']}")

    # ---------- S4 有风险且无批准 delta → DIVERGED + awaiting_human ----------
    ctx = dict(CLEAN_CTX, text="显然，服务B应上线。")
    eng = build()
    r = eng.reconstruct(ctx, max_rounds=5)
    ok = (r["final_state"] == "DIVERGED" and not r["is_true_convergence"]
          and r["awaiting_human"])
    record("S4", "有风险且无批准 delta → DIVERGED + awaiting_human", ok,
           f"round0 risks={r['rounds'][0]['risk_count']} / "
           f"rounds={r['total_rounds']} / awaiting_human={r['awaiting_human']}\n"
           f"reconstruct = {r['final_state']} / is_true_convergence={r['is_true_convergence']}")

    # ---------- S5 风险逐轮变化跑满预算 → BUDGET_EXHAUSTED ----------
    eng = build()
    r = eng.reconstruct(
        dict(CLEAN_CTX, text="显然版本0"),
        human_approved_deltas=[{"text": "显然版本A"}, {"text": "显然版本B"}, {"text": "显然版本C"}],
        max_rounds=2,
    )
    ok = r["final_state"] == "BUDGET_EXHAUSTED" and not r["is_true_convergence"]
    record("S5", "风险逐轮变化跑满预算 → BUDGET_EXHAUSTED（非收敛）", ok,
           f"rounds={r['total_rounds']}（max_rounds=2）\n"
           f"reconstruct = {r['final_state']} / is_true_convergence={r['is_true_convergence']}")

    # ---------- S6 风险不变且已人工推进 → FIXED_POINT ----------
    eng = build()
    r = eng.reconstruct(
        dict(CLEAN_CTX, text="显然版本0"),
        human_approved_deltas=[{"audit_note": "r1"}, {"audit_note": "r2"}],  # 算子不可观测的 delta
        max_rounds=5,
    )
    ok = r["final_state"] == "FIXED_POINT" and r["is_true_convergence"]
    record("S6", "风险集合两轮不变 → FIXED_POINT（真收敛）", ok,
           f"rounds={r['total_rounds']} / "
           f"r0={r['rounds'][0]['status']} r1={r['rounds'][1]['status']}\n"
           f"reconstruct = {r['final_state']} / is_true_convergence={r['is_true_convergence']}")

    passed = sum(RESULTS)
    print("=" * 68)
    print(f"合计: {passed}/{len(RESULTS)} 场景符合预期")
    print("=" * 68)
    sys.exit(0 if passed == len(RESULTS) else 1)


if __name__ == "__main__":
    main()
