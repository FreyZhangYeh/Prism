import json
from typing import Dict, Any, List, Optional
from datetime import datetime

from core.models import WebSearchQuery, Issue, EvaluateSnapshot
from llm.client import LLMClient


class WebSearchQueryGenerator:
    """Generate queries for web searches."""
    
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client
    
    def generate_query(self,
                      step: Dict[str, str],
                      claims_active: List[Dict],
                      last_evaluate: EvaluateSnapshot) -> WebSearchQuery:
        """Generate web search query based on gaps, freshness, and quality issues."""
        
        # Get current date for context
        current_date = datetime.now().strftime("%Y-%m-%d")
        
        # Build prompt
        prompt = self._build_prompt(step, claims_active, last_evaluate, current_date)
        
        # System prompt according to refine.md
        system_prompt = """你是"外部检索查询生成器"。根据 step 与 eval 的 issues（freshness/quality/gap），为通用搜索引擎生成一个查询。

规则:
- 最小输出：{"query":"...", "num_results":N}
- 附加 {"params": {time_range/site_filters/file_types/sort_by_date/language}}；不支持则不要出现 params。
- 关键词基于 gap.aspect；若存在 freshness，则在 query 中自然加入"最新/年份/版本"等时效词。
- 如需权威来源，site_filters 包含映射的官方/学术/监管域（若 API 支持）；否则只体现在 query 文本中。
- 使用少量必要操作符（如 "精确短语", intitle, site, -排除），避免冗余。
- 只返回单个 JSON 对象。
- num_results <= 5。

Context:
- Step: <goal/way>
- Claims (summary): <...>
- Eval JSON: <...>
- Now: <YYYY-MM-DD>
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
            num_results = result.get("num_results", 5)
            params = result.get("params", None)
            
            # Validate
            if not query:
                raise ValueError("Empty query")
            if not isinstance(num_results, int) or num_results < 1 or num_results > 50:
                num_results = 5
            
            # Validate params if provided
            if params and not isinstance(params, dict):
                params = None
            
            return WebSearchQuery(
                query=query,
                num_results=num_results,
                params=params
            )
        
        except Exception as e:
            print(f"Error parsing web search query response: {e}")
            # Fallback query generation
            return self._generate_fallback_query(step, last_evaluate)
    
    def _build_prompt(self,
                      step: Dict[str, str],
                      claims_active: List[Dict],
                      last_evaluate: EvaluateSnapshot,
                      current_date: str) -> str:
        """Build prompt for web search query generation."""
        
        # Format step
        step_str = f"goal: {step.get('goal', '')}"
        if step.get('way'):
            step_str += f"\nway: {step['way']}"
        
        # Extract key claims
        high_conf_claims = [c for c in claims_active if c.get('confidence', 0) >= 0.7]
        claims_summary = "现有观点:\n"
        for claim in high_conf_claims[:3]:
            claims_summary += f"- {claim['text']}\n"
        
        if not high_conf_claims:
            claims_summary = "暂无高置信观点"
        
        # Format eval issues focusing on freshness, quality, and gaps
        eval_dict = {
            "passed": last_evaluate.passed,
            "issues": []
        }
        
        # Prioritize freshness and quality issues for web search
        priority_issues = []
        for issue in last_evaluate.issues:
            if issue.type in ["freshness", "quality", "gap"]:
                priority_issues.append(issue)
        
        for issue in priority_issues[:4]:  # Max 4 issues
            issue_dict = {
                "type": issue.type,
                "severity": issue.severity,
                "desc": issue.desc
            }
            
            # Add type-specific fields
            if issue.type == "gap" and issue.aspect:
                issue_dict["aspect"] = issue.aspect
            elif issue.type == "freshness" and issue.time_window:
                issue_dict["time_window"] = issue.time_window
            elif issue.type == "quality" and issue.source_hint:
                issue_dict["source_hint"] = issue.source_hint
            
            eval_dict["issues"].append(issue_dict)
        
        prompt = f"""Step: {step_str}

Claims (summary): {claims_summary}

Eval JSON: {json.dumps(eval_dict, ensure_ascii=False, indent=2)}

Now: {current_date}

请依据系统规则只返回 {{"query":"...","num_results":N}} 或包含可用 params 的同构 JSON。"""
        
        return prompt
    
    def _generate_fallback_query(self,
                                 step: Dict[str, str],
                                 last_evaluate: EvaluateSnapshot) -> WebSearchQuery:
        """Generate fallback query when LLM fails."""
        
        keywords = []
        time_keywords = []
        
        # Extract keywords from issues
        for issue in last_evaluate.issues:
            if issue.type == "gap" and issue.aspect:
                keywords.append(issue.aspect)
            elif issue.type == "freshness":
                time_keywords.extend(["最新", "2024", "2025"])
                if issue.time_window:
                    keywords.append(issue.time_window)
            elif issue.type == "quality" and issue.source_hint:
                keywords.append(issue.source_hint)
        
        # Add goal keywords
        if step.get('goal'):
            goal_words = step['goal'].split()
            keywords.extend([w for w in goal_words if len(w) > 2][:3])
        
        # Build query
        all_keywords = keywords + time_keywords
        if all_keywords:
            query = " ".join(all_keywords[:7])
        else:
            query = f"{step.get('goal', 'information')} 最新"
        
        # Simple params for freshness
        params = None
        has_freshness = any(i.type == "freshness" for i in last_evaluate.issues)
        if has_freshness:
            params = {
                "time_range": "last_6_months",
                "sort_by_date": True
            }
        
        return WebSearchQuery(
            query=query,
            num_results=5,
            params=params
        )