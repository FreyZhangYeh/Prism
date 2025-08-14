import json
from typing import List, Optional, Dict, Any

from core.models import PlanStep, NextAction, EvaluateSnapshot
from llm.client import LLMClient


class Planner:
    """Generate and re-plan steps for deep research."""
    
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client
    
    def generate_plan(self,
                      user_query: str,
                      completed_steps: List[PlanStep] = None,
                      pending_steps: List[PlanStep] = None,
                      last_evaluate: Optional[EvaluateSnapshot] = None) -> List[PlanStep]:
        """Generate or re-generate plan steps."""
        
        # Build context for re-planning
        context_parts = []
        if completed_steps:
            completed_summary = "\n".join([
                f"- {step.step_id}: {step.goal} (已完成)"
                for step in completed_steps
            ])
            context_parts.append(f"已完成步骤：\n{completed_summary}")
        
        if pending_steps:
            pending_summary = "\n".join([
                f"- {step.step_id}: {step.goal} (未完成)"
                for step in pending_steps
            ])
            context_parts.append(f"未完成步骤：\n{pending_summary}")
        
        if last_evaluate:
            eval_summary = {
                "issues": [{"type": i.type, "note": i.note} for i in last_evaluate.issues],
                "next_actions": [
                    {
                        "action": a.action,
                        "query": a.query,
                        "aspects_need": a.aspects_need
                    }
                    for a in last_evaluate.next_actions
                ]
            }
            context_parts.append(f"最近评估结果：\n{json.dumps(eval_summary, ensure_ascii=False, indent=2)}")
        
        context = "\n\n".join(context_parts) if context_parts else ""
        
        # Build prompt
        prompt = self._build_prompt(user_query, context)
        
        # Call LLM
        result = self.llm.generate_json(
            system_prompt="你是研究规划助手。请根据用户问题生成可执行的研究步骤计划。",
            user_prompt=prompt,
            temperature=0.7
        )
        
        # Parse response
        try:
            steps_data = result.get("steps", [])
            
            steps = []
            for step_data in steps_data:
                # Parse action_seed
                action_seed = []
                for action_data in step_data.get("action_seed", []):
                    action = NextAction(
                        action=action_data["action"],
                        query=action_data["query"],
                        aspects_need=action_data.get("aspects_need", []),
                        source_pref=action_data.get("source_pref"),
                        time_window=action_data.get("time_window")
                    )
                    action_seed.append(action)
                
                step = PlanStep(
                    step_id=step_data["step_id"],
                    goal=step_data["goal"],
                    action_seed=action_seed,
                    done_criteria=step_data["done_criteria"],
                    priority=step_data["priority"],
                    status="NOT_START"
                )
                steps.append(step)
            
            return steps
        
        except Exception as e:
            print(f"Error parsing planner response: {e}")
            # Fallback plan
            return [
                PlanStep(
                    step_id="s1",
                    goal="Gather initial information",
                    action_seed=[
                        NextAction(
                            action="RAG",
                            query=user_query,
                            aspects_need=["general_info"]
                        )
                    ],
                    done_criteria="Have basic understanding",
                    priority=1
                )
            ]
    
    def _build_prompt(self, user_query: str, context: str) -> str:
        """Build prompt for planner."""
        base_prompt = f"""问题：{user_query}

{context}

要求：生成研究计划步骤，每个步骤包含明确的子目标和完成标准。

仅输出JSON：
{{"steps":[
  {{"step_id":"s1","goal":"…","action_seed":[{{"action":"RAG|WEB","query":"…","aspects_need":["…"]}}],"done_criteria":"…","priority":1}},
  {{"step_id":"s2","goal":"…","action_seed":[],"done_criteria":"…","priority":2}}
]}}

约束：
- 步骤目标可执行、彼此解耦
- 优先级从小到大
- done_criteria 使用事实性判据
- action_seed 可为空（由决策模块填充）"""
        
        return base_prompt