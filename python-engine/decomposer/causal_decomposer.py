"""Local, offline second-person causal decomposer.

Implements the GCAE paradigm (README):
  A valid decision = Decision (D) + Core Assumptions (A) + Branch Response (ΔD)
  Formal: ¬A ⇒ ΔD

This module is intentionally dependency-free and runs fully offline so the
core audit preserves the engine's neutral / privacy-first identity. The
heuristics here are a v0 baseline; they can be upgraded without touching
the IMDA-verified contract (input JSON -> structured report).
"""
import re
import uuid
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List

UNCERTAINTY_MARKERS = [
    "假设", "假定", "如果", "若", "依赖", "需要", "必须", "应当", "可能", "大概",
    "assume", "assuming", "if", "depends", "requires", "must", "should", "may",
    "likely", "suppose", "given", "provided",
]
DISCRIMINATORY = [
    "种族", "性别", "宗教", "残疾", "年龄歧视",
    "race", "gender", "religion", "disability", "ageism",
]
LOGICAL_JUMP_MARKERS = ["undefined", "未定义", "unknown symbol", "does not exist"]


@dataclass
class ResponsibilityAccount:
    organization: str = "local-audit"
    role: str = "causal-decomposer"
    stage: str = "local-offline"
    nonce: str = field(default_factory=lambda: uuid.uuid4().hex[:8])


class CausalDecomposer:
    def __init__(self, strictness: str = "standard"):
        self.strictness = strictness

    def audit(self, context: Dict[str, Any]) -> Dict[str, Any]:
        decision = (context.get("decision") or "").strip()
        surrounding = (context.get("context") or "").strip()
        metadata = context.get("metadata") or {}
        source = metadata.get("source", "unknown")

        if not decision:
            return {"error": "empty decision", "verdict": False}

        assumptions = self._extract_assumptions(decision, surrounding, source)
        branches = self._build_branches(assumptions)
        scores = self._score(decision, assumptions, surrounding)
        verdict = self._verdict(scores)

        account = ResponsibilityAccount()
        report = {
            "disclaimer": "本审计仅做决策结构核查，不参与决策制定，不对执行结果负责。",
            "responsibility_account": asdict(account),
            "decision": {"D": decision},
            "assumptions": [{"id": a["id"], "text": a["text"]} for a in assumptions],
            "branch_logic": [
                {"if": f"¬{b['id']}", "then": "ΔD", "response": b["response"]}
                for b in branches
            ],
            "imda_scores": scores,
            "overall_score": scores["overall"],
            "verdict": verdict,
            "source": source,
        }
        return report

    def _extract_assumptions(self, decision, surrounding, source) -> List[Dict[str, Any]]:
        found: List[Dict[str, Any]] = []
        low = (decision + "\n" + surrounding).lower()
        for m in UNCERTAINTY_MARKERS:
            if m.lower() in low:
                found.append({
                    "id": f"A{len(found) + 1}",
                    "text": f"表述中隐含前提涉及「{m}」相关条件，需显式成立",
                    "kind": "linguistic",
                })
        if source in ("completion", "refactor"):
            if re.search(r"\w+\(", decision):
                found.append({"id": f"A{len(found) + 1}", "text": "被调用符号 / API 已定义且可用", "kind": "structural"})
            if re.search(r"(import|require|from)\s", decision):
                found.append({"id": f"A{len(found) + 1}", "text": "所依赖模块 / 依赖已安装且版本兼容", "kind": "structural"})
            if re.search(r"(input|argv|args|request)\b", low):
                found.append({"id": f"A{len(found) + 1}", "text": "外部输入已校验且非空 / 合法", "kind": "structural"})
        if not found:
            found.append({"id": "A1", "text": "决策所依据的环境 / 前提保持稳定", "kind": "default"})
        return found

    def _build_branches(self, assumptions) -> List[Dict[str, Any]]:
        branches = []
        for a in assumptions:
            branches.append({
                "id": a["id"],
                "response": (
                    f"若 ¬{a['id']}（{a['text']} 不成立），则回退 / 修正："
                    f"补充该前提的验证或选择替代方案，并重新审计。"
                ),
            })
        return branches

    def _score(self, decision, assumptions, surrounding) -> Dict[str, Any]:
        n = len(assumptions)
        interpretability = min(100, 60 + 10 * min(n, 4))
        jumps = sum(1 for j in LOGICAL_JUMP_MARKERS if j in (decision + surrounding).lower())
        robustness = max(0, min(100, 70 + 8 * min(n, 3) - 20 * jumps))
        accountability = 96
        disc = sum(1 for d in DISCRIMINATORY if d in (decision + surrounding).lower())
        inclusiveness = max(0, 100 - 10 * disc)
        overall = round((interpretability + robustness + accountability + inclusiveness) / 4, 1)
        return {
            "interpretability": interpretability,
            "robustness": robustness,
            "accountability": accountability,
            "inclusiveness": inclusiveness,
            "overall": overall,
        }

    def _verdict(self, scores) -> bool:
        threshold = {"lenient": 50, "standard": 70, "strict": 85}.get(self.strictness, 70)
        return scores["robustness"] >= threshold and scores["interpretability"] >= 50
