"""Agent with memory content monitoring integration."""

from typing import Optional, List, Dict, Any
import traceback
from datetime import datetime

from core.memory import MemoryFacade
from core.logger import logger
from core.memory_content_monitor import MemoryContentMonitor
from core.models import (
    SessionConfig, PlanStep, NextAction, Claim, 
    ConflictInfo, EvidenceItem, Source
)
from core.ids import generate_id
from core.acts.planner import Planner
from core.acts.synthesize import Synthesize
from core.acts.output import GenerateOutput
from core.acts.evaluate import Evaluate
from core.acts.decide import MakeDecision
from core.acts.rag_query import RAGQueryGenerator
from core.acts.web_search_query import WebSearchQueryGenerator
from core.acts.resolve_conflict import ResolveConflict
from core.acts.query_executor import QueryExecutor

from llm.client import LLMClient


class DeepResearchAgentV2WithMemoryContentMonitor:
    """Agent with memory content monitoring."""
    
    def __init__(self, llm_client: Optional[LLMClient] = None):
        # Same initialization as original
        self.llm = llm_client or LLMClient()
        self.memory = MemoryFacade()
        
        # Initialize acts
        self.planner = Planner(self.llm)
        self.synthesize = Synthesize(self.llm)
        self.output_gen = GenerateOutput(self.llm)
        self.evaluate = Evaluate(self.llm)
        self.decide = MakeDecision(self.llm)
        self.rag_generator = RAGQueryGenerator(self.llm)
        self.web_generator = WebSearchQueryGenerator(self.llm)
        self.conflict_resolver = ResolveConflict(self.llm, self.evaluate)
        self.query_executor = QueryExecutor(self.llm)
    
    def run_turn(self,
                 session_id: str,
                 user_query: str,
                 config: Optional[SessionConfig] = None,
                 max_loops: int = 10,
                 verbose: bool = True,
                 include_context: bool = True,
                 enable_memory_monitor: bool = False) -> str:
        """Run turn with memory content monitoring."""
        
        turn_id = generate_id("turn")
        plan_id = generate_id("plan")
        
        # Initialize memory content monitor
        monitor = None
        if enable_memory_monitor:
            monitor = MemoryContentMonitor(enabled=True)
            monitor.set_session(session_id)
            
            # Send initial session config
            if config:
                monitor.update_session_config(config.__dict__)
        
        if verbose:
            logger.section(f"Starting Turn {turn_id}", "=", 70)
            logger.info("Agent", f"User Query: {user_query}")
        
        try:
            # Initialize turn
            self.memory.begin_turn(session_id, turn_id, user_query)
            
            # Update turn queries history
            if monitor:
                turn_queries = []
                turn_data = self.memory._turn_data.get(session_id, {})
                for tid, tdata in turn_data.items():
                    turn_queries.append({
                        'turn_id': tid,
                        'query': tdata.get('user_query', '')
                    })
                monitor.update_turn_queries(turn_queries)
            
            # Handle context
            if include_context:
                context = self.memory.get_previous_turns_context(session_id, turn_id)
                if context['previous_queries']:
                    context_str = self._build_context_string(context)
                    if context_str:
                        user_query = f"{context_str}\n\n当前问题: {user_query}"
                        if verbose:
                            logger.info("Agent", f"Including context from {len(context['previous_queries'])} previous turns")
            
            # Set config
            if config:
                self.memory.set_session_config(session_id, config)
            else:
                config = SessionConfig(
                    prefs={},
                    thresholds={
                        "sufficiency": 0.80,
                        "reliability": 0.75,
                        "consistency": 0.70,
                        "recency": 0.70,
                        "diversity": 0.60
                    },
                    budget_state={"remaining_calls": 30},
                    stance_enabled=False
                )
                self.memory.set_session_config(session_id, config)
            
            # Generate plan
            if verbose:
                logger.subsection("Planning Phase")
                logger.info("Planner", "Generating initial research plan...")
            
            steps = self.planner.generate_plan(user_query)
            self.memory.set_plan_list(session_id, turn_id, steps)
            self.memory.set_current_step(session_id, turn_id, steps[0].step_id)
            
            # Initialize plan tracking
            self.memory.begin_plan(session_id, turn_id, plan_id, [], [])
            
            # Update monitor with plan steps
            if monitor:
                monitor.update_plan_steps(steps)
                monitor.update_current_step(steps[0].step_id)
            
            if verbose:
                logger.success("Planner", f"Generated {len(steps)} steps")
                plan_items = [
                    {"text": f"{step.step_id}: {step.goal}", "status": "pending"}
                    for step in steps
                ]
                logger.tree(plan_items, "Research Plan")
            
            # Main loop
            loops = 0
            step_loop_count = {}
            while loops < max_loops:
                loops += 1
                
                step = self.memory.get_current_step(session_id, turn_id)
                if not step:
                    if verbose:
                        logger.success("Agent", "All steps completed, generating output...")
                    break
                
                if verbose:
                    logger.subsection(f"Loop {loops}")
                    logger.info("Agent", f"Current step: {step.step_id} - {step.goal}")
                
                # Update current step in monitor
                if monitor:
                    monitor.update_current_step(step.step_id)
                
                # Track loops per step
                if step.step_id not in step_loop_count:
                    step_loop_count[step.step_id] = 0
                step_loop_count[step.step_id] += 1
                
                # Safety check
                if step_loop_count[step.step_id] > 5:
                    if verbose:
                        logger.warning("Agent", f"Step {step.step_id} exceeded loop limit, forcing completion")
                    self.memory.set_step_status(session_id, turn_id, step.step_id, "FINISHED")
                    
                    # Update plan steps in monitor
                    if monitor:
                        steps = self.memory.get_plan_list(session_id, turn_id)
                        monitor.update_plan_steps(steps)
                    
                    next_step = self._get_next_unfinished_step(session_id, turn_id)
                    if next_step:
                        self.memory.set_current_step(session_id, turn_id, next_step.step_id)
                        continue
                    else:
                        break
                
                # Get current memory state
                claims_active = self.memory.get_claims(session_id, turn_id)
                evidences = self.memory.get_evidences(session_id, turn_id)
                
                # Update monitor with current memory
                if monitor:
                    monitor.update_active_claims(claims_active)
                    monitor.update_active_evidences(evidences)
                
                # Build evidence metadata
                evidence_meta = []
                for ev in evidences:
                    evidence_meta.append({
                        "id": ev["id"],
                        "url": ev["source"]["url"],
                        "domain": ev["source"]["domain"],
                        "type": ev["source"]["type"],
                        "time": ev["time"]
                    })
                
                if verbose:
                    logger.info("Evaluate", "Assessing current research state...")
                
                evaluate_result = self.evaluate.evaluate(
                    step={"goal": step.goal, "way": step.way},
                    claims=claims_active,
                    evidence_meta=evidence_meta,
                    thresholds=config.thresholds,
                    prefs=config.prefs,
                    budget_state=config.budget_state
                )
                
                # Store evaluation
                self.memory.set_evaluate(session_id, turn_id, plan_id, evaluate_result)
                
                # Update monitor with evaluation
                if monitor:
                    monitor.add_evaluation({
                        'passed': evaluate_result.passed,
                        'metrics': {
                            'sufficiency': evaluate_result.metrics.sufficiency,
                            'reliability': evaluate_result.metrics.reliability,
                            'consistency': evaluate_result.metrics.consistency,
                            'recency': evaluate_result.metrics.recency,
                            'diversity': evaluate_result.metrics.diversity
                        },
                        'issues': [{'blocking': i.blocking, 'severity': i.severity, 'desc': i.desc} 
                                  for i in evaluate_result.issues]
                    })
                
                if verbose:
                    status = "passed" if evaluate_result.passed else "failed"
                    log_level = logger.success if evaluate_result.passed else logger.warning
                    log_level("Evaluate", f"Evaluation {status}")
                    
                    metrics_dict = {
                        "Sufficiency": evaluate_result.metrics.sufficiency,
                        "Reliability": evaluate_result.metrics.reliability,
                        "Consistency": evaluate_result.metrics.consistency,
                        "Recency": evaluate_result.metrics.recency,
                        "Diversity": evaluate_result.metrics.diversity
                    }
                    logger.metrics_table(metrics_dict, "Research Quality Metrics")
                
                # Make decision
                if verbose:
                    logger.info("Decision", "Determining next action...")
                
                claims_summary = self._summarize_claims(claims_active)
                
                decision = self.decide.decide(
                    step=step,
                    claims_active_summary=claims_summary,
                    last_evaluate=evaluate_result,
                    kb_catalog_summary={
                        "topics": ["技术文档", "API规范", "系统设计"],
                        "doc_count": 150,
                        "examples": ["深度学习指南", "系统架构文档", "API参考"]
                    }
                )
                
                if verbose:
                    logger.info("Decision", f"Action: {decision['action']}")
                    logger.debug("Decision", f"Rationale: {decision['rationale']}")
                
                # Add action to monitor
                if monitor:
                    monitor.add_action({
                        'action': decision['action'],
                        'rationale': decision['rationale'],
                        'type': decision['action'],
                        'status': 'pending'
                    })
                
                # Execute decision
                if decision["action"] == "FINISH":
                    self.memory.set_step_status(session_id, turn_id, step.step_id, "FINISHED")
                    
                    # Update plan steps in monitor
                    if monitor:
                        steps = self.memory.get_plan_list(session_id, turn_id)
                        monitor.update_plan_steps(steps)
                    
                    next_step = self._get_next_unfinished_step(session_id, turn_id)
                    if next_step:
                        self.memory.set_current_step(session_id, turn_id, next_step.step_id)
                        continue
                    else:
                        break
                
                elif decision["action"] in ["RAG", "WEB_SEARCH"]:
                    # Execute search
                    if decision["action"] == "RAG":
                        query = self.rag_generator.generate_query(
                            step={"goal": step.goal, "way": step.way},
                            claims_active=claims_active,
                            last_evaluate=evaluate_result
                        )
                        new_evidences = self.query_executor.execute_rag_query(query)
                        source = "RAG"
                    else:
                        query = self.web_generator.generate_query(
                            step={"goal": step.goal, "way": step.way},
                            claims_active=claims_active,
                            last_evaluate=evaluate_result
                        )
                        new_evidences = self.query_executor.execute_web_query(query)
                        source = "WEB"
                    
                    # Process evidences
                    self._process_new_evidences_with_monitor(
                        session_id, turn_id, plan_id,
                        new_evidences, claims_active,
                        config.stance_enabled, verbose, monitor, source, query
                    )
            
            # Generate output
            if verbose:
                logger.subsection("Output Generation")
                logger.info("Output", "Generating final response...")
            
            claims_active = [
                Claim(**claim_dict) if isinstance(claim_dict, dict) else claim_dict
                for claim_dict in self.memory.get_claims(session_id, turn_id)
            ]
            evidence_url_map = self.memory.get_evidence_url_map(session_id, turn_id)
            
            turn_data = self.memory._turn_data.get(session_id, {}).get(turn_id, {})
            user_query_for_output = turn_data.get('user_query', user_query)
            
            output = self.output_gen.generate(user_query_for_output, claims_active, evidence_url_map)
            
            # Roll up to session archive
            self.memory.rollup_to_session_archive(session_id, turn_id)
            
            # Update session archive in monitor
            if monitor:
                archive = self.memory.get_session_archive(session_id)
                if archive:
                    monitor.update_session_archive(archive)
            
            if verbose:
                logger.success("Agent", "Turn completed successfully")
                logger.section("Turn Complete", "=", 70)
            
            return output
        
        except Exception as e:
            error_msg = f"Error in turn execution: {str(e)}\n{traceback.format_exc()}"
            if verbose:
                logger.error("Agent", error_msg)
            return f"An error occurred during research: {str(e)}"
    
    def _process_new_evidences_with_monitor(self, session_id, turn_id, plan_id, 
                                           new_evidences, claims_active, 
                                           stance_enabled, verbose, monitor, source, query):
        """Process new evidences with memory content monitoring."""
        
        if verbose:
            logger.info("Agent", f"Retrieved {len(new_evidences)} evidence items")
        
        # Add evidences
        evidence_ids = self.memory.add_evidences(session_id, turn_id, plan_id, new_evidences)
        
        # Record action
        from core.models import ActionLog
        action_log = ActionLog(
            action_id=generate_id("act"),
            type=source,
            query=query,
            out_evidence_ids=evidence_ids,
            cost=0.1,
            ts=datetime.now().isoformat(),
            status="ok"
        )
        self.memory.record_action(session_id, turn_id, action_log)
        
        # Update action status in monitor
        if monitor:
            monitor.add_action({
                'action': source,
                'type': source,
                'query': query,
                'status': 'completed',
                'evidence_count': len(evidence_ids)
            })
        
        # Synthesize claims
        if verbose:
            logger.info("Synthesize", "Converting evidence to claims...")
        
        working_set = self.memory.get_working_set_for_synthesize(session_id, turn_id)
        new_claims = self.synthesize.synthesize_claims(
            working_set["user_query"],
            working_set["evidences"],
            working_set["previous_claims"],
            working_set["stance_enabled"]
        )
        
        # Count before merge
        old_count = len(self.memory.get_claims(session_id, turn_id))
        
        self.memory.merge_claims(session_id, turn_id, plan_id, new_claims)
        
        # Get updated claims and evidences
        all_claims = self.memory.get_claims(session_id, turn_id)
        all_evidences = self.memory.get_evidences(session_id, turn_id)
        
        # Update monitor with new memory state
        if monitor:
            monitor.update_active_claims(all_claims)
            monitor.update_active_evidences(all_evidences)
            
            # Add synthesis info
            merged = old_count + len(new_claims) - len(all_claims)
            monitor.add_synthesis({
                'new_claims': len(new_claims),
                'merged_claims': merged,
                'total_claims': len(all_claims)
            })
        
        if verbose:
            logger.success("Synthesize", f"Generated/merged {len(new_claims)} claims")
    
    def _summarize_claims(self, claims: List[Dict]) -> str:
        """Summarize claims for decision making."""
        if not claims:
            return "暂无观点"
        
        sorted_claims = sorted(claims, key=lambda c: c.get('confidence', 0), reverse=True)
        
        summary_parts = [f"共{len(claims)}个观点:"]
        for claim in sorted_claims[:5]:
            summary_parts.append(f"- [{claim['id']}] {claim['text']} (置信度: {claim['confidence']})")
        
        if len(claims) > 5:
            summary_parts.append(f"...还有{len(claims)-5}个观点")
        
        return "\n".join(summary_parts)
    
    def _get_next_unfinished_step(self, session_id: str, turn_id: str) -> Optional[PlanStep]:
        """Get next unfinished step."""
        steps = self.memory.get_plan_list(session_id, turn_id)
        for step in steps:
            if step.status != "FINISHED":
                return step
        return None
    
    def _build_context_string(self, context: Dict[str, Any]) -> str:
        """Build context string from previous turns."""
        if not context['previous_queries']:
            return ""
        
        parts = ["基于之前的研究对话:"]
        
        if context.get('session_archive'):
            parts.append(f"\n会话摘要: {context['session_archive']}")
        
        for i, query_info in enumerate(context['previous_queries'], 1):
            parts.append(f"\n\n之前的问题{i}: {query_info['query']}")
            
            turn_findings = [f for f in context['key_findings'] 
                           if f['turn_id'] == query_info['turn_id']]
            
            if turn_findings:
                parts.append("关键发现:")
                for finding in turn_findings[:2]:
                    claim = finding['claim']
                    parts.append(f"- {claim['text']} (置信度: {claim['confidence']:.2f})")
        
        return "\n".join(parts)