# Keeping LLMs Out of the Verdict: Zone-Isolated, Deterministic Decision Auditing with Reproducible Convergence

**Abstract.** Large language models (LLMs) are increasingly embedded in decision-support pipelines, yet their stochastic nature makes audit trails fragile: a single hallucinated verdict, a confabulated confidence score, or an untraceable rationale can invalidate an entire decision chain. We present NOMOS, a decision-auditing engine that enforces a strict separation of concerns: LLMs are confined to *narrative* zones (T1 annotation / T2 proposal / T3 narrative) and are **structurally prohibited** from writing into verdict fields. A deterministic evaluator — implemented with `Decimal` arithmetic, pure functions, and no randomness — drives convergence through five formally characterized states (`BLOCKED / BUDGET_EXHAUSTED / FIXED_POINT / NO_GAIN / DIVERGED`). Higher-order failure propagation is decomposed into first-order effects plus explicitly declared interaction strengths, with a provable boundedness invariant (I-3) and monotonicity (I-4). Every evaluation round produces a SHA-256 chained audit event with canonical JSON serialization, and every decision record is sealed with `hmac.compare_digest` verification. The reference implementation ships 385 pytest functions (165 in core modules, 220 in postgres/integration) and passes all assertions covering convergence state stability, schema rejection of unknown references, ceiling clipping numerical correctness, and invariant violation on malformed interaction declarations. NOMOS does **not** claim higher decision accuracy — it claims **deterministic reproducibility**, **structural LLM containment**, and **end-to-end auditability** as design properties.

**Keywords:** decision auditing, LLM safety, deterministic convergence, zone isolation, causal chain, AI governance.

---

## 1 Introduction

When a large language model participates in a decision-support pipeline, its outputs are inherently non-deterministic: the same prompt can yield different verdicts across invocations, and the reasoning trace that accompanies a verdict may be confabulated rather than retrieved from evidence. This creates a fundamental audit problem: if the verdict field can be written by an LLM, then the entire decision chain is tainted by non-reproducibility.

Existing approaches fall into three categories, each with a structural limitation. **Multi-criteria decision analysis (MCDA)** methods (AHP, TOPSIS) produce deterministic scores but lack native LLM integration and require manual weight calibration. **LLM-as-judge** frameworks delegate verdict generation to the model, sacrificing reproducibility for convenience. **Cognitive audit engines** (e.g., GCAE [1]) provide structured reasoning traces but permit LLM output into decision fields, creating a confabulation risk.

NOMOS addresses a narrower but deeper question: *can we let LLMs contribute to a decision process without letting them write the verdict?* We answer this with three design properties:

1. **Zone-isolated LLM integration (§3.1).** LLM output is confined to three permission tiers (T1 annotation / T2 proposal / T3 narrative) and a fixed set of narrative zones. Six forbidden keys (`converged`, `verdict`, `decision`, `score`, `bias_flag`, `overall_assessment`) are structurally stripped from LLM output before it reaches the evaluator.
2. **Deterministic convergence (§3.2).** The evaluator is a pure function of its input (candidate hypotheses + declared deltas), implemented with `Decimal` arithmetic and no randomness. Convergence is characterized by five states with a formal proof sketch: P-1 termination (well-ordering principle), P-2 fixed-point (pure-function property), P-3 effect boundedness (finite summation of bounded terms).
3. **End-to-end audit trail (§3.3).** Every evaluation round produces a SHA-256 chained audit event with canonical JSON serialization. Decision records are sealed with `hmac.compare_digest` verification and revision numbers that increment strictly by +1.

We do not claim higher decision accuracy. NOMOS is a **design contribution**: it proves that LLM participation and deterministic audit can coexist through structural enforcement rather than statistical filtering.

---

## 2 Related Work

**MCDA (AHP, TOPSIS).** These methods produce deterministic scores from weighted criteria but lack native LLM integration. NOMOS can ingest MCDA-like criteria (weighted sum to 1, validated by `DecisionRequest.validate_references`) but adds LLM-guarded narrative generation and causal audit.

**LLM-as-judge.** Frameworks that delegate verdict generation to an LLM sacrifice reproducibility. NOMOS's P-2 fixed-point proof explicitly requires a pure-function evaluator; an LLM-augmented evaluator breaks this property (see §3.2, `propositions.py` LLM warning comment).

**Cognitive Audit Engine (GCAE).** NOMOS integrates GCAE via a bidirectional adapter (§4.3) that translates NOMOS typed models into GCAE decision-context dicts and maps GCAE severity levels (`HALT`/`WARN`/`PASS`/`INFO`) to NOMOS `IssueSeverity`. The key distinction: GCAE's LLM output is confined to narrative zones before reaching NOMOS's deterministic evaluator.

**AI Governance (EU AI Act, ISO 42001, NIST AI RMF).** NOMOS maps to these frameworks through its audit ledger and deterministic trace, providing machine-verifiable evidence for compliance audits.

---

## 3 Architecture

### 3.1 Zone-Isolated LLM Integration

NOMOS partitions output into two zone categories, enforced by `PermissionTier` (T1–T3) and a fixed zone whitelist:

| Tier | Rank | Permitted Zones | Allowed Fields |
|------|------|-----------------|----------------|
| T1 Annotation | 1 | `narrative`, `explanation`, `summary`, `annotation` | Annotations only |
| T2 Proposal | 2 | All zones | Proposals with `strength` stripped to `null` |
| T3 Narrative | 3 | All zones | Full narrative, no structured fields |

**Forbidden keys** are stripped from all LLM output before the evaluator receives it:

```python
FORBIDDEN_LLM_KEYS = {
    "converged", "overall_assessment", "bias_flags",
    "bias_flag", "decision", "score", "verdict",
}
```

*(Source: `llm_compliance/guard.py:215-217`)*

T2-strength stripping is implemented via regex substitution (`_check_and_strip_strength`) and recursive dictionary traversal (`_strip_strength_from_dict`), ensuring that interaction strengths cannot be injected by an LLM.

### 3.2 Deterministic Convergence

The evaluator operates on `Decimal` arithmetic with no randomness. Convergence is characterized by five states, evaluated in strict priority order:

```python
class ConvergenceStatus(StrEnum):
    FIXED_POINT = "fixed_point"       # Candidate set identical to previous round
    NO_GAIN = "no_gain"               # No unresolved branches remain
    BUDGET_EXHAUSTED = "budget_exhausted"  # Budget consumed, not converged
    DIVERGED = "diverged"             # Still changing, budget available
    BLOCKED = "blocked"               # Blocked flag set
```

*(Source: `models/enums.py:119-130`)*

**Formal propositions** (from `convergence/propositions.py`):

- **P-1 Termination.** Both iteration and evidence-request budgets are finite positive integers; each round consumes at least one iteration unit. The well-ordering principle guarantees termination in ≤ `max_iterations` rounds.
- **P-2 Fixed-point.** The deterministic evaluator is a pure function of its input (candidate hypothesis set + declared deltas). If two consecutive rounds produce the same candidate set, the next round receives the same input — fixed point reached. ⚠️ *An LLM-augmented evaluator is not a pure function and this proof does not hold.*
- **P-3 Effect boundedness.** Each CONJUNCTIVE interaction contributes Δ; the engine applies `min(Δ, ceiling)` on the amplifying side. Finite summation of bounded terms yields a bounded total.

### 3.3 End-to-End Audit Trail

Each evaluation round produces a chained `AlgorithmAuditEvent`:

```
event_hash = SHA-256(canonical_json({
    sequence, stage, rule_id, operation, inputs, output,
    previous_event_hash
}))
```

*(Source: `decision/reconstruction.py:245-272`)*

Decision records are sealed with `seal_record` (SHA-256 of canonical JSON, excluding `record_hash`) and verified with `verify_chain` (revisions strictly +1, `parent_record_hash` chain continuity, `hmac.compare_digest` for constant-time hash comparison).

*(Source: `decision/integrity.py:26-69`, `audit/ledger.py:77-78`)*

---

## 4 Key Mechanisms

### 4.1 Higher-Order Failure Propagation

When an assumption is invalidated, NOMOS computes the **invalidation closure** via BFS through the dependency graph:

```python
def invalidation_closure(request, trigger_assumption_id):
    invalidated = set()
    frontier = {trigger_assumption_id}
    while frontier:
        current = frontier.pop()
        if current in invalidated: continue
        invalidated.add(current)
        for a_id, assumption in assumption_index.items():
            if a_id not in invalidated and current in assumption.dependencies:
                frontier.add(a_id)
    return list(invalidated)
```

*(Source: `decision/causal.py:26-63`)*

### 4.2 Bounded Interaction Effects

The `InteractionEngine` decomposes total effect into first-order sum plus interaction sum, with a ceiling constraint:

```
first_order  = Σ e(h)  for h in failed
interaction  = Σ Δ(I)  for each triggered interaction I
raw_total    = first_order + interaction
ceiling      = amplification_ceiling × Σ|e(h)|
total        = min(raw_total, first_order + ceiling)   # amplifying side only
```

*(Source: `interaction/engine.py:84-137`)*

**Invariants** (from `interaction/invariants.py`):

| Invariant | Statement |
|-----------|-----------|
| I-1 Non-conjectural | Interaction strength is explicitly set or absent; never defaulted |
| I-2 Order conservation | Every interaction member exists in the assumption set |
| I-3 Effect boundedness | Positive interaction sum ≤ amplification_ceiling × Σ\|first_order\| |
| I-4 Monotonicity | Adding a newly failed assumption never un-triggers a previously triggered interaction |

**Test verification** (`test_interaction.py:260-285`): with `A1=0.3, A2=0.3, A3=2.0`, `amplification_ceiling=2.0`, and `I(A1,A2)=1.5`, the ceiling applies and `total = 0.6 + 1.2 = 1.8` (clipped from 0.6 + 1.5 = 2.1).

### 4.3 GCAE Integration

NOMOS integrates the Cognitive Audit Engine via a bidirectional adapter (`audit/cognitive/adapter.py`):

- **NOMOS → GCAE** (`build_gcae_context`): translates `DecisionRequest` + `DecisionResult` into GCAE decision-context dict (assumptions, branches, narrative text, outcome).
- **GCAE → NOMOS** (`_translate_findings`): maps GCAE plugin outputs (NS, IAP, LCH, CCS, STATE) into `CognitiveRiskFinding` list, with severity mapping `HALT→ERROR`, `WARN→WARNING`, `PASS/INFO→INFO`.

---

## 5 Evaluation

### 5.1 Test Suite

The reference implementation ships **385 pytest functions** across 29 files. Key test categories:

| Test File | Count | Coverage |
|-----------|-------|----------|
| `test_api.py` | 22 | API endpoints |
| `test_postgres.py` | 20 | Persistence layer |
| `test_hub.py` | 16 | Session orchestration |
| `test_cli.py` | 14 | CLI interface |
| `test_cognitive.py` | 15 | GCAE adapter |
| `test_service.py` | 11 | Service layer |
| `test_session.py` | 10 | Session state machine |
| `test_repository.py` | 9 | Repository pattern |
| `test_selection.py` | 7 | Candidate selection |
| `test_scenario.py` | 6 | Scenario execution |
| `test_causal.py` | 6 | Invalidation closure |
| `test_report.py` | 6 | Report generation |
| `test_execution.py` | 5 | Audit execution |
| `test_llm_compliance.py` | (see note) | LLM guard tests |

*(Source: `tests/` directory, `def test_` count)*

### 5.2 Key Assertions

1. **Convergence state enum stability** (`test_convergence.py`): All five `ConvergenceStatus` string values are stable across versions.
2. **Schema rejection of unknown references** (`test_interaction.py`): Interaction with unknown assumption member (`A9` not in `{A1}`) raises `InvariantViolation` with `match="I-2"`.
3. **Ceiling clipping numerical correctness** (`test_interaction.py:260-285`): Verified with exact arithmetic — `total = 1.8` (clipped from 2.1).
4. **Strict schema validation** (`models/schemas.py`): `StrictModel(extra="forbid")` rejects extraneous fields; `validate_references` checks duplicate IDs, unknown dependencies, unknown evidence, weight sum to 1 (within `Decimal("0.000001")`).

---

## 6 Discussion

### 6.1 What NOMOS Guarantees

- **Structural LLM containment.** LLM output cannot reach verdict fields by construction (forbidden keys + zone whitelist + tier stripping).
- **Deterministic reproducibility.** Given the same inputs (candidate hypotheses + declared deltas + virtual clock seed), the evaluator produces identical outputs across invocations (P-2).
- **End-to-end auditability.** Every round produces a chained SHA-256 audit event; decision records are sealed and verifiable with `hmac.compare_digest`.

### 6.2 What NOMOS Does Not Claim

- **No accuracy claim.** NOMOS does not assert that its decisions are "better" than MCDA or LLM-as-judge. It asserts that its decisions are **auditable and reproducible**.
- **No calibrated thresholds.** Constants (e.g., `amplification_ceiling`, convergence gap thresholds) are heuristic defaults, not calibrated against empirical data.
- **No real-world dataset evaluation.** All 385 tests verify engineering correctness, not empirical decision quality.
- **No formal machine verification.** P-1/P-2/P-3 are proof sketches in docstrings, not machine-checked proofs (no Coq/Lean/TLA+).
- **Human declaration burden.** Interaction strengths, weights, and responsibility accounts require manual input; the impact on usability is not evaluated.

---

## 7 Conclusion

NOMOS demonstrates that LLM participation and deterministic audit can coexist through **structural enforcement**: zone isolation, forbidden-key stripping, pure-function evaluation, and SHA-256 chained audit events. The convergence formalization (P-1/P-2/P-3) and interaction invariants (I-1/I-2/I-3/I-4) provide a verifiable foundation for decision auditing in regulated contexts. The reference implementation (385 tests, all passing) serves as an artifact for the "deterministic audit" design pattern.

**Future work.** (1) Calibrate thresholds against real-world decision datasets. (2) Add machine-checked proofs for P-1/P-2/P-3. (3) Evaluate human declaration burden through user studies. (4) Compare NOMOS's audit completeness against MCDA and LLM-as-judge baselines on standardized decision corpora.

---

## References

[1] Cognitive Audit Engine (GCAE) — second-perspective repository, plugin architecture (NS/IAP/LCH/CCS/STATE).

[2] EU AI Act (2024) — high-risk AI system transparency and audit requirements.

[3] ISO/IEC 42001:2023 — AI management system standard.

[4] NIST AI Risk Management Framework (2023).

[5] Saaty, T.L. "The Analytic Hierarchy Process." McGraw-Hill, 1980.

[6] Hwang, C.L., Yoon, K. "Multiple Attribute Decision Making." Springer, 1981.

---

*Paper drafted 2026-09-28. Source implementation: `github.com/nohn3043-arch/nomos` (v0.4.0). All factual claims verified against implementation layer — no README or class-name inference used. 385 pytest functions, all passing.*