"""Tests for the evaluation layer (v0.6).

Covers:
  - measurement metrics (numeric correctness + error handling)
  - versioned corpus loading, hashing and deterministic sampling
  - per-dimension control packs (threshold -> DomainViolation)
  - expert panel agreement aggregation
"""

import pytest

from second_perspective.domain.base import DomainPackRegistry, DomainViolation
from second_perspective.evaluation.measurement import (
    Corpus,
    CorpusError,
    MeasurementControlPack,
    MetricError,
    MetricResult,
    MetricThreshold,
    default_dimension_packs,
    register_dimension_packs,
)
from second_perspective.evaluation.measurement.metrics import (
    attack_success_rate,
    brier_score,
    cost_per_task,
    expected_calibration_error,
    fleiss_kappa,
    percentile,
    time_per_output_token,
    token_metering_error,
    tokens_per_second,
    ttft_p99,
)
from second_perspective.evaluation.panel import (
    ExpertScore,
    aggregate_panel_agreement,
)


# ── metrics ───────────────────────────────────────────────────────────


class TestMetrics:
    def test_asr(self):
        r = attack_success_rate([True, False, True, True])
        assert r.metric_id == "asr"
        assert r.value == pytest.approx(0.75)
        assert r.n == 4
        assert r.meta["successes"] == 3

    def test_brier(self):
        r = brier_score([0.9, 0.1], [1, 0])
        assert r.value == pytest.approx(0.01)

    def test_ece(self):
        r = expected_calibration_error([0.9, 0.9], [1, 0], n_bins=10)
        assert r.value == pytest.approx(0.4)

    def test_percentile_interpolates(self):
        assert percentile([10, 20, 30, 40], 50) == pytest.approx(25.0)

    def test_ttft_p99(self):
        r = ttft_p99([100, 200, 300, 400, 500])
        assert r.unit == "ms"
        assert r.value == pytest.approx(496.0)

    def test_tpot(self):
        r = time_per_output_token(100, 2.0)
        assert r.value == pytest.approx(0.02)

    def test_tps(self):
        r = tokens_per_second(1000, 10)
        assert r.value == pytest.approx(100.0)

    def test_cost_per_task(self):
        r = cost_per_task(100.0, 50)
        assert r.value == pytest.approx(2.0)

    def test_token_metering_error(self):
        r = token_metering_error(105, 100)
        assert r.value == pytest.approx(0.05)

    def test_fleiss_perfect_agreement(self):
        # every item rated identically by all three raters -> perfect agreement
        r = fleiss_kappa([[1, 1, 1], [2, 2, 2]])
        assert r.value == pytest.approx(1.0)

    def test_fleiss_no_agreement(self):
        # each item's three raters land in three different categories
        r = fleiss_kappa([[1, 2, 3], [2, 3, 1], [3, 1, 2]])
        assert r.value == pytest.approx(-0.5)

    @pytest.mark.parametrize(
        "fn,args",
        [
            (attack_success_rate, ([],)),
            (brier_score, ([], [])),
            (expected_calibration_error, ([0.5], [0, 1])),
            (percentile, ([], 50)),
            (ttft_p99, ([],)),
            (time_per_output_token, (0, 1.0)),
            (tokens_per_second, (100, 0)),
            (cost_per_task, (10.0, 0)),
            (token_metering_error, (10, 0)),
            (fleiss_kappa, ([[1]],)),
        ],
    )
    def test_metric_errors(self, fn, args):
        with pytest.raises(MetricError):
            fn(*args)


# ── corpus ────────────────────────────────────────────────────────────


class TestCorpus:
    def _payload(self):
        return {
            "id": "jailbreak-suite",
            "version": "2026.1",
            "lang": "en",
            "items": [
                {"id": "P1", "payload": {"prompt": "a"}, "labels": {"kind": "harmful"}},
                {"id": "P2", "payload": {"prompt": "b"}, "labels": {"kind": "benign"}},
                {"id": "P3", "payload": {"prompt": "c"}, "labels": {"kind": "harmful"}},
                {"id": "P4", "payload": {"prompt": "d"}, "labels": {"kind": "benign"}},
            ],
        }

    def test_from_dict_and_len(self):
        c = Corpus.from_dict(self._payload())
        assert len(c) == 4
        assert c.id == "jailbreak-suite"

    def test_digest_is_stable_and_version_sensitive(self):
        c1 = Corpus.from_dict(self._payload())
        c2 = Corpus.from_dict(self._payload())
        assert c1.digest() == c2.digest()
        p = self._payload()
        p["version"] = "2026.2"
        assert Corpus.from_dict(p).digest() != c1.digest()

    def test_sample_is_deterministic(self):
        c = Corpus.from_dict(self._payload())
        a = [it.id for it in c.sample(2, seed=7)]
        b = [it.id for it in c.sample(2, seed=7)]
        assert a == b
        assert len(a) == 2

    def test_sample_full_when_n_ge_len(self):
        c = Corpus.from_dict(self._payload())
        assert len(c.sample(99, seed=0)) == 4

    def test_filter_by_label(self):
        c = Corpus.from_dict(self._payload())
        harmful = c.filter(kind="harmful")
        assert len(harmful) == 2
        assert all(it.labels["kind"] == "harmful" for it in harmful.items)

    def test_duplicate_id_rejected(self):
        p = self._payload()
        p["items"].append({"id": "P1", "payload": {}})
        with pytest.raises(CorpusError):
            Corpus.from_dict(p)

    def test_bad_json_rejected(self):
        with pytest.raises(CorpusError):
            Corpus.from_json("{not json")


# ── dimension packs ───────────────────────────────────────────────────


class TestDimensionPacks:
    def test_quality_pack_flags_high_ece(self):
        pack = next(
            p for p in default_dimension_packs()
            if p.id == "quality-reliability-control"
        )
        results = {"ece": MetricResult("ece", 0.25, unit="score", n=10)}
        violations = pack.evaluate(results)
        assert len(violations) == 1
        v = violations[0]
        assert isinstance(v, DomainViolation)
        assert v.code == "QUAL_ECE_HIGH"
        assert v.severity == "error"
        assert v.pack_id == pack.id

    def test_quality_pack_passes_good_ece(self):
        pack = next(
            p for p in default_dimension_packs()
            if p.id == "quality-reliability-control"
        )
        results = {"ece": MetricResult("ece", 0.05, unit="score", n=10)}
        assert pack.evaluate(results) == []

    def test_methodology_pack_kappa_gate(self):
        pack = next(
            p for p in default_dimension_packs() if p.id == "methodology-control"
        )
        assert pack.evaluate({"fleiss_kappa": MetricResult("fleiss_kappa", 0.5)}) != []
        assert pack.evaluate({"fleiss_kappa": MetricResult("fleiss_kappa", 0.8)}) == []

    def test_missing_metric_is_not_a_violation(self):
        pack = next(
            p for p in default_dimension_packs() if p.id == "methodology-control"
        )
        assert pack.evaluate({}) == []

    def test_validate_adapter_reads_measurement_results(self):
        pack = next(
            p for p in default_dimension_packs() if p.id == "methodology-control"
        )
        req = {"measurement_results": {"fleiss_kappa": MetricResult("fleiss_kappa", 0.4)}}
        assert len(pack.validate(req)) == 1
        assert pack.validate({}) == []

    def test_register_into_registry(self):
        reg = DomainPackRegistry()
        ids = register_dimension_packs(reg)
        assert len(ids) == len(default_dimension_packs())
        assert {p.id for p in reg.all()} == set(ids)

    def test_threshold_ops(self):
        th = MetricThreshold("asr", "<=", 0.05)
        assert th.satisfies(0.05)
        assert not th.satisfies(0.06)
        with pytest.raises(ValueError):
            MetricThreshold("asr", "~~", 1).satisfies(0.5)


# ── expert panel ──────────────────────────────────────────────────────


class TestPanel:
    def test_perfect_agreement(self):
        scores = [
            ExpertScore("I1", "E1", "domain", 1),
            ExpertScore("I1", "E2", "domain", 1),
            ExpertScore("I1", "E3", "domain", 1),
            ExpertScore("I2", "E1", "domain", 1),
            ExpertScore("I2", "E2", "domain", 1),
            ExpertScore("I2", "E3", "domain", 1),
        ]
        ag = aggregate_panel_agreement(scores)
        assert ag.kappa == pytest.approx(1.0)
        assert ag.meets_threshold is True
        assert ag.n_experts == 3

    def test_disagreement_fails_threshold(self):
        scores = [
            ExpertScore("I1", "E1", "domain", 1),
            ExpertScore("I1", "E2", "domain", 2),
            ExpertScore("I1", "E3", "domain", 3),
            ExpertScore("I2", "E1", "domain", 2),
            ExpertScore("I2", "E2", "domain", 3),
            ExpertScore("I2", "E3", "domain", 1),
            ExpertScore("I3", "E1", "domain", 3),
            ExpertScore("I3", "E2", "domain", 1),
            ExpertScore("I3", "E3", "domain", 2),
        ]
        ag = aggregate_panel_agreement(scores)
        assert ag.kappa == pytest.approx(-0.5)
        assert ag.meets_threshold is False

    def test_empty_scores_rejected(self):
        with pytest.raises(ValueError):
            aggregate_panel_agreement([])
