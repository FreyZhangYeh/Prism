import json
from typing import List, Dict, Any
from datetime import datetime

from core.models import NextAction, EvidenceItem, Source, ActionLog
from core.ids import generate_evidence_id, generate_action_id
from llm.client import LLMClient


class UseCapability:
    """Handle RAG and Web research capabilities (mocked)."""
    
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client
    
    def call_once(self, action: NextAction) -> List[EvidenceItem]:
        """Execute a single RAG or Web query."""
        
        # Build prompt for mock evidence generation
        prompt = self._build_mock_prompt(
            action.action,
            action.query,
            action.aspects_need,
            action.source_pref,
            action.time_window
        )
        
        # Call LLM to generate mock evidence
        system_prompt = f"你是{action.action}信息检索模拟器。请生成逼真的搜索结果，内容要具体、有信息量、符合实际。"
        
        result = self.llm.generate_json(
            system_prompt=system_prompt,
            user_prompt=prompt,
            temperature=0.8
        )
        
        # Parse response
        try:
            evidences_data = result.get("evidences", [])
            
            evidences = []
            for ev_data in evidences_data:
                source = Source(
                    url=ev_data["source"]["url"],
                    domain=ev_data["source"]["domain"],
                    type=ev_data["source"]["type"]
                )
                
                evidence = EvidenceItem(
                    id=ev_data["id"],
                    source=source,
                    time=ev_data["time"],
                    text=ev_data["text"]
                )
                evidences.append(evidence)
            
            return evidences
        
        except Exception as e:
            print(f"Error parsing capability response: {e}")
            # Fallback evidence
            return [
                EvidenceItem(
                    id=generate_evidence_id(action.action, 1),
                    source=Source(
                        url="https://fallback.site/doc/1",
                        domain="fallback.site",
                        type="general"
                    ),
                    time=datetime.now().strftime("%Y-%m"),
                    text=f"Fallback evidence for query: {action.query}"
                )
            ]
    
    def create_action_log(self,
                          action: NextAction,
                          evidence_ids: List[str],
                          cost: float = 0.1,
                          status: str = "ok") -> ActionLog:
        """Create action log for recording."""
        return ActionLog(
            action_id=generate_action_id(),
            type=action.action,
            query=action.query,
            out_evidence_ids=evidence_ids,
            cost=cost,
            ts=datetime.now().isoformat(),
            status=status
        )
    
    def _build_mock_prompt(self,
                           source_type: str,
                           query: str,
                           aspects_need: List[str] = None,
                           source_pref: str = None,
                           time_window: str = None) -> str:
        """Build prompt for mock evidence generation."""
        
        k = 3  # Number of evidence items to generate
        
        prompt = f"""系统：你要模拟{source_type}检索，生成{k}条"可信格式"的证据片段，内容与query相关，但不需真实抓取。

用户：query：{query}"""

        if aspects_need:
            prompt += f"\n需要覆盖的方面：{', '.join(aspects_need)}"
        
        if source_pref:
            prompt += f"\n来源偏好：{source_pref}"
        
        if time_window:
            prompt += f"\n时间窗口：{time_window}"

        prompt += f"""

仅输出JSON：
{{"evidences":[
  {{"id":"{source_type}_1","source":{{"url":"https://kb.local/doc/1","domain":"kb.local","type":"official"}},"time":"2025-06","text":"…"}},
  {{"id":"{source_type}_2","source":{{"url":"https://news.site/item/2","domain":"news.site","type":"media"}},"time":"2025-06","text":"…"}}
]}}

约束：
- 文本简短但信息丰富
- time尽量在最近12个月
- domain 与 type 要合理
- 内容要与query和aspects相关"""
        
        return prompt