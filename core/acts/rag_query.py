import json
from typing import Dict, Any, List, Optional

from core.models import RAGQuery, Issue, EvaluateSnapshot
from llm.client import LLMClient


class RAGQueryGenerator:
    """Generate queries for RAG (internal knowledge base) searches."""
    
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client
    
    def generate_query(self,
                      step: Dict[str, str],
                      claims_active: List[Dict],
                      last_evaluate: EvaluateSnapshot) -> RAGQuery:
        """Generate RAG query based on gaps and issues."""
        
        # Build prompt
        prompt = self._build_prompt(step, claims_active, last_evaluate)
        
        # System prompt according to refine.md
        system_prompt = """你是"本地检索查询生成器"。根据 step 与 eval 的 issues（尤其 gap），为公司内部知识库生成一个检索查询。

规则：
- 仅返回 JSON：{"query":"...", "top_k":N}
- 关键词基于 gap.aspect；若无，则基于 step.goal/way 与高置信观点提取。
- 可加入 1-2 个领域别名/同义词；避免赘词。
- 不输出任何外网过滤器或多余字段；top_k 最大为5。

Context:
- Step: <goal/way>
- Claims (summary): <...>
- Eval JSON: <...>
只返回单个 JSON 对象。"""
        
        # Call LLM
        result = self.llm.generate_json(
            system_prompt=system_prompt,
            user_prompt=prompt,
            temperature=0.5
        )
        
        # Parse and validate response
        try:
            query = result.get("query", "")
            top_k = result.get("top_k", 5)
            
            # Validate
            if not query:
                raise ValueError("Empty query")
            if not isinstance(top_k, int) or top_k < 1 or top_k > 20:
                top_k = 5
            
            return RAGQuery(query=query, top_k=top_k)
        
        except Exception as e:
            print(f"Error parsing RAG query response: {e}")
            # Fallback query generation
            return self._generate_fallback_query(step, last_evaluate)
    
    def _build_prompt(self,
                      step: Dict[str, str],
                      claims_active: List[Dict],
                      last_evaluate: EvaluateSnapshot) -> str:
        """Build prompt for RAG query generation."""
        
        # Format step
        step_str = f"goal: {step.get('goal', '')}"
        if step.get('way'):
            step_str += f"\nway: {step['way']}"
        
        # Extract high confidence claims
        high_conf_claims = [c for c in claims_active if c.get('confidence', 0) >= 0.7]
        claims_summary = "高置信观点:\n"
        for claim in high_conf_claims[:5]:
            claims_summary += f"- {claim['text']}\n"
        
        if not high_conf_claims:
            claims_summary = "暂无高置信观点"
        
        # Format eval issues focusing on gaps
        eval_dict = {
            "passed": last_evaluate.passed,
            "issues": []
        }
        
        # Prioritize gap issues
        gap_issues = [i for i in last_evaluate.issues if i.type == "gap"]
        other_issues = [i for i in last_evaluate.issues if i.type != "gap"]
        
        for issue in (gap_issues + other_issues)[:4]:  # Max 4 issues
            issue_dict = {
                "type": issue.type,
                "desc": issue.desc
            }
            if issue.type == "gap" and issue.aspect:
                issue_dict["aspect"] = issue.aspect
            eval_dict["issues"].append(issue_dict)
        
        prompt = f"""Step: {step_str}

Claims (summary): {claims_summary}

Eval JSON: {json.dumps(eval_dict, ensure_ascii=False, indent=2)}

请依据系统规则只返回 {{"query":"...","top_k":N}}。"""
        
        return prompt
    
    def _generate_fallback_query(self,
                                 step: Dict[str, str],
                                 last_evaluate: EvaluateSnapshot) -> RAGQuery:
        """Generate fallback query when LLM fails."""
        
        # Try to extract keywords from gaps
        keywords = []
        
        # Get gap aspects
        for issue in last_evaluate.issues:
            if issue.type == "gap" and issue.aspect:
                keywords.append(issue.aspect)
        
        # Add goal keywords
        if step.get('goal'):
            # Simple keyword extraction from goal
            goal_words = step['goal'].split()
            keywords.extend([w for w in goal_words if len(w) > 2][:3])
        
        # Build query
        if keywords:
            query = " ".join(keywords[:5])
        else:
            query = step.get('goal', 'information')
        
        return RAGQuery(query=query, top_k=5)