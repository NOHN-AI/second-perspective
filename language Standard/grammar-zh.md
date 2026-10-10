# 决策结构语言 · 语法规范

**Decision Structure Language — Grammar Specification**

| 项 | 值 |
|---|---|
| 版本 | 2026.2 |
| 记法 | ISO/IEC 14977 EBNF |
| 上位文档 | [`2026.md`](./2026.md) — Language Standard 2026 |
| 文法文件 | [`decision.ebnf`](./decision.ebnf) |
| 校验工具 | [`dsl.py`](./dsl.py) |
| 文件扩展名 | `.spd` |
| 英文版本 | [`grammar.md`](./grammar.md) |

---

## 0. 定位：这不是编程语言

在讨论语法之前，必须先钉死边界，否则一切后续实现都会跑偏。

本语言属于 **DSL（领域专用描述语言）**，与 Python 这类通用编程语言只有"上半身"相同：

| 层 | 本语言 | Python |
|---|---|---|
| ① 文法 | ✅ `decision.ebnf` | ✅ Language Reference |
| ② 解析/校验 | ✅ `dsl.py check` | ✅ Parser |
| ③ 执行引擎 | ❌ **规范禁止** | ✅ Interpreter |

**为什么没有第 ③ 层。** `2026.md` 的 *Constraints* 段明文规定：不得输出结论或建议、不得评分排序或赋值概率、不得给出优化或决策引导、系统不得替代或模拟决策。因此本语言**只描述"一个决策在什么假设边界内成立"，不计算任何结果**。

它更接近 **JSON Schema** 的定位：定义形状、检查合规、不承载业务逻辑。

---

## 1. 完整文法

以下为规范性文法，与 [`decision.ebnf`](./decision.ebnf) 内容一致。

### 1.1 文档结构

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

**区块顺序是规范性的**，不可调换：

```
Decision  →  Assumption+  →  Dependency*  →  Branch+
```

顺序颠倒将报 `E108`。

### 1.2 核心产生式

```ebnf
decision        = "Decision" , colon , text ;

assumption      = "Assumption" , space , id , colon , text ;

dependency      = "Dependency" , colon , space , id , space , verb , space , id ;

branch          = "Branch" , space , id , colon , text ;
```

| 产生式 | 语义 | 关键约束 |
|---|---|---|
| `decision` | 待执行的具体行动或判断 | 全文有且仅有一条 |
| `assumption` | 使该决策成立的显式前提 | 必须可证伪、不得模糊、不得自明 |
| `dependency` | 前提之间的显式依赖关系 | 可选建议项；必须指向已声明前提；图必须无环 |
| `branch` | 某前提失效时，决策的**结构性变更** | 必须描述结构影响，不得给出替代方案 |

> **关于 `branch` 的边界**：它回答"假设塌了，原决策还成不成立、怎么变形"，而**不是**"那改成什么更好"。后者属于建议，被规范禁止。

### 1.3 词法元素

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

要点：

1. **`id`** 以字母开头，可以后跟字母、数字、下划线。`A1`、`budget_2`、`X` 均合法。
2. **`text`** 按行读取，首尾空白被裁剪；裁剪后不得为空（否则报 `E203`）。
3. **`comment`** 只支持整行注释，不支持行尾注释。这是刻意的：行尾注释会让 `text` 的边界变得不可判定。
4. **全角冒号 `：`** 与半角 `:` 等价，方便中文写作。仅首个冒号参与分词。

---

## 2. 元符号表

| 符号 | 含义 | 例 |
|---|---|---|
| `=` | 定义：左侧概念由右侧替换 | `id = letter , ...` |
| `,` | 连接：左右必须依次出现 | `"Assumption" , id` |
| `\|` | 选择：左右任选其一 | `"requires" \| "depends on"` |
| `{ ... }` | 重复：出现 0 次或多次 | `{ letter \| digit }` |
| `[ ... ]` | 可选：出现 0 次或 1 次 | `[ dependencies ]` |
| `( ... )` | 分组：限定选择与重复的作用域 | — |
| `"..."` | 终结符：原样出现的字面量 | `"Decision"` |
| `? ... ?` | 特殊序列：无法形式化的部分，用自然语言说明 | `? any Unicode character ?` |
| `(* ... *)` | 注释：不参与文法 | 见文件头 |

---

## 3. 合规约束

约束分四级。前三项源于 `2026.md` 的 *Constraints*，第四项源于 *Branches* 段。

### L1 · 结构（Structural）

| 编号 | 规则 | 违反后果 |
|---|---|---|
| `E101` | 必须有且仅有一条 `Decision` | 无决策主体 / 决策歧义 |
| `E103` | 至少一条 `Assumption` | 决策无边界，退化为断言 |
| `E107` | 每条 `Assumption` 必须有同 ID 的 `Branch` | 存在未标注的断裂点 |
| `E105` | `Assumption` ID 唯一 | 引用歧义 |
| `E104` | `Branch` / `Dependency` 引用必须已声明 | 悬空引用 |
| `E106` | 依赖图必须无环 | 循环依赖，无法定序 |
| `E108` | 区块顺序不得颠倒 | 解析歧义 |

### L2 · 约束（Constraints · `2026.md` 第 44-50 行）

| 编号 | 规则 | 依据 |
|---|---|---|
| `E301` | 不得出现结论性表述 | *No conclusions* |
| `E302` | 不得出现建议 / 推荐表述 | *No recommendations* |
| `E303` | 不得出现评分 / 排序 / 概率赋值 | *No scoring, ranking, or probability assignment* |
| `E304` | 不得出现优化或决策引导 | *No optimization or decision guidance* |

> 这四条是**本语言区别于普通笔记格式的全部意义所在**。一个 `.spd` 文件即使语法完美，只要出现"建议采用"，就是不合规的。

### L3 · 质量（Advisory · 只警告不阻断）

| 编号 | 规则 | 说明 |
|---|---|---|
| `W401` | 假设含模糊限定词（可能 / 也许 / 大约 / probably…） | 可证伪性不足 |
| `W402` | 假设无可观测阈值（无数字且无比较词） | 无法判定真伪 |
| `W403` | 假设疑似自明（过短或属常识） | 不构成有效边界 |
| `W404` | 分支响应为占位符（TBD/待定/…，无可执行动作） | 伪 `"锚定"` 主张——失败路径未承诺任何动作 |

### L4 · 依赖语义

- `requires` 表示**前置必需要**：B 不成立则 A 不可评估。
- `depends on` 表示**取值相关**：B 的成立程度影响 A 的成立程度。
- 二者仅作语义标记，语言本身**不计算**依赖强度。

---

## 4. 错误码总表

| 码 | 级别 | 含义 |
|---|---|---|
| `E101` | ERROR | 缺少 `Decision` 块 |
| `E102` | ERROR | `Decision` 重复 |
| `E103` | ERROR | 缺少 `Assumption` 块 |
| `E104` | ERROR | 引用未声明的前提 ID |
| `E105` | ERROR | ID 重复声明 |
| `E106` | ERROR | 依赖图存在环 |
| `E107` | ERROR | 前提缺少对应的 `Branch` |
| `E108` | ERROR | 区块顺序颠倒 |
| `E201` | ERROR | 行无法识别（未知关键字） |
| `E202` | ERROR | ID 格式非法 |
| `E203` | ERROR | 文本为空 |
| `E204` | ERROR | 缺少冒号或分隔符 |
| `E301` | ERROR | 出现结论性表述 |
| `E302` | ERROR | 出现建议 / 推荐表述 |
| `E303` | ERROR | 出现评分 / 排序 / 概率赋值 |
| `E304` | ERROR | 出现优化引导 |
| `W401` | WARN | 假设含模糊限定词 |
| `W402` | WARN | 假设缺少可观测阈值 |
| `W404` | WARN | 分支响应为占位符 |
| `W403` | WARN | 假设疑似自明 |

退出码：`0` = 通过（或仅警告）；`1` = 存在 ERROR；`2` = 用法错误。

---

## 5. 完整示例

### 5.1 规范样本

```spd
# 合规样本 —— 决策结构语言 2026.2
Decision: 接受张江科学城试点作为本季度唯一并行推进项目

Assumption A1: 目标客户的年度 AI 预算 ≥ 500 万元
Assumption A2: 对方的采购合规审核周期 ≤ 8 周
Assumption A3: 我方单位算力成本低于对方自建成本 30%

Dependency: A2 requires A1
Dependency: A3 depends on A1

Branch A1: 预算规模不足，项目降级为单点 PoC，不进入年度框架
Branch A2: 审核周期超限，交付节点整体后移一级，验证范围收窄至单业务线
Branch A3: 算力成本优势不成立，成本叙事作废，资源投入上修
```

**逐条对照**：1 条决策 · 3 条前提（均含可观测阈值）· 2 条依赖（无环，均指向 A1 与 A2）· 3 条分支（与前提 ID 一一对应）· 全部文本无结论 / 建议 / 评分词。

### 5.2 典型违规

完整违规样本见 [`examples/invalid_decision.spd`](./examples/invalid_decision.spd)，核心片段：

```spd
Decision: 我们应当采用排名第一的方案 B

Assumption A1: 客户可能有大预算
Dependency: A3 requires A1
Branch A4: 预算不足则缩减范围
```

实测输出（`python dsl.py check examples/invalid_decision.spd`）：

| 行 | 码 | 命中原因 |
|---|---|---|
| 4 | `E302` | "应当采用"属建议表述 |
| 4 | `E303` | "排名"属排序赋值 |
| 6 | `W401` | "可能"为模糊限定词 |
| 6 | `W402` | "大预算"无可观测阈值 |
| 10 | `E104` | 依赖引用了未声明的 `A3` |
| 12 | `E302` | 分支给出替代方案，属决策引导 |
| 13 | `E104` | 分支引用了未声明的 `A4` |

> **能力边界（必须明示）**：`E301`–`E304` 基于**词面模式匹配**，不做语义推断。因此"方案 B"这类**隐含**排序不会被自动捕获；工具只保证"出现排序/建议词即拦截"，不保证"穷尽所有排序/建议语义"。这是刻意的取舍——宁可漏报语义，不可把推断冒称为事实节点。
>
> `E106` 环形依赖同样实测有效：`Dependency: A1 requires A2` 与 `Dependency: A2 requires A1` 并存时，报 `依赖图存在环：A1 → A2 → A1`。

---

## 6. 与既有文档的关系

| 文档 | 角色 | 关系 |
|---|---|---|
| `2026.md` | 规范性标准（自然语言） | 本文件的形式化对象 |
| `全新决策结构语言.md` | 一页纸概要 | 本文件 §0-§1 的简版 |
| `grammar.md` | 本文件的英文版 | 与本文件互为镜像，内容等价 |
| `decision.ebnf` | 机器可读文法 | 本文件 §1 的原文件 |
| `dsl.py` | 参考工具链 | 本文件 §3-§4 的可执行实现 |

三份文档对同一形式化内核做**不同抽象层次**的投影：一页纸（概览）→ 本文（规范）→ EBNF（形式）→ dsl.py（可执行）。四者必须同步维护；若冲突，以 `2026.md` 为准。

---

## 7. 工具链用法

```bash
# 校验单个/多个文件
python dsl.py check examples/valid_decision.spd

# 严格模式：警告也导致退出码非零
python dsl.py check examples/valid_decision.spd --strict

# JSON 输出，便于接入 CI
python dsl.py check examples/valid_decision.spd --json

# 造词器：依文法生成形式合法的样本（seed 可复现）
python dsl.py gen --seed 2026
python dsl.py gen --seed 2026 --count 5 --out examples/generated/

# 打印文法 / 错误码说明
python dsl.py grammar
python dsl.py codes E302
```

---

*本语言系统仅用于决策过程中的结构审查与拆解。它不参与决策，也不介入最终决定。作者对任何后续执行结果不承担法律或运营责任。*
