# -*- coding: utf-8 -*-
"""⊛∞ 自主进化层：只提案、不适用；人工裁决只记账、不改代码。

这三条恒等式是「自主进化不摧毁可复现性」的全部依靠，必须由断言钉死：
    result.auto_applied                   恒 0
    result.requires_human                 恒 True
    candidate.applies_automatically       恒 False
"""

from __future__ import annotations

import pytest

from second_perspective.audit.cognitive import ResponsibilityAccount
from second_perspective.audit.cognitive.adapter import (
    ADAPTER_BASE_OPERATORS,
    build_gcae_context,
)
from second_perspective.audit.cognitive.engine import CognitiveAuditEngine


def _engine() -> CognitiveAuditEngine:
    eng = CognitiveAuditEngine(
        account=ResponsibilityAccount(
            organization="ACME", role="CFO", stage="post_decision"),
        config={},
    )
    for cls in ADAPTER_BASE_OPERATORS:
        eng.register_plugin(cls())
    return eng


def test_evolve_never_applies_anything(make_request, make_result):
    eng = _engine()
    out = eng.evolve(build_gcae_context(make_request(), make_result()), max_loops=3)

    assert out["auto_applied"] == 0
    assert out["requires_human"] is True
    assert all(p["applies_automatically"] is False for p in out["proposals"])
    assert all(p["requires_human"] is True for p in out["proposals"])
    # 候选只提方向，不给裁决
    assert all(p["status"] == "PROPOSED" for p in out["proposals"])


def test_evolve_reports_lineage_and_entropy(make_request, make_result):
    eng = _engine()
    out = eng.evolve(build_gcae_context(make_request(), make_result()), max_loops=3)

    lineage = out["lineage"]
    assert lineage["operator_set_hash"], "算子集指纹必须入谱系，否则代际不可自证"
    assert lineage["generation"] == 0
    # 天道：A10 有界，使演化收敛于 S*
    assert out["audit_entropy"]["bounded"] is True
    assert out["audit_entropy"]["a10"] <= out["audit_entropy"]["ceiling"]
    # 停机判据始终是图同构，不是「跑够了」
    assert out["fixed_point"]["criterion"] == "g_{n+1} == g_n（图同构判定）"


def test_evolve_records_on_chain(make_request, make_result):
    eng = _engine()
    assert eng.chain_root_hash == "ROOT"
    out = eng.evolve(build_gcae_context(make_request(), make_result()), max_loops=2)
    assert eng.chain_root_hash != "ROOT"
    assert out["session_root_hash"] == eng.chain_root_hash


def test_empty_delta_is_blocked_not_silently_skipped(make_request, make_result):
    """空 delta = 无效批准，必须阻断而不是静默跳过。"""
    eng = _engine()
    out = eng.evolve(
        build_gcae_context(make_request(), make_result()),
        approved_deltas=[{}],
        max_loops=3,
    )
    assert out["verdict"] == "BLOCKED"


def test_approval_only_records_generation(make_request, make_result):
    """人工裁决升代际，但不改代码 —— 改代码必须由人做。"""
    eng = _engine()
    eng.evolve(build_gcae_context(make_request(), make_result()), max_loops=2)

    before = eng.evolution_lineage()
    assert before["generation"] == 0

    result = eng.approve_evolution_proposal(
        {"id": "EVO-TEST01", "code": "CCS:counterfactual"}, approved_by="CFO/张三")

    assert result["applied_to_code"] is False
    assert result["requires_code_change"] is True
    assert result["approved"]["approved_by"] == "CFO/张三"
    # 代际升 1，且谱系哈希随之改变
    assert result["lineage"]["generation"] == 1
    assert result["lineage"]["lineage_hash"] != before["lineage_hash"]
    # 批准记录进链，可复核
    assert any(e.event_type == "EVOLUTION_APPROVED" for e in eng.event_chain)


def test_approval_requires_id_and_signature(make_request, make_result):
    eng = _engine()
    with pytest.raises(ValueError):
        eng.approve_evolution_proposal({}, approved_by="CFO/张三")
    with pytest.raises(ValueError):
        eng.approve_evolution_proposal({"id": "EVO-X"}, approved_by="  ")


def test_evolve_rejects_bad_thresholds(make_request, make_result):
    eng = _engine()
    ctx = build_gcae_context(make_request(), make_result())
    with pytest.raises(ValueError):
        eng.evolve(ctx, gap_threshold=0)
    with pytest.raises(ValueError):
        eng.evolve(ctx, max_loops=0)
