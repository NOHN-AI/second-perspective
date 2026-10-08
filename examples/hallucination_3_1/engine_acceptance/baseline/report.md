# 真引擎实测报告 — 测试规范 v1.0 §3.1 幻觉分类用例集

被测对象：`Cognitive Audit Engine.py`（GCAE 参考内核，真跑，非替身）
用例集：`hallucination_testset_v1.json` · 350 条 · sha256 `1e7804d9d8d66a61…`
抽取器：`t1-rules-v1` · 固定虚拟时钟 1791417600.0 · 责任账户 nonce `4ed00a93`

## 结论

- 四态抽取 vs 裁决真值：**350/350 = 100.0%** （95% Wilson CI [98.9%, 100.0%]）
- 引擎审计信号 vs 四态期望表：全部一致 ✓
- 两遍全量重放：逐条报告字节一致 ✓（sha256 `bd333f8f95fb09b4…`）· 哈希链根一致 ✓（`5f538ef5bf9c9533…`）

## 抽取一致性

- vs 裁决真值 350/350（100.0%）· vs 标注员 A 94.0% · vs 标注员 B 91.1%

混淆矩阵（行=裁决真值，列=引擎抽取态）：

| 真值 \ 抽取 | anchored | floating | opaque | hollow |
|---|---|---|---|---|
| anchored | 131 | 0 | 0 | 0 |
| floating | 0 | 86 | 0 | 0 |
| opaque | 0 | 0 | 56 | 0 |
| hollow | 0 | 0 | 0 | 77 |

## 引擎裁定分布（按裁决真值）

| 真值 \ 裁定 | AUDIT_PASS | AUDIT_WARN | AUDIT_HALT |
|---|---|---|---|
| anchored | 131 | 0 | 0 |
| floating | 0 | 0 | 86 |
| opaque | 0 | 0 | 56 |
| hollow | 0 | 0 | 77 |

## 期望信号核对（规范 §3.1 结构语义 → 引擎检查）

| 真值 | 条目 | 全部信号符合 | 违规 |
|---|---|---|---|
| anchored | 131 | ✓ | 无 |
| floating | 86 | ✓ | 无 |
| opaque | 56 | ✓ | 无 |
| hollow | 77 | ✓ | 无 |

逐项结果分布：

| 真值 | CCS inverse | CCS blackhole | IAP missing |
|---|---|---|---|
| anchored | CONVERGE×131 | CLEAR×131 | 0 |
| floating | SYSTEM_COLLAPSE×86 | CLEAR×86 | 0 |
| opaque | CONVERGE×56 | BLACKHOLE×56 | 56 |
| hollow | SYSTEM_COLLAPSE×77 | BLACKHOLE×77 | 77 |

## 逐算子发现摘录

- LCH ΔD：min 0.0 / max 0.6 · ≥0.7 的条目 0（阻断阈值未触发）
- 审计证书：350 份，audit_id 唯一 350/350
- 哈希链：350 事件 · valid=True · root `5f538ef5bf9c9533…`
- 责任闭环控制项：owner=None 时 `BLOCKED` ✓（RESPONSIBILITY_NOT_CLOSED 路径）

## 确定性

- 两遍全量重放逐条报告字节一致：✓ （350 条）
- 链根一致：✓ （pass1 `5f538ef5bf9c9533…`）
- 本报告不含墙钟时间戳；证据文件重跑可字节重现。

## 证据文件

- `engine_logs/`：350 份原始审计报告（每份含哈希链根与证书签名）
- `per_item.jsonl`：逐条抽取态 / 期望信号 / 裁定 / 证书 / 报告哈希
- `metrics.json`：本报告全部聚合数据（机器可读）
