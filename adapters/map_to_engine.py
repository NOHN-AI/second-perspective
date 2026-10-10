#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
映射适配器（最小版）：企业文档导出 → 引擎输入 → 审计报告
==========================================================

把「客户现有系统里的导出文件」按一张映射表接进引擎，
一条命令跑出审计报告与链根凭据。

最小版边界（刻意不做）：
    连接器（Jira / Confluence / 企微文档实时拉取）、拖拽配置界面、独立 SDK。
    签约前的 POC 里 API 权限批不下来，导出文件 + 映射表是零阻力路径。

原则（沿用引擎护栏 I-1 非猜测）：
    导出文件里没有的字段一律不补；未映射的章节不进入引擎；
    真值（facts / observations）只能由外部显式声明，引擎永不推断。

用法:
    python "adapters/map_to_engine.py" "adapters/sample_confluence_decision.json" \\
        --org "示例公司·风控部" --role "决策评审" --stage pre_decision --owner "风控负责人"

    映射表为第二个位置参数（默认 adapters/mapping.confluence.json）。
    不传 --owner 时责任未闭环，引擎会在报告里显式标注（这是特性，不是故障）。
"""

import argparse
import importlib.util
import json
import os
import sys
from html.parser import HTMLParser

sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ENGINE_PATH = os.path.join(ROOT, "Second Perspective Engine.py")
DEFAULT_MAPPING = os.path.join(HERE, "mapping.confluence.json")
FIXED_CLOCK = 1791504000.0  # 沿用 verify.py / case 脚本约定（2026-10-09T00:00:00Z）
HEADING_TAGS = ("h1", "h2", "h3", "h4", "h5", "h6")

CONFIG = {
    "allowed_stages": ["pre_decision", "in_decision", "post_decision", "review"],
    "disclaimer": "本审计报告由 SPL Cognitive Audit Engine 生成，仅做结构性审计，不替代人类判断。",
}


def load_engine():
    # 必须先写入 sys.modules，否则 dataclasses 反查 cls.__module__ 拿到 None（同 verify.py）
    spec = importlib.util.spec_from_file_location("ca", ENGINE_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["ca"] = mod
    spec.loader.exec_module(mod)
    return mod


class _Sections(HTMLParser):
    """把 XHTML 片段（Confluence storage 等富文本导出）拆成块级序列。

    产出 [{"heading", "texts", "items"}]；只认块级标签 h1-h6 / p / li，
    行内标签（strong / em / a…）的文本并入当前块。表格内容不收集（见 MAPPING-zh.md 边界）。
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.sections = []
        self._heading = None  # 当前章节标题（None = 首个标题之前）
        self._texts = []
        self._items = []
        self._mode = None  # 正在收集: "h" | "p" | "li"
        self._buf = []
        self._stack = []

    def _flush(self):
        text = "".join(self._buf).strip()
        self._buf = []
        mode, self._mode = self._mode, None
        if not text:
            return
        if mode == "h":
            self.sections.append(
                {"heading": self._heading, "texts": self._texts, "items": self._items}
            )
            self._heading = text
            self._texts = []
            self._items = []
        elif mode == "p":
            self._texts.append(text)
        elif mode == "li":
            self._items.append(text)

    def handle_starttag(self, tag, attrs):
        self._stack.append(tag)
        if tag in HEADING_TAGS:
            self._flush()
            self._mode = "h"
        elif tag == "li":
            self._flush()
            self._mode = "li"
        elif tag == "p" and self._mode != "li":
            self._flush()
            self._mode = "p"
        elif tag == "br":
            self._buf.append(" ")

    def handle_endtag(self, tag):
        if tag in self._stack:
            while self._stack and self._stack.pop() != tag:
                pass
        if tag in HEADING_TAGS and self._mode == "h":
            self._flush()
        elif tag == "li" and self._mode == "li":
            self._flush()
        elif tag == "p" and self._mode == "p":
            self._flush()

    def handle_data(self, data):
        if self._mode:
            self._buf.append(data)

    def finish(self):
        self._flush()
        self.sections.append(
            {"heading": self._heading, "texts": self._texts, "items": self._items}
        )
        return [s for s in self.sections if s["heading"] or s["texts"] or s["items"]]


def parse_sections(html_text):
    parser = _Sections()
    parser.feed(html_text)
    parser.close()
    return parser.finish()


def get_path(obj, dotted):
    cur = obj
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def pick_section(index, spec):
    for name in spec["headings"]:
        for sec in index.get(name, []):
            list_mode = spec["mode"] in ("list", "branches")
            primary = sec["items"] if list_mode else sec["texts"]
            fallback = sec["texts"] if list_mode else sec["items"]
            vals = primary or fallback
            if vals:
                return name, vals
    return None, None


def _parse_branch(item):
    """「若 X 不成立 → 回退处理」→ {"assumption", "delta_d"}（箭头 → 或 -> 分隔）。"""
    for sep in ("→", "->"):
        if sep in item:
            left, right = item.split(sep, 1)
            left, right = left.strip(), right.strip()
            if left and right:
                return {"assumption": left, "delta_d": right}
    return {"assumption": item, "delta_d": ""}


def build_context(export, mapping):
    html = get_path(export, mapping["source"]["body"])
    if not isinstance(html, str):
        raise SystemExit(
            f"[x] source.body='{mapping['source']['body']}' 在导出文件中找不到字符串内容"
        )
    title = get_path(export, mapping["source"]["title"]) or export.get("title") or "(无标题)"
    sections = parse_sections(html)
    index = {}
    for sec in sections:
        if sec["heading"]:
            index.setdefault(sec["heading"].strip(), []).append(sec)

    ctx, hits, used = {}, [], set()
    for key, spec in mapping["fields"].items():
        heading, vals = pick_section(index, spec)
        if heading is None:
            continue
        used.add(heading)
        if spec["mode"] == "list":
            ctx[key] = list(vals)
            hits.append((key, heading, f"{len(vals)} 条"))
        elif spec["mode"] == "branches":
            ctx[key] = [_parse_branch(v) for v in vals]
            hits.append((key, heading, f"{len(vals)} 条"))
        else:
            ctx[key] = "\n".join(vals)
            hits.append((key, heading, f"{len(vals)} 段"))

    unmapped = list(
        dict.fromkeys(
            s["heading"] for s in sections if s["heading"] and s["heading"].strip() not in used
        )
    )
    required = mapping.get("required", ["decision", "assumptions", "outcome"])
    missing = [k for k in required if k not in ctx]
    return title, ctx, hits, unmapped, missing, sections


def main():
    ap = argparse.ArgumentParser(description="企业文档导出 → SPE 引擎输入 → 审计报告（最小版）")
    ap.add_argument("export", help="源系统导出文件（JSON）")
    ap.add_argument("mapping", nargs="?", default=DEFAULT_MAPPING,
                    help="映射表（JSON），默认 adapters/mapping.confluence.json")
    ap.add_argument("--org", default="未指定组织")
    ap.add_argument("--role", default="未指定角色")
    ap.add_argument("--stage", default="pre_decision",
                    choices=["pre_decision", "in_decision", "post_decision", "review"])
    ap.add_argument("--owner", default=None, help="责任人；不给出则责任未闭环（引擎会显式标注）")
    args = ap.parse_args()

    with open(args.export, "r", encoding="utf-8") as f:
        export = json.load(f)
    with open(args.mapping, "r", encoding="utf-8") as f:
        mapping = json.load(f)

    print("=" * 72)
    print("映射适配器（最小版）：企业导出 → 引擎输入 → 审计报告")
    print("=" * 72)

    title, ctx, hits, unmapped, missing, sections = build_context(export, mapping)
    print(f"\n[1/4] 导出文件 : {os.path.relpath(args.export, ROOT)}")
    print(f"      系统     : {mapping.get('system', '?')} — 《{title}》"
          f" (id={export.get('id', '?')}, v={(export.get('version') or {}).get('number', '?')})")

    print(f"\n[2/4] 映射表   : {os.path.relpath(args.mapping, ROOT)}")
    for key, heading, count in hits:
        print(f"      {key:<12} <- {heading}（{count}）")
    if unmapped:
        print(f"      未映射章节（不进引擎 · I-1 非猜测）: {'、'.join(unmapped)}")

    if missing:
        found = "、".join(s["heading"] for s in sections if s["heading"])
        print(f"\n[x] 必填字段缺失: {missing} —— 按 I-1 不推断、不填充。")
        print(f"    导出文件中共有章节: {found}")
        print("    请在映射表中补充对应 headings，或补充材料后重跑。")
        return 1

    ca = load_engine()
    acct = ca.ResponsibilityAccount(
        organization=args.org, role=args.role, stage=args.stage, owner=args.owner
    )
    config = dict(CONFIG)
    config["custom_fields"] = {"case": title, "source": f"{mapping.get('system', '?')}:export"}
    eng = ca.CognitiveAuditEngine(acct, config)
    eng.set_clock(FIXED_CLOCK)
    eng.load_core_plugins()
    report = eng.audit(ctx, save_log=True, log_dir=os.path.join(ROOT, "logs"))
    analysis = report["analysis"]

    print(f"\n[3/4] 引擎裁定（SPE {report.get('spe_version', '?')}）:")
    st = analysis.get("ACC", {})
    verdict = st.get("verdict", {})
    print(f"      ACC Level  : {verdict.get('level')}")
    print(f"      ACC Summary: {verdict.get('summary')}")
    for h in verdict.get("halt_items", []):
        print(f"        [HALT] {h}")
    for w in verdict.get("warn_items", []):
        print(f"        [WARN] {w}")
    ns = analysis.get("NS", {})
    iap = analysis.get("IAP", {})
    lch = analysis.get("LCH", {})
    print(f"      NS 叙事剥离   : pass={ns.get('pass')} violations={ns.get('violation_count')}")
    print(f"      IAP 内隐假设  : {len(iap.get('flags', []))} 个 flag")
    print(f"      LCH 脆弱性    : system_delta_d={lch.get('system_delta_d')}")
    rc = analysis.get("RESPONSIBILITY_CLOSURE")
    if rc:
        print(f"      责任闭环      : {rc.get('status')} —— {rc.get('message')}")
        print("      （用 --owner 指定责任人后重跑即可闭环）")
    else:
        print(f"      责任闭环      : closed（owner={args.owner}）")

    print(f"\n[4/4] 凭据:")
    cert = st.get("certificate", {})
    print(f"      audit_id  : {cert.get('audit_id')}")
    print(f"      signature : {cert.get('signature')}")
    print(f"      nonce     : {acct.nonce}（由责任账户推导，固定可复现）")
    v = eng.verify_chain()
    print(f"      chain_root: {report.get('chain_root_hash')}")
    print(f"      verify    : valid={v.get('valid')} events={v.get('total')}")
    log_path = report.get("log_path")
    print(f"      log       : {os.path.relpath(log_path, ROOT) if log_path else '(未落盘)'}")
    print("\n完成。同一材料 + 同一责任账户 + 固定时钟 => 链根逐字节可复现。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
