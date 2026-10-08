# Self-Verification & Evaluation-Design Guide

<p align="center">
[简体中文](TESTING-zh.md) | English
</p>

> The repository's **single test entry point**, in two steps:
> **① Verify the engine** — one command with `verify.py` (~5 minutes, works right after clone);
> **② Design your own evaluation** — methodology and criteria in §4; corpus, annotation, and comparison arms are yours to build.
> Zero third-party dependencies, fully offline.

## 0. What this package tests — and what it does not

| | Content |
|---|---|
| Built in · you run it | The engine's mechanical promises: dependency-free offline loading, determinism, tamper-evidence, reproducibility — verified by `verify.py` in one command |
| Built in · you run it | Five-operator end-to-end demo `demo_audit.py`; language-standard toolchain `language Standard/dsl.py` |
| You build | Evaluation design for **your own subject under test**: corpus, annotation, comparison arms, statistics — methodology in §4 |
| Not shipped | A ready-made question bank. Synthetic corpora have no discriminative power for real subjects; a formal comparison must use your own real subjects and corpus |

## 1. License prerequisite

This repository is not open source (see [LICENSE](./LICENSE)): free for individual non-commercial research; **government agencies and enterprises must sign a commercial license before use and self-testing** (International [ai@nohnlins.com](mailto:ai@nohnlins.com) · China [lin@secondai.top](mailto:lin@secondai.top)). The procedures below assume you hold the corresponding license.

## 2. Requirements

| Item | Requirement |
|---|---|
| Python | 3.10+ (3.13 tested here) |
| Third-party dependencies | **None** — all scripts use the standard library (stdlib) only; no network access at any point |
| OS | Windows / macOS / Linux (on Windows, Git Bash recommended; set `PYTHONIOENCODING=utf-8` in the console to avoid mojibake) |

All commands below assume you are **in the repository root**.

## 3. Step 1 · Verify the engine (~5 minutes)

### 3.1 Independent verification suite — `verify.py`

```bash
python verify.py            # human-readable report
python verify.py --json     # machine-readable (CI-friendly)
python verify.py --root     # print only the chain root (single line), for cross-machine comparison
```

Expected result: **PASS 9 · FAIL 0 · WARN 2**, exit code 0 ("all hard checks passed").

```bash
python verify.py --root
# Expected output (single line, byte-for-byte):
# f5713f49481a80f82356ba1255c0292ddb0d17a235a35348bcff0eef49d6a801
```

The two WARNs are **honestly disclosed design trade-offs, not defects**:

- **V3b — the certificate does not bind the original input**: the report stores only derived conclusions (a privacy design: sensitive decision data is never persisted); the cost is that the certificate cannot independently prove "this is exactly the input that was audited." When describing it externally, state the certificate's coverage explicitly — do not let the other party assume it covers the input.
- **V9 — nonce non-determinism on the default path**: the engine's `ResponsibilityAccount` generates its nonce with `uuid4()` by default, and chain events embed that nonce; therefore **byte-level reproduction requires scripts to explicitly pin the clock and nonce** (all scripts in this repository do so). The WARN also points to a fix direction (deterministic derivation via sha256 over account fields).

### 3.2 Five-operator end-to-end demo — `demo_audit.py`

```bash
python demo_audit.py
```

Expected: no errors; prints the audit report text of all five operators (NS / IAP / LCH / CCS / STATE) over the example decision.

### 3.3 DSL toolchain (optional)

```bash
python "language Standard/dsl.py" check "language Standard/examples/valid_decision.spd"    # PASS, exit 0
python "language Standard/dsl.py" check "language Standard/examples/invalid_decision.spd"  # FAIL, exit 1
python "language Standard/dsl.py" gen --seed 2026 --count 5 --out samples/ --self-check
```

## 4. Step 2 · Design your own evaluation (methodology)

> The following are the general criteria used by the GCAE evaluation pipeline (a simplified version of §5.3 of Test Specification v1.0).
> Design along these lines and your results will align with our reporting criteria and withstand third-party recomputation.

### 4.1 General principles

- **Fix the criteria before running the data**: thresholds, pass definitions, and sample sizes are written down in the design phase; run the full set, never cherry-pick items based on results (cherry-picking = score gaming).
- **Third-party recomputable**: pinned clock, pinned responsibility nonce, frozen inputs; artifacts ship with a per-file SHA-256 manifest so an outsider can run `sha256sum -c` and verify no tampering.
- **Thresholds apply to the subject's response set**, not to the pass rate of individual arms.

### 4.2 Corpus and annotation

- Each item is **independently annotated by 2 annotators** (blind to each other); disagreements are adjudicated item by item and kept on file;
- Report annotation quality: **raw agreement + Cohen's κ** (≥0.70 reference line);
- Route items by modality (prompt response / protocol measurement / audit artifact), recording expected / forbidden behavior per item.

### 4.3 Comparison arms (what counts as the baseline)

- Baseline = the **status-quo process** (humans + existing systems, or an existing LLM-assisted process); other arms are compared against this;
- Model arms: one independent request per item, temperature 0, **≥2 repetitions** to measure stability; the judgment file is frozen and pinned into the evidence chain (the whole file's SHA-256 goes into the audit chain — change one byte and the chain root changes);
- Only the same items (common entries) can be compared pairwise; subset runs must explicitly report the coverage drop.

### 4.4 Statistical criteria (five-layer report)

| Layer | Requirement |
|---|---|
| Marginal | Pass rates must carry a **Wilson 95% CI**; never report a bare point estimate |
| Paired | Same-item comparisons use **exact McNemar** (report b/c discordant counts and p; when there is no discordance, state "no discordance" — do not fabricate a p value) |
| Churn / replay | Re-running the same input must be **zero-flip** (Iron Law II); cross-run flips are listed separately (model stability) |
| Sample size / coverage | List each arm's item count; annotate subset runs with their reduced coverage |
| Per item | Per-item judgment artifacts (JSONL) are kept on file with the report |

### 4.5 Structure and scoring criteria (hallucination dimension example)

| State | Structural definition | Scoring |
|---|---|---|
| `anchored` | Premise assumptions and failure branches both declared; structure closes | Pass |
| `floating` | Premise assumptions declared, but no branch response when they fail | Pass |
| `opaque` | Premise assumptions not declared | Fail |
| `hollow` | No assumptions declared and no substantive content (lexical black hole) | Fail |

- "Hallucination" in this dimension means **assertions with undeclared assumptions** (structural scoring; it does not judge whether content is factually true);
- Threshold example: Hollow rate > 20% → HALT for the batch (thresholds may be customized per dimension, but must be **fixed before use**).

### 4.6 Evidence chain

- Deterministic clock + pinned responsibility nonce (see the V9 note in §3.1) to guarantee byte-level reproducibility;
- Per-event SHA-256 chain + chain root; artifact directories ship with a tamper-evidence manifest;
- Audit certificates explicitly state their coverage (see the V3b note in §3.1).

### 4.7 Honest disclosures to include in the report

- Corpus nature (synthetic/real) and known bias; label uncertainty (κ, number of disagreements);
- Threshold triggers reported truthfully (e.g., Hollow >20% → HALT is the mechanism working as defined, not an anomaly);
- Ceiling effect: if a narrow subject surface leads to a high pass rate, state that it "**does not represent open-domain performance**".

## 5. Formal evaluation & contact

- This file is a simplified guide to the methodology of Test Specification v1.0 for the "hallucination & factual consistency" dimension; for commissioned third-party evaluations or business partnerships, contact:
  - International — [ai@nohnlins.com](mailto:ai@nohnlins.com)
  - China — [lin@secondai.top](mailto:lin@secondai.top)
- License: free for individual non-commercial research (see [LICENSE](./LICENSE)); government agencies / enterprises must sign a commercial license before use.
