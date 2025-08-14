import json
from typing import List, Dict, Any

from core.models import Claim
from llm.client import LLMClient


class GenerateOutput:
    """Generate final output from claims and evidence."""
    
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client
    
    def generate(self,
                 user_query: str,
                 claims: List[Claim],
                 evidence_url_map: Dict[str, str]) -> str:
        """Generate human-readable output with citations."""
        
        # Prepare data for LLM
        claims_data = []
        for claim in claims:
            claim_dict = {
                "id": claim.id,
                "text": claim.text,
                "support_ids": claim.support_ids,
                "confidence": claim.confidence,
                "aspects": claim.aspects
            }
            if claim.stance:
                claim_dict["stance"] = claim.stance
            claims_data.append(claim_dict)
        
        # Build prompt
        prompt = self._build_prompt(user_query, claims_data, evidence_url_map)
        
        # Call LLM
        messages = [
            {"role": "system", "content": "把'观点+引证'组织成可读答案；标注引用来源。"},
            {"role": "user", "content": prompt}
        ]
        
        response = self.llm.chat(messages, temperature=0.5)
        
        return response
    
    def _build_prompt(self,
                      user_query: str,
                      claims: List[Dict[str, Any]],
                      evidence_map: Dict[str, str]) -> str:
        """Build prompt for output generation."""
        
        claims_json = json.dumps(claims, ensure_ascii=False, indent=2)
        evidence_map_json = json.dumps(evidence_map, ensure_ascii=False, indent=2)
        
        prompt = f"""用户问题：
{user_query}

观点(JSON)：
{claims_json}

引证映射(JSON)：
{evidence_map_json}

要求：
- 任务：针对用户问题，根据观点内容和证据，总结一份专业严谨的回答
- 输出结构：按照总分总的结构，先给出一份摘要，然后分不同section阐述，最后给出一份总结
- 按主题或重要性组织多个section
- 重要内容后标注来源URL
- 若观点评分低(confidence<0.7)或存在冲突，请显式写明不确定性
- 使用Markdown格式，引用使用[序号]格式
- 最后列出所有引用的完整引用（包括rag和web url）列表"""
        
        return prompt