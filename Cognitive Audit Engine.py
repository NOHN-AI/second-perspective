"""
第二视角认知审计引擎 v2.0 (GCAE — Global Cognitive Audit Engine)
================================================================

设计定位：「第二视角因果框架」下治理AI的规范参考内核（Reference Implementation）。

    - 单文件 · 零外部依赖 · 仅用 Python 标准库
    - 可直接用于教学/审计/移植到 SPL-G1 硬件或其他语言
    - 所有结构判定均为决定论；不使用概率词；缺失输入直接中断而非猜测
    - LLM 永远不参与结构裁决；所有 status/converged 布尔值由确定性算子给出

核心五步算子 (Five-Operator Causal Audit Kernel)：
    1. 叙事剥离 (Narrative Stripping)       — 去除修辞立场，提取纯粹事件链
    2. 内隐假设透视 (Implicit Assumption)    — 挖掘未声明预设，逆反校验
    3. 脆弱性对冲 (Vulnerability Hedging)    — 定位最脆弱变量，评估崩塌等级
    4. 责任闭环锚定 (Responsibility Closure) — 追溯到最小决策单元，绑定 nonce
    5. 因果重构 (Causal Reconstruction)      — 注入修正变量，判定形式化收敛状态

三大护栏不变式：
    I-1 非猜测 —— 缺失事实/权重/阈值/责任人/交互强度不估算，直接中断并列出补齐条件
    L-1..L-3   —— LLM 三层权限（T1 注解 / T2 提案 / T3 叙述），永不裁决、永不改状态
    C-1..C-3   —— 收敛五状态（FIXED_POINT / NO_GAIN / BUDGET_EXHAUSTED / DIVERGED /
                  BLOCKED）；is_true_convergence 严格区分真收敛与预算耗尽

本模块不含任何主观/概率化推测，仅做决定论因果处理。
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Protocol, Tuple


# ==================== 基础类型与枚举 ====================

GCAE_VERSION = "2.0.0"


class ConvergenceState(str, Enum):
    """形式化收敛五状态分类。

    BLOCKED          本轮出现阻断项（必需输入缺失等），立即终止，不算收敛
    BUDGET_EXHAUSTED 跑满 max_rounds 仍未收敛 —— 预算耗尽，**不是**收敛
    FIXED_POINT      相邻两轮的风险集合完全相同 —— 不动点，收敛
    NO_GAIN          风险集合清空且无未决假设 —— 无残留风险，收敛
    DIVERGED         仍有风险或未决假设，且与上轮不同 —— 发散，需人工介入

    FIXED_POINT 与 NO_GAIN 都算真收敛，区别在于「停在哪」：
      NO_GAIN      = 停在一片干净的风险区（风险清零）
      FIXED_POINT  = 停在某个风险上不再变化（风险有界但不为零）
    只有 BUDGET_EXHAUSTED 是「跑完了但没跑到」——所以 is_true_convergence
    特意把它排除在外，防止把「时间到了」误当成「想通了」。
    """
    FIXED_POINT = "FIXED_POINT"
    NO_GAIN = "NO_GAIN"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
    DIVERGED = "DIVERGED"
    BLOCKED = "BLOCKED"

    @property
    def is_true_convergence(self) -> bool:
        return self in (ConvergenceState.FIXED_POINT, ConvergenceState.NO_GAIN)


# ---------------------------------------------------------------------------
# 关于 T1 / T2 / T3：本文件同时存在两套互不相干的 T1/T2/T3 命名，
# 这是本引擎最容易被误读的地方。它们之间没有任何对应关系，不要混用。
#
#   PluginTier（下方）—— 约束「确定性算子插件」能做什么
#       T1_STRUCTURAL   可产出 BLOCKED/CRITICAL，能真正阻断一次审计
#       T2_SIGNAL       只能产出 WARNING/HIGH_RISK；发阻断会被强制降级
#       T3_NARRATIVE    只能出文字；输出里的 status 会被剥离
#
#   LLMPermissionTier —— 约束「LLM」能做什么，与 PluginTier 毫无关系
#       T1_ANNOTATION   附加批注
#       T2_PROPOSAL     提出建议
#       T3_NARRATIVE    只写叙述文字（默认值，最保守）
#
# 两套唯一的共同点是：数字越小，权限越大。
# 判定 LLM 输出是否越权，看的是 FORBIDDEN_LLM_KEYS，与 PluginTier 无关。
# ---------------------------------------------------------------------------

class PluginTier(str, Enum):
    T1_STRUCTURAL = "T1_STRUCTURAL"   # 可出 BLOCKED（阻断）
    T2_SIGNAL = "T2_SIGNAL"           # 只出风险信号，不得阻断
    T3_NARRATIVE = "T3_NARRATIVE"     # 只出文字，不出 status


class LLMPermissionTier(str, Enum):
    T1_ANNOTATION = "T1_ANNOTATION"
    T2_PROPOSAL = "T2_PROPOSAL"
    T3_NARRATIVE = "T3_NARRATIVE"


class CollapseLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


# ==================== 责任节点 ====================

@dataclass
class ResponsibilityAccount:
    organization: str
    role: str
    stage: str
    owner: Optional[str] = None
    nonce: Optional[str] = None

    def __post_init__(self) -> None:
        # 未显式传入 nonce 时用 uuid4 随机生成，保证每次审计的身份唯一。
        # 代价：默认配置下审计 ID 与哈希链根**不可复现**——
        #       同一输入两次运行会得到不同的 audit_id 与 chain_root_hash。
        # 需要复现（对外披露校验、回归比对、第三方重算）时，
        # 必须显式传入固定 nonce，并配合 engine.set_clock() 一起用。
        # 参考 verify.py 里的 FIXED_NONCE / FIXED_CLOCK 用法。
        if not self.nonce:
            self.nonce = uuid.uuid4().hex[:8]

    @property
    def is_closed(self) -> bool:
        return bool(self.owner)


# ==================== LLM 协议 ====================

class LLMProvider(Protocol):
    def generate(self, prompt: str, **kwargs) -> str: ...


class OpenAIProvider:
    """零依赖 OpenAI 兼容 LLM 调用。

    数据出境合规提示：
        - 默认 base_url 指向境外 https://api.openai.com/v1，调用即数据出境
        - 境内部署请传入境内端点（DeepSeek/通义千问等）并做输入脱敏
        - GCAE 五步算子本身从不调用 LLM；仅在显式注入 provider 时启用且强制护栏
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o",
        base_url: str = "https://api.openai.com/v1",
        timeout: int = 120,
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def generate(self, prompt: str, **kwargs) -> str:
        import urllib.error
        import urllib.request

        # 注意：下面把异常**转成字符串返回**而不是向上抛。
        # 因为叙述层是可选增强，它挂掉不应让整次审计失败——
        # 调用方拿到 "[LLM Error] ..." 字符串即可，核心五算子不受影响。
        temperature = kwargs.get("temperature", 0.3)
        max_tokens = kwargs.get("max_tokens", 4096)
        body = json.dumps({
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                return result["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:
            return f"[LLM Error] HTTP {e.code}: {e.read().decode('utf-8', errors='replace')[:200]}"
        except Exception as e:
            return f"[LLM Error] {e}"


@dataclass
class LLMCallRecord:
    """一次 LLM 调用的留痕。

    permission_tier  当时生效的权限层级
    prompt_hash      prompt 的 SHA-256 前 16 位——**只存哈希不存原文**：
                     既能证明用了哪个 prompt，又避免把决策数据写进日志
    response_excerpt 剥离裁决字段后的响应摘要（最多 400 字）
    stripped         是否发生过字段剥离
    adjudicated      恒为 False。按护栏 L-1..L-3，LLM 永不参与裁决；
                     这个字段存在的意义就是在审计记录里显式证明这一点，
                     任何人翻到报告都能看到「LLM 没有裁决权」
    """

    permission_tier: LLMPermissionTier
    purpose: str
    prompt_hash: str
    response_excerpt: str
    stripped: bool = True
    adjudicated: bool = False
    timestamp: float = field(default_factory=time.time)


# ==================== 审计事件与哈希链 ====================

@dataclass
class AuditEvent:
    event_type: str
    payload: Dict[str, Any]
    prev_hash: str
    timestamp: float = field(default_factory=time.time)
    nonce: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    # 封存哈希：在 _append_event 时一次性写入。其后任何对 payload / event_type /
    # timestamp / nonce 的改动都会使 hash 与 sealed_hash 不一致，从而被 verify_chain 检出。
    # 为 None 表示该事件未经封存，内容不可验证。
    sealed_hash: Optional[str] = None

    @property
    def hash(self) -> str:
        """本事件的链上哈希。三个 json 参数都有讲究，不能随手改：

        sort_keys=True     键序不影响结果，字典构造顺序无关紧要
        ensure_ascii=False 中文按原字符参与哈希，避免编码路径差异
        default=str        datetime 之类不可序列化的对象退化为字符串，
                         宁可损失精度也不让整条链崩掉

        注意：这个属性是**实时重算**的，任何事后修改都会改变它的返回值。
        因此 verify_chain 不拿它当基准，而拿 _append_event 时写下的
        sealed_hash 当基准——否则比对恒成立，篡改检测形同虚设。
        """
        blob = json.dumps({
            "event_type": self.event_type,
            "payload": self.payload,
            "prev_hash": self.prev_hash,
            "timestamp": self.timestamp,
            "nonce": self.nonce,
        }, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# ==================== 审计插件 ====================

@dataclass
class AuditPlugin:
    name: str
    tier: PluginTier
    analyze_func: Callable[[Dict[str, Any]], Any]
    description: str = ""


# ==================== 收敛判定器 ====================

class ConvergenceChecker:
    """形式化收敛判定（P-1 终止 / P-2 不动点 / P-3 风险有界）。"""

    BLOCKING_STATUSES = {"BLOCKED", "CRITICAL"}
    HIGH_RISK_STATUSES = {"HIGH_RISK"}

    @staticmethod
    def classify(
        round_idx: int,
        max_rounds: int,
        previous_risks: frozenset,
        current_risks: frozenset,
        has_blocking: bool,
        has_unresolved_assumptions: bool,
    ) -> ConvergenceState:
        # 判定是一张**优先级链**，从上到下第一个命中即返回，顺序不可调换：
        #   1. has_blocking                → BLOCKED
        #   2. round_idx >= max_rounds     → BUDGET_EXHAUSTED
        #   3. 与上轮风险集合同样且无未决 → FIXED_POINT
        #   4. 风险清空且无未决            → NO_GAIN
        #   5. 其余                        → DIVERGED
        #
        # 为什么阻断排在最前：必需输入缺失时，后面任何「看起来收敛了」
        # 的信号都不可信——风险集清零可能只是因为算子根本没拿到输入。
        #
        # 第 3 条要求 round_idx > 0：首轮没有「上轮」可比，必须落到后面几条。
        if has_blocking:
            return ConvergenceState.BLOCKED
        if round_idx >= max_rounds:
            return ConvergenceState.BUDGET_EXHAUSTED
        if round_idx > 0 and previous_risks == current_risks and not has_unresolved_assumptions:
            return ConvergenceState.FIXED_POINT
        if not current_risks and not has_unresolved_assumptions:
            return ConvergenceState.NO_GAIN
        return ConvergenceState.DIVERGED

    @staticmethod
    def extract_risk_set(report: Dict[str, Any]) -> Tuple[frozenset, bool]:
        # 风险键的构成是 (插件名, status, 结果的规范化 JSON)。
        # 必须把整个结果序列化进去，只比较 status 会漏掉
        # 「同一个 WARNING 但内容变了」这种情况——
        # 而那恰恰是 FIXED_POINT 需要识别的变化。
        risks = set()
        has_blocking = False
        for pname, result in report.get("analysis", {}).items():
            if not isinstance(result, dict):
                continue
            status = result.get("status")
            if status in ConvergenceChecker.BLOCKING_STATUSES:
                has_blocking = True
                risks.add((pname, status, json.dumps(result, sort_keys=True, default=str, ensure_ascii=False)))
            elif status in ConvergenceChecker.HIGH_RISK_STATUSES or status == "WARNING":
                risks.add((pname, status, json.dumps(result, sort_keys=True, default=str, ensure_ascii=False)))
        return frozenset(risks), has_blocking


# ==================== 配置加载器 ====================

class AuditConfigLoader:
    @staticmethod
    def load_from_dict(config: Dict[str, Any]) -> Dict[str, Any]:
        return config

    @staticmethod
    def load_from_json(path: str) -> Dict[str, Any]:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)



# ==================== 认知审计引擎核心 ====================

class CognitiveAuditEngine:
    """GCAE v2.0 规范参考内核。"""

    # LLM 护栏 L-1..L-3：LLM 可以说话，但不能影响结构判定。
    # 这些键一旦出现在 LLM 输出里会被剥离并标记 _tier_violation，
    # 覆盖三类越权：
    #   状态裁决  status / converged / is_converged / blocked / adjudicated
    #   权重排序  weight / score / rank
    #   结论判断  verdict / decision
    # 换句话说：即便模型照着提示词返回了裁决字段，也进不了结构判定。
    FORBIDDEN_LLM_KEYS = {
        'status', 'converged', 'is_converged', 'blocked',
        'adjudicated', 'weight', 'score', 'rank', 'verdict', 'decision',
    }

    def __init__(self, account: ResponsibilityAccount, config: Optional[Dict[str, Any]] = None):
        self.account = account
        self.config: Dict[str, Any] = config or {}
        self.plugins: List[AuditPlugin] = []
        self.llm_provider: Optional[LLMProvider] = None
        self.llm_default_tier: LLMPermissionTier = LLMPermissionTier.T3_NARRATIVE
        self.event_chain: List[AuditEvent] = []
        self._prev_event_hash: str = 'ROOT'
        self._clock: Optional[float] = None

        # 阶段白名单：config['allowed_stages'] 非空时，account.stage 必须落在其中，
        # 否则构造直接失败。这是第一道闸——责任节点本身就不合规时，
        # 没必要再跑算子。注意与 plugins/ 各算子内部的阶段判断是两回事。
        allowed_stages = self.config.get('allowed_stages', [])
        if allowed_stages and account.stage not in allowed_stages:
            raise ValueError(f'Unsupported stage: {account.stage}')

    # -------- 注册 --------

    def set_llm_provider(
        self,
        provider: LLMProvider,
        default_tier: LLMPermissionTier = LLMPermissionTier.T3_NARRATIVE,
    ) -> None:
        self.llm_provider = provider
        self.llm_default_tier = default_tier

    def register_plugin(self, plugin: AuditPlugin) -> None:
        self.plugins.append(plugin)

    def set_clock(self, t: Optional[float]) -> None:
        '''注入虚拟时钟以实现可复现审计；传 None 恢复系统墙钟。

        可复现性前提：未注入时钟时，审计证书与哈希链根**不可复现**
        —— 证书签名内嵌 int(time.time())，链事件时间戳取系统时钟。
        审计内容（裁定 / 各算子分析）在任何情况下均为决定论。
        '''
        self._clock = t

    # 五算子的权限分配，以及每一条的理由：
    #   NS    T3 —— 只输出剥离后的文本骨架，本就不参与判定
    #   IAP   T2 —— 发现隐含假设是「提示」，不足以单独阻断
    #   LCH   T2 —— 脆弱性是量化信号，但权重未经统计校准，
    #               不足以独自判一条决策死刑，只能提示
    #   CCS   T1 —— 信息黑洞属「必需输入缺失」，可以且必须阻断
    #   STATE T1 —— 汇总裁定，本身就是阻断的出口
    #
    # 一句话概括：只有「结构性缺失」才能阻断，「量化意见」不能。
    CORE_PLUGIN_TIERS: Dict[str, 'PluginTier'] = {
        'NS': PluginTier.T3_NARRATIVE,      # 纯文本骨架，不产出 status
        'IAP': PluginTier.T2_SIGNAL,        # 只出风险信号，不得阻断
        'LCH': PluginTier.T2_SIGNAL,        # 只出脆弱性信号，不得阻断
        'CCS': PluginTier.T1_STRUCTURAL,    # 产出 halt_count，允许阻断
        'STATE': PluginTier.T1_STRUCTURAL,  # 产出最终裁定
    }

    def load_core_plugins(self) -> List[str]:
        """加载官方五算子插件（NS / IAP / LCH / CCS / STATE）。

        `plugins/` 下的算子类只暴露 ``name`` 与 ``analyze()``；引擎契约要求
        ``AuditPlugin(name, tier, analyze_func, description)``。此处负责包装并
        按 CORE_PLUGIN_TIERS 赋予权限层级别。返回已注册的插件名列表。
        """
        import sys as _sys

        _here = os.path.dirname(os.path.abspath(__file__))
        if _here not in _sys.path:
            _sys.path.insert(0, _here)

        from plugins import CORE_PLUGINS  # type: ignore

        registered: List[str] = []
        for cls in CORE_PLUGINS:
            instance = cls()
            name = getattr(instance, 'name', cls.PLUGIN_NAME)
            if name not in self.CORE_PLUGIN_TIERS:
                raise ValueError(f'未声明权限层级别的核心插件: {name}')
            self.register_plugin(AuditPlugin(
                name=name,
                tier=self.CORE_PLUGIN_TIERS[name],
                analyze_func=instance.analyze,
                description=getattr(cls, 'PLUGIN_DESCRIPTION', ''),
            ))
            registered.append(name)
        return registered

    # -------- 哈希链 --------

    def _append_event(self, event_type: str, payload: Dict[str, Any]) -> AuditEvent:
        idx = len(self.event_chain)
        ts = self._clock if self._clock is not None else time.time()
        # 确定性 nonce：由前序哈希 / 事件类型 / 序号推导，取代 uuid4 随机值，
        # 否则同一输入两次运行的链根哈希不同，破坏可复现性。
        nonce = hashlib.sha256(
            f'{self._prev_event_hash}|{event_type}|{idx}'.encode('utf-8')
        ).hexdigest()[:8]
        ev = AuditEvent(
            event_type=event_type,
            payload=payload,
            prev_hash=self._prev_event_hash,
            timestamp=ts,
            nonce=nonce,
        )
        # 封存：自此刻起，内容若被改动即与封存值不符。
        ev.sealed_hash = ev.hash
        self.event_chain.append(ev)
        self._prev_event_hash = ev.sealed_hash
        return ev

    @property
    def chain_root_hash(self) -> str:
        """链根哈希，即最后一个事件的 sealed_hash；空链时为哨兵值「ROOT」。

        这是整个审计的唯一指纹。要对外披露校验凭据，披露的应该是它，
        并且这个值必须存在报告之外的地方（落盘后与报告分离保存）——
        与报告放在一起就等于没有锚点。
        """
        return self._prev_event_hash if self.event_chain else 'ROOT'

    # -------- 五步算子①：叙事剥离 --------

    @staticmethod
    def _strip_narrative(ctx: Dict[str, Any]) -> Dict[str, Any]:
        """剥离主观修饰词。

        只做**标记**不做**删除**：原文完整保留在 out 里，
        命中情况单独记进 _narrative_stripped.flagged_fields。
        因为审计的对象是「这句话说了什么」，不是「这句话该被改成什么」——
        改写原文会破坏证据链，也会让调用方无法核对原文。

        注意：本算子只认 narrative/background/summary/description 四个键，
        且要求值为 str。其他位置出现主观词不会被记录。
        """
        SUBJECTIVE_WORDS = {
            '显然', '毫无疑问', '必然', '肯定', '理所应当', '不言而喻',
            'obviously', 'clearly', 'certainly', 'undoubtedly', 'naturally',
        }
        out = copy.deepcopy(ctx)
        flagged: Dict[str, List[str]] = {}
        for key in ('narrative', 'background', 'summary', 'description'):
            if key in out and isinstance(out[key], str):
                hit = [w for w in SUBJECTIVE_WORDS if w in out[key]]
                if hit:
                    flagged[key] = hit
        out['_narrative_stripped'] = {'flagged_fields': flagged}
        return out

    # -------- 五步算子②：内隐假设透视 --------

    @staticmethod
    def _surface_implicit_assumptions(ctx: Dict[str, Any]) -> Dict[str, Any]:
        """决定论规则挖掘未声明预设。三条规则，全部是纯结构判断：

          MISSING_CRITERIA        有 alternatives 却无 criteria
          WEIGHTS_NOT_NORMALIZED  criteria 权重之和 != 1.0（容差 1e-6）
          CONCLUSION_WITHOUT_EVIDENCE  有 conclusions 却无 evidence

        关键区别在 missing_required 这个标志，只有前三条中的第 1、3 条会置真，
        权重未归一**不置真**。理由：权重不对只是口径问题，可以修正；
        而"给了备选却不给评估标准"和"下了结论却没证据"是结构性缺陷，
        修正不了——这正是算子③ 把崩塌等级直接顶到 HIGH 的依据。

        另注意 conclusions 也接受 recommendation 作为别名。
        """
        flags: List[Dict[str, Any]] = []
        missing_required = False

        alts = ctx.get('alternatives')
        criteria = ctx.get('criteria')
        if alts and not criteria:
            flags.append({'type': 'MISSING_CRITERIA',
                          'description': '提供了备选方案但未声明评估标准'})
            missing_required = True

        if criteria and isinstance(criteria, dict):
            weights = []
            for v in criteria.values():
                if isinstance(v, dict) and 'weight' in v:
                    weights.append(v['weight'])
            if weights and all(w is not None for w in weights):
                s = sum(float(w) for w in weights)
                if abs(s - 1.0) > 1e-6:
                    flags.append({'type': 'WEIGHTS_NOT_NORMALIZED',
                                  'description': f'权重之和={s}，未归一到1.0', 'sum': s})

        conclusions = ctx.get('conclusions') or ctx.get('recommendation')
        evidence = ctx.get('evidence')
        if conclusions and not evidence:
            flags.append({'type': 'CONCLUSION_WITHOUT_EVIDENCE',
                          'description': '给出了结论但未提供证据'})
            missing_required = True

        ctx['_implicit_assumptions'] = {'flags': flags, 'missing_required': missing_required}
        return ctx

    # -------- 五步算子③：脆弱性对冲 --------

    @staticmethod
    def _assess_vulnerability(ctx: Dict[str, Any]) -> Dict[str, Any]:
        """定位最脆弱变量并给出崩塌等级（HIGH/MEDIUM/LOW）。

        等级只能**单向上升**，不能回退：
          missing_required 为真          → 直接 HIGH，后面的规则不看
          否则遇 WEIGHTS_NOT_NORMALIZED  → MEDIUM
          否则叙述含主观修饰词           → LOW 提到 weakest，但等级仍为 LOW

        最后一条是有意为之：叙述带修辞是**观察**，不是结构性缺陷，
        不足以把等级抬起来；它只负责指出最脆弱变量在哪。

        weakest 用 `weakest or ...` 串联，因此报告里看到的永远是**第一个**
        触发的原因，不是最后命中的那个。
        """
        implicit = ctx.get('_implicit_assumptions', {})
        flags = implicit.get('flags', [])
        level = CollapseLevel.LOW
        weakest: Optional[str] = None
        reasons: List[str] = []

        if implicit.get('missing_required'):
            level = CollapseLevel.HIGH
            weakest = 'required_assumptions'
            reasons.append('关键假设缺失（评估标准/证据/责任人）')
        else:
            for f in flags:
                if f['type'] == 'WEIGHTS_NOT_NORMALIZED' and level != CollapseLevel.HIGH:
                    level = CollapseLevel.MEDIUM
                    weakest = weakest or 'criteria_weights'
                    reasons.append('评估权重未归一')
            narr = ctx.get('_narrative_stripped', {}).get('flagged_fields')
            if narr and level == CollapseLevel.LOW:
                weakest = weakest or 'narrative_subjectivity'
                reasons.append('叙述中包含主观修饰词')

        ctx['_vulnerability'] = {
            'weakest_variable': weakest,
            'collapse_level': level,
            'reasons': reasons,
        }
        return ctx

    # -------- LLM 护栏 --------

    def _strip_llm_output(self, parsed: Any, tier: LLMPermissionTier) -> Tuple[Dict[str, Any], bool]:
        """剥离 LLM 输出中能影响结构判定的字段。返回 (stripped, violated)。

        violated 表示「LLM 确实越权过」，无论剥离是否成功都会在
        LLMCallRecord.response_excerpt 上打上 [VIOLATION STRIPPED] 前缀。

        T3_NARRATIVE 层的处理更严格：整个返回被压缩成**只有** narrative
        一个键（依次尝试 narrative / overall_assessment / reasoning，
        都没有就把剩余内容整体 JSON 化）。也就是说 T3 连自己新造的字段都
        带不出去——它只能贡献一段文字。

        非 dict 输入（模型没按要求返回 JSON）统一降级为 str 塞进 narrative，
        不会抛错。
        """
        violated = False
        if not isinstance(parsed, dict):
            return {'narrative': str(parsed)}, violated
        stripped: Dict[str, Any] = {}
        for k, v in parsed.items():
            if k in self.FORBIDDEN_LLM_KEYS:
                violated = True
                continue
            stripped[k] = v
        if tier == LLMPermissionTier.T3_NARRATIVE:
            narrative = (stripped.get('narrative') or stripped.get('overall_assessment')
                         or stripped.get('reasoning')
                         or json.dumps(stripped, ensure_ascii=False))
            return {'narrative': narrative}, violated
        return stripped, violated

    def _safe_llm_call(
        self, prompt: str, purpose: str, tier: Optional[LLMPermissionTier] = None,
    ) -> Optional[Tuple[LLMCallRecord, Dict[str, Any]]]:
        if self.llm_provider is None:
            return None
        t = tier or self.llm_default_tier
        try:
            raw = self.llm_provider.generate(prompt, temperature=0.3, max_tokens=4096)
        except Exception as e:
            raw = f'[LLM Exception] {e}'
        prompt_hash = hashlib.sha256(prompt.encode('utf-8')).hexdigest()[:16]
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = raw
        stripped, violated = self._strip_llm_output(parsed, t)
        record = LLMCallRecord(
            permission_tier=t,
            purpose=purpose,
            prompt_hash=prompt_hash,
            response_excerpt=str(stripped)[:400],
            stripped=True,
            adjudicated=False,
        )
        if violated:
            record.response_excerpt = '[VIOLATION STRIPPED] ' + record.response_excerpt[:380]
        return record, stripped

    # -------- 插件权限强制 --------

    def _enforce_plugin_tier(self, plugin: AuditPlugin, result: Any) -> Any:
        """在插件结果进入报告前强制其权限层，越权即降级。

        T3 发了 status   → 剥掉 status，记 _tier_violation
        T2 发了 BLOCKED  → 降级为 WARNING，记 _tier_violation
        T1 不受限

        这是护栏的**执行点**：CORE_PLUGIN_TIERS 只是声明，实际约束在这里。
        违规不会抛异常，只会被改写并在报告里留痕——
        报告要如实反映插件确实越权过，沉默地修正等于掩盖问题。
        """
        if not isinstance(result, dict):
            return result
        status = result.get('status')
        if plugin.tier == PluginTier.T3_NARRATIVE and status is not None:
            result = {k: v for k, v in result.items() if k != 'status'}
            result['_tier_violation'] = f"T3 plugin '{plugin.name}' emitted status={status}"
        elif plugin.tier == PluginTier.T2_SIGNAL and status in {'BLOCKED', 'CRITICAL'}:
            result['status'] = 'WARNING'
            result['_tier_violation'] = (
                f"T2 plugin '{plugin.name}' tried blocking status={status}, downgraded to WARNING"
            )
        return result

    # -------- 五步算子④：静态审计（前序三算子+责任闭环+插件） --------

    def audit(
        self,
        decision_context: Dict[str, Any],
        save_log: bool = False,
        log_dir: str = 'logs',
    ) -> Dict[str, Any]:
        """执行一次静态结构审计。

        decision_context 的输入契约（所有键均为可选）：

          narrative    str        别名 background / summary / description
                                   含修辞的决策陈述，NS 从中剥离主观修饰词
          decision     str        别名 p / premise / action       —— 因果链的 P
          assumptions  list[str]  别名 premises / hypotheses       —— 因果链的 A
          outcome      str        别名 q / result / consequence   —— 因果链的 Q
          branches     list[dict] 别名 branch_responses / failure_paths / delta_d
                                   [{"assumption": "A1", "delta_d": "回滚"}]
                                   语义：¬A ⇒ ΔD
          dependencies dict        别名 dependency_graph / deps
                                   {"A1": ["A2"]}；缺失时按无依赖处理
          criteria     dict       {维度名: {"weight": w}}；权重之和须为 1.0，
                                   否则 IAP 报 WEIGHTS_NOT_NORMALIZED
          evidence     list[str]  支撑结论的证据标识；缺失时 IAP 报
                                   CONCLUSION_WITHOUT_EVIDENCE
          conclusions  str        待审计的结论文本

        最小可用输入：{"decision": ..., "assumptions": [...], "outcome": ...}
        完整示例见 demo_audit.py。各算子的别名表见各自模块头。

        返回 report dict：analysis（五算子结果）、implicit_assumptions、
        vulnerability、responsibility_account。责任人未闭环时
        analysis.RESPONSIBILITY_CLOSURE.status 为 BLOCKED。
        """
        # ---------- 第一阶段：三个静态算子先把 ctx 加工一遍 ----------
        # 顺序有依赖：② 要写 _implicit_assumptions，③ 要读它，所以不能换。
        # 这一阶段只往 ctx 里塞 _开头的派生字段，原始输入一律不改动。
        ctx = self._strip_narrative(decision_context)
        ctx = self._surface_implicit_assumptions(ctx)
        ctx = self._assess_vulnerability(ctx)

        report: Dict[str, Any] = {
            'gcae_version': GCAE_VERSION,
            'disclaimer': self.config.get('disclaimer', ''),
            'responsibility_account': asdict(self.account),
            'analysis': {},
            'custom_fields': self.config.get('custom_fields', {}),
            'narrative_meta': ctx.get('_narrative_stripped', {}),
            'implicit_assumptions': ctx.get('_implicit_assumptions', {}),
            'vulnerability': ctx.get('_vulnerability', {}),
            'llm_calls': [],
        }

        if not self.account.is_closed:
            report['analysis']['RESPONSIBILITY_CLOSURE'] = {
                'status': 'BLOCKED',
                'reason': 'RESPONSIBILITY_NOT_CLOSED',
                'message': f'责任未闭环：stage={self.account.stage} 缺少具体责任人(owner)',
            }

        run_ctx = dict(ctx)
        run_ctx['_responsibility_account'] = asdict(self.account)
        run_ctx['_clock'] = self._clock
        prior: Dict[str, Any] = {}
        run_ctx['_prior_audit_results'] = prior

        # 插件执行顺序 = (是否 STATE, 权限层级)。两个维度都要：
        #   - STATE 排最后，因为它要汇总前四者的结果（读 _prior_audit_results）
        #   - 同一层级内 T1 先于 T2，阻断项应当先于信号项被看到
        def tier_key(p: AuditPlugin) -> int:
            return {PluginTier.T1_STRUCTURAL: 0,
                    PluginTier.T2_SIGNAL: 1,
                    PluginTier.T3_NARRATIVE: 2}[p.tier]

        ordered = sorted(self.plugins, key=lambda p: (p.name == 'STATE', tier_key(p)))
        for plugin in ordered:
            try:
                result = plugin.analyze_func(run_ctx)
            except Exception as e:
                # 插件抛异常**不算通过**，一律记 BLOCKED。
                # 理由：审计失败和审计通过同样不能被当成「没问题」。
                result = {'status': 'BLOCKED', 'reason': 'PLUGIN_EXCEPTION', 'message': str(e)}
            result = self._enforce_plugin_tier(plugin, result)
            report['analysis'][plugin.name] = result
            prior[plugin.name] = result

        if self.llm_provider is not None:
            res = self._safe_llm_call(
                prompt=(
                    '你是认知审计专家（仅T3叙述权限，不得输出status/converged/weight/rank/verdict等裁决字段）。'
                    '请对以下决策上下文做语义级风险与偏见叙述性说明，以JSON返回，仅包含 narrative 字段。\n\n'
                    f'决策上下文：{json.dumps(decision_context, ensure_ascii=False, default=str)}'
                ),
                purpose='STATIC_AUDIT',
                tier=LLMPermissionTier.T3_NARRATIVE,
            )
            if res is not None:
                record, stripped = res
                report['analysis']['llm_narrative'] = stripped
                report['llm_calls'].append(asdict(record))

        # 事件里只放**派生摘要**（报告哈希、脆弱性、是否有阻断），
        # 不放完整报告，也不放原始决策数据——链上不落敏感数据。
        self._append_event('AUDIT', {
            'report_hash': hashlib.sha256(
                json.dumps(report, sort_keys=True, ensure_ascii=False, default=str).encode('utf-8')
            ).hexdigest()[:16],
            'vulnerability': report['vulnerability'],
            'has_blocking': any(
                isinstance(r, dict) and r.get('status') in ConvergenceChecker.BLOCKING_STATUSES
                for r in report['analysis'].values()
            ),
        })

        if save_log:
            report['log_path'] = self._write_log(report, log_dir)
        return report

    def _write_log(self, report: Dict[str, Any], log_dir: str) -> str:
        # 落盘三件事，缺一不可：
        #   audit_id         人类可读的审计编号（nonce + 时间戳）
        #   chain_root_hash  链根指纹——**这是唯一的对外校验凭据**
        #   完整 report      派生结论，不含原始决策数据
        # 注意：日志文件必须与报告分开保存。若校验凭据和被校验对象放在一起，
        # 任何人都能同时改掉两者，验证就失去意义了。
        os.makedirs(log_dir, exist_ok=True)
        audit_id = f'SPL-{self.account.nonce}-{int(self._clock if self._clock is not None else time.time())}'
        report['chain_root_hash'] = self.chain_root_hash
        report['audit_id'] = audit_id
        path = os.path.join(log_dir, f'{audit_id}.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2, default=str)
        return os.path.abspath(path)


    # -------- 五步算子⑤：因果重构（bounded + human gate + 形式化收敛） --------

    def reconstruct(
        self,
        decision_context: Dict[str, Any],
        delta_vars: Optional[Dict[str, Any]] = None,
        max_rounds: int = 5,
        human_approved_deltas: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """⑤ 因果重构：bounded 迭代 + human gate + 五状态形式化收敛。

        语义：
            - 首轮：若提供 delta_vars（视为已声明起始修正），应用；否则不自动修正。
            - 之后每轮只接受 human_approved_deltas 中的修正（由外部审批流提交）。
            - 每轮 audit 后由 ConvergenceChecker 分类；只要不是 DIVERGED 就停止。
            - human gate：每轮结束返回 awaiting_human=True，调用方显式推进。
              本方法一次性跑完所有已批准的 delta 序列（同步、有界）；不做自循环。

        返回：
            session_root_hash / final_state / rounds / is_true_convergence / final_report
        """
        if max_rounds < 1:
            raise ValueError('max_rounds must be >= 1')

        rounds: List[Dict[str, Any]] = []
        current_ctx = copy.deepcopy(decision_context)
        approved = list(human_approved_deltas or [])
        if delta_vars:
            approved.insert(0, delta_vars)

        previous_risks: frozenset = frozenset()
        state = ConvergenceState.DIVERGED
        final_report: Dict[str, Any] = {}

        for idx in range(max_rounds + 1):  # +1 允许初始轮（无 delta）
            # 应用本轮 delta（若有）
            if idx < len(approved):
                d = approved[idx]
                if not isinstance(d, dict) or not d:
                    state = ConvergenceState.BLOCKED
                    rounds.append({
                        'round': idx,
                        'status': state.value,
                        'reason': 'EMPTY_OR_INVALID_DELTA',
                    })
                    break
                current_ctx.update(d)
                self._append_event('DELTA_APPLIED', {'round': idx, 'delta_keys': sorted(d.keys())})
            elif idx > 0:
                # 没有更多已批准 delta，但仍未收敛 → 停在 AWAITING_HUMAN
                state = ConvergenceState.DIVERGED
                rounds.append({
                    'round': idx,
                    'status': state.value,
                    'awaiting_human': True,
                    'reason': 'NO_MORE_APPROVED_DELTAS',
                })
                break

            report = self.audit(current_ctx)
            final_report = report
            current_risks, has_blocking = ConvergenceChecker.extract_risk_set(report)
            has_unresolved = bool(report.get('implicit_assumptions', {}).get('missing_required'))

            state = ConvergenceChecker.classify(
                round_idx=idx,
                max_rounds=max_rounds,
                previous_risks=previous_risks,
                current_risks=current_risks,
                has_blocking=has_blocking,
                has_unresolved_assumptions=has_unresolved,
            )

            round_hash = hashlib.sha256(
                json.dumps({'idx': idx, 'state': state.value, 'risks': sorted(map(str, current_risks))},
                           sort_keys=True).encode('utf-8')
            ).hexdigest()[:16]

            rounds.append({
                'round': idx,
                'status': state.value,
                'risk_count': len(current_risks),
                'has_blocking': has_blocking,
                'round_hash': round_hash,
                'report_ref': report.get('audit_id'),
            })

            self._append_event('RECONSTRUCT_ROUND', {
                'round': idx,
                'state': state.value,
                'risk_count': len(current_risks),
                'round_hash': round_hash,
            })

            if state != ConvergenceState.DIVERGED:
                break
            previous_risks = current_risks

        # 跑完了已批准序列但仍 DIVERGED 且没到预算上限 → 等待人继续批
        awaiting_human = (state == ConvergenceState.DIVERGED and len(rounds) <= max_rounds
                          and rounds[-1].get('reason') == 'NO_MORE_APPROVED_DELTAS')

        return {
            'gcae_version': GCAE_VERSION,
            'final_state': state.value,
            'is_true_convergence': state.is_true_convergence,
            'awaiting_human': awaiting_human,
            'rounds': rounds,
            'final_report': final_report,
            'session_root_hash': self.chain_root_hash,
            'total_rounds': len(rounds),
        }

    # -------- 会话推进（human gate） --------

    def advance_with_human_delta(
        self,
        previous_result: Dict[str, Any],
        decision_context: Dict[str, Any],
        human_delta: Dict[str, Any],
    ) -> Dict[str, Any]:
        """在之前的 reconstruct 结果上由人工提交一个新 delta，再跑一轮。

        便捷入口：把历史 delta 重放到当前上下文、追加 human_delta，再跑一轮 audit 判定。
        """
        # 重建当前上下文（基于初始 + 之前所有已应用 delta 累积）
        current_ctx = copy.deepcopy(decision_context)
        # 这里的简单实现：调用方若需累积多轮，自行维护上下文；reconstruct() 每轮是无状态的
        current_ctx.update(human_delta)
        report = self.audit(current_ctx)
        risks, has_blocking = ConvergenceChecker.extract_risk_set(report)
        has_unresolved = bool(report.get('implicit_assumptions', {}).get('missing_required'))
        state = ConvergenceChecker.classify(
            round_idx=len(self.event_chain),
            max_rounds=len(self.event_chain) + 10,
            previous_risks=frozenset(),
            current_risks=risks,
            has_blocking=has_blocking,
            has_unresolved_assumptions=has_unresolved,
        )
        self._append_event('HUMAN_ADVANCE', {
            'delta_keys': sorted(human_delta.keys()),
            'state': state.value,
        })
        return {
            'final_state': state.value,
            'is_true_convergence': state.is_true_convergence,
            'final_report': report,
            'session_root_hash': self.chain_root_hash,
        }

    # -------- 审计链验证 --------

    def verify_chain(self) -> Dict[str, Any]:
        """独立验证哈希链的链接完整性与内容封存状态。

        校验三类破坏：
          1. 链接破坏 —— prev_hash 与前序链根不符               -> LINK_BROKEN
          2. 内容篡改 —— hash 重算值与封存值 sealed_hash 不符   -> CONTENT_TAMPERED
             覆盖 payload / event_type / timestamp / nonce 的事后改动
          3. 未经封存 —— sealed_hash 为 None                   -> EVENT_NOT_SEALED

        返回 {valid, last_valid_idx, total, root_hash}。
        """
        prev = 'ROOT'
        last_valid = -1
        for i, ev in enumerate(self.event_chain):
            if ev.prev_hash != prev:
                return {'valid': False, 'last_valid_idx': last_valid,
                        'total': len(self.event_chain), 'broken_at': i,
                        'reason': 'LINK_BROKEN',
                        'root_hash': self.chain_root_hash}
            if ev.sealed_hash is None:
                return {'valid': False, 'last_valid_idx': last_valid,
                        'total': len(self.event_chain), 'broken_at': i,
                        'reason': 'EVENT_NOT_SEALED',
                        'root_hash': self.chain_root_hash}
            blob = json.dumps({
                'event_type': ev.event_type,
                'payload': ev.payload,
                'prev_hash': ev.prev_hash,
                'timestamp': ev.timestamp,
                'nonce': ev.nonce,
            }, sort_keys=True, ensure_ascii=False, default=str)
            actual = hashlib.sha256(blob.encode('utf-8')).hexdigest()
            if actual != ev.sealed_hash:
                return {'valid': False, 'last_valid_idx': last_valid,
                        'total': len(self.event_chain), 'broken_at': i,
                        'reason': 'CONTENT_TAMPERED',
                        'root_hash': self.chain_root_hash}
            prev = ev.sealed_hash
            last_valid = i
        return {'valid': True, 'last_valid_idx': last_valid,
                'total': len(self.event_chain), 'root_hash': self.chain_root_hash}


# ==================== 便捷入口（demo） ====================

def _demo():
    """冒烟演示：
        1) 责任未闭环 → BLOCKED
        2) 闭环后做一次静态审计
        3) 注入修正 delta，观察收敛状态
    """
    # 场景1：责任未闭环
    acct_open = ResponsibilityAccount(organization='ACME', role='Risk Officer', stage='INVESTMENT')
    eng = CognitiveAuditEngine(acct_open)
    r = eng.audit({
        'alternatives': {'S1': {'metrics': {'roi': 0.12}}, 'S2': {'metrics': {'roi': 0.08}}},
        'criteria': {'roi': {'weight': 1.0}},
        'conclusions': 'Recommend S1',
        'evidence': ['doc#123'],
    })
    print('[1] Responsibility open ->', r['analysis'].get('RESPONSIBILITY_CLOSURE', {}).get('status'))

    # 场景2：闭环，含主观词 + 权重未归一
    acct = ResponsibilityAccount(organization='ACME', role='Risk Officer',
                                 stage='INVESTMENT', owner='张三/工号888')
    eng = CognitiveAuditEngine(acct)
    r = eng.audit({
        'narrative': '显然S1是最优方案',
        'alternatives': {'S1': {'metrics': {'roi': 0.12}}, 'S2': {'metrics': {'roi': 0.08}}},
        'criteria': {'roi': {'weight': 0.6}, 'risk': {'weight': 0.6}},  # 权重和=1.2
        'conclusions': 'Recommend S1',
        'evidence': ['doc#123'],
    })
    print('[2] Vulnerability ->', r['vulnerability']['collapse_level'],
          '| weakest =', r['vulnerability']['weakest_variable'])
    print('    Narrative flagged ->', r['narrative_meta']['flagged_fields'])
    print('    Implicit flags ->', [f['type'] for f in r['implicit_assumptions']['flags']])

    # 场景3：因果重构 — 注入修正（权重归一），应该收敛到 NO_GAIN
    r3 = eng.reconstruct(
        decision_context={
            'alternatives': {'S1': {'metrics': {'roi': 0.12}}, 'S2': {'metrics': {'roi': 0.08}}},
            'criteria': {'roi': {'weight': 0.6}, 'risk': {'weight': 0.6}},
            'conclusions': 'Recommend S1',
            'evidence': ['doc#123'],
        },
        delta_vars={'criteria': {'roi': {'weight': 0.5}, 'risk': {'weight': 0.5}}},
        max_rounds=3,
    )
    print('[3] Final state ->', r3['final_state'],
          '| true_convergence =', r3['is_true_convergence'],
          '| root_hash =', r3['session_root_hash'][:16])

    # 场景4：验证哈希链完整性
    v = eng.verify_chain()
    print('[4] Chain valid ->', v['valid'], '| events =', v['total'])


if __name__ == '__main__':
    _demo()
