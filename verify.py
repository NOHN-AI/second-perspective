#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GCAE 独立验证脚本 / GCAE Independent Verification Suite
================================================================
零依赖、纯标准库、离线运行。无需 pip install，无需配置环境变量。

    python verify.py            # 跑全部检查
    python verify.py --json     # 机器可读输出（可接 CI）
    python verify.py --root     # 只打印当前环境链根，供跨机比对

设计原则：脚本如实报告 PASS / FAIL / WARN，不为了好看而放宽断言。
FAIL 即为产品当前缺陷，请在对外承诺前修复。
退出码：0 = 无 FAIL；1 = 存在 FAIL。
"""

import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(HERE, "Cognitive Audit Engine.py")

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
    spec = importlib.util.spec_from_file_location("ca", ENGINE)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["ca"] = mod
    spec.loader.exec_module(mod)
    return mod


ca = load_engine()


def build(ctx, nonce=FIXED_NONCE, clock=FIXED_CLOCK, owner="verify-bot/工号001"):
    acct = ca.ResponsibilityAccount(
        organization="GCAE-Verify", role="third_party_auditor",
        stage="review", owner=owner,
    )
    acct.nonce = nonce            # 覆盖 __post_init__ 生成的 uuid4
    eng = ca.CognitiveAuditEngine(acct)
    eng.set_clock(clock)          # 覆盖系统墙钟
    eng.load_core_plugins()
    return eng, acct


BASE_CTX = {
    "narrative": "项目 X 应立即批准上线，因为需求已经充分验证。",
    "alternatives": {"S1": {"metrics": {"roi": 0.12}}, "S2": {"metrics": {"roi": 0.08}}},
    "criteria": {"roi": {"weight": 1.0}},
    "conclusions": "Recommend S1",
    "evidence": ["doc#123"],
}


def root_of(ctx, nonce=FIXED_NONCE):
    eng, _ = build(ctx, nonce=nonce)
    eng.audit(dict(ctx))
    return eng.chain_root_hash


# ------------------------------------------------------------------ 检查项

def check_v1_zero_dependency():
    """V1 核心可离线运行：仅标准库即可装载引擎与五算子。"""
    try:
        eng, _ = build(BASE_CTX)          # 会真实装载 NS/IAP/LCH/CCS/STATE
        record("V1", "零依赖离线装载 (stdlib only)", True,
               "引擎装载成功；五个算子插件注册成功；全程未使用 requirements.txt", "PASS")
    except Exception as e:
        record("V1", "零依赖离线装载 (stdlib only)", False,
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
    变化才会传导。以下选取两处必然传导的变异点。
    """
    try:
        base = root_of(BASE_CTX)
        rows = []

        c1 = dict(BASE_CTX)
        c1["narrative"] = "显然" + BASE_CTX["narrative"]        # 触发 NS 主观词标记
        rows.append(("narrative 加入主观修饰词", root_of(c1)))

        c2 = dict(BASE_CTX)
        c2["evidence"] = []                                      # 触发 IAP CONCLUSION_WITHOUT_EVIDENCE
        rows.append(("删除 evidence", root_of(c2)))

        unchanged = [label for label, r in rows if r == base]
        ok = not unchanged
        detail = [f"base = {base[:32]}"]
        detail += [f"{label:<24} -> {r[:32]}" for label, r in rows]
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
            "输入大幅改动（conclusions 与 alternatives 全部替换）后：",
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
        detail_lines.append("根因: verify_chain() 中 expected = ev.hash 是实时重算属性，")
        detail_lines.append("      改动 payload 后重算值同步改变，actual 恒等于 expected，")
        detail_lines.append("      故只有 prev_hash 断链能被检出。")
        detail_lines.append("修法: append 时把链根落盘为不可变字段，比对冻结值而非重算值。")
        record("V5", "篡改可检出 (payload/type/prev_hash)", False, "\n".join(detail_lines))


def check_v6_blocking():
    """V6 阻断能力:责任未闭环必须 BLOCKED；闭环后不再阻断。"""
    try:
        acct_open = ca.ResponsibilityAccount(
            organization="GCAE-Verify", role="third_party_auditor", stage="review")
        eng = ca.CognitiveAuditEngine(acct_open)
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
                      + "核心五算子仅用标准库即可运行，本文件无需安装。\n"
                      + "README 指示 `pip install -r requirements.txt`，会让接手的工程师\n"
                      + "装入无关的 GUI/打包依赖。\n"
                      + "建议: 清空 requirements.txt，或改为注释说明核心零依赖。")
            record("V8", "依赖清单与内核一致", False, detail)
        else:
            record("V8", "依赖清单与内核一致", True, "依赖清单干净", "PASS")
    except Exception as e:
        record("V8", "依赖清单与内核一致", False, f"异常: {e}", "WARN")


def check_v9_nonce_warn():
    """V9 默认路径（不固定 nonce）是否可复现 —— 已知缺陷，标记 WARN。"""
    try:
        roots = []
        for _ in range(2):
            acct = ca.ResponsibilityAccount(
                organization="GCAE-Verify", role="third_party_auditor",
                stage="review", owner="verify-bot/工号001")
            eng = ca.CognitiveAuditEngine(acct)
            eng.set_clock(FIXED_CLOCK)
            eng.load_core_plugins()
            eng.audit(dict(BASE_CTX))
            roots.append((acct.nonce, eng.chain_root_hash))
        ok = roots[0][1] == roots[1][1]
        if ok:
            record("V9", "默认路径可复现 (无 nonce 固定)", True, "默认即可复现", "PASS")
        else:
            detail = ("即使固定了 clock，默认路径仍不可复现:\n"
                      f"  run1 nonce={roots[0][0]} root={roots[0][1][:24]}\n"
                      f"  run2 nonce={roots[1][0]} root={roots[1][1][:24]}\n"
                      "根因: ResponsibilityAccount.__post_init__ 用 uuid.uuid4() 生成 nonce，\n"
                      "      而 audit_id 与链事件均含该 nonce。\n"
                      "影响: 验证脚本必须显式固定 nonce，README 需说明。\n"
                      "修法: 将 uuid4() 改为按 account 字段做 sha256 确定性推导。")
            record("V9", "默认路径可复现 (无 nonce 固定)", False, detail, "WARN")
    except Exception as e:
        record("V9", "默认路径可复现 (无 nonce 固定)", False, f"异常: {e}", "WARN")


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
    print("GCAE 独立验证套件 / Independent Verification Suite")
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
    check_v9_nonce_warn()

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