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
| **Neutral audit** | 中立审计 | 不绑定任何大模型厂商，只做结构核验，不出主观结论。 |
| **Core offline** | 内核离线 | 审计全程本地运行、确定性强；联网增强默认关闭。 |
| **Decision-agnostic** | 决策无关 | 引擎不替你做决定，也不给优化建议，只给结构诊断。 |
| **Five Operators** | 五大算子 | 审计流水线的五个步骤：NS → IAP → LCH → CCS → STATE。 |
| **Narrative Stripping (NS)** | 叙事剥离 | 删掉修辞、情绪与模糊限定词，只留逻辑主干。 |
| **Implicit Assumption Perspective (IAP)** | 隐含假设透视 | 把没说出口的预设、越权前提与循环论证翻出来。 |
| **Fragility Latch (LCH)** | 脆弱性闩锁 | 给每个假设算一个坍塌概率 ΔD，找出最脆弱的那一环。 |
| **Causal Chain Synchronization (CCS)** | 因果链同步 | 反向验证 + 反事实验证 + 信息黑洞检测。 |
| **State Anchoring (STATE)** | 状态锚定 | 锚定责任人，并出具 SHA-256 审计证书。 |
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
| **Diagnostic codes** | 诊断码 | 19 个机器可读的诊断编号。 |
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
| **Five Operators** | The five steps of the audit pipeline: NS → IAP → LCH → CCS → STATE. |
| **Narrative Stripping (NS)** | Strips rhetoric, emotion and vague qualifiers, keeping only the logical backbone. |
| **Implicit Assumption Perspective (IAP)** | Digs out unstated premises, overreaching assumptions and circular arguments. |
| **Fragility Latch (LCH)** | Computes a collapse probability ΔD for each assumption to find the most fragile link. |
| **Causal Chain Synchronization (CCS)** | Backward verification + counterfactual verification + information-black-hole detection. |
| **State Anchoring (STATE)** | Anchors the responsible party and issues a SHA-256 audit certificate. |
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
| **Diagnostic codes** | The 19 machine-readable diagnostic numbers. |
| **IMDA AI Verify** | Singapore's official AI governance framework; this engine scores 95 overall. |
| **Clean-room declaration** | Without full evidence of independent development, substantial derivative infringement is presumed. |

---

<div align="center">

[← 返回 README](./README.md) &nbsp;·&nbsp; [中文说明](./README-zh.md)

<sub>NOHN AI · SECOND-PERSPECTIVE (GCAE)</sub>

</div>
