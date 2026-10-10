# 数据清单与映射规范（v0.1 · 最小版）

把客户现有系统里的决策材料接进 SPE 引擎，跑出审计报告。
本版只覆盖一个入口方向：**导出文件 + 映射表 → 一条命令出报告**。

## 1. 数据清单（客户侧准备什么）

1. **一份导出文件（JSON）**：Confluence 页面导出、Jira 工单导出、企微文档接口返回……
   任何系统都可以，只要能指出下列内容在文件里的位置。
2. **一张映射表（JSON）**：哪段文字 → 引擎哪个键（格式见 §3）。

输入分三档：

**必填**（脚本强制，缺一即中止）：

| 引擎键 | 类型 | 语义 | Confluence 典型章节 | Jira / 企微文档同类位置 |
| --- | --- | --- | --- | --- |
| `decision` | 文本 | 被审的决策本身 | 决策 / 决议 | 描述字段 / 正文「决策」段 |
| `assumptions` | 列表 | 决策成立所依赖的前提 | 关键假设 / 前提 | 正文「假设」列表项 |
| `outcome` | 文本 | 决策声称的结果 | 预期结果 / 结果 | 正文「预期结果」段 |

**完整线**（缺失不中止，但引擎会如实给出致命判定——判定本身就是审计结论）：

| 引擎键 | 类型 | 语义 | 缺失后果 |
| --- | --- | --- | --- |
| `origin` | 文本 | 决策的缘起（链的起点） | `GA: ORIGIN_VACUUM` 阻断 |
| `branches` | 结构列表 | 失败路径 / 回退方案（ΔD） | `CCS: SYSTEM_COLLAPSE` 阻断 |

**可选**：`narrative`（背景）、`goal`（目标稳态）、`evidence`（证据）等。
`facts` / `dependencies` / `topology` 等仍属 POC 手工补充（真值只能外部显式声明，引擎永不推断）。

## 2. 规则（沿用引擎护栏 I-1 非猜测）

- 导出文件里没有的字段，一律**不补、不推断**；
- **未映射的章节不进入引擎**——样例里「评审意见」就留在原地；
- 必填字段缺失时，脚本**中止并报错**，不会拿别的内容顶替。

## 3. 映射表格式

见 `mapping.confluence.json`：

```json
{
  "system": "confluence",
  "version": 1,
  "source": { "title": "title", "body": "body.storage.value" },
  "fields": {
    "decision": { "headings": ["决策", "决议"], "mode": "text" },
    "assumptions": { "headings": ["关键假设", "前提"], "mode": "list" },
    "branches": { "headings": ["失败路径与回退方案"], "mode": "branches" }
  },
  "required": ["decision", "assumptions", "outcome"]
}
```

- `source.title` / `source.body`：用点号路径指向导出文件里的字段；
- `fields.<引擎键>.headings`：章节标题候选，按顺序取第一个命中的；
- `fields.<引擎键>.mode`：`text`（合并为文本）/ `list`（逐条列表）/ `branches`（失败路径：
  每条按「若 X 不成立 → 回退处理」书写，箭头 `→` 或 `->` 分隔，解析为 `[{"assumption", "delta_d"}]`）；
- `required`：缺任一即中止——不猜、不填充。

## 4. 运行

在仓库根目录：

```bash
python "adapters/map_to_engine.py" "adapters/sample_confluence_decision.json" \
    --org "示例公司·风控部" --role "决策评审" --stage pre_decision --owner "风控负责人"
```

输出顺序：命中映射 → 引擎裁定（ACC / NS / IAP / LCH / 责任闭环）→ 凭据
（audit_id / signature / chain_root / verify）。审计日志落在仓库 `logs/`（不入 git）。

演示技巧：把样例里「失败路径与回退方案」一节删掉再跑，ACC 立即变为 HALT——
引擎对材料完整性缺口有判别力，不是橡皮图章。

客户现场演示：把 `sample_confluence_decision.json` 换成客户自己的导出文件即可；
章节名对不上时改映射表 `headings`，**不改代码、不改引擎**。

## 5. 可复现性

固定时钟 + 责任账户推导 nonce：**同一材料、同一责任账户，每次跑出同一个链根**，
第三方可离线重算核对。同一账户要多次审计彼此可区分时传入不同 `instance_salt`
（本版未开放 CLI 参数，POC 按需加）。

不传 `--owner` 时责任未闭环，引擎在报告中显式标注 `RESPONSIBILITY_CLOSURE: BLOCKED`——
这是特性：审计结论必须锚定到具体责任人。

## 6. 边界（本版刻意不做）

- **连接器**（Jira / Confluence / 企微文档实时拉取）：签约前 API 权限批不下来，
  导出文件是零阻力路径。等首个签约 POC 明确数据源后再做对应那一个，按实施服务计费。
- **拖拽配置界面**：映射难点是语义判断（哪条是假设、哪条是结果），不是字段名对应——
  界面解决不了语义，工期却是大头。
- **独立 SDK**：引擎单文件 + 输入契约（见引擎 `audit()` docstring）即最小 SDK。
- **表格内容**：当前解析器不收集 `<table>` 文本；遇到以表格承载关键信息的文档，先扩展解析器。

## 7. 文件清单

| 文件 | 作用 |
| --- | --- |
| `sample_confluence_decision.json` | 合成样例（模拟 Confluence REST 导出，非真实企业数据） |
| `mapping.confluence.json` | 样例映射表 |
| `map_to_engine.py` | 映射 + 跑引擎 + 打印裁定与凭据 |
| `MAPPING-zh.md` | 本文档 |
