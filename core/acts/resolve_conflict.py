import json
from typing import List, Dict, Any, Optional
from datetime import datetime

from core.models import (
    ConflictInfo, UpdatedClaim, ResolutionSummary,
    EvidenceItem, Source, Claim, Issue
)
from core.ids import generate_evidence_id, generate_claim_id
from core.acts.evaluate import Evaluate
from llm.client import LLMClient


class ResolveConflict:
    """Resolve conflicting claims through targeted search and analysis."""
    
    def __init__(self, llm_client: LLMClient, evaluator: Optional[Evaluate] = None):
        self.llm = llm_client
        self.evaluator = evaluator or Evaluate(llm_client)
    
    def resolve(self,
                step: Dict[str, str],
                claims_active: List[Dict],
                conflicts: List[ConflictInfo],
                last_evaluate: Dict,
                kb_catalog_summary: Optional[Dict] = None) -> Dict[str, Any]:
        """Complete conflict resolution process."""
        
        # Default KB catalog if not provided
        if kb_catalog_summary is None:
            kb_catalog_summary = {
                "topics": ["内部文档", "技术规范"],
                "examples": ["系统设计", "API文档"]
            }
        
        # Phase 1: Generate search plan and rubric
        search_plan = self._generate_search_plan(
            step, claims_active, conflicts, last_evaluate, kb_catalog_summary
        )
        
        # Phase 2: Execute searches (mocked)
        evidences = self._execute_searches(search_plan)
        
        # Phase 3: Resolve conflicts and update claims
        resolution = self._resolve_conflicts(
            step, claims_active, conflicts, evidences, search_plan.get("rubric", {})
        )
        
        # Phase 4: Update memory and evaluate
        updated_claims_list = self._apply_updates(claims_active, resolution["updated_claims"])
        
        # Phase 5: Re-evaluate with updated claims
        post_evaluate = self._post_evaluate(step, updated_claims_list, evidences)
        
        # Build response
        response = {
            "updated_claims": resolution["updated_claims"],
            "evidence_added": [self._evidence_to_dict(e) for e in evidences],
            "resolution_summary": resolution["resolution_summary"],
            "post_evaluate": self._evaluate_to_dict(post_evaluate),
            "partial_resolved": self._check_partial_resolved(post_evaluate)
        }
        
        return response
    
    def _generate_search_plan(self,
                              step: Dict[str, str],
                              claims_active: List[Dict],
                              conflicts: List[ConflictInfo],
                              last_evaluate: Dict,
                              kb_catalog_summary: Dict) -> Dict[str, Any]:
        """Phase 1: Generate search queries and alignment rubric."""
        
        # Build prompt
        prompt = self._build_search_plan_prompt(
            step, claims_active, conflicts, last_evaluate, kb_catalog_summary
        )
        
        system_prompt = """你是"冲突解决-检索规划器"。为当前冲突观点生成最小且有效的检索计划（内部RAG与外部Web），并给出对齐与取舍规则（rubric）。只返回 JSON，不要输出多余文本。

规则:
RAG：内部文档/规范/流程/设计类主题与 KB topics 明显匹配时；最多 1-2 条
Web：内部覆盖不足，或需要权威/最新信息时；最多 1-2 条
关键词围绕冲突点与必要对齐维度（统计口径/时间窗/样本/单位等），简洁明确
freshness→Web 查询中自然加入"最新/年份/版本"；quality→偏权威词（官方/学术/监管）

仅返回：
{
"queries_rag": [{ "query":"...", "top_k": N }],
"queries_web": [{ "query":"...", "num_results": N, "params": { 可选: time_range/site_filters/file_types/sort_by_date/language }}],
"rubric": {
"normalization": ["对齐项..."],
"precedence": ["官方/学术 > 标准/监管 > 厂商 > 媒体/博客"],
"comparison_keys": ["统计口径","时间窗","样本范围","单位"]
}
}"""
        
        # Call LLM
        result = self.llm.generate_json(
            system_prompt=system_prompt,
            user_prompt=prompt,
            temperature=0.5
        )
        
        # Validate and return
        return self._validate_search_plan(result)
    
    def _execute_searches(self, search_plan: Dict[str, Any]) -> List[EvidenceItem]:
        """Phase 2: Execute searches (mocked with LLM)."""
        
        evidences = []
        
        # Execute RAG queries
        for rag_query in search_plan.get("queries_rag", []):
            rag_evidences = self._mock_rag_search(rag_query)
            evidences.extend(rag_evidences)
        
        # Execute Web queries
        for web_query in search_plan.get("queries_web", []):
            web_evidences = self._mock_web_search(web_query)
            evidences.extend(web_evidences)
        
        return evidences
    
    def _resolve_conflicts(self,
                          step: Dict[str, str],
                          claims_active: List[Dict],
                          conflicts: List[ConflictInfo],
                          evidences: List[EvidenceItem],
                          rubric: Dict[str, Any]) -> Dict[str, Any]:
        """Phase 3: Resolve conflicts based on evidence and rubric."""
        
        # Build prompt
        prompt = self._build_resolution_prompt(
            step, claims_active, conflicts, evidences, rubric
        )
        
        system_prompt = """你是"冲突解决-裁决器"。基于新证据对冲突 claims 进行对齐与裁决，并直接给出更新结果。只返回 JSON，不要输出多余文本。

任务:
- 按 rubric 的 normalization/comparison_keys 对证据做口径/时间窗/样本/单位等对齐比较
- 按 precedence 进行来源取舍（官方/学术 > 标准/监管 > 厂商 > 媒体）
- 对每组冲突 claims 逐条裁决：upheld|revised|retracted
- revised 产出 new_text；所有结果给出 new_confidence（0~1，两位小数）、evidence_ids、rationale_md（≤150字）

输出 JSON:
{
"updated_claims": [
{ "claim_id":"...", "action":"upheld|revised|retracted", "new_text":"...", "new_confidence":0.00-1.00, "supersedes_id":"...", "evidence_ids":["..."], "rationale_md":"..." }
],
"resolution_summary": { "conflict_groups_total": N, "groups_resolved": N, "remaining_conflicts": [["C12","C19"]] }
}"""
        
        # Call LLM
        result = self.llm.generate_json(
            system_prompt=system_prompt,
            user_prompt=prompt,
            temperature=0.3
        )
        
        # Parse and validate
        return self._validate_resolution(result)
    
    def _apply_updates(self,
                       claims_active: List[Dict],
                       updated_claims: List[Dict]) -> List[Dict]:
        """Apply claim updates to active claims list."""
        
        # Create a copy of claims
        claims_map = {c["id"]: c.copy() for c in claims_active}
        
        # Apply updates
        for update in updated_claims:
            claim_id = update["claim_id"]
            action = update["action"]
            
            if claim_id in claims_map:
                if action == "upheld":
                    claims_map[claim_id]["confidence"] = update["new_confidence"]
                elif action == "revised":
                    claims_map[claim_id]["text"] = update["new_text"]
                    claims_map[claim_id]["confidence"] = update["new_confidence"]
                elif action == "retracted":
                    claims_map[claim_id]["confidence"] = 0.0
                    claims_map[claim_id]["retracted"] = True
                
                # Update evidence references
                if "evidence_ids" in update:
                    existing_ids = claims_map[claim_id].get("support_ids", [])
                    claims_map[claim_id]["support_ids"] = list(set(existing_ids + update["evidence_ids"]))
        
        # Return updated claims list (excluding retracted with confidence 0)
        return [c for c in claims_map.values() if c.get("confidence", 0) > 0]
    
    def _post_evaluate(self,
                       step: Dict[str, str],
                       updated_claims: List[Dict],
                       new_evidences: List[EvidenceItem]) -> Any:
        """Re-evaluate after conflict resolution."""
        
        # Prepare evidence metadata
        evidence_meta = []
        for ev in new_evidences:
            evidence_meta.append({
                "id": ev.id,
                "url": ev.source.url,
                "domain": ev.source.domain,
                "type": ev.source.type,
                "time": ev.time
            })
        
        # Call evaluator
        return self.evaluator.evaluate(
            step=step,
            claims=updated_claims,
            evidence_meta=evidence_meta
        )
    
    # Helper methods for prompts and validation
    
    def _build_search_plan_prompt(self, step, claims, conflicts, eval_data, kb_catalog) -> str:
        """Build prompt for search plan generation."""
        
        # Format conflicts
        conflict_groups = []
        for conf in conflicts:
            conflict_groups.append(conf.claims)
        
        prompt = f"""Step: {json.dumps(step, ensure_ascii=False)}

Active claims: {json.dumps(claims[:10], ensure_ascii=False)}

Conflicts (claims IDs groups): {json.dumps(conflict_groups, ensure_ascii=False)}

Eval JSON: {json.dumps(eval_data, ensure_ascii=False)}

KB Catalog (topics / examples): {json.dumps(kb_catalog, ensure_ascii=False)}

只返回一个 JSON 对象。"""
        
        return prompt
    
    def _build_resolution_prompt(self, step, claims, conflicts, evidences, rubric) -> str:
        """Build prompt for conflict resolution."""
        
        # Format claims
        claims_dict = {c["id"]: c for c in claims}
        
        # Format conflicts
        conflict_groups = [conf.claims for conf in conflicts]
        
        # Format evidences
        evidence_list = []
        for ev in evidences:
            evidence_list.append({
                "evidence_id": ev.id,
                "source": ev.source.url,
                "url": ev.source.url,
                "date": ev.time,
                "snippet": ev.text[:200] + "..." if len(ev.text) > 200 else ev.text,
                "provenance": "rag" if "local" in ev.source.domain else "web",
                "confidence": 0.8  # Default confidence
            })
        
        prompt = f"""Step: {json.dumps(step, ensure_ascii=False)}

Active claims: {json.dumps(claims, ensure_ascii=False)}

Conflicts: {json.dumps(conflict_groups, ensure_ascii=False)}

Evidence: {json.dumps(evidence_list, ensure_ascii=False)}

Rubric: {json.dumps(rubric, ensure_ascii=False)}

只返回一个 JSON 对象。"""
        
        return prompt
    
    def _validate_search_plan(self, result: Dict) -> Dict:
        """Validate search plan structure."""
        
        validated = {
            "queries_rag": result.get("queries_rag", []),
            "queries_web": result.get("queries_web", []),
            "rubric": result.get("rubric", {
                "normalization": ["统一标准"],
                "precedence": ["官方 > 学术 > 媒体"],
                "comparison_keys": ["数据来源", "时间范围"]
            })
        }
        
        return validated
    
    def _validate_resolution(self, result: Dict) -> Dict:
        """Validate resolution structure."""
        
        # Parse updated claims
        updated_claims = []
        for claim_data in result.get("updated_claims", []):
            updated = {
                "claim_id": claim_data.get("claim_id", ""),
                "action": claim_data.get("action", "upheld"),
                "new_confidence": claim_data.get("new_confidence", 0.5)
            }
            
            if claim_data.get("new_text"):
                updated["new_text"] = claim_data["new_text"]
            if claim_data.get("supersedes_id"):
                updated["supersedes_id"] = claim_data["supersedes_id"]
            if claim_data.get("evidence_ids"):
                updated["evidence_ids"] = claim_data["evidence_ids"]
            if claim_data.get("rationale_md"):
                updated["rationale_md"] = claim_data["rationale_md"]
            
            updated_claims.append(updated)
        
        # Parse resolution summary
        summary_data = result.get("resolution_summary", {})
        resolution_summary = {
            "conflict_groups_total": summary_data.get("conflict_groups_total", 0),
            "groups_resolved": summary_data.get("groups_resolved", 0),
            "remaining_conflicts": summary_data.get("remaining_conflicts", [])
        }
        
        return {
            "updated_claims": updated_claims,
            "resolution_summary": resolution_summary
        }
    
    def _mock_rag_search(self, query: Dict) -> List[EvidenceItem]:
        """Mock RAG search using LLM."""
        
        prompt = f"""模拟内部知识库检索，查询: {query['query']}
请生成 {query.get('top_k', 3)} 条相关的内部文档片段。

输出JSON:
{{"results": [
  {{"id": "RAG_1", "text": "...", "source": "内部文档名", "time": "2024-12"}}
]}}"""
        
        result = self.llm.generate_json(
            system_prompt="你是内部知识库检索模拟器",
            user_prompt=prompt,
            temperature=0.7
        )
        
        evidences = []
        for i, res in enumerate(result.get("results", [])):
            evidences.append(EvidenceItem(
                id=f"RAG_{i+1}",
                source=Source(
                    url=f"internal://docs/{res.get('source', 'doc')}",
                    domain="internal.local",
                    type="internal"
                ),
                time=res.get("time", "2024-12"),
                text=res.get("text", "Mock internal content")
            ))
        
        return evidences
    
    def _mock_web_search(self, query: Dict) -> List[EvidenceItem]:
        """Mock web search using LLM."""
        
        params_str = ""
        if query.get("params"):
            params_str = f"\n搜索参数: {json.dumps(query['params'], ensure_ascii=False)}"
        
        prompt = f"""模拟网络搜索，查询: {query['query']}{params_str}
请生成 {query.get('num_results', 3)} 条相关的网络搜索结果。

输出JSON:
{{"results": [
  {{"id": "WEB_1", "text": "...", "url": "https://...", "domain": "example.com", "time": "2025-01"}}
]}}"""
        
        result = self.llm.generate_json(
            system_prompt="你是网络搜索模拟器",
            user_prompt=prompt,
            temperature=0.7
        )
        
        evidences = []
        for i, res in enumerate(result.get("results", [])):
            evidences.append(EvidenceItem(
                id=f"WEB_{i+1}",
                source=Source(
                    url=res.get("url", f"https://example.com/page{i+1}"),
                    domain=res.get("domain", "example.com"),
                    type="web"
                ),
                time=res.get("time", "2025-01"),
                text=res.get("text", "Mock web content")
            ))
        
        return evidences
    
    def _evidence_to_dict(self, evidence: EvidenceItem) -> Dict:
        """Convert evidence to response format."""
        
        return {
            "evidence_id": evidence.id,
            "source": evidence.source.domain,
            "url": evidence.source.url,
            "date": evidence.time,
            "snippet": evidence.text[:200] + "..." if len(evidence.text) > 200 else evidence.text,
            "provenance": "rag" if "internal" in evidence.source.url else "web",
            "confidence": 0.8
        }
    
    def _evaluate_to_dict(self, evaluate_snapshot) -> Dict:
        """Convert evaluate snapshot to dict."""
        
        return {
            "passed": evaluate_snapshot.passed,
            "metrics": {
                "sufficiency": evaluate_snapshot.metrics.sufficiency,
                "reliability": evaluate_snapshot.metrics.reliability,
                "consistency": evaluate_snapshot.metrics.consistency,
                "recency": evaluate_snapshot.metrics.recency,
                "diversity": evaluate_snapshot.metrics.diversity
            },
            "issues": [
                {
                    "type": issue.type,
                    "severity": issue.severity,
                    "blocking": issue.blocking,
                    "desc": issue.desc
                }
                for issue in evaluate_snapshot.issues
            ]
        }
    
    def _check_partial_resolved(self, post_evaluate) -> bool:
        """Check if conflicts are partially resolved."""
        
        # Check if there are still blocking conflicts
        for issue in post_evaluate.issues:
            if issue.type == "conflict" and issue.blocking:
                return True
        
        return False