<div align="center">

# 📖 术语表 · Glossary

**GCAE · Global Cognitive Audit Engine**

*每个词都用一句人话解释 · Every term explained in one plain sentence*

</div>

---

> 英文术语保留原样，方便你对照 README、标准文档与代码。
> The English term is kept as-is so you can match it against the README, the standard and the source code.

| 术语 Term | 中文 | 一句话人话 · Plain meaning |
|---|---|---|
| **GCAE (Global Cognitive Audit Engine)** | 全球认知审计引擎 | 一台中立的「决策体检机」——不改你的模型代码，只审你决策的结构。 |
| **Second Perspective Engine (SPE 1.2)** | 第二视角引擎 1.2 | 内核的当前实现：在五算子上补一层无语义拓扑，并加上叠加螺旋式迭代。 |
| **Neutral audit** | 中立审计 | 不绑定任何大模型厂商，只做结构核验，不出主观结论。 |
| **Core offline** | 内核离线 | 审计全程本地运行、确定性强；联网增强默认关闭。 |
| **Decision-agnostic** | 决策无关 | 引擎不替你做决定，也不给优化建议，只给结构诊断。 |
| **Five Operators** | 五算子（2026.1） | 审计流水线原有的五个步骤：NS → IAP → LCH → CCS → ACC。 |
| **Ten Operators** | 十算子（2026.3） | 五算子 + 拓扑层四项 + 元因果账本：⊙GA → ⊗NS → ⊕IAP → ⊿LCH → ⊞LFT → BFC → ⚙CCS → ⇄GRF → META → ⊚ACC。 |
| **Binary Fact Check (BFC)** | 二元事实校验 | 把一条断言归约为真或假；证据真空、证据互斥、已证伪前提仍在用 → 阻断。**没有第三个真值**。 |
| **Extension seam** | 插件缝 | 引擎唯一的扩展 API：`register_operator()`。一条缝、四道闸门、一处留痕；不是插件生态。 |
| **Operator manifest** | 算子清单 | 报告里的 `operator_manifest`（顺序/权限层/来源），参与报告哈希——「这份报告由哪个算子集产生」因此可自证。 |
| **Operator-set hash** | 算子集指纹 | 只由「算子名 + 权限层 + 顺序」推导的哈希，写在链上事件里，可跨进程/跨语言复算。 |
| **Infinite reconstruction** | 无限因果重构 | `limit_reconstruct()`：层数不设上限，只按语义判据停（极限 S∞ = S\*）。 |
| **Convergence Rank** | 到目标稳态的收敛秩 | `(风险集规模, 是否有未决假设)` 的字典序量，判「还在不在逼近」的唯一依据。 |
| **LIMIT_REACHED / FLAT_SPIRAL / NOT_MONOTONE** | 极限抵达 / 画地为牢 / 不再逼近 | 无限重构的三类新终局判据。 |
| **spiral_step** | 单层推进 | 外部驱动的无限迭代入口：跑一层就交回控制权；引擎永不自己生成修正。 |
| **Third truth value** | 第三真值 | 本层不允许的东西——"不知道"不是答案。`binary=None` 只表示未声明，必然伴随 VERDICT_UNDECLARED 信号。 |
| **Evidence vacuum** | 证据真空 | 断言一条证据都没有；此时归约无法成立，直接中断并列出补齐条件。 |
| **Evidence conflict** | 证据互斥 | 同一断言的证据互相否定；本层不选边，交由证据源裁定，直接中断。 |
| **Falsified premise** | 已证伪前提 | 断言已被核验为假，却仍挂在假设集里——决策支柱已断，必须撤下或触发 ΔD。 |
| **Genesis Anchor (GA · ⊙)** | 第一原点锚定 | 钉死链的起点（原点事件）、终点（目标稳态）与能量资源约束；原点真空即阻断。 |
| **Label-Free Topology (LFT · ⊞)** | 无标签拓扑图 | 把决策拆成无语义的「节点 + 边」，只谈连接不谈命名，再跑四类校验。 |
| **Gray Feedback (GRF · ⇄)** | 灰度执行与现实反馈 | 把预测的崩塌与现实返回的观测对齐；现实已证伪却没有回退路径，直接阻断。 |
| **Superimposed Spiral (SPR · ↻)** | 叠加螺旋式迭代链路 | 每一圈在上一圈的结构上继续长，已收敛子图冻结后不再重开。 |
| **Topology symbols** | 拓扑符号 | `□` 节点 · `→` 因果边 · `t` 链内时序 · `⦿` 全局公理约束 · `△` 上游（可证伪输入）· `◇` 下游（不可篡改输出）。 |
| **Chain-internal time order (`t`)** | 链内时序 | 公理 5：时间不是可拆字段，而是「链」的构成条件。可选声明；缺位由**最长路径**派生。 |
| **Parallel vs fork** | 平行 vs 分支 | 平行是同一世界线上多条各自有序的链（多起点，**合法**）；分支是未来在一个节点上真的分叉（同一对节点多条边，**违规**）。SPL 是强决定论，只承认前者。 |
| **Relative labels** | 相对标签 | △/◇ 不是节点的固有属性：同一节点在 A→B 上是 ◇，在 B→C 上就是 △。 |
| **Four parallel checks** | 四类并行校验 | 一致性（致命）· 约束满足（致命）· 拓扑闭合（警告，结果无效）· 链内时序（警告，结果无效）。 |
| **Meta-Causal Ledger (META)** | 元因果账本 | 把规范第六条的元因果基底落成五个可计算的账本；是**度量**不是裁决，取 T2 层，**永不阻断**。 |
| **Meta-causal Grounds** | 元因果基底 | 溯源缺口 · 并行收敛 · 叙事遮蔽 · 审计有界 · 因果承接 —— 五条元基，规范里本就存在，此前只停在注释里。 |
| **Hundun · Unparsed Antecedence (溯源缺口)** | 溯源缺口 | 原初起点与能量本根。「随机」不在溯源缺口之中，**只在观测者的知识缺口之中**：全部前置因未被解析，故显为溯源缺口。 |
| **Wuji · Non-forking Convergence (并行收敛)** | 并行收敛 | 最初之始亦最终之终：**多线并行而非分支分叉**；极限处唯一收敛（S∞ = S\\*）。 |
| **Xuhuan · Narrative Register (叙事遮蔽)** | 叙事遮蔽 | 现实的反面，与现实一体两面，是叙事事件 N_t 的所在；由 ⊖ 析出干逻辑。 |
| **A6 narrative entropy** | A6 叙事熵 | 遮蔽字符数 / 原文总字符数 —— 一个**有理数**，不是概率。它只度量遮蔽程度，不判断对错。 |
| **Tiandao · Neutrality Invariant (审计有界)** | 审计有界 | 公平本身：审计中立的本体表述——审计不参与决策，只审计决策如何形成。 |
| **A10 audit entropy** | A10 审计熵增 | 每层新增留痕条数，即 version 递增速率的离散版。**有界**才使演化收敛于 S\\*（这是自主进化的停机定理来源）。 |
| **Lunhui · Effect-to-Cause Succession (因果承接)** | 因果承接 | 不是链的自环，而是链的**普遍承接**：能量动态守恒，每一个果即刻成为下一个因，序不可倒置。 |
| **Autonomous evolution (`evolve()`)** | 自主进化层 | 引擎自己**发现**结构缺口并产出候选清单，但**永不自己改写判定规则**。 |
| **Propose-only** | 只提案不适用 | 三条恒等式：`applies_automatically=False` · `requires_human=True` · `auto_applied=0`。 |
| **Lineage** | 版本谱系 | 「这份链根属于第几代引擎」：代际 + 算子集指纹 + 管线顺序 + 文法版本。它是进化与可复现性共存的前提。 |
| **Minimal fixed point** | 最小不动点 | 自主进化的停机判据：`g_{n+1} == g_n`（图同构），而不是「预算跑完了」。 |
| **Causal paradox** | 因果悖论 | A→B→C→¬A 这类有向环；时间序不可循环，故链不能绕回自身（诊断码 T303）。 |
| **Origin drift** | 原点漂移 | 螺旋绕到目标已经不是原来那个；一旦检出立即停机（ORIGIN_DRIFT）。 |
| **Frozen subgraph** | 冻结子图 | 已判定收敛的节点集合，只增不减；被解冻即螺旋退化为覆盖。 |
| **Spiral Budget** | 螺旋预算 | 螺旋每层消耗额度，预算不足即停——拓扑无边界，但「无限」必须有硬顶。 |
| **Graph hash** | 拓扑指纹 | 只由纯结构推导的哈希：不含标签、不含留痕，故「换了名字不换结构」指纹不变。 |
| **Narrative Stripping (NS)** | 叙事剥离 | 删掉修辞、情绪与模糊限定词，只留逻辑主干。 |
| **Implicit Assumption Perspective (IAP)** | 隐含假设透视 | 把没说出口的预设、越权前提与循环论证翻出来。 |
| **Fragility Localization (LCH)** | 脆弱性定位 | 给每个假设算一个坍塌概率 ΔD，找出最脆弱的那一环。 |
| **Chain Closure Scan (CCS)** | 链闭合扫描 | 反向验证 + 反事实验证 + 信息黑洞检测。 |
| **Accountability Anchoring (ACC)** | 责任锚定 | 锚定责任人，并出具 SHA-256 审计证书。 |
| **p → Q** | 因果连接 | p 是原则 / 规则 / 约束，Q 是结果 / 状态；箭头表示不可绕过、不可切断的因果连接。 |
| **Structural Audit Predicate Φ{f_s, x, y}** | 结构审计谓词 | 只回答一个问题：「这个决策结构是否满足最低理性一致要求」——是或否。 |
| **¬A ⇒ ΔD** | 第二视角决策公式 | 一个有效决策 = 决策 D × 假设前提 A × 分支响应 ΔD；核心假设失效时，分支响应必须触发。 |
| **ΔD** | 坍塌概率 / 分支响应 | 假设失效之后，系统的变动幅度。 |
| **Information black hole** | 信息黑洞 | 因果链里缺了「必需节点」，导致后面至少两个节点无法成立。 |
| **ResponsibilityAccount** | 责任人账户 | 把每条审计结论锚定到具体的组织 / 角色 / 阶段。 |
| **Audit certificate** | 审计证书 | SHA-256 哈希链凭证，可跨机器比对、独立复验。 |
| **Deterministic / seeded** | 确定性 / 随机种子 | 同样的输入永远给同样的输出；随机也用固定种子。 |
| **Decision Structure Language (`.spd`)** | 决策结构语言 | 一套只描述「决策在什么边界内成立」的结构 DSL，本身不带执行语义。 |
| **Validator (`dsl.py check`)** | 校验器 | 检查 `.spd` 记录是否符合语法与约束；不合规直接拒绝。 |
| **Diagnostic codes** | 诊断码 | 机器可读的诊断编号；拓扑层为 T101–T308（含 2026.3 新增的 T305 分叉 / T307 序倒置 / T308 序不可赋值）。 |
| **IMDA AI Verify** | 新加坡 AI 合规评估 | 新加坡官方 AI 治理框架；本引擎总分 95。 |
| **Clean-room declaration** | 洁净室声明 | 若无法提供独立开发的完整证据，则推定构成实质性衍生侵权。 |

---

## ✦ English Glossary

*Every term explained in one plain sentence.*

| Term | Plain meaning |
|---|---|
| **GCAE (Global Cognitive Audit Engine)** | A neutral "decision health check" — it doesn't change your model's code, it audits the structure of your decision. |
| **Neutral audit** | Bound to no model vendor; it only verifies structure and issues no subjective conclusion. |
| **Core offline** | The whole audit runs locally with strong determinism; online enhancement is off by default. |
| **Decision-agnostic** | The engine won't decide for you or suggest optimizations — only structural diagnosis. |
| **Second Perspective Engine (SPE 1.2)** | The current implementation of the core: a de-semantic topology layer on top of the five operators, plus superimposed spiral iteration. |
| **Five Operators** | The five original steps of the audit pipeline: NS → IAP → LCH → CCS → ACC. |
| **Ten Operators** | The five operators plus the four topology-layer ones plus the meta-causal ledger: ⊙GA → ⊗NS → ⊕IAP → ⊿LCH → ⊞LFT → BFC → ⚙CCS → ⇄GRF → META → ⊚ACC. |
| **Binary Fact Check (BFC)** | Reduces a claim to true or false; an evidence vacuum, mutually negating evidence, or a falsified premise still in use blocks the audit. **No third truth value.** |
| **Extension seam** | The engine's one extension API: `register_operator()`. One seam, four gates, one trace — not a plugin ecosystem. |
| **Operator manifest** | The `operator_manifest` field in a report (order / tier / origin); it takes part in the report hash, so "which operator set produced this report" is self-proving. |
| **Operator-set hash** | A hash derived from operator name + tier + order only, written into the chain event, recomputable in another process or language. |
| **Infinite reconstruction** | `limit_reconstruct()`: no ceiling on layers; stops only on semantic criteria (the limit S∞ = S\*). |
| **Convergence Rank** | The lexicographic quantity `(risk-set size, has unresolved assumptions)` — the sole basis for "is it still approaching". |
| **LIMIT_REACHED / FLAT_SPIRAL / NOT_MONOTONE** | The three new terminal criteria of infinite reconstruction. |
| **spiral_step** | The externally driven entry point: run one layer, hand control back; the engine never invents corrections. |
| **Third truth value** | The one thing this layer forbids — "unknown" is not an answer. `binary=None` only means "not declared", always paired with a VERDICT_UNDECLARED signal. |
| **Evidence vacuum** | A claim with no evidence at all; reduction cannot hold, so the audit halts and lists what must be supplied. |
| **Evidence conflict** | Sources on one claim negate each other; this layer does not pick a side — it halts and leaves the call to the sources. |
| **Falsified premise** | A claim verified false that still sits in the assumption set — the pillar is broken; drop it or fire the matching ΔD. |
| **Genesis Anchor (GA · ⊙)** | Pins the start of the chain (origin event), the end (target state) and the energy/resource constraints; an origin vacuum blocks the audit. |
| **Label-Free Topology (LFT · ⊞)** | Breaks a decision into de-semantic nodes and edges — connection first, naming later — then runs four checks. |
| **Gray Feedback (GRF · ⇄)** | Aligns predicted collapse with observed reality; reality already falsified the assumption while no branch fired — blocks. |
| **Superimposed Spiral (SPR · ↻)** | Each loop grows on top of the previous structure; a converged subgraph is frozen and never reopened. |
| **Topology symbols** | `□` node · `→` causal edge · `t` chain-internal time order · `⦿` global axiom · `△` upstream (falsifiable input) · `◇` downstream (untamperable output). |
| **Chain-internal time order (`t`)** | Axiom 5: time is not a detachable field but a constitutive condition of a *chain*. Optional; when absent it is derived by **longest path**. |
| **Parallel vs fork** | Parallel is several chains on one world line, each ordered on its own (many roots — **legal**); a fork is the future really splitting at a node (one pair, many edges — **forbidden**). SPL is strongly deterministic and admits the former only. |
| **Relative labels** | △/◇ are not intrinsic node properties: a node is ◇ on A→B and △ on B→C. |
| **Four parallel checks** | consistency (fatal) · constraint satisfaction (fatal) · closure (warning — result void) · time order (warning — result void). |
| **Meta-Causal Ledger (META)** | Turns the five meta-grounds of normative clause 6 into five computable ledgers. It **measures**, it does not adjudicate: tier T2, structurally incapable of blocking. |
| **Meta-causal Grounds** | Hundun · Wuji · Xuhuan · Tiandao · Lunhui — five meta-grounds that already existed in the normative reference, until now only in comments. |
| **Hundun · Unparsed Antecedence (溯源缺口)** | The primal origin and the root of energy. "Chance" is not in chaos, **only in the observer's knowledge gap**: every antecedent unparsed, hence it appears as chaos. |
| **Wuji · Non-forking Convergence (并行收敛)** | First beginning and final end: **many chains in parallel, never a fork**; at the limit it converges uniquely (S∞ = S\*). |
| **Xuhuan · Narrative Register (叙事遮蔽)** | The reverse of reality, one thing with two faces, where narrative events N_t live; ⊖ extracts the logical core from it. |
| **A6 narrative entropy** | Masked characters / total characters — a **rational number**, not a probability. It measures the degree of occlusion and judges nothing. |
| **Tiandao · Neutrality Invariant (审计有界)** | Fairness itself: the ontological statement of audit neutrality — the audit does not take part in the decision, only in how the decision was formed. |
| **A10 audit entropy** | Provenance entries per layer, the discrete form of d(version)/dt. A **bounded** A10 is what lets evolution converge to S\* — the halting theorem behind autonomous evolution. |
| **Lunhui · Effect-to-Cause Succession (因果承接)** | Not the chain's self-loop but its **universal succession**: energy is dynamically conserved, every effect immediately becomes the next cause, and order is never inverted. |
| **Autonomous evolution (`evolve()`)** | The engine **discovers** structural gaps and emits a proposal list, but **never rewrites its own adjudication rules**. |
| **Propose-only** | Three identities: `applies_automatically=False` · `requires_human=True` · `auto_applied=0`. |
| **Lineage** | "Which generation of the engine produced this chain root": generation · operator-set hash · pipeline order · grammar version. It is what lets evolution and reproducibility coexist. |
| **Minimal fixed point** | The halting criterion of autonomous evolution: `g_{n+1} == g_n` (graph isomorphism), not "the budget ran out". |
| **Causal paradox** | A directed cycle such as A→B→C→¬A; time order cannot loop, so a chain cannot fold back onto itself (diagnostic code T303). |
| **Origin drift** | The spiral circles until the target is no longer the original one; detected → immediate halt (ORIGIN_DRIFT). |
| **Frozen subgraph** | The set of nodes declared converged; it only ever grows. Unfreezing it means the spiral degraded into overwriting. |
| **Spiral Budget** | Each spiral layer costs budget; when it runs out, stop — topology is unbounded, but "infinite" needs a hard ceiling. |
| **Graph hash** | A hash derived from pure structure only: no labels, no provenance — so renaming a node does not change the fingerprint. |
| **Narrative Stripping (NS)** | Strips rhetoric, emotion and vague qualifiers, keeping only the logical backbone. |
| **Implicit Assumption Perspective (IAP)** | Digs out unstated premises, overreaching assumptions and circular arguments. |
| **Fragility Localization (LCH)** | Computes a collapse probability ΔD for each assumption to find the most fragile link. |
| **Chain Closure Scan (CCS)** | Backward verification + counterfactual verification + information-black-hole detection. |
| **Accountability Anchoring (ACC)** | Anchors the responsible party and issues a SHA-256 audit certificate. |
| **p → Q** | p is the principle / rule / constraint, Q is the result / state; the arrow is a causal link that cannot be bypassed or cut. |
| **Structural Audit Predicate Φ{f_s, x, y}** | Answers one question only: does this decision structure meet the minimum requirement of rational consistency — yes or no. |
| **¬A ⇒ ΔD** | A valid decision = decision D × premise A × branch response ΔD; when a core assumption fails, the branch response must fire. |
| **ΔD** | The magnitude of system change after an assumption fails. |
| **Information black hole** | A missing mandatory node in the causal chain that makes at least two downstream nodes impossible. |
| **ResponsibilityAccount** | Anchors every audit conclusion to a specific organization / role / stage. |
| **Audit certificate** | A SHA-256 hash-chain credential, comparable across machines and independently verifiable. |
| **Deterministic / seeded** | Same input always gives the same output; even randomness uses a fixed seed. |
| **Decision Structure Language (`.spd`)** | A structural DSL that only describes the boundaries within which a decision holds; it carries no execution semantics. |
| **Validator (`dsl.py check`)** | Checks whether a `.spd` record satisfies the grammar and constraints; non-compliant ones are rejected outright. |
| **Diagnostic codes** | Machine-readable diagnostic numbers; the topology layer spans T101–T308 (including the 2026.3 additions T305 fork / T307 inverted order / T308 unassignable order). |
| **IMDA AI Verify** | Singapore's official AI governance framework; this engine scores 95 overall. |
| **Clean-room declaration** | Without full evidence of independent development, substantial derivative infringement is presumed. |

---

<div align="center">

[← 返回 README](./README.md) &nbsp;·&nbsp; [中文说明](./README-zh.md)

<sub>NOHN AI · SECOND-PERSPECTIVE (GCAE)</sub>

</div>
