#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPE 独立验证脚本 / Second Perspective Engine Independent Verification Suite
================================================================
零依赖、纯标准库、离线运行。无需 pip install，无需配置环境变量。

    python verify.py            # 跑全部检查
    python verify.py --json     # 机器可读输出（可接 CI）
    python verify.py --root     # 只打印当前环境链根，供跨机比对

设计原则：脚本如实报告 PASS / FAIL / WARN，不为了好看而放宽断言。
FAIL 即为产品当前缺陷，请在对外承诺前修复。
退出码：0 = 无 FAIL；1 = 存在 FAIL。

检查项：V1–V9 覆盖引擎内核（迁移到 SPE 1.0 后按现状重新判定），
V10–V13 覆盖拓扑层四项能力，V14 覆盖二元事实校验，
V15 覆盖唯一插件缝（四道闸门 · 清单入哈希 · 越权降级），
V16 覆盖 ∞ 极限收敛器（层数无上限 · 判据停机 · 引擎不自驱），
V17 覆盖元因果账本（混沌·无极·虚幻 A6·天道 A10·轮回）与链内时序（公理 5），
以及自主进化层（只提案不适用 · 版本谱系 · 记账不改判定）。
"""

import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile

# Windows 控制台常为 GBK，无法编码 ⊞ / ⇄ / ↻ 等拓扑符号。
# 降级为替代字符，而不是让一次缺字形的打印中断整场验证。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(errors="replace")
    except Exception:
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(HERE, "Second Perspective Engine.py")

# 复现实验用固定值：clock 决定链事件时间戳，nonce 决定审计身份
FIXED_CLOCK = 1700000000.0
FIXED_NONCE = "deadbeef"

RESULTS = []


def record(cid, name, ok, detail, level=None):
    """level 省略时由 ok 推导；仅在需要标 WARN 时显式传入。"""
    level = level or ("PASS" if ok else "FAIL")
    RESULTS.append({"id": cid, "name": name, "level": level, "detail": detail})
    icon = {"PASS": "[PASS]", "FAIL": "[FAIL]", "WARN": "[WARN]"}[level]
    print(f"  {icon}  {cid}  {name}")
    for line in detail.splitlines():
        print(f"          {line}")


# ------------------------------------------------------------------ 引擎装载

def load_engine():
    """以绝对路径装载带空格文件名的引擎。

    注意：必须先写入 sys.modules，否则 dataclasses 反查 cls.__module__
    时拿到 None，抛 AttributeError。
    """
    spec = importlib.util.spec_from_file_location("spe", ENGINE)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["spe"] = mod
    spec.loader.exec_module(mod)
    return mod


spe = load_engine()


def build(ctx, nonce=FIXED_NONCE, clock=FIXED_CLOCK, owner="verify-bot/工号001"):
    acct = spe.ResponsibilityAccount(
        organization="SPE-Verify", role="third_party_auditor",
        stage="review", owner=owner,
    )
    acct.nonce = nonce            # 覆盖确定性推导，保证跨运行一致
    eng = spe.SecondPerspectiveEngine(acct)
    eng.set_clock(clock)          # 覆盖系统墙钟
    eng.load_core_plugins()
    return eng, acct


# 基线上下文：一个「结构健康」的输入——原点/目标/资源齐备，拓扑可闭合。
BASE_CTX = {
    "origin": "2026Q1 试点立项",
    "goal": "本季度把 ROI 稳定到 12%",
    "resources": {"compute": {"budget": 100.0, "committed": 40.0}},
    "narrative": "项目 X 应立即批准上线，因为需求已经充分验证。",
    "decision": "上线 S1",
    "assumptions": ["需求稳定", "成本可控"],
    "outcome": "ROI 达到 12%",
    "dependencies": {"需求稳定": ["成本可控"]},
    "branches": [
        {"assumption": "需求稳定", "delta_d": "降级为单点 PoC"},
        {"assumption": "成本可控", "delta_d": "资源投入上修"},
    ],
    "alternatives": {"S1": {"metrics": {"roi": 0.12}}, "S2": {"metrics": {"roi": 0.08}}},
    "criteria": {"roi": {"weight": 1.0}},
    "conclusions": "Recommend S1",
    "evidence": ["doc#123"],
    "gray_levels": [0.01, 0.05, 0.25, 1.0],
    "commit_ratio": 0.25,
    "feedback": {"需求稳定": "confirmed", "成本可控": "confirmed"},
}


def root_of(ctx, nonce=FIXED_NONCE):
    eng, _ = build(ctx, nonce=nonce)
    eng.audit(dict(ctx))
    return eng.chain_root_hash


# ------------------------------------------------------------------ 检查项

def check_v1_zero_dependency():
    """V1 核心可离线运行：仅标准库即可装载引擎与十算子。"""
    try:
        eng, _ = build(BASE_CTX)
        names = [p.name for p in eng.plugins]
        expect = {"GA", "NS", "IAP", "LCH", "LFT", "BFC", "CCS", "GRF",
                  "META", "ACC"}
        ok = set(names) == expect
        detail = ("引擎装载成功；十算子注册成功；全程未使用 requirements.txt\n"
                  f"registered = {names}")
        if not ok:
            detail += f"\n缺失/多余算子：{sorted(expect.symmetric_difference(names))}"
        record("V1", "零依赖离线装载 (stdlib only · 十算子)", ok, detail,
               "PASS" if ok else "FAIL")
    except Exception as e:
        record("V1", "零依赖离线装载 (stdlib only · 十算子)", False,
               f"装载失败: {type(e).__name__}: {e}")


def check_v2_reproducible():
    """V2 同输入 + 同 clock + 同 nonce => 链根逐次一致。"""
    try:
        roots = [root_of(BASE_CTX) for _ in range(3)]
        ok = len(set(roots)) == 1
        record("V2", "审计链根可复现 (3 次一致)", ok,
               f"root = {roots[0][:32]}\n三次运行结果: {'一致' if ok else '不一致 -> ' + str(roots)}")
    except Exception as e:
        record("V2", "审计链根可复现 (3 次一致)", False, f"异常: {e}")


def check_v3_sensitivity():
    """V3 输入改变 => 链根必须改变。防止哈希退化为常量。

    注意：链根哈希的是「审计报告」而非「原始输入」。只有被算子实际观测到的
    变化才会传导。以下选取三处必然传导的变异点。
    """
    try:
        base = root_of(BASE_CTX)
        rows = []

        c1 = dict(BASE_CTX)
        c1["narrative"] = "显然" + BASE_CTX["narrative"]        # 触发 ⊗NS 主观词标记
        rows.append(("narrative 加入主观修饰词", root_of(c1)))

        c2 = dict(BASE_CTX)
        c2["evidence"] = []                                      # 触发 ⊕IAP CONCLUSION_WITHOUT_EVIDENCE
        rows.append(("删除 evidence", root_of(c2)))

        c3 = dict(BASE_CTX)
        c3["branches"] = [dict(b) for b in BASE_CTX["branches"]]
        c3["branches"].append({"assumption": "需求稳定2", "delta_d": "新增分支"})
        rows.append(("新增一条分支边（改拓扑）", root_of(c3)))

        unchanged = [label for label, r in rows if r == base]
        ok = not unchanged
        detail = [f"base = {base[:32]}"]
        detail += [f"{label:<26} -> {r[:32]}" for label, r in rows]
        if not ok:
            detail.append("以下变异未改变链根: " + ", ".join(unchanged))
        record("V3", "输入敏感性 (改输入必改链根)", ok, "\n".join(detail))
    except Exception as e:
        record("V3", "输入敏感性 (改输入必改链根)", False, f"异常: {e}")


def check_v3b_input_coverage():
    """V3b 证书覆盖范围: 链根是否绑定「原始输入」而非仅「审计报告」。

    当前实现只哈希派生报告，未哈希 decision_context 原文。
    这既可解读为隐私设计（敏感决策数据不落库），也意味着
    「这份证书对应的是这一份输入」无法被独立验证。属需明示的范围限制。
    """
    try:
        ctx = dict(BASE_CTX)
        ctx["conclusions"] = "Recommend S2 (完全不同的一句话)"
        ctx["alternatives"] = {"S1": {"metrics": {"roi": 0.99}}}
        same = root_of(ctx) == root_of(BASE_CTX)
        detail = [
            "输入大幅改动（conclusions 与 alternatives 全部替换，但两者均不被任何算子观测）后：",
            f"  链根是否仍相同 = {same}",
            "",
            "解读 A（隐私设计）: 报告只存派生结论，敏感决策数据不落库 —— 合规友好。",
            "解读 B（验证缺口）: 证书无法独立证明「审计的正是这一份输入」。",
            "",
            "修法（若需可验证）: 在 audit() 中把 decision_context 的规范化摘要",
            "并入报告并参与 report_hash，使证书同时覆盖输入与输出。",
            "对外表述建议: 主动声明证书覆盖范围，不要让对方默认它覆盖输入。",
        ]
        record("V3b", "证书是否绑定原始输入", False, "\n".join(detail), "WARN")
    except Exception as e:
        record("V3b", "证书是否绑定原始输入", False, f"异常: {e}", "WARN")


def check_v4_chain_valid():
    """V4 未篡改时链路完整。"""
    try:
        eng, _ = build(BASE_CTX)
        eng.audit(dict(BASE_CTX))
        v = eng.verify_chain()
        record("V4", "未篡改链路校验通过", v["valid"],
               f"valid={v['valid']} events={v['total']} root={v['root_hash'][:32]}")
    except Exception as e:
        record("V4", "未篡改链路校验通过", False, f"异常: {e}")


def check_v5_tamper_evidence():
    """V5 篡改证据链：改 payload / event_type / prev_hash 均必须被检出。

    这是审计产品的核心承诺。若任一逃逸，证书不具防篡改意义。
    """
    rows = []
    for label, mutate in [
        ("payload", lambda e: e.event_chain[0].payload.__setitem__("report_hash", "TAMPERED")),
        ("event_type", lambda e: setattr(e.event_chain[0], "event_type", "TAMPERED")),
        ("prev_hash", lambda e: setattr(e.event_chain[0], "prev_hash", "BROKEN")),
    ]:
        eng, _ = build(BASE_CTX)
        eng.audit(dict(BASE_CTX))
        mutate(eng)
        rows.append((label, eng.verify_chain()["valid"]))

    detail_lines = [
        f"篡改 {label:<11} -> valid={val}   {'(已检出)' if val is False else '(逃逸! 未检出)'}"
        for label, val in rows
    ]
    ok = all(val is False for _, val in rows)
    if ok:
        record("V5", "篡改可检出 (payload/type/prev_hash)", True, "\n".join(detail_lines), "PASS")
    else:
        detail_lines.append("")
        detail_lines.append("根因: verify_chain() 中比对的是实时重算值而非封存值，")
        detail_lines.append("      改动 payload 后重算值同步改变，actual 恒等于 expected。")
        record("V5", "篡改可检出 (payload/type/prev_hash)", False, "\n".join(detail_lines))


def check_v6_blocking():
    """V6 阻断能力:责任未闭环必须 BLOCKED；闭环后不再阻断。"""
    try:
        acct_open = spe.ResponsibilityAccount(
            organization="SPE-Verify", role="third_party_auditor", stage="review")
        eng = spe.SecondPerspectiveEngine(acct_open)
        eng.set_clock(FIXED_CLOCK)
        eng.load_core_plugins()
        rep = eng.audit(dict(BASE_CTX))
        blocked = rep["analysis"].get("RESPONSIBILITY_CLOSURE", {}).get("status")

        eng2, acct2 = build(BASE_CTX)
        rep2 = eng2.audit(dict(BASE_CTX))
        after = rep2["analysis"].get("RESPONSIBILITY_CLOSURE")

        ok = blocked == "BLOCKED" and after is None
        record("V6", "阻断能力 (缺责任人即 BLOCKED)", ok,
               f"owner=None  -> {blocked}\nowner 已设 -> {'不再阻断' if after is None else after}")
    except Exception as e:
        record("V6", "阻断能力 (缺责任人即 BLOCKED)", False, f"异常: {e}")


def check_v7_dsl_determinism():
    """V7 DSL 造词器同 seed 逐字节复现。"""
    dsl = os.path.join(HERE, "language Standard", "dsl.py")
    sample = os.path.join(HERE, "language Standard", "examples", "valid_decision.spd")
    if not os.path.exists(dsl):
        record("V7", "DSL 同 seed 复现", False, "未找到 dsl.py", "WARN")
        return
    try:
        def gen_hash(outdir):
            subprocess.run([sys.executable, dsl, "gen", "--seed", "2026", "--count", "5", "--out", outdir],
                           capture_output=True, cwd=HERE)
            h = hashlib.sha256()
            for fn in sorted(os.listdir(outdir)):
                with open(os.path.join(outdir, fn), "rb") as f:
                    h.update(fn.encode())
                    h.update(f.read())
            return h.hexdigest()

        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            h1, h2 = gen_hash(d1), gen_hash(d2)
            ok = h1 == h2
            record("V7", "DSL 同 seed 复现", ok,
                   f"seed=2026 count=5\nrun1 = {h1[:32]}\nrun2 = {h2[:32]}")

        r = subprocess.run([sys.executable, dsl, "check", sample], capture_output=True, cwd=HERE)
        record("V7b", "DSL 样本校验退出码", r.returncode == 0,
               f"valid_decision.spd exit={r.returncode}", "PASS" if r.returncode == 0 else "FAIL")
    except Exception as e:
        record("V7", "DSL 同 seed 复现", False, f"异常: {e}")


def check_v8_requirements():
    """V8 依赖清单是否与核心一致（影响能否 30 分钟跑起来）。"""
    req = os.path.join(HERE, "requirements.txt")
    try:
        with open(req, "r", encoding="utf-8") as f:
            lines = [x.strip() for x in f if x.strip() and not x.startswith("#")]
        stdlib_ok = {
            "kivy": "Android GUI 框架，与审计内核无关",
            "buildozer": "Android 打包工具，与审计内核无关",
            "cython": "编译加速器，与审计内核无关",
        }
        bad = [l for l in lines if l.split("==")[0].lower() in stdlib_ok]
        if bad:
            detail = ("requirements.txt 内容: " + ", ".join(lines) + "\n"
                      + "核心八算子仅用标准库即可运行，本文件无需安装。\n"
                      + "README 指示 `pip install -r requirements.txt`，会让接手的工程师\n"
                      + "装入无关的 GUI/打包依赖。\n"
                      + "建议: 清空 requirements.txt，或改为注释说明核心零依赖。")
            record("V8", "依赖清单与内核一致", False, detail)
        else:
            record("V8", "依赖清单与内核一致", True, "依赖清单干净", "PASS")
    except Exception as e:
        record("V8", "依赖清单与内核一致", False, f"异常: {e}", "WARN")


def check_v9_nonce_reproducible():
    """V9 默认路径（不固定 nonce）是否可复现。

    v2.0 此处为已知缺陷：nonce 用 uuid4，默认路径不可复现。
    SPE 1.0 改为按责任账户 SHA-256 确定性推导，故本项现在应为 PASS。
    """
    try:
        roots = []
        for _ in range(2):
            acct = spe.ResponsibilityAccount(
                organization="SPE-Verify", role="third_party_auditor",
                stage="review", owner="verify-bot/工号001")
            eng = spe.SecondPerspectiveEngine(acct)
            eng.set_clock(FIXED_CLOCK)
            eng.load_core_plugins()
            eng.audit(dict(BASE_CTX))
            roots.append((acct.nonce, eng.chain_root_hash))
        ok = roots[0][1] == roots[1][1]
        if ok:
            record("V9", "默认路径可复现 (无 nonce 固定)", True,
                   f"默认即可复现（nonce 由责任账户确定性推导）\n"
                   f"  nonce={roots[0][0]} root={roots[0][1][:24]}", "PASS")
        else:
            detail = ("即使固定了 clock，默认路径仍不可复现:\n"
                      f"  run1 nonce={roots[0][0]} root={roots[0][1][:24]}\n"
                      f"  run2 nonce={roots[1][0]} root={roots[1][1][:24]}\n"
                      "根因: ResponsibilityAccount 的 nonce 不是确定性推导。")
            record("V9", "默认路径可复现 (无 nonce 固定)", False, detail, "WARN")
    except Exception as e:
        record("V9", "默认路径可复现 (无 nonce 固定)", False, f"异常: {e}", "WARN")


# ------------------------------------------------------------------ 拓扑层新增

def check_v10_origin_anchor():
    """V10 ⊙ 第一原点锚定：原点真空必须阻断；锚定完成后不得阻断。

    这是「链无起点则后续信号不可信」的可执行断言。
    """
    try:
        no_origin = dict(BASE_CTX)
        no_origin.pop("origin")
        eng, _ = build(no_origin)
        ori_a = eng.audit(no_origin)["analysis"]["GA"]

        eng2, _ = build(BASE_CTX)
        ori_b = eng2.audit(dict(BASE_CTX))["analysis"]["GA"]

        deficit = dict(BASE_CTX)
        deficit["resources"] = {"compute": {"budget": 100.0, "committed": 140.0}}
        eng3, _ = build(deficit)
        ori_c = eng3.audit(deficit)["analysis"]["GA"]

        ok = (ori_a["status"] == "BLOCKED" and ori_a["reason"] == "ORIGIN_VACUUM"
              and ori_b["status"] == "PASS"
              and ori_c["status"] == "HIGH_RISK" and ori_c["reason"] == "RESOURCE_DEFICIT")
        detail = [
            f"无 origin      -> {ori_a['status']} ({ori_a['reason']})",
            f"原点+目标齐备  -> {ori_b['status']} | origin_hash={ori_b['origin_hash']}",
            f"资源缺口为负    -> {ori_c['status']} ({ori_c['reason']}) gap={ori_c['resource_gap_total']}",
        ]
        record("V10", "⊙ 原点锚定 (真空阻断 · 缺口信号)", ok, "\n".join(detail))
    except Exception as e:
        record("V10", "⊙ 原点锚定 (真空阻断 · 缺口信号)", False, f"异常: {e}")


def check_v11_topology_checks():
    """V11 ⊞ 三类并行校验：因果悖论必须使结果无效；矛盾边必须致命。

    两者等级不同、后果不同，必须分别断言：
      悖论（闭合）  -> WARNING，可继续但 result_valid = False
      矛盾边（一致性） -> BLOCKED，推演终止
    """
    try:
        cyclic = dict(BASE_CTX)
        cyclic["topology"] = {
            "nodes": ["n1", "n2", "n3"],
            "edges": [
                {"src": "n1", "dst": "n2"},
                {"src": "n2", "dst": "n3"},
                {"src": "n3", "dst": "n1"},
            ],
        }
        eng, _ = build(cyclic)
        tpg_a = eng.audit(cyclic)["analysis"]["LFT"]
        codes = [i["code"] for i in tpg_a["validation"]["closure"]["issues"]]

        contrad = dict(BASE_CTX)
        contrad["topology"] = {
            "nodes": ["n1", "n2"],
            "edges": [
                {"src": "n1", "dst": "n2", "relation": "causal"},
                {"src": "n1", "dst": "n2", "relation": "requires"},
            ],
        }
        eng2, _ = build(contrad)
        tpg_b = eng2.audit(contrad)["analysis"]["LFT"]

        ok = ("T303" in codes
              and tpg_a["validation"]["result_valid"] is False
              and tpg_b["status"] == "BLOCKED"
              and any(i["code"] == "T101" for i in tpg_b["validation"]["consistency"]["issues"]))
        detail = [
            f"环 n1→n2→n3→n1 : status={tpg_a['status']} result_valid={tpg_a['validation']['result_valid']}",
            f"                  closure codes={codes}",
            f"矛盾边 n1→n2×2 : status={tpg_b['status']} compile={tpg_b['validation']['compile_status']}",
            f"                  consistency codes="
            f"{[i['code'] for i in tpg_b['validation']['consistency']['issues']]}",
        ]
        record("V11", "⊞ 拓扑校验 (悖论失效 · 矛盾致命)", ok, "\n".join(detail))
    except Exception as e:
        record("V11", "⊞ 拓扑校验 (悖论失效 · 矛盾致命)", False, f"异常: {e}")


def check_v12_reality_feedback():
    """V12 ⇄ 灰度执行与现实反馈：证伪却无回退路径必须阻断。"""
    try:
        without_branch = dict(BASE_CTX)
        without_branch["branches"] = [{"assumption": "成本可控", "delta_d": "资源投入上修"}]
        without_branch["feedback"] = {"需求稳定": "falsified", "成本可控": "confirmed"}
        eng, _ = build(without_branch)
        grf_a = eng.audit(without_branch)["analysis"]["GRF"]

        with_branch = dict(BASE_CTX)
        with_branch["feedback"] = {"需求稳定": "falsified", "成本可控": "confirmed"}
        eng2, _ = build(with_branch)
        grf_b = eng2.audit(with_branch)["analysis"]["GRF"]

        no_ladder = dict(BASE_CTX)
        no_ladder.pop("gray_levels")
        no_ladder["commit_ratio"] = 1.0
        eng3, _ = build(no_ladder)
        grf_c = eng3.audit(no_ladder)["analysis"]["GRF"]

        ok = (grf_a["status"] == "BLOCKED" and grf_a["reason"] == "REALITY_CONTRADICTION"
              and grf_b["status"] != "BLOCKED"
              and grf_c["reason"] == "NO_GRAY_LADDER")
        detail = [
            f"证伪且无分支 -> {grf_a['status']} ({grf_a['reason']})"
            f" | 冲突项={grf_a['falsified_without_branch']}",
            f"证伪且有分支 -> {grf_b['status']} ({grf_b['reason']})",
            f"无灰度档位全量 -> {grf_c['status']} ({grf_c['reason']})",
        ]
        record("V12", "⇄ 现实反馈 (证伪无回退即阻断)", ok, "\n".join(detail))
    except Exception as e:
        record("V12", "⇄ 现实反馈 (证伪无回退即阻断)", False, f"异常: {e}")


def check_v13_spiral_superposition():
    """V13 ↻ 叠加螺旋：可复现 + 层叠加（冻结非空）+ 半径趋势可读。

    「叠加而非覆盖」的可观测证据是冻结集合非空且已收敛节点在后续层仍存在。
    """
    ctx = dict(BASE_CTX)
    deltas = [
        {"feedback": {"需求稳定": "confirmed", "成本可控": "unobserved"}},
        {"feedback": {"需求稳定": "confirmed", "成本可控": "confirmed"}, "commit_ratio": 0.5},
    ]
    try:
        runs = []
        for _ in range(2):
            eng, _ = build(ctx)
            runs.append(eng.spiral(
                decision_context=dict(ctx),
                approved_deltas=[dict(d) for d in deltas],
                max_loops=4,
                energy_budget=5.0,
            ))
        a, b = runs
        reproducible = a["session_root_hash"] == b["session_root_hash"]
        frozen = a["spiral"]["frozen_nodes"]
        # 叠加的可观测证据：冻结集合非空，且每个已冻结节点仍出现在各层拓扑里
        kept = all(
            set(frozen) <= {n["id"] for n in layer["topology"].get("nodes", [])}
            for layer in a["spiral"]["layers"]
        ) if frozen else False
        layered = a["spiral"]["layer_count"] >= 2 and len(frozen) > 0 and kept
        ok = reproducible and layered
        detail = [
            f"run1 root = {a['session_root_hash'][:32]}",
            f"run2 root = {b['session_root_hash'][:32]}  -> 可复现={reproducible}",
            f"层数={a['spiral']['layer_count']} 半径趋势={a['spiral']['radius_trend']}",
            f"冻结集合={len(frozen)} 节点 · 各层仍保留={kept} -> 叠加而非覆盖={layered}",
            f"终局 verdict={a['verdict']} final_state={a['final_state']} "
            f"drift={a['origin_drift']} energy_left={a['spiral']['energy_left']}",
            f"叠加违规记录={a['spiral']['violations']}",
        ]
        record("V13", "↻ 叠加螺旋 (可复现 · 层叠加)", ok, "\n".join(detail))
    except Exception as e:
        record("V13", "↻ 叠加螺旋 (可复现 · 层叠加)", False, f"异常: {e}")


def check_v14_binary_fact_check():
    """V14 BFC 二元事实校验：只出真/假，不能归约时给 status 而不是第三值。

    六项子断言，覆盖「默认关闸」与「五条判定分支」：
      a 未启用        -> SKIPPED（且不参与任何判定）
      b 证据真空      -> BLOCKED / EVIDENCE_VACUUM
      c 证据互斥      -> BLOCKED / EVIDENCE_CONFLICT
      d 有证据未核验  -> HIGH_RISK / VERDICT_UNDECLARED（信号级）
      e 已证伪仍在用  -> BLOCKED / FALSIFIED_PREMISE
      f 全部为真      -> PASS，且 undeclared_count == 0
    """
    try:
        def bfc_of(extra):
            ctx = dict(BASE_CTX)
            ctx.update(extra)
            eng, _ = build(ctx)
            return eng.audit(ctx)["analysis"]["BFC"]

        skipped = bfc_of({})

        vacuum = bfc_of({
            "facts": [{"id": "F1", "claim": "需求稳定", "evidence": []}],
            "observations": {"F1": True},
        })

        conflict = bfc_of({
            "facts": [{
                "id": "F1", "claim": "需求稳定",
                "evidence": [{"source": "doc#1", "polarity": True},
                             {"source": "doc#2", "polarity": False}],
            }],
        })

        undeclared = bfc_of({
            "facts": [{"id": "F1", "claim": "需求稳定", "evidence": ["doc#123"]}],
        })

        falsified = bfc_of({
            "facts": [{"id": "F1", "claim": "需求稳定", "evidence": ["doc#123"]}],
            "observations": {"F1": False},
        })

        verified = bfc_of({
            "facts": [
                {"id": "F1", "claim": "需求稳定", "evidence": ["doc#123"]},
                {"id": "F2", "claim": "成本可控", "evidence": ["doc#456"]},
            ],
            "observations": {"F1": True, "F2": True},
        })

        rows = [
            ("未启用      ", skipped),
            ("证据真空    ", vacuum),
            ("证据互斥    ", conflict),
            ("有证据未核验", undeclared),
            ("已证伪仍在用", falsified),
            ("全部为真    ", verified),
        ]
        ok = (
            skipped["status"] == "SKIPPED" and skipped["pass"] is True
            and vacuum["status"] == "BLOCKED" and vacuum["reason"] == "EVIDENCE_VACUUM"
            and len(vacuum["remediation"]) >= 1
            and conflict["status"] == "BLOCKED" and conflict["reason"] == "EVIDENCE_CONFLICT"
            and undeclared["status"] == "HIGH_RISK" and undeclared["reason"] == "VERDICT_UNDECLARED"
            and undeclared["verdicts"][0]["binary"] is None
            and falsified["status"] == "BLOCKED" and falsified["reason"] == "FALSIFIED_PREMISE"
            and verified["status"] == "PASS" and verified["true_count"] == 2
            and verified["undeclared_count"] == 0 and verified["false_count"] == 0
        )
        detail = [f"{label} -> {r['status']:<9} {r['reason']}" for label, r in rows]
        detail.append(f"未启用时 status=SKIPPED（默认关闸，不改变存量判定与链根）")
        detail.append(f"e 命中时 verdicts[0].binary={undeclared['verdicts'][0]['binary']}"
                      f"（None 只表示未声明，不是第三真值）")
        record("V14", "BFC 二元事实校验 (真/假 · 不给第三值)", ok, "\n".join(detail))
    except Exception as e:
        record("V14", "BFC 二元事实校验 (真/假 · 不给第三值)", False, f"异常: {e}")


def _seam_probe(_ctx):
    """插件缝探针：只发 WARNING 信号，永不阻断。"""
    return {"status": "WARNING", "reason": "SEAM_PROBE", "pass": False, "seam": True}


def _blocking_probe(_ctx):
    """越权探针：T2 算子试图发 BLOCKED —— 必须被强制降级为 WARNING。"""
    return {"status": "BLOCKED", "reason": "TRY_BLOCK", "pass": False, "seam": True}


def check_v15_extension_seam():
    """V15 唯一插件缝：可用 + 四道闸门生效 + 清单并入哈希 + 拒绝时零副作用。

    a 缝可用      注册 T2 扩展算子 → 出现在清单，且紧随 after 之后
    b 闸门·重名   与官方算子重名 → ValueError
    c 闸门·T1     外部算子持 T1 → ValueError（不允许外部改动「能不能通过」）
    d 闸门·after  after 缺失或指向不存在 → ValueError
    e 闸门·名字   非 ASCII 标识符 → ValueError
    f 闸门·层     tier 非 PluginTier 成员 → ValueError
    g 零副作用    任一拒绝后：算子数、执行序、链根均不变
    h 并入哈希    注册扩展算子后链根 ≠ 未注册时链根
    i 链上自证    链上事件带 operator_set_hash，且与当前算子集一致
    j 越权降级    扩展算子试图发 BLOCKED → 被降级为 WARNING 并留 _tier_violation
    """
    try:
        # ---- a 缝可用 + 位置正确 ----
        eng, _ = build(BASE_CTX)
        eng.register_operator("SEAM_PROBE", spe.PluginTier.T2_SIGNAL, _seam_probe,
                              description="插件缝探针", after="LFT")
        names = [m["name"] for m in eng.operator_manifest()]
        pos_ok = names.index("SEAM_PROBE") == names.index("LFT") + 1
        in_manifest = any(
            m["name"] == "SEAM_PROBE" and m["tier"] == "T2_SIGNAL"
            and m["origin"] == "extension" and m["registered_after"] == "LFT"
            for m in eng.operator_manifest()
        )
        rep = eng.audit(dict(BASE_CTX))
        in_report = any(m["name"] == "SEAM_PROBE" for m in rep["operator_manifest"])
        probe_signal = rep["analysis"].get("SEAM_PROBE", {}).get("status")

        # ---- b–f 四道闸门 ----
        def reject(label, **kw):
            e, _ = build(BASE_CTX)
            try:
                e.register_operator(**kw)
                return (label, "NO-RAISE")
            except ValueError:
                return (label, "ValueError")
            except Exception as exc:                     # noqa: BLE001
                return (label, f"{type(exc).__name__}")

        T2 = spe.PluginTier.T2_SIGNAL
        gates = [
            reject("重名(GA)", name="GA", tier=T2, analyze=_seam_probe, after="LFT"),
            reject("外部持 T1", name="X1", tier=spe.PluginTier.T1_STRUCTURAL,
                   analyze=_seam_probe, after="LFT"),
            reject("after 缺失", name="X2", tier=T2, analyze=_seam_probe),
            reject("after 不存在", name="X3", tier=T2, analyze=_seam_probe, after="NOPE"),
            reject("非 ASCII 标识符", name="探针", tier=T2, analyze=_seam_probe, after="LFT"),
            reject("非枚举 tier", name="X4", tier="T2_SIGNAL", analyze=_seam_probe, after="LFT"),
        ]

        # ---- g 零副作用 ----
        root_plain = root_of(BASE_CTX)
        e2, _ = build(BASE_CTX)
        n_before, order_before = len(e2.plugins), list(e2.PIPELINE_ORDER)
        try:
            e2.register_operator("GA", T2, _seam_probe, after="LFT")
        except ValueError:
            pass
        e2.audit(dict(BASE_CTX))
        zero_side_effect = (len(e2.plugins) == n_before
                            and e2.PIPELINE_ORDER == order_before
                            and e2.chain_root_hash == root_plain)

        # ---- h 并入哈希 ----
        eng_h, _ = build(BASE_CTX)
        eng_h.register_operator("SEAM_PROBE", T2, _seam_probe, after="LFT")
        eng_h.audit(dict(BASE_CTX))
        hash_changed = eng_h.chain_root_hash != root_plain

        # ---- i 链上自证 ----
        audit_events = [e for e in eng_h.event_chain if e.event_type == "AUDIT"]
        on_chain = audit_events[-1].payload.get("operator_set_hash") if audit_events else None
        chain_self_proves = bool(on_chain) and on_chain == eng_h.operator_set_hash()

        # ---- j 越权降级 ----
        eng_j, _ = build(BASE_CTX)
        eng_j.register_operator("BLOCK_PROBE", T2, _blocking_probe, after="LFT")
        rep_j = eng_j.audit(dict(BASE_CTX))
        probe_j = rep_j["analysis"].get("BLOCK_PROBE", {})
        downgraded = (probe_j.get("status") == "WARNING"
                      and "_tier_violation" in probe_j)

        rows = [
            f"a 缝可用      : 位置紧随 LFT = {pos_ok} | 清单={in_manifest} | 报告={in_report} "
            f"| 探针 status={probe_signal}",
            "b–f 四道闸门  : " + " · ".join(f"{lb}→{r}" for lb, r in gates),
            f"g 零副作用    : 算子数/执行序/链根均不变 = {zero_side_effect}",
            f"h 并入哈希    : 注册扩展后链根改变 = {hash_changed}",
            f"i 链上自证    : operator_set_hash={on_chain} | 与算子集一致 = {chain_self_proves}",
            f"j 越权降级    : 外部 BLOCKED→{probe_j.get('status')} "
            f"| _tier_violation={'有' if '_tier_violation' in probe_j else '无'}",
        ]
        ok = (pos_ok and in_manifest and in_report and probe_signal == "WARNING"
              and all(r == "ValueError" for _, r in gates)
              and zero_side_effect and hash_changed and chain_self_proves and downgraded)
        record("V15", "唯一插件缝 (四道闸门 · 清单入哈希 · 越权降级)", ok, "\n".join(rows))
    except Exception as e:
        record("V15", "唯一插件缝 (四道闸门 · 清单入哈希 · 越权降级)", False, f"异常: {e}")


def check_v16_limit_reconstruct():
    """V16 ∞ 极限收敛器：层数无上限、只按语义判据停机、引擎永不自驱。

    a 硬闸门        无 energy_budget 且无 max_loops → ValueError（无限必须有界）
    b 无算术上限    给 20 层 delta、能量充足、不设 max_loops → 由语义判据停，层数 < 20
    c FLAT_SPIRAL   半径连续三层纹丝不动 → 画地为牢
    d LIMIT_REACHED 距离归零并连续保持 → 抵达 S∞ = S*
    e NOT_MONOTONE  谓词单测：距离 (1,0),(2,0),(3,0) → 不再逼近
    f spiral_step   单层推进可续跑 ≥3 层，状态可序列化往返
    g 引擎不自驱    delta 用尽 → AWAITING_HUMAN，绝不自己生成修正
    """
    try:
        # ---- a 硬闸门 ----
        eng, _ = build(BASE_CTX)
        try:
            eng.limit_reconstruct(dict(BASE_CTX))
            gate = "NO-RAISE"
        except ValueError:
            gate = "ValueError"

        # ---- b 无算术上限 + c FLAT_SPIRAL ----
        flat_ctx = dict(BASE_CTX)
        flat_ctx["evidence"] = []          # ⊕IAP 结论无证据 → 风险每层都在，半径恒定
        eng_b, _ = build(flat_ctx)
        out_b = eng_b.limit_reconstruct(
            dict(flat_ctx),
            approved_deltas=[{"audit_note": f"n{i}"} for i in range(20)],
            energy_budget=100.0,          # 能量远够；且刻意不设 max_loops
        )
        flat_ok = (out_b["verdict"] == "FLAT_SPIRAL" and out_b["total_loops"] < 20)

        # ---- d LIMIT_REACHED ----
        eng_d, _ = build(BASE_CTX)
        out_d = eng_d.limit_reconstruct(
            dict(BASE_CTX),
            approved_deltas=[
                {"feedback": {"需求稳定": "confirmed", "成本可控": "unobserved"}},
                {"feedback": {"需求稳定": "confirmed", "成本可控": "confirmed"}},
                {"commit_ratio": 0.5},
            ],
            energy_budget=50.0,
        )
        limit_ok = (out_d["verdict"] == "LIMIT_REACHED"
                    and out_d["is_true_convergence"]
                    and out_d["distance_trend"][-1] == [0, 0])

        # ---- e NOT_MONOTONE 谓词单测 ----
        probe = spe.SpiralStack()
        for i, radius in enumerate((1, 2, 3)):   # 半径递增 = 越走越远
            probe.push(state="DIVERGED", origin_hash="o",
                       risk_set=[f"r{j}" for j in range(radius)],
                       graph_hash="g", topology={}, index=i)
        monotone_ok = (probe.is_plateau(3) and not probe.is_static(3))

        # ---- f spiral_step 续跑 + 状态往返 ----
        eng_f, _ = build(flat_ctx)
        state = None
        steps = []
        for i in range(3):
            res = eng_f.spiral_step(dict(flat_ctx), delta={"audit_note": f"s{i}"}, state=state)
            steps.append(res["verdict"])
            state = res["spiral_state"]
        roundtrip = spe.SpiralStack.from_dict(state)
        step_ok = (len(state["layers"]) == 3
                   and len(roundtrip.layers) == 3
                   and roundtrip.loop_cost == state["loop_cost"]
                   and [list(d) for d in roundtrip.distance_trend()] == state["distance_trend"])

        # ---- g 引擎不自驱 ----
        eng_g, _ = build(BASE_CTX)
        out_g = eng_g.limit_reconstruct(dict(BASE_CTX), approved_deltas=[],
                                       energy_budget=5.0)
        no_self_drive = out_g["verdict"] == "AWAITING_HUMAN"

        rows = [
            f"a 硬闸门      : 无硬顶 → {gate}",
            f"b/c 无上限    : verdict={out_b['verdict']} 层数={out_b['total_loops']} "
            f"(<20 说明是语义判据停的) | 半径趋势={out_b['spiral']['radius_trend']}",
            f"d LIMIT       : verdict={out_d['verdict']} 距离序列={out_d['distance_trend']} "
            f"真收敛={out_d['is_true_convergence']}",
            f"e 谓词单测    : 距离(1,0)(2,0)(3,0) → plateau={probe.is_plateau(3)} "
            f"static={probe.is_static(3)} flat={probe.check_flat(3)}",
            f"f spiral_step : 三步 verdict={steps} 往返层数={len(roundtrip.layers)} "
            f"距离={state['distance_trend']}",
            f"g 不自驱      : delta 用尽 → {out_g['verdict']}",
        ]
        ok = (gate == "ValueError" and flat_ok and limit_ok and monotone_ok
              and step_ok and no_self_drive)
        record("V16", "∞ 极限收敛器 (无上限 · 判据停机 · 不自驱)", ok, "\n".join(rows))
    except Exception as e:
        record("V16", "∞ 极限收敛器 (无上限 · 判据停机 · 不自驱)", False, f"异常: {e}")


# ------------------------------------------------------------------ 元因果 + 自主进化

def _codes(validation):
    """从四类并行校验里取全部诊断码。"""
    return [i["code"] for part in ("consistency", "constraint", "closure", "time_order")
            for i in validation[part]["issues"]]


def check_v17_meta_and_autonomous_evolution():
    """V17 元因果账本 + 链内时序 + 自主进化层。

    规范第六条把元因果基底定为五条（混沌·无极·虚幻·天道·轮回）；
    规范第六节（IR 层）把运行期演化定为 evolve / rewrite / 最小不动点 / A10。
    本项验证这两件事在内核里可计算、可复现，并且**进化不越权**。

    a 五元基齐备    META 账本五条元基全在，各有 status 与 reason
    b A6 可复现     同一输入两次审计，A6 叙事熵逐位相同（有理数，非概率）
    c A10 有界      天道：A10 审计熵增给出数值与判据；有界才收敛于 S*
    d 混沌归因拦截  「随机 / 运气」+ 真实缺口 → HIGH_RISK，且缺口被逐条点名
    e 平行 ≠ 分支   多起点合法（无极 PASS）；同一对节点多边 → T305 分叉违规
    f 时序不可倒置  声明 t 与链内序冲突 → T307；有环 → 时序无法赋值
    g 只提案不适用  三条恒等式：applies_automatically=False · requires_human=True
                    · auto_applied=0
    h 可复现        两次 evolve 的 lineage_hash 与候选 id 完全一致
    i 最小不动点    g_{n+1} == g_n（图同构判定）可检出
    j 记账不改判定  人工裁决只升代际：各算子 status 逐位不变，仅 lineage_hash 变
    """
    try:
        # ---- a/b/c 五元基与两个度量 ----
        eng_a, _ = build(BASE_CTX)
        rep_a = eng_a.audit(dict(BASE_CTX))
        bases = rep_a.get("meta_ledger", {}).get("bases", {})
        five = ("混沌", "无极", "虚幻", "天道", "轮回")
        complete = all(b in bases and "status" in bases[b] and "reason" in bases[b]
                       for b in five)

        # A6 必须在**真的遮蔽**上测：BASE_CTX 的叙述不带修辞，A6 恒为 0，
        # 「0 等于 0」证明不了任何事。
        a6_ctx = dict(BASE_CTX)
        a6_ctx["narrative"] = "显然，这次上线是最优选择，毫无疑问。"
        eng_b, _ = build(a6_ctx)
        rep_b = eng_b.audit(dict(a6_ctx))
        a6 = rep_b["meta_ledger"]["bases"]["虚幻"]["a6_narrative_entropy"]
        eng_b2, _ = build(a6_ctx)
        rep_b2 = eng_b2.audit(dict(a6_ctx))
        a6_b = rep_b2["meta_ledger"]["bases"]["虚幻"]["a6_narrative_entropy"]
        a6_ok = isinstance(a6, float) and a6 > 0 and a6 == a6_b

        a10 = bases.get("天道", {}).get("a10_audit_entropy")
        a10_ok = isinstance(a10, float) and bases["天道"].get("bounded") is True

        # ---- d 混沌：随机不在世界，在缺口 ----
        chaos_ctx = dict(BASE_CTX)
        chaos_ctx.pop("branches", None)
        chaos_ctx["feedback"] = {}
        chaos_ctx["narrative"] = "这次能不能成全看运气，市场是随机的。"
        eng_d, _ = build(chaos_ctx)
        chaos = eng_d.audit(chaos_ctx)["meta_ledger"]["bases"]["混沌"]
        chaos_ok = (chaos["status"] == "HIGH_RISK" and chaos["gap_count"] >= 1
                    and bool(chaos["misattributed"]))

        # ---- e 平行 ≠ 分支 ----
        par = spe.TopologyGraph(layer=0)
        par.add_edge(spe.TopoEdge("N0", "ND"))
        par.add_edge(spe.TopoEdge("NA", "ND", relation="requires"))
        par_order = par.assign_time_order()
        parallel_ok = (par_order["parallel_chains"] == 2 and par_order["forks"] == []
                       and par_order["assignable"])

        fork = spe.TopologyGraph(layer=0)
        fork.add_edge(spe.TopoEdge("N0", "ND"))
        fork.add_edge(spe.TopoEdge("N0", "ND", t=0))
        fork_val = spe.TopologyValidator.run_all(fork)
        fork_codes = _codes(fork_val)
        fork_ok = ("T305" in fork_codes) and (fork_val["result_valid"] is False)

        # ---- f 时序 ----
        inv = spe.TopologyGraph(layer=0)
        inv.add_edge(spe.TopoEdge("N0", "ND", t=7))
        invert_ok = "T307" in _codes(spe.TopologyValidator.run_all(inv))

        cyc = spe.TopologyGraph(layer=0)
        cyc.add_edge(spe.TopoEdge("N0", "ND"))
        cyc.add_edge(spe.TopoEdge("ND", "N0"))
        cyc_order = cyc.assign_time_order()
        cycle_ok = (not cyc_order["assignable"]) and bool(cyc_order["unassignable"])

        # ---- g/h/i evolve：只提案 · 可复现 · 最小不动点 ----
        # 输入刻意留一个真实缺口（一条假设始终未被观测）→ 保证一定有候选，
        # 否则「候选清单」这项会因为没有缺口而空过，等于没测。
        evo_ctx = dict(BASE_CTX)
        evo_ctx["feedback"] = {"需求稳定": "confirmed", "成本可控": "unobserved"}
        # 两层「算子不可观测的 delta」⇒ 邻层图指纹相同 ⇒ 走最小不动点停机。
        noop = [{"audit_note": "r1"}, {"audit_note": "r2"}]
        eng_g, _ = build(evo_ctx)
        ev1 = eng_g.evolve(dict(evo_ctx), approved_deltas=noop,
                           max_loops=4, energy_budget=20.0)
        ids1 = [p["id"] for p in ev1["proposals"]]
        gate_ok = (ev1["auto_applied"] == 0
                   and ev1["requires_human"] is True
                   and len(ids1) >= 1
                   and all(p["applies_automatically"] is False
                           and p["requires_human"] is True
                           for p in ev1["proposals"]))

        eng_h, _ = build(evo_ctx)
        ev2 = eng_h.evolve(dict(evo_ctx), approved_deltas=noop,
                           max_loops=4, energy_budget=20.0)
        ids2 = [p["id"] for p in ev2["proposals"]]
        repro_ok = (ev1["lineage"]["lineage_hash"] == ev2["lineage"]["lineage_hash"]
                    and ids1 == ids2)

        fixed_ok = ev1["fixed_point"]["found"] is True
        ev_a10_ok = ev1["audit_entropy"]["bounded"] is True

        # ---- j 记账不改判定 ----
        eng_j, _ = build(evo_ctx)
        before = eng_j.audit(dict(evo_ctx))
        st_before = {k: v.get("status") for k, v in before["analysis"].items()
                     if isinstance(v, dict)}
        lin_before = before["lineage"]["lineage_hash"]
        appr = eng_j.approve_evolution_proposal(ev1["proposals"][0],
                                                approved_by="verify-bot/工号001")
        after = eng_j.audit(dict(evo_ctx))
        st_after = {k: v.get("status") for k, v in after["analysis"].items()
                    if isinstance(v, dict)}
        lin_after = after["lineage"]["lineage_hash"]
        account_ok = (appr["applied_to_code"] is False
                      and appr["requires_code_change"] is True
                      and appr["lineage"]["generation"] == 1
                      and st_before == st_after
                      and lin_before != lin_after)

        five_txt = (" · ".join("{}={}".format(b, bases[b]["status"]) for b in five)
                    if complete else "缺项")
        rows = [
            f"a 五元基      : {five_txt}",
            f"b A6 叙事熵   : 两次审计 {a6} == {a6_b} → 可复现={a6 == a6_b}（有理数，非概率）",
            f"c A10 审计熵增: {a10} | bounded={bases['天道'].get('bounded')}"
            f" | ceiling={bases['天道'].get('ceiling')}（天道：有界才收敛于 S*）",
            f"d 混沌归因    : {chaos['status']} | 缺口 {chaos['gap_count']} 条"
            f" | 归因于随机的词 {chaos['misattributed']}",
            f"e 平行/分支   : 平行起点={par_order['parallel_chains']} 合法"
            f" | 同一对节点多边 → T305={('T305' in fork_codes)}"
            f" result_valid={fork_val['result_valid']}",
            f"f 时序        : 声明 t=7 越界 → T307={('T307' in _codes(spe.TopologyValidator.run_all(inv)))}"
            f" | 有环可赋值={cyc_order['assignable']}",
            f"g 只提案      : 候选 {len(ids1)} 条 | auto_applied={ev1['auto_applied']}"
            f" | requires_human={ev1['requires_human']}",
            f"h 可复现      : lineage {ev1['lineage']['lineage_hash']} == "
            f"{ev2['lineage']['lineage_hash']} | 候选 id 一致={ids1 == ids2}",
            f"i 最小不动点  : found={ev1['fixed_point']['found']}"
            f" round={ev1['fixed_point']['round']}（g_{{n+1}} == g_n）",
            f"j 记账不改判定: applied_to_code={appr['applied_to_code']}"
            f" | 代际 0→{appr['lineage']['generation']}"
            f" | 算子 status 不变={st_before == st_after}"
            f" | lineage {lin_before}→{lin_after}",
        ]
        ok = (complete and a6_ok and a10_ok and chaos_ok and parallel_ok and fork_ok
              and invert_ok and cycle_ok and gate_ok and repro_ok and fixed_ok
              and ev_a10_ok and account_ok)
        record("V17", "元因果账本 + 时序 + 自主进化 (只提案 · 谱系 · 记账不改判定)",
               ok, "\n".join(rows))
    except Exception as e:
        record("V17", "元因果账本 + 时序 + 自主进化 (只提案 · 谱系 · 记账不改判定)",
               False, f"异常: {e}")


# ------------------------------------------------------------------ 主流程

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--root", action="store_true", help="只打印当前环境链根")
    args = ap.parse_args()

    if args.root:
        print(root_of(BASE_CTX))
        return

    print("=" * 68)
    print("SPE 独立验证套件 / Independent Verification Suite")
    print(f"目标: {ENGINE}")
    print("=" * 68)

    check_v1_zero_dependency()
    check_v2_reproducible()
    check_v3_sensitivity()
    check_v3b_input_coverage()
    check_v4_chain_valid()
    check_v5_tamper_evidence()
    check_v6_blocking()
    check_v7_dsl_determinism()
    check_v8_requirements()
    check_v9_nonce_reproducible()
    check_v10_origin_anchor()
    check_v11_topology_checks()
    check_v12_reality_feedback()
    check_v13_spiral_superposition()
    check_v14_binary_fact_check()
    check_v15_extension_seam()
    check_v16_limit_reconstruct()
    check_v17_meta_and_autonomous_evolution()

    n_fail = sum(1 for r in RESULTS if r["level"] == "FAIL")
    n_warn = sum(1 for r in RESULTS if r["level"] == "WARN")
    n_pass = sum(1 for r in RESULTS if r["level"] == "PASS")

    print("=" * 68)
    print(f"合计: PASS {n_pass} · FAIL {n_fail} · WARN {n_warn}")
    if n_fail:
        print("结论: 存在 FAIL 项，在对外承诺『防篡改审计证书』前必须先修复。")
    else:
        print("结论: 全部硬性检查通过。")
    print("=" * 68)

    if args.json:
        print(json.dumps({
            "summary": {"pass": n_pass, "fail": n_fail, "warn": n_warn},
            "checks": RESULTS,
        }, ensure_ascii=False, indent=2))

    sys.exit(1 if n_fail else 0)


if __name__ == "__main__":
    main()
