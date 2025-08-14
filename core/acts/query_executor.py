import json
from typing import List, Dict, Any
from datetime import datetime

from core.models import (
    EvidenceItem, Source, RAGQuery, WebSearchQuery
)
from core.ids import generate_evidence_id
from llm.client import LLMClient


class QueryExecutor:
    """Execute RAG and Web queries by simulating search results using LLM."""
    
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client
    
    def execute_rag_query(self, query: RAGQuery) -> List[EvidenceItem]:
        """Execute RAG query and return evidence items."""
        
        # Build prompt for LLM to generate mock RAG results
        prompt = f"""你要模拟RAG检索，生成{query.top_k}条"可信格式"的证据片段，内容与query相关。

query：{query.query}

仅输出JSON：
{{"evidences":[
  {{"id":"RAG_1","source":{{"url":"https://kb.local/doc/1","domain":"kb.local","type":"internal"}},"time":"2024-12","text":"…"}},
  {{"id":"RAG_2","source":{{"url":"https://kb.local/doc/2","domain":"kb.local","type":"internal"}},"time":"2024-11","text":"…"}}
]}}

约束：
- 生成与查询相关的内部文档内容
- 文本要具体、有信息量（100-200字）
- time使用近期月份
- domain固定为"kb.local"
- type固定为"internal"
"""
        
        system_prompt = "你是RAG信息检索模拟器。请生成逼真的内部知识库搜索结果。"
        
        result = self.llm.generate_json(
            system_prompt=system_prompt,
            user_prompt=prompt,
            temperature=0.8
        )
        
        # Parse results
        evidences = []
        for i, ev_data in enumerate(result.get("evidences", [])):
            try:
                source = Source(
                    url=ev_data["source"]["url"],
                    domain=ev_data["source"]["domain"],
                    type=ev_data["source"]["type"]
                )
                
                evidence = EvidenceItem(
                    id=ev_data.get("id", f"RAG_{i+1}"),
                    source=source,
                    time=ev_data.get("time", datetime.now().strftime("%Y-%m")),
                    text=ev_data.get("text", f"RAG result {i+1} for query: {query.query}")
                )
                evidences.append(evidence)
            except Exception as e:
                print(f"Error parsing RAG evidence {i}: {e}")
        
        return evidences
    
    def execute_web_query(self, query: WebSearchQuery) -> List[EvidenceItem]:
        """Execute web search query and return evidence items."""
        
        # Build params description
        params_desc = ""
        if query.params:
            if query.params.get("time_range"):
                params_desc += f"\n时间范围: {query.params['time_range']}"
            if query.params.get("site_filters"):
                params_desc += f"\n站点过滤: {', '.join(query.params['site_filters'])}"
            if query.params.get("sort_by_date"):
                params_desc += "\n按日期排序: 是"
        
        # Build prompt
        prompt = f"""你要模拟WEB检索，生成{query.num_results}条"可信格式"的网络搜索结果，内容与query相关。

query：{query.query}{params_desc}

仅输出JSON：
{{"evidences":[
  {{"id":"WEB_1","source":{{"url":"https://example.com/article1","domain":"example.com","type":"media"}},"time":"2025-01","text":"…"}},
  {{"id":"WEB_2","source":{{"url":"https://official.gov/report","domain":"official.gov","type":"official"}},"time":"2024-12","text":"…"}}
]}}

约束：
- 生成与查询相关的网络内容
- 文本要具体、有信息量（100-200字）
- 根据查询内容选择合适的domain和type（official/media/academic/forum等）
- time要符合时间范围要求
- 如有site_filters，domain要匹配
"""
        
        system_prompt = "你是WEB信息检索模拟器。请生成逼真的网络搜索结果，内容要具体、有信息量。"
        
        result = self.llm.generate_json(
            system_prompt=system_prompt,
            user_prompt=prompt,
            temperature=0.8
        )
        
        # Parse results
        evidences = []
        for i, ev_data in enumerate(result.get("evidences", [])):
            try:
                source = Source(
                    url=ev_data["source"]["url"],
                    domain=ev_data["source"]["domain"],
                    type=ev_data["source"]["type"]
                )
                
                evidence = EvidenceItem(
                    id=ev_data.get("id", f"WEB_{i+1}"),
                    source=source,
                    time=ev_data.get("time", datetime.now().strftime("%Y-%m")),
                    text=ev_data.get("text", f"Web result {i+1} for query: {query.query}")
                )
                evidences.append(evidence)
            except Exception as e:
                print(f"Error parsing web evidence {i}: {e}")
        
        return evidences