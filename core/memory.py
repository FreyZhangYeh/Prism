from typing import List, Dict, Optional, Any
from collections import defaultdict
from datetime import datetime
import json

from core.models import (
    SessionConfig, EvidenceItem, Claim, EvaluateSnapshot,
    ActionLog, PlanStep, PlanSnapshot, PlanPatch
)
from core.ids import generate_fingerprint, generate_id


class MemoryFacade:
    """In-memory implementation of the memory facade for deep research demo."""
    
    def __init__(self):
        # Session level storage
        self._session_configs: Dict[str, SessionConfig] = {}
        self._session_archives: Dict[str, str] = {}
        
        # Turn level storage (nested by session_id -> turn_id)
        self._turn_data: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(lambda: defaultdict(dict))
        
        # Plan level storage (nested by session_id -> turn_id -> plan_id)
        self._plan_data: Dict[str, Dict[str, Dict[str, Dict[str, Any]]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(dict))
        )
        
        # Action level storage
        self._action_logs: Dict[str, Dict[str, List[ActionLog]]] = defaultdict(lambda: defaultdict(list))
        
        # Evidence deduplication index
        self._evidence_index: Dict[str, EvidenceItem] = {}

    def begin_turn(self, session_id: str, turn_id: str, user_query: str):
        """Initialize a new turn, inheriting session-level context."""
        # Initialize turn data
        self._turn_data[session_id][turn_id] = {
            'user_query': user_query,
            'plan_list': [],
            'current_step_id': None,
            'evidences_active': [],
            'claims_active': [],
            'last_evaluate': None
        }
        
        # Inherit high-value evidence and claims from previous turns if available
        previous_turns = [tid for tid in self._turn_data[session_id].keys() if tid != turn_id]
        if previous_turns:
            # Collect high-confidence claims from previous turns
            inherited_claims = []
            inherited_evidences = []
            
            for prev_turn_id in previous_turns[-2:]:  # Last 2 turns
                prev_turn_data = self._turn_data[session_id].get(prev_turn_id, {})
                
                # Inherit high-confidence claims
                for claim in prev_turn_data.get('claims_active', []):
                    if claim.confidence >= 0.8 and (claim.salience or 0.5) >= 0.6:
                        inherited_claims.append(claim)
                
                # Inherit key evidences
                for evidence in prev_turn_data.get('evidences_active', []):
                    # Check if this evidence supports any high-confidence claim
                    for claim in inherited_claims:
                        if evidence.id in claim.support_ids:
                            inherited_evidences.append(evidence)
                            break
            
            # Add inherited items to current turn
            self._turn_data[session_id][turn_id]['evidences_active'].extend(inherited_evidences)
            self._turn_data[session_id][turn_id]['claims_active'].extend(inherited_claims)

    def begin_plan(self, session_id: str, turn_id: str, plan_id: str,
                   base_evidence_ids: List[str], base_claim_ids: List[str]):
        """Initialize a new plan with baseline snapshot."""
        self._plan_data[session_id][turn_id][plan_id] = {
            'plan_start_snapshot': PlanSnapshot(
                evidence_base_ids=base_evidence_ids,
                claim_base_ids=base_claim_ids
            ),
            'plan_patches': [],
            'plan_gate': {}
        }

    def next_action_id(self, session_id: str, turn_id: str, plan_id: str) -> str:
        """Generate next action ID."""
        return generate_id('act')

    def record_action(self, session_id: str, turn_id: str, log: ActionLog):
        """Record an action log."""
        self._action_logs[session_id][turn_id].append(log)

    def add_evidences(self, session_id: str, turn_id: str, plan_id: str,
                      evidences: List[EvidenceItem]) -> List[str]:
        """Add evidences with deduplication."""
        turn_data = self._turn_data[session_id][turn_id]
        plan_data = self._plan_data[session_id][turn_id].get(plan_id, {})
        
        new_ids = []
        for evidence in evidences:
            # Generate fingerprint for deduplication
            fingerprint = generate_fingerprint(evidence.text, evidence.source.url)
            
            if fingerprint not in self._evidence_index:
                self._evidence_index[fingerprint] = evidence
                turn_data['evidences_active'].append(evidence)
                new_ids.append(evidence.id)
        
        # Record in plan patch
        if new_ids and plan_id in self._plan_data[session_id][turn_id]:
            step_id = turn_data.get('current_step_id')
            if step_id:
                patch = PlanPatch(add_evidence_ids=new_ids)
                plan_data['plan_patches'].append({
                    'step_id': step_id,
                    'patch': patch
                })
        
        return new_ids

    def merge_claims(self, session_id: str, turn_id: str, plan_id: str,
                     claims: List[Claim]):
        """Merge claims with existing ones."""
        turn_data = self._turn_data[session_id][turn_id]
        existing_claims = {c.id: c for c in turn_data['claims_active']}
        
        merged_claims = []
        for new_claim in claims:
            if new_claim.id in existing_claims:
                # Merge logic: combine support_ids, take max confidence
                existing = existing_claims[new_claim.id]
                existing.support_ids = list(set(existing.support_ids + new_claim.support_ids))
                existing.confidence = max(existing.confidence, new_claim.confidence)
                if new_claim.stance:
                    existing.stance = new_claim.stance
                if new_claim.salience:
                    existing.salience = max(existing.salience or 0, new_claim.salience)
                if new_claim.aspects:
                    existing.aspects = list(set(existing.aspects + new_claim.aspects))
                merged_claims.append(new_claim)
            else:
                turn_data['claims_active'].append(new_claim)
                merged_claims.append(new_claim)
        
        # Record in plan patch
        if merged_claims and plan_id in self._plan_data[session_id][turn_id]:
            step_id = turn_data.get('current_step_id')
            if step_id:
                plan_data = self._plan_data[session_id][turn_id][plan_id]
                patch = PlanPatch(merge_claims=merged_claims)
                plan_data['plan_patches'].append({
                    'step_id': step_id,
                    'patch': patch
                })

    def set_evaluate(self, session_id: str, turn_id: str, plan_id: str,
                     snapshot: EvaluateSnapshot):
        """Set evaluation snapshot for current step."""
        turn_data = self._turn_data[session_id][turn_id]
        turn_data['last_evaluate'] = snapshot
        
        # Record in plan patch and gate
        if plan_id in self._plan_data[session_id][turn_id]:
            step_id = turn_data.get('current_step_id')
            if step_id:
                plan_data = self._plan_data[session_id][turn_id][plan_id]
                patch = PlanPatch(set_evaluate=snapshot)
                plan_data['plan_patches'].append({
                    'step_id': step_id,
                    'patch': patch
                })
                plan_data['plan_gate'][step_id] = snapshot.passed

    def set_session_config(self, session_id: str, cfg: SessionConfig):
        """Set session configuration."""
        self._session_configs[session_id] = cfg

    def get_session_config(self, session_id: str) -> Optional[SessionConfig]:
        """Get session configuration."""
        return self._session_configs.get(session_id)

    def get_last_evaluate(self, session_id: str, turn_id: str) -> Optional[EvaluateSnapshot]:
        """Get last evaluation snapshot."""
        turn_data = self._turn_data.get(session_id, {}).get(turn_id, {})
        return turn_data.get('last_evaluate')

    def get_claims(self, session_id: str, turn_id: str) -> List[Dict]:
        """Get active claims as dictionaries."""
        turn_data = self._turn_data.get(session_id, {}).get(turn_id, {})
        claims = turn_data.get('claims_active', [])
        return [self._claim_to_dict(c) for c in claims]

    def get_evidences(self, session_id: str, turn_id: str) -> List[Dict]:
        """Get active evidences as dictionaries."""
        turn_data = self._turn_data.get(session_id, {}).get(turn_id, {})
        evidences = turn_data.get('evidences_active', [])
        return [self._evidence_to_dict(e) for e in evidences]

    def apply_claim_updates(self, session_id: str, turn_id: str, updated_claims: List[Dict]):
        """Apply claim updates from conflict resolution to memory."""
        turn_data = self._turn_data.get(session_id, {}).get(turn_id)
        if not turn_data:
            return

        active_claims = turn_data.get('claims_active', [])
        claims_map = {c.id: c for c in active_claims}

        for update in updated_claims:
            claim_id = update.get("claim_id")
            action = update.get("action")
            
            if not claim_id or claim_id not in claims_map:
                continue
            
            claim_obj = claims_map[claim_id]
            
            if action == "upheld":
                claim_obj.confidence = update["new_confidence"]
            elif action == "revised":
                claim_obj.text = update["new_text"]
                claim_obj.confidence = update["new_confidence"]
                if "evidence_ids" in update:
                    claim_obj.support_ids = list(set(claim_obj.support_ids + update["evidence_ids"]))
            elif action == "retracted":
                claim_obj.confidence = 0.0  # Mark for removal

        # Filter out retracted claims and update memory
        turn_data['claims_active'] = [c for c in active_claims if c.confidence > 0]

    def get_working_set_for_synthesize(self, session_id: str, turn_id: str) -> Dict:
        """Get working set for synthesize operation."""
        turn_data = self._turn_data.get(session_id, {}).get(turn_id, {})
        config = self.get_session_config(session_id)
        
        return {
            'user_query': turn_data.get('user_query', ''),
            'evidences': self.get_evidences(session_id, turn_id),
            'previous_claims': self.get_claims(session_id, turn_id),
            'stance_enabled': config.stance_enabled if config else False
        }

    def get_working_set_for_evaluate(self, session_id: str, turn_id: str) -> Dict:
        """Get working set for evaluate operation."""
        turn_data = self._turn_data.get(session_id, {}).get(turn_id, {})
        config = self.get_session_config(session_id) or SessionConfig(
            prefs={}, thresholds={}, budget_state={}
        )
        
        evidences = turn_data.get('evidences_active', [])
        evidence_meta = [
            {
                'id': e.id,
                'url': e.source.url,
                'domain': e.source.domain,
                'time': e.time
            }
            for e in evidences
        ]
        
        return {
            'user_query': turn_data.get('user_query', ''),
            'claims': self.get_claims(session_id, turn_id),
            'evidence_meta': evidence_meta,
            'thresholds': config.thresholds,
            'prefs': config.prefs,
            'budget_state': config.budget_state
        }

    def rollup_to_session_archive(self, session_id: str, turn_id: str):
        """Roll up high-quality claims to session archive."""
        turn_data = self._turn_data.get(session_id, {}).get(turn_id, {})
        claims = turn_data.get('claims_active', [])
        
        # Filter high confidence and salience claims
        high_quality_claims = [
            c for c in claims
            if c.confidence >= 0.7 and (c.salience or 0.5) >= 0.5
        ]
        
        if high_quality_claims:
            summary_texts = [c.text for c in high_quality_claims[:5]]
            archive = f"Key findings: {'; '.join(summary_texts)}"
            self._session_archives[session_id] = archive

    def set_plan_list(self, session_id: str, turn_id: str, steps: List[PlanStep]):
        """Set plan list for the turn."""
        self._turn_data[session_id][turn_id]['plan_list'] = steps
        if steps:
            self._turn_data[session_id][turn_id]['current_step_id'] = steps[0].step_id

    def get_plan_list(self, session_id: str, turn_id: str) -> List[PlanStep]:
        """Get plan list for the turn."""
        turn_data = self._turn_data.get(session_id, {}).get(turn_id, {})
        return turn_data.get('plan_list', [])

    def get_current_step(self, session_id: str, turn_id: str) -> Optional[PlanStep]:
        """Get current step."""
        turn_data = self._turn_data.get(session_id, {}).get(turn_id, {})
        current_step_id = turn_data.get('current_step_id')
        if current_step_id:
            plan_list = turn_data.get('plan_list', [])
            for step in plan_list:
                if step.step_id == current_step_id:
                    return step
        return None

    def set_current_step(self, session_id: str, turn_id: str, step_id: str):
        """Set current step ID."""
        self._turn_data[session_id][turn_id]['current_step_id'] = step_id

    def set_step_status(self, session_id: str, turn_id: str, step_id: str, status: str):
        """Set step status."""
        turn_data = self._turn_data.get(session_id, {}).get(turn_id, {})
        plan_list = turn_data.get('plan_list', [])
        for step in plan_list:
            if step.step_id == step_id:
                step.status = status
                break

    def get_evidence_url_map(self, session_id: str, turn_id: str) -> Dict[str, str]:
        """Get evidence ID to URL mapping."""
        turn_data = self._turn_data.get(session_id, {}).get(turn_id, {})
        evidences = turn_data.get('evidences_active', [])
        return {e.id: e.source.url for e in evidences}

    def _claim_to_dict(self, claim: Claim) -> Dict:
        """Convert claim to dictionary."""
        d = {
            'id': claim.id,
            'text': claim.text,
            'support_ids': claim.support_ids,
            'aspects': claim.aspects,
            'confidence': claim.confidence
        }
        if claim.stance:
            d['stance'] = claim.stance
        if claim.salience is not None:
            d['salience'] = claim.salience
        return d

    def _evidence_to_dict(self, evidence: EvidenceItem) -> Dict:
        """Convert evidence to dictionary."""
        return {
            'id': evidence.id,
            'source': {
                'url': evidence.source.url,
                'domain': evidence.source.domain,
                'type': evidence.source.type
            },
            'time': evidence.time,
            'text': evidence.text
        }
    
    def get_session_archive(self, session_id: str) -> Optional[str]:
        """Get session archive summary."""
        return self._session_archives.get(session_id)
    
    def get_all_session_claims(self, session_id: str, min_confidence: float = 0.7) -> List[Claim]:
        """Get all high-confidence claims from entire session."""
        all_claims = []
        for turn_id, turn_data in self._turn_data.get(session_id, {}).items():
            for claim in turn_data.get('claims_active', []):
                # Handle both Claim objects and dictionaries
                if isinstance(claim, dict):
                    if claim.get('confidence', 0) >= min_confidence:
                        all_claims.append(claim)
                else:
                    if claim.confidence >= min_confidence:
                        all_claims.append(claim)
        return all_claims
    
    def get_all_session_evidences(self, session_id: str) -> List[EvidenceItem]:
        """Get all evidences from entire session."""
        all_evidences = []
        seen_ids = set()
        
        for turn_id, turn_data in self._turn_data.get(session_id, {}).items():
            for evidence in turn_data.get('evidences_active', []):
                if evidence.id not in seen_ids:
                    all_evidences.append(evidence)
                    seen_ids.add(evidence.id)
        
        return all_evidences
    
    def get_previous_turns_context(self, session_id: str, current_turn_id: str, limit: int = 3) -> Dict[str, Any]:
        """Get context from previous turns for multi-turn conversation."""
        context = {
            'previous_queries': [],
            'key_findings': [],
            'session_archive': self.get_session_archive(session_id)
        }
        
        turn_ids = sorted([tid for tid in self._turn_data.get(session_id, {}).keys() 
                          if tid != current_turn_id])[-limit:]
        
        for turn_id in turn_ids:
            turn_data = self._turn_data[session_id][turn_id]
            context['previous_queries'].append({
                'turn_id': turn_id,
                'query': turn_data.get('user_query', '')
            })
            
            # Get top claims from this turn
            claims = sorted(turn_data.get('claims_active', []), 
                          key=lambda c: c.confidence * (c.salience or 0.5), 
                          reverse=True)[:3]
            
            context['key_findings'].extend([{
                'turn_id': turn_id,
                'claim': self._claim_to_dict(claim)
            } for claim in claims])
        
        return context