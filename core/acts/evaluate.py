import json
from typing import List, Dict, Any, Optional

from core.models import (
    EvaluateSnapshot, Metrics, Issue
)
from llm.client import LLMClient


class Evaluate:
    """Evaluate claims and evidence quality with new metrics and issue structure."""
    
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client
    
    def evaluate(self,
                 step: Dict[str, str],
                 claims: List[Dict],
                 evidence_meta: List[Dict],
                 thresholds: Optional[Dict[str, float]] = None,
                 prefs: Optional[Dict[str, Any]] = None,
                 budget_state: Optional[Dict[str, Any]] = None) -> EvaluateSnapshot:
        """Evaluate current research state with new metrics."""
        
        # Default thresholds
        if thresholds is None:
            thresholds = {
                "sufficiency": 0.80,
                "reliability": 0.75,
                "consistency": 0.70,
                "recency": 0.70,
                "diversity": 0.60
            }
        
        if prefs is None:
            prefs = {}
        
        if budget_state is None:
            budget_state = {"remaining_calls": 10}
        
        # Build prompt
        prompt = self._build_prompt(
            step,
            claims,
            evidence_meta,
            thresholds,
            prefs,
            budget_state
        )
        
        # System prompt according to refine.md
        system_prompt = """你是一个严谨的"评审器"。你的唯一任务是评估当前研究状态，并返回严格符合下述 JSON 架构的对象。禁止输出多余文本、禁止给出下一步建议或动作，仅返回 JSON。若第一次输出不符合架构，请自我纠正并仅重发合规 JSON。

评分定义（0~1，保留两位小数）:
- sufficiency: 信息是否足以支撑稳定结论（覆盖关键方面、证据深度足够）。
- reliability: 来源/证据可信度（权威性、交叉印证、一致可验证）。
- consistency: 观点一致度（未解决冲突越多，分越低）。
- recency: 时效性（对时间敏感问题，证据是否足够新）。
- diversity: 多样性（来源类型/观点/方法的多样程度）。

通过判定:
- "passed" 由你综合判断。推荐倾向：当 sufficiency ≥ 0.80 且不存在 blocking=true 的问题时可判为 true；若存在会阻断稳定结论的严重问题（如高严重度冲突、关键缺口未补、刚性时效未满足），应判为 false。

问题条目（issues）规范:
- 仅在"能指明具体行动缺口/矛盾/时效/质量/多样性问题"时生成，最多 6 条，避免重复。
- 通用字段(所有 issue 必填): 
  - type: gap | conflict | freshness | quality | diversity
  - severity: low | med | high
  - blocking: true | false  // 是否阻断稳定结论
  - desc: ≤120字中文说明，直指问题本身，避免泛化
- 各类型附加字段:
  - gap:    需含 "aspect"
  - conflict: 需含 "claims"
  - freshness: 需含 "time_window"
  - quality: 建议含 "source_hint"
  - diversity: 建议含 "dimension"（source|viewpoint|method）
- 严重度与阻断:
  - high 通常 blocking=true（会阻断稳定结论）
  - med/low 仅在确有阻断时才置 blocking=true
- 去重与主因选择:
  - 若多样性不足是质量不足的主因，优先输出 type=diversity，不再另加 quality。
  - 若缺口导致充分度低，使用 type=gap 即可，不重复"分数低"的泛化描述。
  - 不因"分数偏低"机械地产生 issue；仅在能够明确"行动方向"时生成。

输出 JSON 架构（键名严格一致，数值为 0~1 且两位小数）:
{
  "passed": true|false,
  "metrics": {
    "sufficiency": 0.00-1.00,
    "reliability": 0.00-1.00,
    "consistency": 0.00-1.00,
    "recency": 0.00-1.00,
    "diversity": 0.00-1.00
  },
  "issues": [
    {
      "type": "gap|conflict|freshness|quality|diversity",
      "severity": "low|med|high",
      "blocking": true|false,
      "desc": "≤120字中文",
      "aspect": "当 type=gap 必填",
      "claims": ["C12","C19"],
      "time_window": "近3个月",
      "source_hint": "官方/学术/监管",
      "dimension": "source|viewpoint|method"
    }
  ]
}

注意事项:
- 仅返回单个 JSON 对象；不要包裹反引号，不要添加解释性文本。
- 数值统一两位小数；issues 不超过 6 条；desc 必须为中文简述。
- 若证据不足以支持结论，请降低 sufficiency，并通过 gap 明确缺口的具体 aspect。
- 若存在相互矛盾的结论，请降低 consistency，并用 conflict 标注 claims。
- 若任务与时间高度相关，请据此设置 recency 与 freshness（含 time_window）。
- 若来源/观点/方法单一，请降低 diversity，并给出 diversity 类型问题（dimension）。"""
        
        # Call LLM
        result = self.llm.generate_json(
            system_prompt=system_prompt,
            user_prompt=prompt,
            temperature=0.3
        )
        
        # Parse response
        try:
            # Parse metrics
            metrics = Metrics(
                sufficiency=round(result["metrics"]["sufficiency"], 2),
                reliability=round(result["metrics"]["reliability"], 2),
                consistency=round(result["metrics"]["consistency"], 2),
                recency=round(result["metrics"]["recency"], 2),
                diversity=round(result["metrics"]["diversity"], 2)
            )
            
            # Parse issues
            issues = []
            for issue_data in result.get("issues", []):
                issue = Issue(
                    type=issue_data["type"],
                    severity=issue_data["severity"],
                    blocking=issue_data["blocking"],
                    desc=issue_data["desc"],
                    aspect=issue_data.get("aspect"),
                    claims=issue_data.get("claims"),
                    time_window=issue_data.get("time_window"),
                    source_hint=issue_data.get("source_hint"),
                    dimension=issue_data.get("dimension")
                )
                issues.append(issue)
            
            # Create snapshot (remove next_actions as it's not in new spec)
            snapshot = EvaluateSnapshot(
                metrics=metrics,
                issues=issues,
                passed=result["passed"],
                unmet=[],  # Not used in new spec
                next_actions=[],  # Not used in new spec
                stance_stats=None
            )
            
            return snapshot
        
        except Exception as e:
            print(f"Error parsing evaluate response: {e}")
            # Fallback evaluation
            return EvaluateSnapshot(
                metrics=Metrics(
                    sufficiency=0.50,
                    reliability=0.50,
                    consistency=0.50,
                    recency=0.50,
                    diversity=0.50
                ),
                issues=[
                    Issue(
                        type="gap",
                        severity="med",
                        blocking=False,
                        desc="需要更多信息",
                        aspect="general"
                    )
                ],
                passed=False,
                unmet=[],
                next_actions=[]
            )
    
    def _build_prompt(self,
                      step: Dict[str, str],
                      claims: List[Dict],
                      evidence_meta: List[Dict],
                      thresholds: Dict[str, float],
                      prefs: Dict[str, Any],
                      budget_state: Dict[str, Any]) -> str:
        """Build prompt for evaluation."""
        
        # Format step
        step_str = f"目标: {step.get('goal', '')}"
        if step.get('way'):
            step_str += f"\n达成路径: {step['way']}"
        
        # Format claims
        claims_str = "Claims:\n"
        for claim in claims[-10:]:  # Limit to 10 for context
            claims_str += f"- [{claim['id']}] {claim['text']} (置信度: {claim['confidence']})\n"
        
        # Format evidence meta
        evidence_str = "Evidence meta:\n"
        source_types = {}
        time_distribution = {}
        
        for ev in evidence_meta:
            # Count source types
            source_type = ev.get('type', 'unknown')
            source_types[source_type] = source_types.get(source_type, 0) + 1
            
            # Count time distribution
            time = ev.get('time', 'unknown')
            if time != 'unknown':
                year = time.split('-')[0] if '-' in time else time
                time_distribution[year] = time_distribution.get(year, 0) + 1
        
        evidence_str += f"- 来源类型分布: {source_types}\n"
        evidence_str += f"- 时间分布: {time_distribution}\n"
        evidence_str += f"- 总证据数: {len(evidence_meta)}\n"
        
        # Build final prompt
        prompt = f"""Step:
{step_str}

{claims_str}

{evidence_str}

Thresholds: {json.dumps(thresholds, ensure_ascii=False)}
Prefs: {json.dumps(prefs, ensure_ascii=False)}
Budget: {json.dumps(budget_state, ensure_ascii=False)}

请依据系统规则只返回 JSON。"""
        
        return prompt