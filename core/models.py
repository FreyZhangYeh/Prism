from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any


@dataclass
class Source:
    url: str
    domain: str
    type: str  # "official" | "media" | "forum" | "lab" | ...


@dataclass
class EvidenceItem:
    id: str
    source: Source
    time: str       # "YYYY-MM"
    text: str


@dataclass
class Claim:
    id: str
    text: str
    support_ids: List[str]
    aspects: List[str]
    confidence: float                 # 0..1
    stance: Optional[str] = None      # "pro" | "neutral" | "con"
    salience: Optional[float] = None  # 0..1


@dataclass
class Metrics:
    sufficiency: float      # 信息是否足以支撑稳定结论
    reliability: float      # 来源/证据可信度
    consistency: float      # 观点一致度
    recency: float         # 时效性
    diversity: float       # 多样性


@dataclass
class Issue:
    type: str              # "gap" | "conflict" | "freshness" | "quality" | "diversity"
    severity: str          # "low" | "med" | "high"
    blocking: bool         # 是否阻断稳定结论
    desc: str             # ≤120字中文问题描述
    # Type-specific fields (optional)
    aspect: Optional[str] = None              # for type="gap"
    claims: Optional[List[str]] = None        # for type="conflict"
    time_window: Optional[str] = None        # for type="freshness"
    source_hint: Optional[str] = None        # for type="quality"
    dimension: Optional[str] = None          # for type="diversity": "source"|"viewpoint"|"method"


@dataclass
class NextAction:
    action: str      # "RAG" | "WEB"
    query: str
    aspects_need: List[str]
    source_pref: Optional[str] = None
    time_window: Optional[str] = None


@dataclass
class EvaluateSnapshot:
    metrics: Metrics
    issues: List[Issue]
    passed: bool
    unmet: List[Dict]
    next_actions: List[NextAction]
    stance_stats: Optional[Dict[str, int]] = None


@dataclass
class SessionConfig:
    prefs: Dict
    thresholds: Dict
    budget_state: Dict
    stance_enabled: bool = False


@dataclass
class PlanSnapshot:
    evidence_base_ids: List[str]
    claim_base_ids: List[str]


@dataclass
class PlanPatch:
    add_evidence_ids: List[str] = field(default_factory=list)
    merge_claims: List[Claim] = field(default_factory=list)
    set_evaluate: Optional[EvaluateSnapshot] = None


@dataclass
class ActionLog:
    action_id: str
    type: str             # "RAG" | "WEB" | "final_output"
    query: str
    out_evidence_ids: List[str]
    cost: float
    ts: str
    status: str           # "ok" | "fail"


@dataclass
class PlanStep:
    step_id: str
    goal: str                      # 子目标/问题
    action_seed: List[NextAction]  # 候选行动指令（可为空）
    done_criteria: str             # 判定完成的标准
    priority: int                  # 执行优先级（数值越小越先）
    way: str = ""                  # 达成路径
    status: str = "NOT_START"      # "NOT_START" | "RUNNING" | "FINISHED"


# New models for sub-agents
@dataclass
class RAGQuery:
    query: str
    top_k: int = 5


@dataclass
class WebSearchQuery:
    query: str
    num_results: int = 5
    params: Optional[Dict[str, Any]] = None


@dataclass
class ConflictInfo:
    claims: List[str]         # Conflicting claim IDs
    severity: str             # "low" | "med" | "high"
    desc: Optional[str] = None


@dataclass 
class ResolveConflictRequest:
    step: Dict[str, str]      # {"goal": "...", "way": "..."}
    claims_active: List[Dict]
    conflicts: List[ConflictInfo]
    last_evaluate: Dict
    kb_catalog_summary: Optional[Dict] = None


@dataclass
class UpdatedClaim:
    claim_id: str
    action: str               # "upheld" | "revised" | "retracted"
    new_confidence: float
    evidence_ids: List[str]
    rationale_md: str
    new_text: Optional[str] = None
    supersedes_id: Optional[str] = None


@dataclass
class ResolutionSummary:
    conflict_groups_total: int
    groups_resolved: int
    remaining_conflicts: List[List[str]]