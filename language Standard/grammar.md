# Decision Structure Language — Grammar Specification

| Item | Value |
|---|---|
| Version | 2026.1 |
| Notation | ISO/IEC 14977 EBNF |
| Parent standard | [`2026.md`](./2026.md) — Language Standard 2026 |
| Grammar file | [`decision.ebnf`](./decision.ebnf) |
| Toolchain | [`dsl.py`](./dsl.py) |
| File extension | `.spd` |
| Chinese edition | [`grammar-zh.md`](./grammar-zh.md) |

---

## 0. Positioning: this is not a programming language

Before any grammar discussion, the boundary must be nailed down — otherwise every downstream
implementation drifts.

This language is a **DSL (domain-specific description language)**. It shares only the *upper half*
with general-purpose languages such as Python:

| Layer | This language | Python |
|---|---|---|
| ① Grammar | ✅ `decision.ebnf` | ✅ Language Reference |
| ② Parse / validate | ✅ `dsl.py check` | ✅ Parser |
| ③ Execution engine | ❌ **forbidden by the standard** | ✅ Interpreter |

**Why layer ③ is absent.** The *Constraints* section of `2026.md` states explicitly: no conclusions
or recommendations may be emitted; no scoring, ranking or probability assignment; no optimisation
or decision guidance; the system must not replace or simulate decision-making. Therefore this
language **only describes "the boundary within which a decision holds" and computes no result**.

Its closest analogue is **JSON Schema**: it defines shape, checks conformance, and carries no
business logic.

---

## 1. Complete grammar

The following is normative and matches [`decision.ebnf`](./decision.ebnf) verbatim.

### 1.1 Document structure

```ebnf
document        = { comment } , decision ,
                  { comment } , assumptions ,
                  { comment } , [ dependencies ] ,
                  { comment } , branches ,
                  { comment } ;

assumptions     = assumption , { { comment } , assumption } ;
dependencies    = dependency , { { comment } , dependency } ;
branches        = branch , { { comment } , branch } ;
```

**Block order is normative** and may not be permuted:

```
Decision  →  Assumption+  →  Dependency*  →  Branch+
```

Any other order raises `E108`.

### 1.2 Core productions

```ebnf
decision        = "Decision" , colon , text ;

assumption      = "Assumption" , space , id , colon , text ;

dependency      = "Dependency" , colon , space , id , space , verb , space , id ;

branch          = "Branch" , space , id , colon , text ;
```

| Production | Semantics | Key constraint |
|---|---|---|
| `decision` | The concrete action or judgement to execute | Exactly one per document |
| `assumption` | An explicit premise that validates the decision | Must be falsifiable, non-vague, non-self-evident |
| `dependency` | An explicit ordering relation between premises | Optional; must reference declared premises; graph must be acyclic |
| `branch` | The **structural change** to the decision when a premise fails | Must describe structural impact — never an alternative decision |

> **On the boundary of `branch`**: it answers "if this assumption collapses, does the decision still
> hold, and how does it deform?" — **not** "what would be better instead?" The latter is a
> recommendation, and the standard forbids it.

### 1.3 Lexical elements

```ebnf
verb            = "requires" | "depends" , space , "on" ;

id              = letter , { letter | digit | "_" } ;

text            = { space } , nonspace , { graphic | space } ;

comment         = "#" , { graphic | space } ;

colon           = ":" | "：" ;
space           = " " ;
letter          = upper | lower ;
upper           = ? U+0041 .. U+005A , i.e. "A" to "Z" ? ;
lower           = ? U+0061 .. U+007A , i.e. "a" to "z" ? ;
digit           = ? U+0030 .. U+0039 , i.e. "0" to "9" ? ;
nonspace        = ? any Unicode character except U+0009, U+000A, U+000D, U+0020 ? ;
graphic         = ? any Unicode character except U+0009, U+000A, U+000D ? ;
newline         = ? U+000A | U+000D U+000A ? ;
```

Points of note:

1. **`id`** starts with a letter, optionally followed by letters, digits or underscores. `A1`,
   `budget_2` and `X` are all valid.
2. **`text`** is read per line; leading and trailing whitespace is trimmed. After trimming it must
   not be empty (otherwise `E203`).
3. **`comment`** supports whole-line comments only, never trailing comments. This is deliberate:
   trailing comments make the extent of `text` undecidable.
4. **Full-width colon `：`** is equivalent to `:` for convenience in CJK writing. Only the first
   colon participates in tokenisation.

---

## 2. Meta-symbol table

| Symbol | Meaning | Example |
|---|---|---|
| `=` | Definition: the left-hand concept is replaced by the right-hand side | `id = letter , ...` |
| `,` | Concatenation: both sides must appear in order | `"Assumption" , id` |
| `\|` | Choice: either side | `"requires" \| "depends on"` |
| `{ ... }` | Repetition: zero or more occurrences | `{ letter \| digit }` |
| `[ ... ]` | Optional: zero or one occurrence | `[ dependencies ]` |
| `( ... )` | Grouping: scopes choice and repetition | — |
| `"..."` | Terminal: a literal sequence appearing verbatim | `"Decision"` |
| `? ... ?` | Special sequence: not expressible in EBNF, described in prose | `? any Unicode character ?` |
| `(* ... *)` | Comment: not part of the grammar | see file header |

---

## 3. Compliance constraints

Constraints are graded in four tiers. The first three derive from the *Constraints* section of
`2026.md`; the fourth derives from its *Branches* section.

### L1 · Structural

| Code | Rule | Consequence of violation |
|---|---|---|
| `E101` | Exactly one `Decision` is required | No subject, or ambiguous subject |
| `E103` | At least one `Assumption` is required | Decision has no boundary — it degrades into an assertion |
| `E107` | Every `Assumption` needs a `Branch` with the same id | Unlabelled failure points |
| `E105` | `Assumption` ids must be unique | Ambiguous references |
| `E104` | `Branch` / `Dependency` references must be declared | Dangling references |
| `E106` | The dependency graph must be acyclic | Cyclic dependencies cannot be ordered |
| `E108` | Block order may not be permuted | Parsing ambiguity |

### L2 · Constraints (*2026.md*, lines 44–50)

| Code | Rule | Authority |
|---|---|---|
| `E301` | No conclusion-bearing statements | *No conclusions* |
| `E302` | No recommendation statements | *No recommendations* |
| `E303` | No scoring, ranking or probability assignment | *No scoring, ranking, or probability assignment* |
| `E304` | No optimisation or decision guidance | *No optimization or decision guidance* |

> These four rules are **the entire reason this language exists** as distinct from a plain note
> format. A `.spd` file may be syntactically perfect and still be non-conforming if it contains the
> phrase "we should adopt" — that is a recommendation.

### L3 · Quality (advisory; warns, does not block)

| Code | Rule | Rationale |
|---|---|---|
| `W401` | Assumption contains a vague qualifier (probably / roughly / 可能 / 大约 …) | Insufficient falsifiability |
| `W402` | Assumption has no observable threshold (neither a number nor a comparison) | Cannot be adjudicated true or false |
| `W403` | Assumption looks self-evident (too short, or a platitude) | Does not constitute a valid boundary |

### L4 · Dependency semantics

- `requires` — **hard prerequisite**: if B does not hold, A cannot be evaluated.
- `depends on` — **value coupling**: the degree to which B holds affects the degree to which A holds.
- Both are semantic markers only. The language itself **does not compute** dependency strength.

---

## 4. Diagnostic code index

| Code | Level | Meaning |
|---|---|---|
| `E101` | ERROR | Missing `Decision` block |
| `E102` | ERROR | Duplicate `Decision` block |
| `E103` | ERROR | Missing `Assumption` block |
| `E104` | ERROR | Reference to an undeclared assumption id |
| `E105` | ERROR | Duplicate id declaration |
| `E106` | ERROR | Cycle in the dependency graph |
| `E107` | ERROR | Assumption without a matching `Branch` |
| `E108` | ERROR | Block order violated |
| `E201` | ERROR | Unrecognised line (unknown keyword) |
| `E202` | ERROR | Invalid identifier format |
| `E203` | ERROR | Empty text |
| `E204` | ERROR | Missing colon or separator |
| `E301` | ERROR | Conclusion-bearing statement |
| `E302` | ERROR | Recommendation statement |
| `E303` | ERROR | Scoring / ranking / probability assignment |
| `E304` | ERROR | Optimisation guidance |
| `W401` | WARN | Assumption contains a vague qualifier |
| `W402` | WARN | Assumption lacks an observable threshold |
| `W403` | WARN | Assumption looks self-evident |

Exit codes: `0` = conforming (or warnings only); `1` = at least one ERROR; `2` = usage error.

---

## 5. Worked examples

### 5.1 Conforming sample

```spd
# Conforming sample — Decision Structure Language 2026.1
Decision: Accept the Zhangjiang pilot as this quarter's only parallel workstream

Assumption A1: The target account's annual AI budget >= CNY 5,000,000
Assumption A2: Their procurement compliance review cycle <= 8 weeks
Assumption A3: Our unit compute cost is <= 70% of their self-built alternative

Dependency: A2 requires A1
Dependency: A3 depends on A1

Branch A1: Budget falls short — the project degrades to a single PoC and leaves the annual framework
Branch A2: Review overruns — delivery milestones shift by one tier and validation narrows to one line
Branch A3: Cost advantage fails — the cost narrative is voided and resource commitment is revised up
```

**Field by field:** 1 decision · 3 assumptions (each carrying an observable threshold) · 2
dependencies (acyclic, both anchored on `A1`/`A2`) · 3 branches (in one-to-one correspondence with
the assumption ids) · no conclusion, recommendation or ranking terms anywhere.

Source file: [`examples/valid_decision.en.spd`](./examples/valid_decision.en.spd).

### 5.2 Typical violations

The full violating sample is
[`examples/invalid_decision.en.spd`](./examples/invalid_decision.en.spd). Core fragment:

```spd
Decision: We should adopt the top-ranked option B

Assumption A1: The client probably has a large budget
Dependency: A3 requires A1
Branch A4: If budget falls short, the scope shrinks
```

Observed output (`python dsl.py check examples/invalid_decision.en.spd`), with line numbers
referring to that sample file:

| Line | Code | Trigger |
|---|---|---|
| 4 | `E302` | "should" — recommendation wording |
| 4 | `E303` | "ranked" — ranking assignment |
| 6 | `W401` | "probably" — vague qualifier |
| 6 | `W402` | "a large budget" — no observable threshold |
| 7 | `W402` | no observable threshold |
| 7 | `W403` | "This is obvious" — self-evident |
| 7 | `E107` | `A2` has no matching Branch |
| 8 | `E105` | duplicate identifier `A2` |
| 8 | `E107` | `A2` has no matching Branch |
| 10 | `E104` | dependency references undeclared `A3` |
| 12 | `E302` | "recommend" — recommendation wording |
| 13 | `E104` | branch references undeclared `A4` |

Result: 8 ERROR / 4 WARN, exit code `1`.

> **Capability boundary (stated explicitly).** `E301`–`E304` are **surface-pattern** matches, not
> semantic inference. Therefore an *implicit* ranking such as "option B" is not caught automatically.
> The tool guarantees "a ranking/recommendation term is intercepted when present" — it does **not**
> guarantee "every ranking/recommendation meaning is exhausted". This is a deliberate trade-off:
> better to under-report semantics than to pass inference off as a fact node.
>
> `E106` is likewise verified: with both `Dependency: A1 requires A2` and `Dependency: A2 requires A1`
> present, the tool reports `dependency cycle detected: A1 -> A2 -> A1`.

---

## 6. Relationship to existing documents

| Document | Role | Relation |
|---|---|---|
| `2026.md` | Normative standard (natural language) | The formalisation target of this file |
| `全新决策结构语言.md` | One-page overview | Condensed form of §0–§1 |
| `grammar-zh.md` | Chinese edition of this file | Mirrors this document |
| `decision.ebnf` | Machine-readable grammar | The source file of §1 |
| `dsl.py` | Reference toolchain | Executable implementation of §3–§4 |

The documents project one and the same formal kernel at **different levels of abstraction**:
one-pager (overview) → this file (specification) → EBNF (formalism) → dsl.py (executable). All must
be kept in sync; where they conflict, `2026.md` prevails.

---

## 7. Toolchain usage

```bash
# Validate one or more files
python dsl.py check examples/valid_decision.en.spd

# Strict mode: warnings also fail the exit code
python dsl.py check examples/valid_decision.en.spd --strict

# JSON output, for CI integration
python dsl.py check examples/valid_decision.en.spd --json

# Sample generator (seeded, reproducible). --lang en|zh, default en
python dsl.py gen --seed 2026
python dsl.py gen --seed 2026 --lang zh
python dsl.py gen --seed 2026 --count 5 --out examples/generated/ --self-check

# Print the grammar / look up a diagnostic code
python dsl.py grammar
python dsl.py codes E302
```

> **Bilingual validation.** The constraint and quality lexicons cover both English and Chinese
> terms. This is functional data, not documentation prose: a Chinese-language `.spd` file is
> validated with exactly the same diagnostic codes as an English one. See
> [`examples/valid_decision.spd`](./examples/valid_decision.spd) (Chinese) and
> [`examples/valid_decision.en.spd`](./examples/valid_decision.en.spd) (English).

---

*This language system is used only for structural review and decomposition within a decision
process. It does not participate in decision-making, nor does it intervene in the final decision.
The author assumes no legal or operational liability for any subsequent execution results.*
