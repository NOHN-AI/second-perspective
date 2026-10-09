# -*- coding: utf-8 -*-
"""条件注册：声明了原点/灰度阶梯才审。

这两条是本次契约扩展的核心语义，必须被断言钉住：
  1. 未声明 → 对应算子不注册，且不产生「每次审计都阻断」的永真真空；
  2. 已声明 → 对应算子参与，并且真的读到了我们喂进去的值。
"""

from __future__ import annotations

from second_perspective.audit.cognitive.adapter import run_gcae_audit
from second_perspective.models.schemas import (
    DecisionOrigin,
    DecisionRollout,
    ResourceBudget,
    RolloutStage,
)


def _analysis(request, result) -> dict:
    _, raw = run_gcae_audit(request, result)
    return raw["analysis"]


def test_without_origin_ori_is_not_registered(make_request, make_result):
    analysis = _analysis(make_request(), make_result())
    assert "ORI" not in analysis
    # 关键：不能因为「没声明原点」就把整次审计顶到阻断
    assert analysis["STATE"]["verdict"]["level"] != "AUDIT_HALT"
    assert analysis["STATE"]["verdict"]["halt_items"] == []


def test_with_origin_ori_engages_and_anchors(make_request, make_result):
    request = make_request().model_copy(update={"origin": DecisionOrigin(
        trigger="2026 Q3 预算超支 12%，触发成本削减决策",
        source="财务部",
        resources=[ResourceBudget(name="预算额度", budget=100.0, used=40.0, unit="万元")],
    )})
    analysis = _analysis(request, make_result())

    assert "ORI" in analysis
    ori = analysis["ORI"]
    assert ori["status"] == "PASS", ori
    assert ori["origin_hash"], "原点已声明就必须锚定出 origin_hash"
    assert ori["resource_ledger"][0]["gap"] == 60.0


def test_origin_with_negative_gap_is_flagged(make_request, make_result):
    """资源缺口为负 = 能量守恒被违反，必须被 ORI 抓住而不是放过。"""
    request = make_request().model_copy(update={"origin": DecisionOrigin(
        trigger="Q4 追加预算申请",
        resources=[ResourceBudget(name="预算额度", budget=50.0, used=80.0)],
    )})
    ori = _analysis(request, make_result())["ORI"]
    assert ori["status"] != "PASS"
    assert ori["resource_gap_total"] == -30.0


def test_without_rollout_grf_is_not_registered(make_request, make_result):
    assert "GRF" not in _analysis(make_request(), make_result())


def test_with_rollout_grf_engages(make_request, make_result):
    request = make_request().model_copy(update={"rollout": DecisionRollout(
        stages=[
            RolloutStage(name="试点", ratio=0.05),
            RolloutStage(name="分批", ratio=0.25),
            RolloutStage(name="全量", ratio=1.0),
        ],
        current_ratio=0.05,
    )})
    analysis = _analysis(request, make_result())

    assert "GRF" in analysis
    assert analysis["GRF"]["gray_levels"] == [0.05, 0.25, 1.0]


def test_origin_and_rollout_are_independent(make_request, make_result):
    """两者互不牵连：只声明其中一个时，另一个仍然不注册。"""
    only_origin = make_request().model_copy(
        update={"origin": DecisionOrigin(trigger="客户投诉升级")})
    only_rollout = make_request().model_copy(
        update={"rollout": DecisionRollout(stages=[RolloutStage(name="全量", ratio=1.0)])})

    a = _analysis(only_origin, make_result())
    b = _analysis(only_rollout, make_result())
    assert "ORI" in a and "GRF" not in a
    assert "GRF" in b and "ORI" not in b
