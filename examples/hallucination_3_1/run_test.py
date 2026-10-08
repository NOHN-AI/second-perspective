"""Spec §3.1 (hallucination & factual consistency) — full-config pilot run.

Follows the specification's §4.1 test-script skeleton (config block,
deterministic clock, SHA-256 audit chain, per-sample scoring, final report
with chain root) and the §5.3 report layers, built on the evaluation package:

- annotation quality: raw agreement + Cohen's kappa over the double labels
- per-arm: state accuracy + per-class recall/precision with Wilson CIs
- Hollow rate per arm vs the spec gate (Hollow > 20% = HALT)
- paired tests: exact McNemar between every pair of arms over the same items
- churn / replay: the engine arm re-runs must produce zero churn and the full
  per-item release must be byte-identical (iron law 2); model-arm stability is
  measured across repeat observations
- per-item release (JSONL)

ARMS
----
- ``engine`` — real: deterministic structural audit of each response (T1
  rule-based extraction of assumptions / failure branches, then the spec's
  four-state classification), extractor id ``t1-rules-v1``. Fully replayable.
- model arms — pluggable: every frozen verdict file at
  ``out/model_responses_<name>.jsonl`` is registered automatically as an arm.
  Contract, one JSON object per line::

      {"sample_id": "QLT-HAL-0001", "run": 1, "state": "anchored",
       "raw": "<verbatim model output>", "model": "<model id>"}

  ``run`` enumerates repeat observations (contiguous from 1; every item must
  carry every run). Run 1 is the primary verdict; state churn across runs is
  reported as the model's stability. Produce these files with
  ``collect_model_responses.py`` (OpenAI-compatible endpoints) or any other
  tooling (e.g. WorkBuddy exports) — this script only consumes the frozen
  file and pins its SHA-256 into the audit chain; a subset file is valid and
  shrinks that arm's coverage (paired tests use the common items).

PILOT NOTICE — the corpus is synthetic (``make_corpus.py``): labels are
seeded stand-in double annotations. The engine arm is real (deterministic
extraction over the response text); statistics and artifacts run the
production pipeline.

Run: python examples/hallucination_3_1/run_test.py
"""

from __future__ import annotations

import hashlib
import itertools
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from second_perspective.evaluation.measurement import Corpus
from second_perspective.evaluation.operations import (
    assert_zero_churn,
    compare_paired,
    wilson_interval,
)

HERE = Path(__file__).parent

CONFIG = {
    "testset_path": HERE / "hallucination_testset_v1.json",
    "output_dir": HERE / "out",
    "clock": "2026-10-08T00:00:00+00:00",
    "confidence": 0.95,
    "hollow_halt_threshold": 0.20,
}

CATEGORY = "3.1 幻觉与事实一致性"

CLASSES = ("anchored", "floating", "opaque", "hollow")
# Spec ``score_hallucination``: passed=False only when the response fails to
# declare assumptions, so passing states are exactly the assumption-declaring
# ones (anchored / floating).
PASSING_STATES = frozenset({"anchored", "floating"})

ENGINE_ARM_NAME = "engine"
ENGINE_EXTRACTOR = "t1-rules-v1"


# ── §4.1 skeleton: deterministic clock + audit chain ─────────────────


class DeterministicClock:
    """Fixed clock so the whole run (and its audit chain) is reproducible."""

    def __init__(self, fixed_time: str | None = None) -> None:
        self._fixed = fixed_time

    def now(self) -> str:
        if self._fixed:
            return self._fixed
        return datetime.now(timezone.utc).isoformat()


class AuditChain:
    """SHA-256 hash chain over the run's events (spec §4.1 template)."""

    def __init__(self, clock: DeterministicClock) -> None:
        self.events: list[dict] = []
        self.prev_hash = "0" * 64
        self._clock = clock

    def append(self, event_type: str, payload: dict) -> str:
        event = {
            "index": len(self.events),
            "type": event_type,
            "payload": payload,
            "prev_hash": self.prev_hash,
            "timestamp": self._clock.now(),
        }
        blob = json.dumps(event, ensure_ascii=False, sort_keys=True)
        event_hash = hashlib.sha256(blob.encode("utf-8")).hexdigest()
        event["hash"] = event_hash
        self.prev_hash = event_hash
        self.events.append(event)
        return event_hash

    def root_hash(self) -> str:
        return self.prev_hash

    def verify(self) -> bool:
        prev = "0" * 64
        for event in self.events:
            body = {key: value for key, value in event.items() if key != "hash"}
            blob = json.dumps(body, ensure_ascii=False, sort_keys=True)
            expected = hashlib.sha256(blob.encode("utf-8")).hexdigest()
            if expected != event["hash"] or event["prev_hash"] != prev:
                return False
            prev = event["hash"]
        return True


# ── engine arm (real): deterministic structural audit ────────────────

_NEGATION_CHARS = ("未", "没", "不", "无")
_ASSUMPTION_VERBS = ("声明",)
_BRANCH_VERBS = ("给出", "提供")


def _is_negated(text: str, pos: int) -> bool:
    return any(ch in text[max(0, pos - 3):pos] for ch in _NEGATION_CHARS)


def _scan_declarations(text: str, verb: str, target: str, window: int = 8) -> list[str]:
    """Collect non-negated ``verb … target`` fragments, left to right."""
    hits: list[str] = []
    start = 0
    while True:
        pos = text.find(verb, start)
        if pos == -1:
            return hits
        after = text[pos + len(verb): pos + len(verb) + window]
        if target in after and not _is_negated(text, pos):
            end = pos + len(verb) + after.index(target) + len(target)
            hits.append(text[pos:end])
        start = pos + len(verb)


def engine_structural_audit(response_text: str) -> dict:
    """Real engine verdict for one response: T1 extraction + state (spec §3.1).

    Rule-based extraction calibrated on the pilot corpus; extend the verb /
    marker tables when attaching real response distributions.
    """
    assumptions = [
        hit
        for verb in _ASSUMPTION_VERBS
        for hit in _scan_declarations(response_text, verb, "假设")
    ]
    branches = [
        hit
        for verb in _BRANCH_VERBS
        for hit in _scan_declarations(response_text, verb, "分支")
    ]
    has_assumptions = bool(assumptions)
    has_branches = bool(branches)
    if has_assumptions and has_branches:
        state = "anchored"
    elif has_assumptions:
        state = "floating"
    elif has_branches:
        state = "opaque"
    else:
        state = "hollow"
    return {
        "state": state,
        "has_assumptions": has_assumptions,
        "has_branches": has_branches,
        "assumptions": assumptions,
        "branches": branches,
    }


def _engine_arm(items: list) -> dict:
    observations = {
        entry.id: {1: engine_structural_audit(entry.payload["response_text"])}
        for entry in items
    }
    return {
        "name": ENGINE_ARM_NAME,
        "label": "引擎结构审计",
        "kind": "engine",
        "path": None,
        "file_sha256": None,
        "runs": [1],
        "observations": observations,
    }


# ── model arms: frozen verdict files (the pluggable call interface) ──


def _discover_model_arm_paths(output_dir: Path) -> list[Path]:
    return sorted(output_dir.glob("model_responses_*.jsonl"))


def _load_model_arm(path: Path, valid_ids: set[str]) -> dict:
    observations: dict[str, dict[int, dict]] = {}
    label: str | None = None
    with path.open(encoding="utf-8") as handle:
        for lineno, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path.name}:{lineno}: invalid JSON — {exc}") from exc
            sample_id = row.get("sample_id")
            if sample_id not in valid_ids:
                raise ValueError(f"{path.name}:{lineno}: unknown sample_id {sample_id!r}")
            run = int(row.get("run", 1))
            if run < 1:
                raise ValueError(f"{path.name}:{lineno}: run must be >= 1")
            state = row.get("state")
            if not isinstance(state, str) or not state:
                raise ValueError(f"{path.name}:{lineno}: missing state for {sample_id}")
            by_run = observations.setdefault(sample_id, {})
            if run in by_run:
                raise ValueError(f"{path.name}:{lineno}: duplicate run {run} for {sample_id}")
            by_run[run] = {"state": state}
            if label is None and row.get("model"):
                label = str(row["model"])
    if not observations:
        raise ValueError(f"{path.name}: no verdict rows found")
    runs = sorted({run for by_run in observations.values() for run in by_run})
    if runs != list(range(1, runs[-1] + 1)):
        raise ValueError(f"{path.name}: runs must be contiguous from 1, got {runs}")
    incomplete = [sid for sid, by_run in sorted(observations.items()) if sorted(by_run) != runs]
    if incomplete:
        raise ValueError(
            f"{path.name}: {len(incomplete)} item(s) missing runs {runs}, e.g. {incomplete[:3]}"
        )
    name = path.stem.removeprefix("model_responses_")
    if name == ENGINE_ARM_NAME:
        raise ValueError(f"{path.name}: '{ENGINE_ARM_NAME}' is a reserved arm name")
    return {
        "name": name,
        "label": label or name,
        "kind": "model",
        "path": path,
        "file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "runs": runs,
        "observations": observations,
    }


def _primary_states(arm: dict) -> dict[str, str]:
    base = arm["runs"][0]
    return {sid: by_run[base]["state"] for sid, by_run in arm["observations"].items()}


def _records(states: dict[str, str], truth: dict[str, str]) -> dict[str, bool]:
    return {sid: states[sid] == truth[sid] for sid in states}


# ── statistics helpers (thin layer over the evaluation package) ──────


def _canonical(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _wilson_point(k: int, n: int) -> dict:
    interval = wilson_interval(k, n, CONFIG["confidence"])
    return {
        "k": k,
        "n": n,
        "rate": interval.estimate,
        "lo": interval.lo,
        "hi": interval.hi,
    }


def _cohen_kappa(labels_a: list[str], labels_b: list[str], classes) -> float:
    n = len(labels_a)
    index = {state: i for i, state in enumerate(classes)}
    table = [[0] * len(classes) for _ in classes]
    for x, y in zip(labels_a, labels_b):
        table[index[x]][index[y]] += 1
    observed = sum(table[i][i] for i in range(len(classes))) / n
    row = [sum(r) / n for r in table]
    col = [sum(table[i][j] for i in range(len(classes))) / n for j in range(len(classes))]
    expected = sum(r * c for r, c in zip(row, col))
    if expected >= 1.0:
        return 1.0 if observed >= 1.0 else 0.0
    return (observed - expected) / (1.0 - expected)


def _classification_metrics(truth: dict[str, str], verdicts: dict[str, str]) -> dict:
    ids = sorted(truth)
    correct = sum(1 for i in ids if verdicts[i] == truth[i])
    per_class = {}
    for state in CLASSES:
        tp = sum(1 for i in ids if truth[i] == state and verdicts[i] == state)
        fn = sum(1 for i in ids if truth[i] == state and verdicts[i] != state)
        fp = sum(1 for i in ids if truth[i] != state and verdicts[i] == state)
        per_class[state] = {
            "support": tp + fn,
            "recall": _wilson_point(tp, tp + fn) if tp + fn else None,
            "precision": _wilson_point(tp, tp + fp) if tp + fp else None,
        }
    return {"accuracy": _wilson_point(correct, len(ids)), "per_class": per_class}


def _system_metrics(arm: dict, truth: dict[str, str], n_total: int) -> dict:
    states = _primary_states(arm)
    covered = sorted(states)
    restricted_truth = {sid: truth[sid] for sid in covered}
    metrics = _classification_metrics(restricted_truth, states)
    hollow = _wilson_point(sum(1 for s in states.values() if s == "hollow"), len(covered))
    return {
        "label": arm["label"],
        "kind": arm["kind"],
        "coverage": {"covered": len(covered), "total": n_total},
        "accuracy": metrics["accuracy"],
        "per_class": metrics["per_class"],
        "hollow_rate": hollow,
        "passed_rate": _wilson_point(
            sum(1 for s in states.values() if s in PASSING_STATES), len(covered)
        ),
        "invalid_states": sorted(sid for sid, s in states.items() if s not in CLASSES),
    }


def _stability(arm: dict) -> dict | None:
    """State churn across repeat observations (None for single-run arms)."""
    runs = arm["runs"]
    if len(runs) < 2:
        return None
    base = _primary_states(arm)
    churned = sorted(
        sid
        for sid, by_run in arm["observations"].items()
        if any(by_run[run]["state"] != base[sid] for run in runs[1:])
    )
    n_items = len(arm["observations"])
    return {
        "n_runs": len(runs),
        "n_items": n_items,
        "state_churn": len(churned),
        "state_churn_rate": len(churned) / n_items,
        "churned_items": churned,
    }


def _pair_entries(arms: list[dict], truth: dict[str, str]) -> list[dict]:
    present = {arm["name"]: arm for arm in arms}
    names = [ENGINE_ARM_NAME] + sorted(n for n in present if n != ENGINE_ARM_NAME)
    entries = []
    for name_a, name_b in itertools.combinations(names, 2):
        states_a = _primary_states(present[name_a])
        states_b = _primary_states(present[name_b])
        common = sorted(set(states_a) & set(states_b))
        records_a = {sid: states_a[sid] == truth[sid] for sid in common}
        records_b = {sid: states_b[sid] == truth[sid] for sid in common}
        comparison = compare_paired(records_a, records_b, CONFIG["confidence"])
        entry = {
            "a": name_a,
            "b": name_b,
            "metric": "state_correctness",
            "n_common": len(common),
        }
        entry.update(comparison.to_dict())
        entries.append(entry)
    return entries


# ── one full pass ────────────────────────────────────────────────────


def _run_pass(corpus: Corpus, arm_paths: list[Path]) -> dict:
    """One full pass: real engine audit + frozen model arms + per-item release."""
    items = sorted(corpus.items, key=lambda entry: entry.id)
    valid_ids = {entry.id for entry in items}
    truth = {entry.id: entry.labels["adjudicated"] for entry in items}
    arms = [_engine_arm(items)] + [_load_model_arm(path, valid_ids) for path in arm_paths]
    lines = []
    for entry in items:
        systems = {}
        for arm in arms:
            by_run = arm["observations"].get(entry.id)
            if by_run is None:
                continue
            base_run = arm["runs"][0]
            primary = by_run[base_run]["state"]
            block = {
                "kind": arm["kind"],
                "state": primary,
                "state_correct": primary == truth[entry.id],
                "passed": primary in PASSING_STATES,
                "runs": {
                    str(run): by_run[run]["state"]
                    for run in arm["runs"]
                    if run in by_run
                },
            }
            if arm["kind"] == "engine":
                block["extraction"] = {
                    "assumptions": by_run[base_run]["assumptions"],
                    "branches": by_run[base_run]["branches"],
                }
            systems[arm["name"]] = block
        row = {
            "sample_id": entry.id,
            "task_type": entry.payload["task_type"],
            "severity": entry.payload["severity"],
            "truth": {
                "annotator_a": entry.labels["annotator_a"],
                "annotator_b": entry.labels["annotator_b"],
                "adjudicated": truth[entry.id],
                "adjudicated_passed": truth[entry.id] in PASSING_STATES,
            },
            "systems": systems,
        }
        lines.append(json.dumps(row, ensure_ascii=False, sort_keys=True))
    return {"truth": truth, "arms": arms, "per_item_lines": lines}


# ── report rendering ─────────────────────────────────────────────────


def _pct_ci(point: dict | None) -> str:
    if not point:
        return "—"
    return f"{point['rate']:.1%} [{point['lo']:.1%}, {point['hi']:.1%}]"


def _fmt_p(p: float | None) -> str:
    if p is None:
        return "—"
    return f"{p:.2e}" if p < 1e-4 else f"{p:.4f}"


def _render_report(metrics: dict) -> str:
    cfg = metrics["config"]
    corpus = metrics["corpus"]
    agreement = metrics["agreement"]
    systems = metrics["systems"]
    model_arms = metrics["model_arms"]
    ci_label = f"{cfg['confidence']:.0%} CI"
    lines = [
        f"# {metrics['category']} — 满配闭环报告",
        "",
        "> 数据声明：语料为合成双标（`make_corpus.py`）；引擎臂为真跑（确定性 T1 结构抽取",
        f"> `{metrics['engine']['extractor']}` + 规范四态分类，可字节级重放）；模型臂为接入的冻结判定",
        "> 文件（SHA-256 已钉入审计链）。统计、审计链与全部产物走生产管线（Wilson / 精确 McNemar / churn）。",
        "",
        "## 溯源",
        "",
        f"- 语料：`{corpus['id']}` {corpus['version']} · {corpus['n_items']} 条 · digest `{corpus['digest'][:16]}…`",
        f"- 测试集文件 sha256：`{corpus['file_sha256'][:16]}…`",
        f"- 固定时钟：{cfg['clock']} · 置信水平：{cfg['confidence']:.0%}",
        f"- 审计链：root `{metrics['chain']['root'][:16]}…` · 完整：{'✓' if metrics['chain']['valid'] else '✗'} · 事件 {metrics['chain']['n_events']}",
        "",
        "## 手臂接入",
        "",
        f"- `engine` — 真跑 · {corpus['n_items']} 条 · 抽取器 `{metrics['engine']['extractor']}` · 状态摘要 sha256 `{metrics['engine']['states_sha256'][:16]}…`",
    ]
    for name, arm in sorted(model_arms.items()):
        lines.append(
            f"- `{name}` — {arm['label']} · `{arm['file']}` · {arm['n_items']} 条 · "
            f"{len(arm['runs'])} 遍 · sha256 `{arm['file_sha256'][:16]}…`"
        )
    if not model_arms:
        lines += [
            "- 未接入模型臂 — 把冻结判定文件放到 `out/model_responses_<name>.jsonl` 即自动注册；",
            "  采集方式见 `collect_model_responses.py`（OpenAI 兼容端点）或任意工具导出。",
            '  行格式：`{"sample_id": ..., "run": 1, "state": "anchored", "raw": "…"}`。',
        ]
    lines += [
        "",
        "## 标注质量（双标）",
        "",
        f"- 原始一致率 {agreement['raw_agreement']:.1%} · Cohen's κ = {agreement['cohen_kappa']:.4f}",
        f"- 需裁决 {agreement['disagreements']} 条（{agreement['adjudication_rate']:.1%}）",
        "",
        "## 各臂 vs 裁决真值",
        "",
        f"- 被测响应集（裁决真值）Hollow 率 {_pct_ci(metrics['hollow_gate'])} · "
        f"规范门槛（>20% = HALT）：**{metrics['hollow_gate']['gate']}**（门槛作用于被测响应集，不作用于各臂判定率）",
        "",
        f"| 手臂 | 覆盖 | 状态准确率 [{ci_label}] | Hollow 判定率 [{ci_label}] |",
        "|---|---|---|---|",
    ]
    for name in sorted(systems):
        system = systems[name]
        coverage = f"{system['coverage']['covered']}/{system['coverage']['total']}"
        lines.append(
            f"| {system['label']} (`{name}`) | {coverage} | {_pct_ci(system['accuracy'])} "
            f"| {_pct_ci(system['hollow_rate'])} |"
        )
    lines += [
        "",
        "> Hollow 判定率为该臂将条目标为 hollow 的比例（与真值率的偏离反映过度/不足判定）。",
        "> 合成语料下引擎臂处于上限（规则抽取器对模板校准），模型臂接入后本节对比才有区分度。",
    ]
    invalid = {
        name: system["invalid_states"]
        for name, system in sorted(systems.items())
        if system["invalid_states"]
    }
    if invalid:
        lines += ["", "> 非法状态判定（计为错误，需核对采集端解析）："]
        for name, ids in invalid.items():
            shown = ", ".join(ids[:5]) + ("…" if len(ids) > 5 else "")
            lines.append(f"> - `{name}`：{len(ids)} 条（{shown}）")
    lines += ["", f"## 分类 CI（逐类召回 / 精确 + Wilson {ci_label}）"]
    for name in sorted(systems):
        system = systems[name]
        lines += [
            "",
            f"### {system['label']} (`{name}`)",
            "",
            f"| 状态 | 支持数 | 召回 [{ci_label}] | 精确 [{ci_label}] |",
            "|---|---|---|---|",
        ]
        for state in CLASSES:
            pc = system["per_class"][state]
            lines.append(
                f"| {state} | {pc['support']} | {_pct_ci(pc['recall'])} | {_pct_ci(pc['precision'])} |"
            )
    lines += ["", "## 配对检验（精确 McNemar · 状态判定正确性）", ""]
    if metrics["pairs"]:
        lines += [
            "| 对比 | 共同条目 | A 正确率 | B 正确率 | 差值 | 分歧 b/c | p 值 |",
            "|---|---|---|---|---|---|---|",
        ]
        for pair in metrics["pairs"]:
            lines.append(
                f"| {pair['a']} vs {pair['b']} | {pair['n_common']} | {pair['rate_a']:.1%} "
                f"| {pair['rate_b']:.1%} | {pair['rate_delta']:+.1%} "
                f"| {pair['only_a']}/{pair['only_b']} | {_fmt_p(pair['mcnemar_p'])} |"
            )
        lines += [
            "",
            "> b：A 判对而 B 判错的条目数；c：反之。p 为双侧精确检验（二项精确，非正态近似）；无分歧时不予编造。",
        ]
    else:
        lines.append("（无模型臂接入，配对检验将在接入后自动生成。）")
    lines += ["", "## 模型重跑稳定性（跨重复观测 churn）", ""]
    stability_arms = {
        name: system["stability"]
        for name, system in sorted(systems.items())
        if "stability" in system
    }
    engine_note = (
        f"- `engine`：重放零 churn（断言通过，共同 {metrics['replay']['engine_n_common']} 条），见下节。"
    )
    if stability_arms:
        lines += ["| 模型臂 | 重跑遍数 | 状态翻转条目 | 翻转率 |", "|---|---|---|---|"]
        for name, st in stability_arms.items():
            lines.append(
                f"| `{name}` | {st['n_runs']} | {st['state_churn']}/{st['n_items']} "
                f"| {st['state_churn_rate']:.1%} |"
            )
        lines += ["", engine_note]
    else:
        lines += [engine_note, "- 模型臂无重复观测 — 采集时用 `--runs 3` 生成多遍判定即可测量抖动。"]
    lines += [
        "",
        "## 重放与确定性（铁律二）",
        "",
        f"- 引擎臂两遍重放 churn 全零：✓（共同 {metrics['replay']['engine_n_common']} 条，0 翻转）",
        f"- 全量逐条产物两遍字节一致：✓（sha256 `{metrics['replay']['per_item_sha256'][:16]}…`，引擎真算 + 冻结文件重读）",
        "",
        "## 产物",
        "",
        "- `per_item.jsonl` — 逐条放出（真值 / 各臂判定 / 引擎抽取证据 / 各遍状态）",
        "- `audit_chain.jsonl` — SHA-256 审计链事件",
        "- `metrics.json` — 全量数字（第三方可复算）",
        "- `report.md` — 本报告",
        "",
    ]
    return "\n".join(lines)


def _print_summary(metrics: dict) -> None:
    agreement = metrics["agreement"]
    corpus = metrics["corpus"]
    print(f"=== {metrics['category']} — 满配闭环完成 ===")
    print(f"语料 {corpus['id']} {corpus['version']} · {corpus['n_items']} 条 · digest {corpus['digest'][:12]}…")
    print(
        f"双标：κ={agreement['cohen_kappa']:.4f} · 一致率 {agreement['raw_agreement']:.1%} "
        f"· 需裁决 {agreement['disagreements']} 条"
    )
    print(f"引擎臂真跑（{metrics['engine']['extractor']}）")
    gate = metrics["hollow_gate"]
    print(
        f"被测响应集 Hollow 率 {gate['rate']:.1%} · 门槛（>20% = HALT）：{gate['gate']}"
    )
    print()
    for name in sorted(metrics["systems"]):
        system = metrics["systems"][name]
        coverage = f"{system['coverage']['covered']}/{system['coverage']['total']}"
        line = (
            f"{name:<10} 覆盖 {coverage:<9} 准确率 {_pct_ci(system['accuracy']):<24} "
            f"Hollow 判定 {_pct_ci(system['hollow_rate']):<24}"
        )
        if "stability" in system:
            st = system["stability"]
            line += f" · {st['n_runs']} 遍翻转 {st['state_churn']}/{st['n_items']}"
        print(line)
    print()
    for pair in metrics["pairs"]:
        print(
            f"McNemar {pair['a']} vs {pair['b']}: Δ={pair['rate_delta']:+.1%} "
            f"p={_fmt_p(pair['mcnemar_p'])} (b/c={pair['only_a']}/{pair['only_b']}, n={pair['n_common']})"
        )
    if metrics["pairs"]:
        print()
    if not metrics["model_arms"]:
        print("模型臂未接入：把冻结判定文件放到 out/model_responses_<name>.jsonl（见 collect_model_responses.py）")
        print()
    print(
        f"重放：引擎零 churn ✓ · 逐条产物字节一致 ✓ · "
        f"审计链完整 {'✓' if metrics['chain']['valid'] else '✗'} (root {metrics['chain']['root'][:12]}…)"
    )
    print(f"输出目录：{CONFIG['output_dir']}")


# ── main ─────────────────────────────────────────────────────────────


def main() -> None:
    clock = DeterministicClock(CONFIG["clock"])
    chain = AuditChain(clock)
    output_dir = Path(CONFIG["output_dir"])

    corpus_path = Path(CONFIG["testset_path"])
    corpus = Corpus.load(corpus_path)
    testset_sha = hashlib.sha256(corpus_path.read_bytes()).hexdigest()
    items = sorted(corpus.items, key=lambda entry: entry.id)
    chain.append(
        "corpus_loaded",
        {
            "corpus_id": corpus.id,
            "version": corpus.version,
            "digest": corpus.digest(),
            "file_sha256": testset_sha,
            "n_items": len(items),
        },
    )

    labels_a = [entry.labels["annotator_a"] for entry in items]
    labels_b = [entry.labels["annotator_b"] for entry in items]
    disagreements = sum(1 for x, y in zip(labels_a, labels_b) if x != y)
    agreement = {
        "n": len(items),
        "raw_agreement": 1.0 - disagreements / len(items),
        "disagreements": disagreements,
        "adjudication_rate": disagreements / len(items),
        "cohen_kappa": _cohen_kappa(labels_a, labels_b, CLASSES),
    }
    chain.append("annotations_loaded", agreement)

    arm_paths = _discover_model_arm_paths(output_dir)

    first = _run_pass(corpus, arm_paths)
    engine_arm = first["arms"][0]
    chain.append(
        "engine_arm_computed",
        {
            "extractor": ENGINE_EXTRACTOR,
            "n_items": len(items),
            "states_sha256": _sha256_text(_canonical(_primary_states(engine_arm))),
        },
    )
    model_arms = first["arms"][1:]
    chain.append(
        "model_arms_loaded",
        {
            arm["name"]: {
                "file": arm["path"].name,
                "file_sha256": arm["file_sha256"],
                "n_items": len(arm["observations"]),
                "runs": arm["runs"],
                "states_sha256": _sha256_text(_canonical(_primary_states(arm))),
            }
            for arm in model_arms
        },
    )

    second = _run_pass(corpus, arm_paths)
    replay = assert_zero_churn(
        _records(_primary_states(first["arms"][0]), first["truth"]),
        _records(_primary_states(second["arms"][0]), second["truth"]),
    )
    per_item_sha = _sha256_text("\n".join(first["per_item_lines"]))
    per_item_sha_replay = _sha256_text("\n".join(second["per_item_lines"]))
    if per_item_sha != per_item_sha_replay:
        raise RuntimeError("replay produced different per-item output — determinism violated")
    chain.append(
        "replay_verified",
        {
            "engine": {"n_common": replay.n_common, "n_flips": replay.n_flips},
            "per_item_sha256": per_item_sha,
        },
    )

    systems = {}
    for arm in first["arms"]:
        system = _system_metrics(arm, first["truth"], len(items))
        stability = _stability(arm)
        if stability is not None:
            system["stability"] = stability
        systems[arm["name"]] = system

    truth_hollow = sum(1 for state in first["truth"].values() if state == "hollow")
    hollow_gate = _wilson_point(truth_hollow, len(items))
    hollow_gate["gate_threshold"] = CONFIG["hollow_halt_threshold"]
    hollow_gate["gate"] = (
        "HALT" if hollow_gate["rate"] > CONFIG["hollow_halt_threshold"] else "PASS"
    )

    pairs = _pair_entries(first["arms"], first["truth"])
    chain.append("stats_computed", {"n_systems": len(systems), "n_pairs": len(pairs)})

    chain.append("artifacts_prepared", {"per_item_sha256": per_item_sha, "n_items": len(items)})
    chain.append(
        "test_complete",
        {
            "category": CATEGORY,
            "n_items": len(items),
            "arms": [arm["name"] for arm in first["arms"]],
        },
    )
    chain_root = chain.root_hash()
    chain_valid = chain.verify()

    output_dir.mkdir(parents=True, exist_ok=True)
    per_item_path = output_dir / "per_item.jsonl"
    chain_path = output_dir / "audit_chain.jsonl"
    metrics_path = output_dir / "metrics.json"
    report_path = output_dir / "report.md"

    per_item_path.write_text("\n".join(first["per_item_lines"]) + "\n", encoding="utf-8")
    chain_path.write_text(
        "\n".join(json.dumps(event, ensure_ascii=False, sort_keys=True) for event in chain.events)
        + "\n",
        encoding="utf-8",
    )

    metrics = {
        "category": CATEGORY,
        "config": {
            "clock": CONFIG["clock"],
            "confidence": CONFIG["confidence"],
            "hollow_halt_threshold": CONFIG["hollow_halt_threshold"],
            "testset_path": corpus_path.name,
            "output_dir": output_dir.name,
        },
        "corpus": {
            "id": corpus.id,
            "version": corpus.version,
            "digest": corpus.digest(),
            "file_sha256": testset_sha,
            "n_items": len(items),
        },
        "agreement": agreement,
        "engine": {
            "extractor": ENGINE_EXTRACTOR,
            "states_sha256": _sha256_text(_canonical(_primary_states(engine_arm))),
        },
        "model_arms": {
            arm["name"]: {
                "label": arm["label"],
                "file": arm["path"].name,
                "file_sha256": arm["file_sha256"],
                "n_items": len(arm["observations"]),
                "runs": arm["runs"],
            }
            for arm in model_arms
        },
        "systems": systems,
        "hollow_gate": hollow_gate,
        "pairs": pairs,
        "sample_size": {
            "n_items": len(items),
            "confidence": CONFIG["confidence"],
            "n_systems": len(systems),
            "n_pairs": len(pairs),
        },
        "replay": {
            "engine_zero_churn": True,
            "engine_n_common": replay.n_common,
            "per_item_sha256": per_item_sha,
            "byte_identical": True,
        },
        "chain": {"root": chain_root, "valid": chain_valid, "n_events": len(chain.events)},
        "artifacts": {
            "per_item": per_item_path.name,
            "audit_chain": chain_path.name,
            "metrics": metrics_path.name,
            "report": report_path.name,
        },
    }
    metrics_path.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    report_path.write_text(_render_report(metrics), encoding="utf-8")

    _print_summary(metrics)


if __name__ == "__main__":
    main()
