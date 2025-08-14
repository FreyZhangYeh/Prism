"""Enhanced logging system for Deep Research Agent with beautiful output."""

import sys
from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum
import json
# Monitor client will be imported dynamically to avoid circular imports


class LogLevel(Enum):
    """Log levels with colors and icons."""
    DEBUG = ("DEBUG", "🔍", "\033[90m")      # Gray
    INFO = ("INFO", "ℹ️ ", "\033[94m")       # Blue
    SUCCESS = ("SUCCESS", "✅", "\033[92m")  # Green
    WARNING = ("WARNING", "⚠️ ", "\033[93m") # Yellow
    ERROR = ("ERROR", "❌", "\033[91m")      # Red
    CRITICAL = ("CRITICAL", "🚨", "\033[95m") # Magenta


class LoggerConfig:
    """Configuration for the logger."""
    def __init__(self, 
                 enable_colors: bool = True,
                 enable_icons: bool = True,
                 show_timestamp: bool = True,
                 show_module: bool = True,
                 indent_size: int = 2):
        self.enable_colors = enable_colors
        self.enable_icons = enable_icons
        self.show_timestamp = show_timestamp
        self.show_module = show_module
        self.indent_size = indent_size


class AgentLogger:
    """Beautiful logger for Deep Research Agent."""
    
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    
    # Module colors
    MODULE_COLORS = {
        "Planner": "\033[96m",      # Cyan
        "Evaluate": "\033[95m",      # Magenta
        "Decision": "\033[94m",      # Blue
        "RAG": "\033[92m",          # Green
        "WebSearch": "\033[93m",     # Yellow
        "Synthesize": "\033[96m",    # Cyan
        "ConflictResolver": "\033[91m", # Red
        "Output": "\033[92m",        # Green
        "Agent": "\033[97m",         # White
        "Memory": "\033[90m",        # Gray
    }
    
    def __init__(self, config: Optional[LoggerConfig] = None):
        self.config = config or LoggerConfig()
        self.indent_level = 0
        
    def _get_timestamp(self) -> str:
        """Get formatted timestamp."""
        if not self.config.show_timestamp:
            return ""
        return datetime.now().strftime("%H:%M:%S.%f")[:-3]
    
    def _get_color(self, text: str, color: str) -> str:
        """Apply color to text if enabled."""
        if not self.config.enable_colors:
            return text
        return f"{color}{text}{self.RESET}"
    
    def _get_icon(self, level: LogLevel) -> str:
        """Get icon for log level."""
        if not self.config.enable_icons:
            return ""
        return level.value[1]
    
    def _format_module(self, module: str) -> str:
        """Format module name with color."""
        if not self.config.show_module:
            return ""
        color = self.MODULE_COLORS.get(module, "\033[97m")
        return self._get_color(f"[{module}]", color)
    
    def _get_indent(self) -> str:
        """Get indentation string."""
        return " " * (self.indent_level * self.config.indent_size)
    
    def log(self, level: LogLevel, module: str, message: str, data: Optional[Dict] = None):
        """Log a message with beautiful formatting."""
        timestamp = self._get_timestamp()
        icon = self._get_icon(level)
        module_str = self._format_module(module)
        color = level.value[2]
        
        # Build log line
        parts = []
        if timestamp:
            parts.append(self._get_color(timestamp, self.DIM))
        if icon:
            parts.append(icon)
        if module_str:
            parts.append(module_str)
        
        indent = self._get_indent()
        prefix = " ".join(parts)
        
        # Format message
        message_colored = self._get_color(message, color)
        
        # Print main message
        print(f"{indent}{prefix} {message_colored}")
        
        # Print data if provided
        if data:
            self._print_data(data, indent + "  ")
        
        # Send to monitor if available
        try:
            import core.monitor_client as mc
            if hasattr(mc, '_monitor_client') and mc._monitor_client and mc._monitor_client.enabled:
                mc._monitor_client.log(level.value[0].lower(), module, message)
        except:
            pass  # Ignore monitor errors
    
    def _print_data(self, data: Dict, indent: str):
        """Pretty print data dictionary."""
        for key, value in data.items():
            if isinstance(value, dict):
                print(f"{indent}{self._get_color(key + ':', self.DIM)}")
                self._print_data(value, indent + "  ")
            elif isinstance(value, list):
                print(f"{indent}{self._get_color(key + ':', self.DIM)}")
                for item in value:
                    if isinstance(item, dict):
                        self._print_data(item, indent + "  ")
                    else:
                        print(f"{indent}  • {item}")
            else:
                print(f"{indent}{self._get_color(key + ':', self.DIM)} {value}")
    
    def section(self, title: str, char: str = "=", width: int = 60):
        """Print a section header."""
        border = char * width
        print(f"\n{self._get_color(border, self.BOLD)}")
        print(f"{self._get_color(title.center(width), self.BOLD)}")
        print(f"{self._get_color(border, self.BOLD)}\n")
    
    def subsection(self, title: str):
        """Print a subsection header."""
        print(f"\n{self._get_color('─' * 40, self.DIM)}")
        print(f"{self._get_color(title, self.BOLD)}")
        print(f"{self._get_color('─' * 40, self.DIM)}")
    
    def progress(self, current: int, total: int, label: str = "Progress"):
        """Print a progress bar."""
        percentage = (current / total) * 100 if total > 0 else 0
        bar_width = 30
        filled = int(bar_width * current / total) if total > 0 else 0
        
        bar = "█" * filled + "░" * (bar_width - filled)
        
        color = "\033[92m" if percentage >= 100 else "\033[93m" if percentage >= 50 else "\033[94m"
        
        print(f"\r{self._get_indent()}{label}: {self._get_color(bar, color)} {percentage:.1f}%", end="")
        if percentage >= 100:
            print()  # New line when complete
    
    def tree(self, items: List[Dict[str, Any]], title: Optional[str] = None):
        """Print items in a tree structure."""
        if title:
            print(f"\n{self._get_indent()}{self._get_color(title, self.BOLD)}")
        
        for i, item in enumerate(items):
            is_last = i == len(items) - 1
            prefix = "└── " if is_last else "├── "
            
            # Print main item
            main_text = item.get("text", str(item))
            status = item.get("status", "")
            if status:
                status_icon = "✅" if status == "completed" else "🔄" if status == "in_progress" else "⏳"
                main_text = f"{status_icon} {main_text}"
            
            print(f"{self._get_indent()}{prefix}{main_text}")
            
            # Print children if any
            if "children" in item:
                child_indent = "    " if is_last else "│   "
                with self.indent_context():
                    print(f"{self._get_indent()}{child_indent}", end="")
                    self.tree(item["children"])
    
    def metrics_table(self, metrics: Dict[str, float], title: str = "Metrics"):
        """Print metrics in a beautiful table format."""
        print(f"\n{self._get_indent()}{self._get_color(title, self.BOLD)}")
        print(f"{self._get_indent()}{self._get_color('─' * 40, self.DIM)}")
        
        for name, value in metrics.items():
            # Color based on value
            if value >= 0.8:
                color = "\033[92m"  # Green
            elif value >= 0.6:
                color = "\033[93m"  # Yellow
            else:
                color = "\033[91m"  # Red
            
            bar_width = 20
            filled = int(bar_width * value)
            bar = "█" * filled + "░" * (bar_width - filled)
            
            print(f"{self._get_indent()}{name:.<20} {self._get_color(bar, color)} {self._get_color(f'{value:.2f}', color)}")
    
    def indent_context(self):
        """Context manager for indentation."""
        class IndentContext:
            def __init__(self, logger):
                self.logger = logger
            
            def __enter__(self):
                self.logger.indent_level += 1
                return self
            
            def __exit__(self, exc_type, exc_val, exc_tb):
                self.logger.indent_level -= 1
        
        return IndentContext(self)
    
    # Convenience methods
    def debug(self, module: str, message: str, data: Optional[Dict] = None):
        self.log(LogLevel.DEBUG, module, message, data)
    
    def info(self, module: str, message: str, data: Optional[Dict] = None):
        self.log(LogLevel.INFO, module, message, data)
    
    def success(self, module: str, message: str, data: Optional[Dict] = None):
        self.log(LogLevel.SUCCESS, module, message, data)
    
    def warning(self, module: str, message: str, data: Optional[Dict] = None):
        self.log(LogLevel.WARNING, module, message, data)
    
    def error(self, module: str, message: str, data: Optional[Dict] = None):
        self.log(LogLevel.ERROR, module, message, data)
    
    def critical(self, module: str, message: str, data: Optional[Dict] = None):
        self.log(LogLevel.CRITICAL, module, message, data)


# Global logger instance
logger = AgentLogger()