"""Tests for the evaluation operations layer (module C, v0.6)."""

import json
from datetime import datetime, timedelta, timezone

import pytest

from second_perspective.evaluation.operations import (
    AppealCase,
    AppealStatus,
    ComparisonError,
    DriftSchedule,
    InMemoryAppealWorkflow,
    InMemoryDriftScheduler,
    InMemoryLeaderboard,
    InMemoryReportPortal,
    LeaderboardEntry,
    ReportRef,
    assert_zero_churn,
    cadence_seconds,
    churn,
    compare_paired,
    mcnemar_exact,
    wilson_interval,
)

TZ = timezone.utc
NOW = datetime(2026, 10, 7, tzinfo=TZ)


class TestLeaderboard:
    def test_rank_desc_with_none_last(self):
        lb = InMemoryLeaderboard()
        lb.publish(LeaderboardEntry("A", NOW, {"q": 0.9}, composite=0.9))
        lb.publish(LeaderboardEntry("B", NOW, {"q": 0.5}, composite=0.5))
        lb.publish(LeaderboardEntry("C", NOW, {"q": 0.7}, composite=None))
        assert [e.subject_id for e in lb.top(10)] == ["A", "B", "C"]

    def test_tie_break_by_subject_id(self):
        lb = InMemoryLeaderboard()
        lb.publish(LeaderboardEntry("Z", NOW, {}, composite=0.5))
        lb.publish(LeaderboardEntry("A", NOW, {}, composite=0.5))
        assert [e.subject_id for e in lb.top(2)] == ["A", "Z"]

    def test_top_zero_or_negative(self):
        lb = InMemoryLeaderboard()
        lb.publish(LeaderboardEntry("A", NOW, {}, composite=1.0))
        assert lb.top(0) == []
        assert lb.top(-3) == []

    def test_publish_overwrites_same_subject(self):
        lb = InMemoryLeaderboard()
        lb.publish(LeaderboardEntry("A", NOW, {}, composite=0.1))
        lb.publish(LeaderboardEntry("A", NOW, {}, composite=0.9))
        assert lb.get("A").composite == pytest.approx(0.9)
        assert len(lb.all()) == 1


class TestReportPortal:
    def test_index_and_latest(self):
        portal = InMemoryReportPortal()
        portal.add(ReportRef("R1", "model-x", "v1", digest="a" * 8))
        portal.add(ReportRef("R2", "model-x", "v2", digest="b" * 8))
        portal.add(ReportRef("R3", "model-y", "v1", digest="c" * 8))
        assert len(portal.index("model-x")) == 2
        assert portal.latest("model-x").report_id == "R2"
        assert portal.latest("unknown") is None


class TestAppealWorkflow:
    def test_legal_path(self):
        wf = InMemoryAppealWorkflow()
        wf.file(AppealCase("A1", "model-x", "score too low"))
        wf.advance("A1", AppealStatus.TRIAGED)
        wf.advance("A1", AppealStatus.UNDER_REVIEW)
        case = wf.advance("A1", AppealStatus.RESOLVED, note="upheld")
        assert case.status is AppealStatus.RESOLVED
        assert case.resolution == "upheld"

    def test_illegal_jump_rejected(self):
        wf = InMemoryAppealWorkflow()
        wf.file(AppealCase("A1", "model-x", "claim"))
        with pytest.raises(ValueError):
            wf.advance("A1", AppealStatus.RESOLVED)

    def test_duplicate_file_rejected(self):
        wf = InMemoryAppealWorkflow()
        wf.file(AppealCase("A1", "model-x", "claim"))
        with pytest.raises(ValueError):
            wf.file(AppealCase("A1", "model-y", "other"))

    def test_unknown_case(self):
        wf = InMemoryAppealWorkflow()
        with pytest.raises(KeyError):
            wf.advance("nope", AppealStatus.TRIAGED)


class TestDriftScheduler:
    @pytest.mark.parametrize(
        "cadence,seconds",
        [("hourly", 3600), ("daily", 86400), ("weekly", 604800),
         ("30m", 1800), ("6h", 21600), ("2d", 172800), ("45s", 45)],
    )
    def test_cadence_parsing(self, cadence, seconds):
        assert cadence_seconds(cadence) == seconds

    def test_bad_cadence(self):
        with pytest.raises(ValueError):
            cadence_seconds("fortnightly")

    def test_never_run_is_due(self):
        sch = InMemoryDriftScheduler()
        sch.register(DriftSchedule("model-x", "daily", "corpus-1", "d" * 8))
        assert [s.subject_id for s in sch.due(NOW)] == ["model-x"]

    def test_recent_run_not_due_old_run_due(self):
        sch = InMemoryDriftScheduler()
        sch.register(DriftSchedule("recent", "daily", "c", "d" * 8, last_run=NOW - timedelta(hours=1)))
        sch.register(DriftSchedule("stale", "daily", "c", "d" * 8, last_run=NOW - timedelta(days=2)))
        assert [s.subject_id for s in sch.due(NOW)] == ["stale"]

    def test_disabled_not_due(self):
        sch = InMemoryDriftScheduler()
        sch.register(DriftSchedule("off", "daily", "c", "d" * 8, enabled=False))
        assert sch.due(NOW) == []

    def test_mark_run_updates_last_run(self):
        sch = InMemoryDriftScheduler()
        sch.register(DriftSchedule("model-x", "daily", "c", "d" * 8))
        updated = sch.mark_run("model-x", NOW)
        assert updated.last_run == NOW
        assert sch.due(NOW) == []  # just ran -> not due

    def test_mark_run_unknown(self):
        sch = InMemoryDriftScheduler()
        with pytest.raises(KeyError):
            sch.mark_run("nope", NOW)


class TestWilsonInterval:
    def test_half_of_hundred_matches_reference_table(self):
        iv = wilson_interval(50, 100)
        assert iv.estimate == pytest.approx(0.5)
        assert iv.lo == pytest.approx(0.4038, abs=1e-4)
        assert iv.hi == pytest.approx(0.5962, abs=1e-4)

    def test_all_pass_keeps_honest_upper_bound(self):
        iv = wilson_interval(500, 500)
        assert iv.hi == 1.0
        assert iv.lo == pytest.approx(0.9924, abs=1e-3)

    def test_zero_passes_upper_bound_positive(self):
        iv = wilson_interval(0, 100)
        assert iv.lo == 0.0
        assert iv.hi == pytest.approx(0.0370, abs=1e-3)

    def test_confidence_level_changes_width(self):
        narrow = wilson_interval(50, 100, confidence=0.90)
        wide = wilson_interval(50, 100, confidence=0.99)
        assert narrow.lo > wide.lo
        assert narrow.hi < wide.hi

    def test_validations(self):
        with pytest.raises(ComparisonError):
            wilson_interval(0, 0)
        with pytest.raises(ComparisonError):
            wilson_interval(5, 4)
        with pytest.raises(ComparisonError):
            wilson_interval(1, 10, confidence=0.93)


class TestMcNemarExact:
    def test_known_example_45_5(self):
        r = mcnemar_exact(45, 5)
        assert r.n_discordant == 50
        assert r.p_value == pytest.approx(4.2099e-9, rel=0.01)

    def test_known_example_13_5(self):
        r = mcnemar_exact(13, 5)
        assert r.p_value == pytest.approx(0.0963, abs=1e-3)

    def test_symmetric_split_is_one(self):
        assert mcnemar_exact(10, 10).p_value == 1.0

    def test_more_lopsided_gives_smaller_p(self):
        assert mcnemar_exact(20, 2).p_value < mcnemar_exact(12, 10).p_value

    def test_validations(self):
        with pytest.raises(ComparisonError):
            mcnemar_exact(0, 0)
        with pytest.raises(ComparisonError):
            mcnemar_exact(-1, 3)


class TestChurn:
    def test_flips_and_stable(self):
        a = {"i1": True, "i2": False, "i3": True, "i4": False}
        b = {"i1": True, "i2": True, "i3": False, "i4": False}
        r = churn(a, b)
        assert r.n_common == 4
        assert r.stable == 2
        assert r.flipped_up == ("i2",)
        assert r.flipped_down == ("i3",)
        assert r.n_flips == 2
        assert not r.is_zero()

    def test_only_in_buckets_are_reported(self):
        r = churn({"i1": True}, {"i2": False})
        assert r.n_common == 0
        assert r.only_in_a == ("i1",)
        assert r.only_in_b == ("i2",)

    def test_ordering_is_deterministic(self):
        a = {f"i{n}": False for n in (3, 1, 2)}
        b = {f"i{n}": True for n in (3, 1, 2)}
        assert churn(a, b).flipped_up == ("i1", "i2", "i3")

    def test_rejects_non_bool_outcomes(self):
        with pytest.raises(ComparisonError):
            churn({"i1": 1}, {"i1": True})

    def test_assert_zero_churn_passes_on_identical_replay(self):
        a = {"i1": True, "i2": False}
        report = assert_zero_churn(a, dict(a))
        assert report.is_zero()

    def test_assert_zero_churn_enumerates_flips(self):
        a = {"i1": True, "i2": False}
        with pytest.raises(ComparisonError) as exc:
            assert_zero_churn(a, {"i1": True, "i2": True})
        assert "i2" in str(exc.value)


class TestPairedComparison:
    def test_full_report(self):
        records_a = {
            "i1": True, "i2": True, "i3": True, "i4": True, "i5": True,
            "i6": True, "i7": True, "i8": False, "i9": False, "i10": False,
        }
        records_b = {
            "i1": True, "i2": False, "i3": False, "i4": False, "i5": False,
            "i6": False, "i7": False, "i8": True, "i9": False, "i10": False,
        }
        rep = compare_paired(records_a, records_b)
        assert rep.n_pairs == 10
        assert (rep.both_pass, rep.both_fail) == (1, 2)
        assert rep.only_a == 6
        assert rep.only_b == 1
        assert rep.rate_a == pytest.approx(0.7)
        assert rep.rate_b == pytest.approx(0.2)
        assert rep.rate_delta == pytest.approx(0.5)
        assert rep.mcnemar_p == pytest.approx(0.125)
        assert rep.interval_a.n == 10
        assert rep.churn.flipped_down == ("i2", "i3", "i4", "i5", "i6", "i7")
        assert rep.churn.flipped_up == ("i8",)

    def test_identical_systems_have_no_fabricated_p_value(self):
        a = {"i1": True, "i2": False}
        rep = compare_paired(a, dict(a))
        assert rep.mcnemar_p is None
        assert rep.rate_delta == 0.0
        assert rep.churn.is_zero()

    def test_id_mismatch_raises(self):
        with pytest.raises(ComparisonError):
            compare_paired({"i1": True}, {"i2": True})

    def test_empty_raises(self):
        with pytest.raises(ComparisonError):
            compare_paired({}, {})

    def test_report_is_json_serializable(self):
        rep = compare_paired({"i1": True}, {"i1": False})
        payload = json.dumps(rep.to_dict())
        assert '"mcnemar_p"' in payload
