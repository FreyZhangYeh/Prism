import json
from typing import Dict, Any, Optional, List

from core.models import PlanStep, EvaluateSnapshot, Issue
from llm.client import LLMClient


class MakeDecision:
    """Make decisions based on evaluation results with new action types."""
    
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client
    
    def decide(self,
               step: PlanStep,
               claims_active_summary: str,
               last_evaluate: EvaluateSnapshot,
               kb_catalog_summary: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Decide next action: RAG, WEB_SEARCH, RESOLVE_CONFLICT, or FINISH."""
        
        # Quick check: if evaluation passed, prioritize FINISH
        if last_evaluate.passed:
            # Check for real blocking issues (only high severity blocking issues matter)
            real_blocking = [i for i in last_evaluate.issues 
                           if i.blocking and i.severity == "high"]
            if not real_blocking:
                return {
                    "action": "FINISH",
                    "rationale": "评估已通过，当前步骤研究目标已充分达成"
                }
        
        # Default KB catalog if not provided
        if kb_catalog_summary is None:
            kb_catalog_summary = {
                "topics": ["内部文档", "技术规范", "流程设计"],
                "doc_count": 100,
                "examples": ["系统设计文档", "API规范", "部署流程"]
            }
        
        # Build prompt
        prompt = self._build_prompt(
            step,
            claims_active_summary,
            last_evaluate,
            kb_catalog_summary
        )
        
        # System prompt according to refine.md
        system_prompt = """你是"路由决策器"。你的任务是基于评估结果与本地知识库覆盖情况选择一个动作，仅从：
- RAG：优先利用公司内部知识（内部文档/规范/流程/设计）
- WEB_SEARCH：优先利用外部信息（权威/最新/公开网络）
- RESOLVE_CONFLICT：优先解决冲突观点
- FINISH：信息已充分且无阻断

严格响应要求：
- 仅返回 JSON：{"action":"...", "rationale":"..."}（中文、≤100字）
- 不得输出参数或任何中间判断值（例如内部覆盖布尔）

判断偏好（非硬规则）：
- 若 last_evaluate.passed 为 true 且无 blocking=true → 选择 FINISH
- 若存在高严重度且 blocking=true 的 conflict → 选择 RESOLVE_CONFLICT
- 否则在 RAG 与 WEB_SEARCH 之间选择：
  - 判断内部覆盖：将 issues（尤其 gap.aspect）与 KB Catalog 的 topics/示例标题进行语义对齐
  - 内部覆盖明显匹配 → 倾向 RAG（内部知识可补齐）
  - 内部覆盖不足/不相关 → 倾向 WEB_SEARCH
  - 若存在明确时效需求（freshness.time_window）且内部覆盖不足 → 强烈倾向 WEB_SEARCH
  - 若需要权威背书（quality.source_hint 指向官方/学术/监管）→ 倾向 WEB_SEARCH
- 若多条件并存，优先级：RESOLVE_CONFLICT > WEB_SEARCH（强时效/权威） > RAG（内部可补齐） > FINISH

输出 JSON 架构：
{"action":"RAG|WEB_SEARCH|RESOLVE_CONFLICT|FINISH","rationale":"..."}"""
        
        # Call LLM
        result = self.llm.generate_json(
            system_prompt=system_prompt,
            user_prompt=prompt,
            temperature=0.3
        )
        
        # Validate and return
        try:
            if "action" not in result or "rationale" not in result:
                raise ValueError("Missing required fields in response")
            
            valid_actions = ["RAG", "WEB_SEARCH", "RESOLVE_CONFLICT", "FINISH"]
            if result["action"] not in valid_actions:
                raise ValueError(f"Invalid action: {result['action']}")
            
            return result
        
        except Exception as e:
            print(f"Error parsing decision response: {e}")
            # Fallback decision logic
            return self._fallback_decision(last_evaluate)
    
    def _build_prompt(self,
                      step: PlanStep,
                      claims_summary: str,
                      last_evaluate: EvaluateSnapshot,
                      kb_catalog: Dict[str, Any]) -> str:
        """Build prompt for decision making."""
        
        # Format step
        step_dict = {
            "goal": step.goal,
            "way": step.way if step.way else "未指定"
        }
        
        # Format evaluate results
        eval_dict = {
            "passed": last_evaluate.passed,
            "metrics": {
                "sufficiency": last_evaluate.metrics.sufficiency,
                "reliability": last_evaluate.metrics.reliability,
                "consistency": last_evaluate.metrics.consistency,
                "recency": last_evaluate.metrics.recency,
                "diversity": last_evaluate.metrics.diversity
            },
            "issues": []
        }
        
        # Format issues
        for issue in last_evaluate.issues[:6]:  # Max 6 issues
            issue_dict = {
                "type": issue.type,
                "severity": issue.severity,
                "blocking": issue.blocking,
                "desc": issue.desc
            }
            
            # Add type-specific fields
            if issue.type == "gap" and issue.aspect:
                issue_dict["aspect"] = issue.aspect
            elif issue.type == "conflict" and issue.claims:
                issue_dict["claims"] = issue.claims
            elif issue.type == "freshness" and issue.time_window:
                issue_dict["time_window"] = issue.time_window
            elif issue.type == "quality" and issue.source_hint:
                issue_dict["source_hint"] = issue.source_hint
            elif issue.type == "diversity" and issue.dimension:
                issue_dict["dimension"] = issue.dimension
            
            eval_dict["issues"].append(issue_dict)
        
        # Format KB catalog
        kb_summary = f"主题: {', '.join(kb_catalog['topics'][:5])}\n"
        kb_summary += f"文档数: {kb_catalog.get('doc_count', '未知')}\n"
        kb_summary += f"示例: {', '.join(kb_catalog.get('examples', [])[:3])}"
        
        # Build prompt
        prompt = f"""Step:
- goal: {step_dict['goal']}
- way: {step_dict['way']}

Claims (summary):
{claims_summary}

Eval JSON:
{json.dumps(eval_dict, ensure_ascii=False, indent=2)}

KB Catalog Summary:
{kb_summary}"""
        
        return prompt
    
    def _fallback_decision(self, last_evaluate: EvaluateSnapshot) -> Dict[str, Any]:
        """Fallback decision logic when LLM fails."""
        
        # Check if passed with no blocking issues
        has_blocking = any(issue.blocking for issue in last_evaluate.issues)
        if last_evaluate.passed and not has_blocking:
            return {
                "action": "FINISH",
                "rationale": "评估通过且无阻塞问题"
            }
        
        # Check for high-severity conflicts
        for issue in last_evaluate.issues:
            if issue.type == "conflict" and issue.severity == "high" and issue.blocking:
                return {
                    "action": "RESOLVE_CONFLICT",
                    "rationale": f"存在高严重度冲突需要解决"
                }
        
        # Check for freshness issues
        for issue in last_evaluate.issues:
            if issue.type == "freshness" and issue.blocking:
                return {
                    "action": "WEB_SEARCH",
                    "rationale": f"需要获取最新信息"
                }
        
        # Default to RAG for gaps
        for issue in last_evaluate.issues:
            if issue.type == "gap":
                return {
                    "action": "RAG",
                    "rationale": f"需要补充{issue.aspect or '相关'}信息"
                }
        
        # Final fallback
        return {
            "action": "RAG",
            "rationale": "需要收集更多信息"
        }