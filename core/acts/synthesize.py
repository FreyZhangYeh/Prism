import json
from typing import List, Dict, Any

from core.models import Claim, EvidenceItem
from core.ids import generate_claim_id
from llm.client import LLMClient


class Synthesize:
    """Convert evidence to claims."""
    
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client
    
    def synthesize_claims(self,
                          user_query: str,
                          evidences: List[Dict],
                          previous_claims: List[Dict] = None,
                          stance_enabled: bool = False) -> List[Claim]:
        """Synthesize claims from evidence."""
        
        if previous_claims is None:
            previous_claims = []
        
        # Build prompt
        prompt = self._build_prompt(
            user_query,
            evidences,
            previous_claims,
            stance_enabled
        )
        
        # Call LLM
        result = self.llm.generate_json(
            system_prompt="你是研究助理。请基于证据总结客观'观点'，严禁无依据臆测。",
            user_prompt=prompt,
            temperature=0.5
        )
        
        # Parse response
        try:
            claims_data = result.get("claims", [])
            
            claims = []
            for claim_data in claims_data:
                claim = Claim(
                    id=claim_data["id"],
                    text=claim_data["text"],
                    support_ids=claim_data["support_ids"],
                    aspects=claim_data.get("aspects", []),
                    confidence=claim_data.get("confidence", 0.5),
                    stance=claim_data.get("stance") if stance_enabled else None,
                    salience=claim_data.get("salience")
                )
                claims.append(claim)
            
            return claims
        
        except Exception as e:
            print(f"Error parsing synthesize response: {e}")
            # Fallback claim
            return [
                Claim(
                    id=generate_claim_id(1),
                    text="Based on available evidence, initial understanding formed",
                    support_ids=[ev["id"] for ev in evidences[:1]] if evidences else [],
                    aspects=["general"],
                    confidence=0.5
                )
            ]
    
    def _build_prompt(self,
                      user_query: str,
                      evidences: List[Dict],
                      previous_claims: List[Dict],
                      stance_enabled: bool) -> str:
        """Build prompt for synthesis."""
        
        evidences_json = json.dumps(evidences, ensure_ascii=False, indent=2)
        claims_json = json.dumps(previous_claims, ensure_ascii=False, indent=2)
        
        # Pre-build stance-related strings to avoid complex f-string nesting
        stance_json_example = ',"stance":"pro|neutral|con"' if stance_enabled else ''
        stance_requirement = '- stance: pro(支持)/neutral(中立)/con(反对)，仅在观点类问题时使用' if stance_enabled else ''

        prompt = f"""问题：{user_query}

证据(JSON)：
{evidences_json}

已有观点(JSON，可为空)：
{claims_json}

要求：
- 仅输出JSON：{{"claims":[{{ "id":"c1","text":"…","support_ids":["e1"],"aspects":["…"],"confidence":0.7{stance_json_example},"salience":0.6(可省)}}]}}
- text 必须被 support_ids 覆盖；不得额外发挥
- confidence: 0-1之间，表示观点的可信度
- salience: 0-1之间，表示观点的重要性（可选）
- aspects: 观点涉及的方面/维度
{stance_requirement}"""
        
        return prompt