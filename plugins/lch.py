"""
LCH — Fragility Latch Plugin
============================

脆弱性对冲：定位逻辑链中最脆弱的隐性变量 A。
计算当 非A（变量缺失或失效）发生时，整体决策的崩塌概率 Delta D。

命名对照
--------
代码标识是 LCH / FragilityLatchPlugin（脆弱性*闩锁*，见 README-zh.md 表格），
本算子的中文职责名是「脆弱性*对冲*」，引擎侧函数名是 _assess_vulnerability。
三者指同一个算子，检索时三种拼写都试。

输入契约（decision_context 中本算子读取的键，全部可选）
------------------------------------------------
  assumptions   list[str]   别名 premises / hypotheses / core_assumptions
                             待审计的前提 A1..An；也接受单个字符串
  dependencies  dict        别名 dependency_graph / deps
                             {"A1": ["A2","A3"]} 表示 A1 依赖 A2、A3
  branches      list[dict]  别名 branch_responses / failure_paths / delta_d
                             [{"assumption": "A1", "delta_d": "回滚上一版本"}]
                             语义是「若 A1 失效，则执行 ΔD」

全部缺失时不报错、不猜测，直接返回 _empty_result()。

Delta D 计算式
--------------
  Delta D = 0.30                 基础值：一个尚无任何信息的前提
          + 0.30   若无分支响应   ¬A 成立时没有回退路径
          - 0.10   若有分支响应   回退路径的存在本身就是减损
          + 0.15 × N              N = 被它支撑的前提个数；它失效则下游同时失效
          + 0.10 × M              M = 模糊限定词个数（可能/大概/应该/通常…）
          + 0.25   若不可证伪     总是/永远/必然 一类表述，失效时无预警手段
  最后 clamp 到 [0, 1]

阈值 0.7 的来历
----------------
最常见的失效组合「无分支响应 + 不可证伪」= 0.30+0.30+0.25 = 0.85 > 0.7，
判不通过（pass=False）。若已有分支响应，则为 0.30-0.10+0.25 = 0.45 < 0.7。
也就是说这条线实质上在区分一件事：**为这个前提有没有准备回退路径**。

这些权重是确定性常数，不是概率估计，也没有经过统计拟合。
改动权重会直接改变判定结果，属设计变更而非参数调优。

输出：
  - 脆弱变量列表（按 Delta D 降序）
  - 每个变量的依赖链路径
  - 崩塌场景描述

确定性 · 零随机 · 零 LLM 调用
"""

from typing import Dict, Any, List


class FragilityLatchPlugin:
    """LCH 算子：脆弱性对冲。"""

    PLUGIN_NAME = "LCH"
    PLUGIN_VERSION = "1.0.0"
    PLUGIN_DESCRIPTION = "Fragility Latch — 定位最脆弱变量，计算崩塌概率 Delta D"

    def __init__(self):
        self.name = self.PLUGIN_NAME

    # ── main entry ──
    def analyze(self, decision_context: Dict[str, Any]) -> Dict[str, Any]:
        assumptions = self._extract_assumptions(decision_context)
        dependencies = self._extract_dependencies(decision_context)
        branches = self._extract_branches(decision_context)

        if not assumptions:
            return self._empty_result()

        # 为每个前提计算脆弱性
        fragility_report: List[Dict[str, Any]] = []
        for i, assumption in enumerate(assumptions):
            frag = self._assess_fragility(
                assumption=assumption,
                index=i,
                assumptions=assumptions,
                dependencies=dependencies,
                branches=branches,
            )
            fragility_report.append(frag)

        # 按 Delta D 降序
        fragility_report.sort(key=lambda x: x["delta_d"], reverse=True)

        # 最脆弱变量
        weakest = fragility_report[0] if fragility_report else None
        system_delta_d = max((f["delta_d"] for f in fragility_report), default=0.0)

        return {
            "plugin": self.PLUGIN_NAME,
            "version": self.PLUGIN_VERSION,
            "assumptions_audited": len(assumptions),
            "fragility_report": fragility_report,
            "weakest_variable": weakest,
            "system_delta_d": round(system_delta_d, 4),
            "has_branch_coverage": self._check_branch_coverage(assumptions, branches),
            "pass": system_delta_d < 0.7 and self._check_branch_coverage(assumptions, branches),
        }

    # ── internals ──

    @staticmethod
    def _extract_assumptions(ctx: Dict[str, Any]) -> List[str]:
        if isinstance(ctx, dict):
            for key in ("assumptions", "premises", "hypotheses", "core_assumptions"):
                val = ctx.get(key)
                if isinstance(val, list):
                    return [str(a) for a in val if a]
                if isinstance(val, str):
                    return [val] if val.strip() else []
        return []

    @staticmethod
    def _extract_dependencies(ctx: Dict[str, Any]) -> Dict[str, List[str]]:
        """提取依赖关系图。格式: {"A": ["B", "C"]} 表示 A 依赖 B 和 C。"""
        if isinstance(ctx, dict):
            for key in ("dependencies", "dependency_graph", "deps"):
                val = ctx.get(key)
                if isinstance(val, dict):
                    return {str(k): [str(v) for v in vs] for k, vs in val.items()}
        return {}

    @staticmethod
    def _extract_branches(ctx: Dict[str, Any]) -> List[Dict[str, Any]]:
        """提取分支响应。格式: [{"assumption": "A1", "delta_d": "ΔD1"}]"""
        if isinstance(ctx, dict):
            for key in ("branches", "branch_responses", "failure_paths", "delta_d"):
                val = ctx.get(key)
                if isinstance(val, list):
                    return val if all(isinstance(v, dict) for v in val) else []
        return []

    @staticmethod
    def _assess_fragility(
        assumption: str,
        index: int,
        assumptions: List[str],
        dependencies: Dict[str, List[str]],
        branches: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """评估单个前提的脆弱性。"""
        # 因素 0：基础值。假定这条前提本身成立，但尚不知道它是否有回退路径，
        # 也不做任何有利假设，因此给一个中等偏上的起点。
        delta_d = 0.3  # 基础值

        # 因素 1：分支响应（ΔD）是否存在。
        # 这是权重最大的一项（±0.3），因为「假设失效时有没有退路」
        # 直接决定崩塌是系统性的还是可收敛的。
        # 匹配同时接受两种写法：写全称文本，或写编号 A1/A2/…
        has_branch = any(
            b.get("assumption", b.get("premise", "")) == assumption
            or b.get("assumption", b.get("premise", "")) == f"A{index+1}"
            for b in branches
        )
        if not has_branch:
            delta_d += 0.3
        else:
            delta_d -= 0.1

        # 因素 2：依赖图的入度。它被多少条前提支撑？
        # 入度越高越是关键节点——它一失效，下游成片失效。
        # 0.15/个 的设定使「被 3 条依赖」时该项累计 +0.45，
        # 足以单独把一个本来合格的前提推过 0.7 阈值。
        dependents = [
            a for a, deps in dependencies.items()
            if assumption in deps or f"A{index+1}" in deps
        ]
        if dependents:
            delta_d += 0.15 * len(dependents)

        # 因素 3：模糊限定词。中英各 8 个，可叠加计数。
        # 「需求大概稳定」比「需求稳定」多 0.1——
        # 限定词越多，前提越难被证伪，也就越难及时发现它已失效。
        vague_markers = ["可能", "大概", "也许", "或许", "通常", "一般", "应该",
                         "maybe", "probably", "usually", "generally", "should"]
        lower_assumption = assumption.lower() if isinstance(assumption, str) else ""
        vague_count = sum(1 for m in vague_markers if m in lower_assumption)
        delta_d += 0.1 * vague_count

        # 因素 4：不可证伪表述。这是与前几项性质不同的一类风险——
        # 前几项是「失效了会怎样」，这一项是「失效了你也不会知道」。
        # 没有检测手段的假设，即使后果不严重，也应按高脆弱处理。
        if not FragilityLatchPlugin._is_falsifiable(assumption):
            delta_d += 0.25

        # 各项叠加可能越界，统一夹到 [0, 1]：
        # Delta D 是概率量，超出该区间的值没有意义，也会破坏下游比较。
        delta_d = max(0.0, min(1.0, delta_d))

        return {
            "assumption": assumption,
            "index": index,
            "delta_d": round(delta_d, 4),
            "has_branch_response": has_branch,
            "dependents": dependents,
            "is_falsifiable": FragilityLatchPlugin._is_falsifiable(assumption),
            "vague_markers_found": vague_count,
            "failure_scenario": f"若 非A{index+1} 成立（'{assumption[:40]}' 失效），"
                                f"决策崩塌概率 Delta D = {delta_d:.2f}",
        }

    @staticmethod
    def _is_falsifiable(assumption: str) -> bool:
        """检查前提是否可证伪。"""
        if not isinstance(assumption, str) or not assumption.strip():
            return False
        # 不可证伪的标志
        non_falsifiable = ["总是", "永远", "从不", "必然", "绝对",
                            "always", "never", "inevitably", "absolutely"]
        lower = assumption.lower()
        return not any(m in lower for m in non_falsifiable)

    @staticmethod
    def _check_branch_coverage(assumptions: List[str], branches: List[Dict[str, Any]]) -> bool:
        """检查是否所有前提都有对应的分支响应。"""
        if not assumptions:
            return True
        branch_targets = set()
        for b in branches:
            for key in ("assumption", "premise", "target"):
                val = b.get(key)
                if val:
                    branch_targets.add(str(val))
        covered = sum(1 for i, a in enumerate(assumptions)
                      if a in branch_targets or f"A{i+1}" in branch_targets)
        return covered == len(assumptions)

    @staticmethod
    def _empty_result() -> Dict[str, Any]:
        return {
            "plugin": "LCH",
            "version": "1.0.0",
            "assumptions_audited": 0,
            "fragility_report": [],
            "weakest_variable": None,
            "system_delta_d": 0.0,
            "has_branch_coverage": True,
            "pass": True,
            "note": "No assumptions found to assess fragility.",
        }
