# Deep Research Project Structure

## Directory Layout

```
deep_research/
├── config/                     # Configuration management
│   ├── __init__.py
│   └── config.py              # Configuration classes and utilities
├── core/                      # Core system components
│   ├── __init__.py
│   ├── acts/                  # Agent actions
│   │   ├── __init__.py
│   │   ├── capability.py      # System capability checks
│   │   ├── decide.py          # Decision making
│   │   ├── evaluate.py        # Research evaluation
│   │   ├── output.py          # Output generation
│   │   ├── planner.py         # Research planning
│   │   ├── query_executor.py  # Query execution
│   │   ├── rag_query.py       # RAG query generation
│   │   ├── resolve_conflict.py # Conflict resolution
│   │   ├── synthesize.py     # Claim synthesis
│   │   └── web_search_query.py # Web search query generation
│   ├── agent.py               # Main agent implementation
│   ├── agent_with_memory_content_monitor.py # Agent with monitoring
│   ├── ids.py                 # ID generation utilities
│   ├── logger.py              # Beautiful logging system
│   ├── memory.py              # Memory facade and management
│   ├── memory_content_monitor.py # Memory content monitoring
│   ├── models.py              # Data models
│   └── monitor_server.py      # Monitoring server
├── llm/                       # LLM integration
│   ├── __init__.py
│   └── client.py              # LLM client (Qwen API)
├── docs/                      # Documentation
│   └── project_structure.md   # This file
├── .env.example               # Environment variables example
├── .gitignore                 # Git ignore file
├── config.example.json        # Configuration example
├── multi_turn_demo.py         # Multi-turn conversation demo
├── requirements.txt           # Python dependencies
└── start.py                   # Main launcher script
```

## Key Components

### 1. Configuration System (`config/`)
- Centralized configuration management
- Support for environment variables
- JSON configuration files
- Validation and defaults

### 2. Core System (`core/`)
- **Agent**: Main research agent implementation
- **Memory**: Hierarchical memory system (Session, Turn, Plan, Action)
- **Acts**: Modular actions for research tasks
- **Logger**: Beautiful console output with colors and icons
- **Monitor**: Real-time memory content visualization

### 3. LLM Integration (`llm/`)
- Supports Qwen API (OpenAI-compatible)
- Configurable models and parameters
- JSON response parsing

### 4. Entry Points
- `start.py`: Main launcher with monitor server
- `multi_turn_demo.py`: Multi-turn conversation interface

## Usage

1. Set up environment:
   ```bash
   cp .env.example .env
   # Edit .env with your API key
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the system:
   ```bash
   python start.py
   ```

## Architecture

The system follows a modular architecture:

1. **Agent Layer**: Orchestrates the research process
2. **Memory Layer**: Maintains context and state
3. **Action Layer**: Executes specific research tasks
4. **LLM Layer**: Interfaces with language models
5. **Monitor Layer**: Provides real-time visibility

Each component is designed to be:
- **Modular**: Easy to extend or replace
- **Configurable**: Behavior controlled via configuration
- **Observable**: Built-in monitoring and logging