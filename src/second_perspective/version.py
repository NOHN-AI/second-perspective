"""NOMOS version."""

# 0.6.0 — 认知审计内核由五算子升级为十算子（⊙ORI / ⊞TPG / BFC / ⇄GRF / META）。
#   新增：无规则思维拓扑（四进程校验，含公理 5 链内时序）、二元事实校验、
#         灰度反馈、元因果账本（混沌·无极·虚幻(A6)·天道(A10)·轮回）。
#   产物版本串随之由 GCAE-1.0.0 升至 GCAE-1.1.0（见 adapter.ADAPTER_SCANNER_VERSION）。
#   注意：NOMOS 的 DecisionRequest 契约尚无 origin / gray_levels 字段，
#   adapter 路径因此暂不注册 ORI 与 GRF —— 详见 adapter.ADAPTER_OPERATORS。
VERSION = "0.6.0"