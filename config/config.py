"""Configuration management for Deep Research system."""

import os
from dataclasses import dataclass, field
from typing import Dict, Optional
import json
from pathlib import Path


@dataclass
class LLMConfig:
    """LLM configuration."""
    api_key: str = ""
    base_url: str = ""
    model: str = "qwen-flash"
    max_retries: int = 3
    timeout: int = 30
    


@dataclass
class ResearchConfig:
    """Research configuration."""
    # Thresholds
    thresholds: Dict[str, float] = field(default_factory=lambda: {
        "sufficiency": 0.80,
        "reliability": 0.75,
        "consistency": 0.70,
        "recency": 0.70,
        "diversity": 0.60
    })
    
    # Preferences
    prefs: Dict[str, str] = field(default_factory=lambda: {
        "source_preference": "variety",
        "time_preference": "recent"
    })
    
    # Budget
    max_loops_per_turn: int = 12
    max_loops_per_step: int = 5
    initial_budget_calls: int = 100
    max_evidence: int = 200
    
    # Search settings
    rag_top_k: int = 5
    web_search_results: int = 8


@dataclass
class MonitorConfig:
    """Monitor configuration."""
    enabled: bool = True
    server_url: str = "http://localhost:5678"
    port: int = 5678
    auto_open_browser: bool = False


@dataclass
class SystemConfig:
    """System configuration."""
    # Logger settings
    enable_colors: bool = True
    enable_icons: bool = True
    show_timestamp: bool = True
    show_module: bool = True
    
    # Demo settings
    demo_mode: bool = False
    example_queries: list = field(default_factory=list)


class Config:
    """Main configuration class."""
    
    def __init__(self):
        self.llm = LLMConfig()
        self.research = ResearchConfig()
        self.monitor = MonitorConfig()
        self.system = SystemConfig()
        
        # Automatically load from config.json if it exists
        config_path = Path(__file__).parent.parent / 'config.json'
        if config_path.exists():
            self.load_from_file(str(config_path))
    
    def load_from_file(self, filepath: str):
        """Load configuration from JSON file."""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Update LLM config
        if 'llm' in data:
            for key, value in data['llm'].items():
                if hasattr(self.llm, key):
                    setattr(self.llm, key, value)
        
        # Update Research config  
        if 'research' in data:
            for key, value in data['research'].items():
                if hasattr(self.research, key):
                    setattr(self.research, key, value)
        
        # Update Monitor config
        if 'monitor' in data:
            for key, value in data['monitor'].items():
                if hasattr(self.monitor, key):
                    setattr(self.monitor, key, value)
        
        # Update System config
        if 'system' in data:
            for key, value in data['system'].items():
                if hasattr(self.system, key):
                    setattr(self.system, key, value)
    
    
    def validate(self):
        """Validate configuration."""
        errors = []
        
        # Check LLM config
        if not self.llm.api_key:
            errors.append("LLM API key is not set. Please set 'api_key' in config.json under 'llm' section.")
        
        # Check thresholds
        for name, value in self.research.thresholds.items():
            if not 0 <= value <= 1:
                errors.append(f"Threshold {name} must be between 0 and 1, got {value}")
        
        if errors:
            raise ValueError("Configuration validation failed:\n" + "\n".join(errors))


# Default configuration instance
config = Config()