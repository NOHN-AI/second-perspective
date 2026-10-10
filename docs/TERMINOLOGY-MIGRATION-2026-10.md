# 术语 v2 迁移说明 · Terminology v2 Migration

**日期**：2026-10-09 · **版本**：SPE 1.0.0 → 1.1.0 · **性质**：术语层重命名（引擎逻辑零改动）

> 判定标准：一个英文词如果已被目标读者的第一语言**占用于一个不同的精确含义**，
> 就必须处理。本次共处理 14 条：8 条 P1（语义撞词 / 文化真空）、5 条 P2、1 条 P3（不动）。

---

## 一、算子更名（P1，参与 `operator_set_hash`）

| 旧 | 新 | 更名理由 |
|---|---|---|
| `⊙ORI` Origin Anchor | `⊙GA` **Genesis Anchor** | origin 首读是 git remote / CORS origin；Genesis 与 "Genesis-Locked" 提法自洽 |
| `⊞TPG` Rule-Free Thinking Topology | `⊞LFT` **Label-Free Topology** | "rule-free" 名实相反（本算子约束最密）；本义是去语义标签；Thinking 是口语词 |
| `⚙CCS` Causal Chain Synchronization | `⚙CCS` **Chain Closure Scan**（缩写保留） | synchronization 是分布式系统专有词；本算子三件事（反向验证 / 反事实 / 黑洞检测）没有一件是同步 |
| `⊚STATE` State Anchoring | `⊚ACC` **Accountability Anchoring** | state 是 CS 重载最狠的词；本算子只做锚定责任人 + 出证书 |

同步中文侧（名实修正）：无规则思维拓扑图→**无标签拓扑图** · 因果链同步→**链闭合扫描** ·
状态锚定→**责任锚定** · 脆弱性闩锁/脆弱性对冲→**脆弱性定位**（`LCH` 缩写不变，
英文 Fragility Latch → **Fragility Localization**）。

## 二、五元基两层契约（P1，纯文档层）

拼音作定义过的专有名词 + 形式描述词用于正文与论文（修掉 Chaos/Illusion 与
Wuji/Tiandao/Lunhui 两套策略并存的内部不一致）：

| 旧 | 新 |
|---|---|
| Chaos（溯源缺口） | **Hundun · Unparsed Antecedence**（未解析之因的全体；随机性属于解析度，不属于它） |
| Illusion（叙事遮蔽） | **Xuhuan · Narrative Register**（现实之另一面，叙事事件 N_t 的所在；illusion 自带"假"义，名实不符） |
| Wuji（并行收敛） | **Wuji · Non-forking Convergence**（多链并行不分支，极限唯一收敛） |
| Tiandao（审计有界） | **Tiandao · Neutrality Invariant**（审计中立的本体表述） |
| Lunhui（因果承接） | **Lunhui · Effect-to-Cause Succession**（每个果即刻成因，序不可倒置；弃用 Samsara 宗教义） |

## 三、概念更名（P2/P3）

| 旧 | 新 | 理由 |
|---|---|---|
| Energy budget 能量预算 | **Spiral Budget** 螺旋预算 | physics energy = 守恒量（焦耳），此处是迭代额度 |
| Distance to S\* | **Convergence Rank** 收敛秩 | 是字典序二元组，不满足度量公理，不能叫 distance |
| Meta-causal bases | **Meta-causal Grounds** | base 歧义过多 |
| Operator manifest | 不改 | 限定在自家报告命名空间，风险可控 |

## 四、刻意不改的代码标识符（报告 schema 稳定性）

`energy_budget` / `energy_left` / `energy_ledger` / `distance` / `distance_trend` /
`meta_bases` / `chaos_gaps` / `_chaos` / `_wuji` / `_illusion` / `_tiandao` / `_lunhui` 等
内部标识符与 JSON 键**全部保留**——文档术语已更名，实现标识符留待下一次破坏性版本统一处理。
同理 `Narrative Strip (NS)`、`Extension seam`、`Binary Fact Check`、`Third truth value`、
`Evidence vacuum / conflict`、`Clean-room declaration`、`Graph hash`、`Frozen subgraph`、
`Lineage`、`Propose-only`、`Minimal fixed point` 等术语经评审**原样保留**。

## 五、哈希与谱系影响

- `operator_set_hash = hash([[name, tier, order]])`（引擎 4210-4217 行）：算子更名
  → `operator_set_hash` 变（`d21db6e4e41a1cb7…`）→ 新一代 lineage。
- **链根**：`dedba0ae…`（1.0.0）→ `d47f41fc83b824025132d00e1067bfbf0b3e6bf1e3e6ee0e3303f87f2b01fcd6`（1.1.0）。
- **旧产物不作废**：`logs/` 下既有 JSON 是上一代 lineage 的签发物，按设计由 Lineage
  代际机制承接（"这份链根属于第几代引擎"），保留不重签。新签发物自动携带新算子集
  指纹（如本次冒烟产生的 `logs/SPE-19ec0fd7-*.json`）。
- `verify_convergence_fix.py` 的 S3 期望链根已重算更新（`STRATEGY_ROOT_EXPECTED`）。

## 六、回归验证结果（与 HEAD 逐项对照）

| 检查 | HEAD（1.0.0） | 本次（1.1.0） | 结论 |
|---|---|---|---|
| `verify.py` | PASS 18 · FAIL 0 · WARN 1 | PASS 18 · FAIL 0 · WARN 1 | 一致，硬性检查全过 |
| 链根 `--root` | `dedba0ae…` | `d47f41fc…` | 差异来自算子更名，符合预期 |
| `verify_convergence_fix.py` | 6/6 | 6/6（S3 期望值已重算） | 一致 |
| `demo_audit.py` DSL 检查 | valid PASS / invalid FAIL(1) | 同 | 一致 |
| `adapters/map_to_engine.py` 端到端 | — | 链根逐字节可复现，verify valid | 通过 |

**既有问题（非本次引入，HEAD 同样存在）**：
1. `demo_audit.py` 测试 2「干净的决策（应 PASS）」实际得到 `AUDIT_HALT`——demo 的
   预期标注或引擎早期行为存在历史偏差，待单独排查。
2. TESTING.md 原记载「PASS 9 · WARN 2 / 链根 f5713f49…」在本次改动前即已过时
   （套件已扩至 V17、V9 已修复为 PASS），本次已一并修正为实测值。

## 七、未触碰的冻结物

- `docs/zenodo/deposit/**`（2026-10-09 deposit 的 paper.md / paper.pdf / zip）——已冻结投递物，
  术语 v2 将随下一次 deposit 重投。
- `docs/zenodo/paper.html`（仓库内渲染版）——**已同步**至术语 v2 + SPE 1.1.0 实测数据
  （2026-10-10 追加，与 `docs/paper/paper.md` 同步：算子更名、V9 已解决、
  19 项 PASS 18 · FAIL 0 · WARN 1、新链根 d47f41fc…、Artifacts 清单改为单文件引擎）。
- `logs/*.json` 既有签发物 —— 上一代 lineage 产物，见第五节。
- `language Standard/**` —— 语法层不含算子名，零改动。

## 八、涉及文件

代码：`Second Perspective Engine.py`（SPE_VERSION → 1.1.0）· `verify.py` ·
`verify_convergence_fix.py` · `case_memo_audit.py` · `case_strategy_audit.py` ·
`demo_audit.py` · `adapters/map_to_engine.py`

文档：`GLOSSARY.md` · `README.md` · `README-zh.md` · `TESTING.md` · `TESTING-zh.md` ·
`adapters/MAPPING-zh.md` · `docs/paper/paper.md` · `docs/zenodo/paper.html`（2026-10-10 追加同步）

---

## 九、SPE 1.2.0 增补（2026-10-10 同日）

在术语 v2 落地同日完成的四项功能性变更，随本批次一并提交：

1. **V3b 解决（证书输入绑定）**：证书新增 `input_digest = SHA-256(canonical-JSON(input))` 并入签。
   签名格式变更 → 链根再次代际更替：`d47f41fc…` → `aece60f5…`。旧证书由 Lineage 机制承接。
2. **Language Standard 2026.1 → 2026.2**：新增 W404（分支响应为占位符，无可执行动作），
   规则 R1–R12 → R1–R13，诊断码 19 → 20。
3. **模型防火墙三层化**：递归剥离（任意嵌套深度的禁用键）+ 深度上限 12 + T3 白名单压缩。
4. **demo 夹具修正**：干净用例补 origin/goal/resources 声明——GA 对缺失第一原点的阻断系规范行为，
   非 bug；附录 C 注记由 "under review" 改为 resolved。

验证基准（2026-10-10）：verify.py PASS 18 · FAIL 0 · WARN 1；verify_convergence_fix.py 6/6；demo ✅。

---

## 十、SPE 1.2.1 版本口径修正（2026-10-10 同日）

术语 v2 收尾时发现的**版本口径不一致**的修正，以及由此引发的链根代际更替。

**改了什么**：

1. **证书 note 去硬编码**：证书内 "本证书由第二视角引擎 SPE 1.1 生成…" 硬编码了旧版本号，
   与实际模块常量 `SPE_VERSION = "1.2.0"` 矛盾。改为引用模块常量：
   `f"本证书由第二视角引擎 SPE {SPE_VERSION} 生成…"`。
2. **引擎头注释去硬编码**：文件头 "版本：以模块常量 SPE_VERSION 为准（当前 1.2.0）" → 去掉括注，
   避免同一文件出现两处版本事实源。
3. **口径一致性批扫**（README.md / README-zh.md / TESTING.md / TESTING-zh.md /
   `demo_audit.py` / `requirements.txt`）：算子数 9 → 10（META 已在内核）、
   检查项 18 → 19、诊断码 19 → 20、横幅与演示标题统一至 1.2 口径。

**链根为什么变**（Lineage 承接，非缺陷）：

证书 note 进入报告 → 报告哈希 `report_hash` 进入 AUDIT 事件 → 链根随代际更替。
按引擎自身的谱系纪律（"改代码必须由人完成，完成后须重算金标并升 SPE_VERSION"），
本次同步升版：`SPE_VERSION 1.2.0 → 1.2.1`，并重算全部在库金标：

| 金标 | 旧值（1.2.0 代） | 新值（1.2.1 代） |
|---|---|---|
| `verify.py --root` | `aece60f5…` | `ca07e5e4…` |
| `verify_convergence_fix.py` S3 期望链根 | `2b65ea46…` | `b16ba1be…` |

**同步更新的位置**：`TESTING.md`（--root 预期）· `TESTING-zh.md`（同上）·
`verify_convergence_fix.py`（`STRATEGY_ROOT_EXPECTED` + 注释）。

**未触碰**：`docs/paper/paper.md` 与 `docs/zenodo/**`（含 paper.html / deposit）——
其内数字与链根属于论文快照口径，是否同步为 1.2.1 数据由作者单独决定。
