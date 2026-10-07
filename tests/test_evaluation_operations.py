"""Tests for the evaluation operations layer (module C, v0.6)."""

from datetime import datetime, timedelta, timezone

import pytest

from second_perspective.evaluation.operations import (
    AppealCase,
    AppealStatus,
    DriftSchedule,
    InMemoryAppealWorkflow,
    InMemoryDriftScheduler,
    InMemoryLeaderboard,
    InMemoryReportPortal,
    LeaderboardEntry,
    ReportRef,
    cadence_seconds,
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
