"""Memory content monitor - sends actual memory contents to monitoring server."""

import requests
from typing import Dict, List, Any, Optional
from datetime import datetime
import threading
import json


class MemoryContentMonitor:
    """Monitor that sends actual memory contents to monitoring server."""
    
    def __init__(self, server_url: str = "http://localhost:5678", enabled: bool = True):
        self.server_url = server_url
        self.enabled = enabled
        self.session_id = None
        
    def set_session(self, session_id: str):
        """Set the current session ID."""
        self.session_id = session_id
        
    def _send_memory(self, memory_type: str, content: Any):
        """Send memory content to server."""
        if not self.enabled or not self.session_id:
            return
            
        def _send():
            try:
                url = f"{self.server_url}/api/memory/{self.session_id}/{memory_type}"
                requests.post(url, json=content, timeout=1)
            except:
                pass
        
        thread = threading.Thread(target=_send)
        thread.daemon = True
        thread.start()
    
    def update_session_config(self, config: Dict):
        """Update session configuration."""
        self._send_memory('session_config', config)
    
    def update_session_archive(self, archive: str):
        """Update session archive."""
        self._send_memory('session_archive', archive)
    
    def update_turn_queries(self, queries: List[Dict]):
        """Update turn queries history."""
        self._send_memory('turn_queries', queries)
    
    def update_active_claims(self, claims: List[Dict]):
        """Update active claims with full content."""
        # Convert claim objects to dicts if needed
        claim_dicts = []
        for claim in claims:
            if hasattr(claim, '__dict__'):
                claim_dict = {
                    'id': getattr(claim, 'id', None),
                    'text': getattr(claim, 'text', str(claim)),
                    'confidence': getattr(claim, 'confidence', 0),
                    'source_ids': getattr(claim, 'source_ids', [])
                }
            else:
                claim_dict = claim
            claim_dicts.append(claim_dict)
        
        self._send_memory('active_claims', claim_dicts)
    
    def update_active_evidences(self, evidences: List[Dict]):
        """Update active evidences with full content."""
        # Convert evidence objects to dicts if needed
        evidence_dicts = []
        for evidence in evidences:
            if isinstance(evidence, dict):
                evidence_dict = evidence
            else:
                evidence_dict = {
                    'id': getattr(evidence, 'id', None),
                    'text': getattr(evidence, 'text', getattr(evidence, 'excerpt', '')),
                    'source': getattr(evidence, 'source', {}),
                    'relevance': getattr(evidence, 'relevance', 0),
                    'time': getattr(evidence, 'time', None)
                }
            evidence_dicts.append(evidence_dict)
        
        self._send_memory('active_evidences', evidence_dicts)
    
    def update_plan_steps(self, steps: List[Dict]):
        """Update plan steps."""
        step_dicts = []
        for step in steps:
            if hasattr(step, '__dict__'):
                step_dict = {
                    'step_id': getattr(step, 'step_id', None),
                    'goal': getattr(step, 'goal', ''),
                    'way': getattr(step, 'way', ''),
                    'status': getattr(step, 'status', 'pending')
                }
            else:
                step_dict = step
            step_dicts.append(step_dict)
        
        self._send_memory('plan_steps', step_dicts)
    
    def update_current_step(self, step_id: str):
        """Update current step."""
        self._send_memory('current_step', step_id)
    
    def add_evaluation(self, evaluation: Dict):
        """Add evaluation result."""
        eval_dict = {
            'passed': evaluation.get('passed', False),
            'metrics': evaluation.get('metrics', {}),
            'issues': evaluation.get('issues', []),
            'timestamp': datetime.now().isoformat()
        }
        
        # Get existing evaluations and append
        try:
            response = requests.get(f"{self.server_url}/api/memory/{self.session_id}", timeout=1)
            if response.ok:
                data = response.json()
                evaluations = data.get('memories', {}).get('evaluations', [])
                evaluations.append(eval_dict)
                self._send_memory('evaluations', evaluations)
        except:
            self._send_memory('evaluations', [eval_dict])
    
    def add_action(self, action: Dict):
        """Add action to history."""
        action_dict = {
            'type': action.get('type', action.get('action', 'unknown')),
            'query': action.get('query', ''),
            'rationale': action.get('rationale', ''),
            'status': action.get('status', 'ok'),
            'ts': action.get('ts', datetime.now().isoformat())
        }
        
        # Get existing actions and append
        try:
            response = requests.get(f"{self.server_url}/api/memory/{self.session_id}", timeout=1)
            if response.ok:
                data = response.json()
                actions = data.get('memories', {}).get('actions', [])
                actions.append(action_dict)
                self._send_memory('actions', actions[-20:])  # Keep last 20
        except:
            self._send_memory('actions', [action_dict])
    
    def update_conflicts(self, conflicts: List[Dict]):
        """Update conflict information."""
        self._send_memory('conflicts', conflicts)
    
    def add_synthesis(self, synthesis_info: Dict):
        """Add synthesis event."""
        synthesis_dict = {
            'new_claims': synthesis_info.get('new_claims', 0),
            'merged_claims': synthesis_info.get('merged_claims', 0),
            'total_claims': synthesis_info.get('total_claims', 0),
            'timestamp': datetime.now().isoformat()
        }
        
        # Get existing synthesis history and append
        try:
            response = requests.get(f"{self.server_url}/api/memory/{self.session_id}", timeout=1)
            if response.ok:
                data = response.json()
                history = data.get('memories', {}).get('synthesis_history', [])
                history.append(synthesis_dict)
                self._send_memory('synthesis_history', history[-10:])  # Keep last 10
        except:
            self._send_memory('synthesis_history', [synthesis_dict])