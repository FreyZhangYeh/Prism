"""Memory content monitoring server - displays actual memory contents."""

from flask import Flask, jsonify, render_template_string, request
from flask_cors import CORS
import threading
from datetime import datetime
from collections import defaultdict
import json

app = Flask(__name__)
CORS(app)

# Memory content storage
class MemoryContentStore:
    def __init__(self):
        self.sessions = defaultdict(lambda: {
            'created': datetime.now().isoformat(),
            'memories': {
                'session_config': {},
                'session_archive': '',
                'turn_queries': [],
                'active_claims': [],
                'active_evidences': [],
                'plan_steps': [],
                'current_step': None,
                'evaluations': [],
                'actions': [],
                'conflicts': [],
                'synthesis_history': []
            },
            'last_update': None
        })
        self.lock = threading.Lock()
    
    def update_memory(self, session_id, memory_type, content):
        """Update specific memory content."""
        with self.lock:
            session = self.sessions[session_id]
            session['memories'][memory_type] = content
            session['last_update'] = datetime.now().isoformat()
    
    def get_session_memories(self, session_id):
        """Get all memories for a session."""
        with self.lock:
            if session_id in self.sessions:
                return self.sessions[session_id]
            return None

# Initialize store
memory_store = MemoryContentStore()

# API Routes
@app.route('/api/memory/<session_id>/<memory_type>', methods=['POST'])
def update_memory_type(session_id, memory_type):
    """Update specific memory type."""
    data = request.json
    memory_store.update_memory(session_id, memory_type, data)
    return jsonify({'status': 'ok'})

@app.route('/api/memory/<session_id>')
def get_memories(session_id):
    """Get all memories for a session."""
    data = memory_store.get_session_memories(session_id)
    if data:
        return jsonify(data)
    return jsonify({'error': 'Session not found'}), 404

@app.route('/api/sessions')
def get_sessions():
    """Get all active sessions."""
    with memory_store.lock:
        sessions = []
        for sid, sdata in memory_store.sessions.items():
            sessions.append({
                'session_id': sid,
                'created': sdata['created'],
                'last_update': sdata['last_update']
            })
        return jsonify(sessions)

# Web UI
@app.route('/')
def index():
    """Main dashboard."""
    return render_template_string(DASHBOARD_HTML)

@app.route('/memory/<session_id>')
def memory_view(session_id):
    """Memory content view."""
    return render_template_string(MEMORY_CONTENT_HTML, session_id=session_id)

# HTML Templates
DASHBOARD_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>Deep Research Memory Content Monitor</title>
    <style>
        body {
            font-family: 'Monaco', 'Consolas', monospace;
            background: #0f0f0f;
            color: #e0e0e0;
            margin: 0;
            padding: 20px;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        h1 {
            color: #00ff88;
            text-align: center;
            text-shadow: 0 0 20px #00ff8850;
        }
        .session-list {
            display: grid;
            gap: 15px;
        }
        .session-card {
            background: #1a1a1a;
            border: 1px solid #00ff8830;
            border-radius: 10px;
            padding: 20px;
            cursor: pointer;
            transition: all 0.3s;
        }
        .session-card:hover {
            border-color: #00ff88;
            box-shadow: 0 0 20px #00ff8830;
            transform: translateX(5px);
        }
        .session-id {
            color: #00ff88;
            font-size: 18px;
            font-weight: bold;
        }
        .session-info {
            margin-top: 10px;
            color: #888;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🧠 Memory Content Monitor</h1>
        <div id="sessions" class="session-list"></div>
    </div>
    
    <script>
        async function loadSessions() {
            const response = await fetch('/api/sessions');
            const sessions = await response.json();
            
            const container = document.getElementById('sessions');
            container.innerHTML = sessions.map(session => `
                <div class="session-card" onclick="window.location.href='/memory/${session.session_id}'">
                    <div class="session-id">${session.session_id}</div>
                    <div class="session-info">
                        Created: ${new Date(session.created).toLocaleString()}<br>
                        Last Update: ${session.last_update ? new Date(session.last_update).toLocaleString() : 'Never'}
                    </div>
                </div>
            `).join('');
        }
        
        loadSessions();
        setInterval(loadSessions, 2000);
    </script>
</body>
</html>
'''

MEMORY_CONTENT_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>Memory Contents - {{ session_id }}</title>
    <style>
        body {
            font-family: 'Monaco', 'Consolas', monospace;
            background: #0f0f0f;
            color: #e0e0e0;
            margin: 0;
            padding: 20px;
        }
        .container {
            max-width: 1800px;
            margin: 0 auto;
        }
        h1 {
            color: #00ff88;
            text-align: center;
            text-shadow: 0 0 20px #00ff8850;
            margin-bottom: 30px;
        }
        .memory-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }
        .memory-panel {
            background: #1a1a1a;
            border: 1px solid #333;
            border-radius: 10px;
            overflow: hidden;
        }
        .memory-header {
            background: linear-gradient(135deg, #00ff88 0%, #00d4ff 100%);
            color: #000;
            padding: 15px;
            font-weight: bold;
            font-size: 16px;
        }
        .memory-content {
            padding: 20px;
            max-height: 400px;
            overflow-y: auto;
        }
        .memory-item {
            background: #0f0f0f;
            border: 1px solid #333;
            border-radius: 5px;
            padding: 10px;
            margin-bottom: 10px;
        }
        .memory-empty {
            color: #666;
            text-align: center;
            padding: 40px;
        }
        .claim-item {
            border-left: 3px solid #00ff88;
            padding-left: 15px;
        }
        .evidence-item {
            border-left: 3px solid #00d4ff;
            padding-left: 15px;
        }
        .plan-item {
            border-left: 3px solid #ff6b6b;
            padding-left: 15px;
        }
        .action-item {
            border-left: 3px solid #f59e0b;
            padding-left: 15px;
        }
        .confidence {
            color: #00ff88;
            font-weight: bold;
        }
        .source {
            color: #00d4ff;
            font-size: 12px;
        }
        .timestamp {
            color: #666;
            font-size: 11px;
        }
        .back-btn {
            position: fixed;
            top: 20px;
            left: 20px;
            background: #00ff88;
            color: #000;
            border: none;
            padding: 10px 20px;
            border-radius: 5px;
            cursor: pointer;
            text-decoration: none;
            font-weight: bold;
        }
        .status-pending { color: #f59e0b; }
        .status-in-progress { color: #00d4ff; }
        .status-completed { color: #00ff88; }
        .status-failed { color: #ff4444; }
        
        /* Scrollbar styling */
        .memory-content::-webkit-scrollbar {
            width: 8px;
        }
        .memory-content::-webkit-scrollbar-track {
            background: #0f0f0f;
        }
        .memory-content::-webkit-scrollbar-thumb {
            background: #333;
            border-radius: 4px;
        }
        .memory-content::-webkit-scrollbar-thumb:hover {
            background: #555;
        }
        
        /* Animation for new items */
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .memory-item {
            animation: fadeIn 0.3s ease-out;
        }
    </style>
</head>
<body>
    <a href="/" class="back-btn">← Back</a>
    <div class="container">
        <h1>🧠 Memory Contents: {{ session_id }}</h1>
        
        <div class="memory-grid">
            <!-- Active Claims -->
            <div class="memory-panel">
                <div class="memory-header">💡 Active Claims</div>
                <div class="memory-content" id="active-claims">
                    <div class="memory-empty">No claims yet...</div>
                </div>
            </div>
            
            <!-- Active Evidence -->
            <div class="memory-panel">
                <div class="memory-header">📚 Active Evidence</div>
                <div class="memory-content" id="active-evidence">
                    <div class="memory-empty">No evidence yet...</div>
                </div>
            </div>
            
            <!-- Plan Steps -->
            <div class="memory-panel">
                <div class="memory-header">📋 Plan Steps</div>
                <div class="memory-content" id="plan-steps">
                    <div class="memory-empty">No plan yet...</div>
                </div>
            </div>
            
            <!-- Actions -->
            <div class="memory-panel">
                <div class="memory-header">⚡ Actions</div>
                <div class="memory-content" id="actions">
                    <div class="memory-empty">No actions yet...</div>
                </div>
            </div>
            
            <!-- Evaluations -->
            <div class="memory-panel">
                <div class="memory-header">📊 Evaluations</div>
                <div class="memory-content" id="evaluations">
                    <div class="memory-empty">No evaluations yet...</div>
                </div>
            </div>
            
            <!-- Turn Queries -->
            <div class="memory-panel">
                <div class="memory-header">🔄 Turn Queries</div>
                <div class="memory-content" id="turn-queries">
                    <div class="memory-empty">No queries yet...</div>
                </div>
            </div>
        </div>
        
        <!-- Session Info -->
        <div class="memory-panel" style="margin-top: 20px;">
            <div class="memory-header">🏛️ Session Information</div>
            <div class="memory-content" id="session-info">
                <div class="memory-empty">Loading...</div>
            </div>
        </div>
    </div>
    
    <script>
        const sessionId = '{{ session_id }}';
        let lastUpdate = null;
        
        function formatClaim(claim, index) {
            return `
                <div class="memory-item claim-item">
                    <div><strong>#${index + 1}</strong></div>
                    <div>${claim.text || claim}</div>
                    ${claim.confidence !== undefined ? 
                        `<div class="confidence">Confidence: ${(claim.confidence * 100).toFixed(0)}%</div>` : ''}
                    ${claim.id ? `<div class="timestamp">ID: ${claim.id}</div>` : ''}
                </div>
            `;
        }
        
        function formatEvidence(evidence, index) {
            return `
                <div class="memory-item evidence-item">
                    <div><strong>#${index + 1}</strong></div>
                    <div>${evidence.text || evidence.excerpt || 'No text'}</div>
                    ${evidence.source ? `<div class="source">Source: ${evidence.source.domain || evidence.source.url || 'Unknown'}</div>` : ''}
                    ${evidence.relevance !== undefined ? 
                        `<div>Relevance: ${(evidence.relevance * 100).toFixed(0)}%</div>` : ''}
                    ${evidence.time ? `<div class="timestamp">${evidence.time}</div>` : ''}
                </div>
            `;
        }
        
        function formatPlanStep(step, index, currentStep) {
            const isCurrent = currentStep && (step.step_id === currentStep || step.id === currentStep);
            const status = step.status || 'pending';
            return `
                <div class="memory-item plan-item">
                    <div><strong>${step.step_id || step.id || `Step ${index + 1}`}</strong> 
                        ${isCurrent ? '👈 Current' : ''}</div>
                    <div>${step.goal}</div>
                    <div class="status-${status}">Status: ${status}</div>
                    ${step.way ? `<div>Approach: ${step.way}</div>` : ''}
                </div>
            `;
        }
        
        function formatAction(action, index) {
            return `
                <div class="memory-item action-item">
                    <div><strong>${action.type || action.action || 'Action'}</strong></div>
                    ${action.query ? `<div>Query: ${action.query}</div>` : ''}
                    ${action.rationale ? `<div>Rationale: ${action.rationale}</div>` : ''}
                    ${action.status ? `<div class="status-${action.status}">Status: ${action.status}</div>` : ''}
                    ${action.ts ? `<div class="timestamp">${new Date(action.ts).toLocaleTimeString()}</div>` : ''}
                </div>
            `;
        }
        
        function formatEvaluation(evaluation, index) {
            return `
                <div class="memory-item">
                    <div><strong>Evaluation #${index + 1}</strong></div>
                    <div class="${evaluation.passed ? 'status-completed' : 'status-failed'}">
                        ${evaluation.passed ? '✅ Passed' : '❌ Failed'}
                    </div>
                    ${evaluation.metrics ? `
                        <div style="margin-top: 10px;">
                            <div>Sufficiency: ${(evaluation.metrics.sufficiency * 100).toFixed(0)}%</div>
                            <div>Reliability: ${(evaluation.metrics.reliability * 100).toFixed(0)}%</div>
                            <div>Consistency: ${(evaluation.metrics.consistency * 100).toFixed(0)}%</div>
                            <div>Recency: ${(evaluation.metrics.recency * 100).toFixed(0)}%</div>
                            <div>Diversity: ${(evaluation.metrics.diversity * 100).toFixed(0)}%</div>
                        </div>
                    ` : ''}
                </div>
            `;
        }
        
        function formatTurnQuery(query, index) {
            return `
                <div class="memory-item">
                    <div><strong>Turn ${index + 1}</strong></div>
                    <div>${query.query || query}</div>
                    ${query.turn_id ? `<div class="timestamp">Turn ID: ${query.turn_id}</div>` : ''}
                </div>
            `;
        }
        
        async function updateMemories() {
            try {
                const response = await fetch(`/api/memory/${sessionId}`);
                if (!response.ok) return;
                
                const data = await response.json();
                if (!data.memories) return;
                
                const memories = data.memories;
                
                // Update Active Claims
                const claimsContainer = document.getElementById('active-claims');
                if (memories.active_claims && memories.active_claims.length > 0) {
                    claimsContainer.innerHTML = memories.active_claims
                        .map((claim, i) => formatClaim(claim, i))
                        .join('');
                }
                
                // Update Active Evidence
                const evidenceContainer = document.getElementById('active-evidence');
                if (memories.active_evidences && memories.active_evidences.length > 0) {
                    evidenceContainer.innerHTML = memories.active_evidences
                        .slice(-10)  // Show last 10
                        .map((evidence, i) => formatEvidence(evidence, i))
                        .join('');
                }
                
                // Update Plan Steps
                const planContainer = document.getElementById('plan-steps');
                if (memories.plan_steps && memories.plan_steps.length > 0) {
                    planContainer.innerHTML = memories.plan_steps
                        .map((step, i) => formatPlanStep(step, i, memories.current_step))
                        .join('');
                }
                
                // Update Actions
                const actionsContainer = document.getElementById('actions');
                if (memories.actions && memories.actions.length > 0) {
                    actionsContainer.innerHTML = memories.actions
                        .slice(-10)  // Show last 10
                        .map((action, i) => formatAction(action, i))
                        .join('');
                }
                
                // Update Evaluations
                const evaluationsContainer = document.getElementById('evaluations');
                if (memories.evaluations && memories.evaluations.length > 0) {
                    evaluationsContainer.innerHTML = memories.evaluations
                        .slice(-5)  // Show last 5
                        .map((evaluation, i) => formatEvaluation(evaluation, i))
                        .join('');
                }
                
                // Update Turn Queries
                const queriesContainer = document.getElementById('turn-queries');
                if (memories.turn_queries && memories.turn_queries.length > 0) {
                    queriesContainer.innerHTML = memories.turn_queries
                        .map((query, i) => formatTurnQuery(query, i))
                        .join('');
                }
                
                // Update Session Info
                const sessionContainer = document.getElementById('session-info');
                let sessionHtml = '<div class="memory-item">';
                if (memories.session_config && Object.keys(memories.session_config).length > 0) {
                    sessionHtml += `<div><strong>Configuration:</strong></div>
                        <pre style="margin: 10px 0; color: #888;">${JSON.stringify(memories.session_config, null, 2)}</pre>`;
                }
                if (memories.session_archive) {
                    sessionHtml += `<div><strong>Archive:</strong> ${memories.session_archive}</div>`;
                }
                sessionHtml += `<div class="timestamp">Last Update: ${data.last_update || 'Never'}</div>`;
                sessionHtml += '</div>';
                sessionContainer.innerHTML = sessionHtml;
                
                lastUpdate = data.last_update;
                
            } catch (error) {
                console.error('Error updating memories:', error);
            }
        }
        
        updateMemories();
        setInterval(updateMemories, 1000);
    </script>
</body>
</html>
'''

def run_server(port=5678):
    """Run the memory content monitoring server."""
    print(f"🧠 Starting Memory Content Monitor Server on http://localhost:{port}")
    print(f"📊 Dashboard: http://localhost:{port}")
    print(f"🔌 API endpoint: http://localhost:{port}/api/memory/<session_id>/<memory_type>")
    try:
        app.run(host='0.0.0.0', port=port, debug=False)
    except OSError as e:
        if "Address already in use" in str(e):
            print(f"\n❌ Port {port} is already in use!")
            print(f"💡 Try using a different port: python -m core.monitor_server_v3 --port 8080")
        else:
            raise

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Deep Research Memory Content Monitor Server')
    parser.add_argument('--port', type=int, default=5678, help='Port to run the server on (default: 5678)')
    args = parser.parse_args()
    run_server(port=args.port)