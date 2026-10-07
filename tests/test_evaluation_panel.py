"""Tests for the evaluation panel layer (module B, v0.6)."""

import pytest

from second_perspective.evaluation.panel import (
    EthicsReviewCase,
    EthicsStatus,
    ExpertScore,
    ExpertScoreSet,
    InMemoryEthicsReview,
    ScoreSetError,
    aggregate_by_dimension,
    kappa_metric_result,
)


def _agree_scores():
    return [
        ExpertScore("I1", "E1", "quality", 1),
        ExpertScore("I1", "E2", "quality", 1),
        ExpertScore("I1", "E3", "quality", 1),
        ExpertScore("I2", "E1", "quality", 1),
        ExpertScore("I2", "E2", "quality", 1),
        ExpertScore("I2", "E3", "quality", 1),
    ]


def _disagree_scores():
    return [
        ExpertScore("I1", "E1", "quality", 1),
        ExpertScore("I1", "E2", "quality", 2),
        ExpertScore("I1", "E3", "quality", 3),
        ExpertScore("I2", "E1", "quality", 2),
        ExpertScore("I2", "E2", "quality", 3),
        ExpertScore("I2", "E3", "quality", 1),
    ]


class TestAggregation:
    def test_kappa_metric_result_passes_on_agreement(self):
        r = kappa_metric_result(_agree_scores())
        assert r.metric_id == "fleiss_kappa"
        assert r.value == pytest.approx(1.0)
        assert r.passed is True

    def test_kappa_metric_result_fails_on_disagreement(self):
        r = kappa_metric_result(_disagree_scores())
        assert r.value == pytest.approx(-0.5)
        assert r.passed is False

    def test_aggregate_by_dimension(self):
        scores = _agree_scores() + [
            ExpertScore("J1", "E1", "safety", 1),
            ExpertScore("J1", "E2", "safety", 1),
            ExpertScore("J1", "E3", "safety", 1),
        ]
        by_dim = aggregate_by_dimension(scores)
        assert set(by_dim) == {"quality", "safety"}
        assert by_dim["safety"].n_items == 1
        assert by_dim["quality"].n_items == 2

    def test_feeds_measurement_control_pack(self):
        from second_perspective.evaluation.measurement import (
            default_dimension_packs,
        )

        pack = next(
            p for p in default_dimension_packs() if p.id == "methodology-control"
        )
        bad = kappa_metric_result(_disagree_scores())
        assert pack.evaluate({"fleiss_kappa": bad}) != []
        good = kappa_metric_result(_agree_scores())
        assert pack.evaluate({"fleiss_kappa": good}) == []


class TestScoreSet:
    def _payload(self):
        return {
            "id": "panel-2026",
            "version": "1.0",
            "scores": [
                {"item_id": "I1", "expert_id": "E1", "dimension": "quality", "score": 1},
                {"item_id": "I1", "expert_id": "E2", "dimension": "quality", "score": 2},
            ],
        }

    def test_len_and_digest_stable(self):
        s1 = ExpertScoreSet.from_dict(self._payload())
        s2 = ExpertScoreSet.from_dict(self._payload())
        assert len(s1) == 2
        assert s1.digest() == s2.digest()

    def test_digest_version_sensitive(self):
        s1 = ExpertScoreSet.from_dict(self._payload())
        p = self._payload()
        p["version"] = "1.1"
        assert ExpertScoreSet.from_dict(p).digest() != s1.digest()

    def test_roundtrip(self):
        s = ExpertScoreSet.from_dict(self._payload())
        again = ExpertScoreSet.from_dict(s.to_dict())
        assert again.scores == s.scores

    def test_agreement_helper(self):
        s = ExpertScoreSet(
            id="x", version="1", scores=_agree_scores()
        )
        assert s.agreement().meets_threshold is True

    def test_bad_payload_rejected(self):
        with pytest.raises(ScoreSetError):
            ExpertScoreSet.from_dict({"id": "x"})
        with pytest.raises(ScoreSetError):
            ExpertScoreSet.from_json("{not json")


class TestEthicsReview:
    def test_legal_path_records_history(self):
        wf = InMemoryEthicsReview()
        wf.open(EthicsReviewCase("C1", "model-x", "data provenance concern"))
        wf.advance("C1", EthicsStatus.UNDER_REVIEW, reviewer="r1")
        wf.advance("C1", EthicsStatus.APPROVED, reviewer="r2", note="ok")
        case = wf.get("C1")
        assert case.status is EthicsStatus.APPROVED
        assert case.reviewers == ["r1", "r2"]
        assert case.decision_note == "ok"
        assert case.history[0]["from"] == "PENDING"
        assert case.history[1]["from"] == "UNDER_REVIEW"

    def test_illegal_transition_raises(self):
        wf = InMemoryEthicsReview()
        wf.open(EthicsReviewCase("C1", "model-x", "concern"))
        with pytest.raises(ValueError):
            wf.advance("C1", EthicsStatus.APPROVED)

    def test_terminal_state_blocks_further_moves(self):
        wf = InMemoryEthicsReview()
        wf.open(EthicsReviewCase("C1", "model-x", "concern"))
        wf.advance("C1", EthicsStatus.UNDER_REVIEW)
        wf.advance("C1", EthicsStatus.REJECTED)
        with pytest.raises(ValueError):
            wf.advance("C1", EthicsStatus.APPROVED)

    def test_duplicate_open_rejected(self):
        wf = InMemoryEthicsReview()
        wf.open(EthicsReviewCase("C1", "model-x", "concern"))
        with pytest.raises(ValueError):
            wf.open(EthicsReviewCase("C1", "model-y", "other"))

    def test_unknown_case(self):
        wf = InMemoryEthicsReview()
        with pytest.raises(KeyError):
            wf.advance("nope", EthicsStatus.UNDER_REVIEW)
