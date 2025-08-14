#!/usr/bin/env python3
"""
Deep Research System Launcher

This script starts both the monitor server and the main application.
"""

import os
import sys
import time
import subprocess
import signal
import webbrowser
import argparse
from pathlib import Path

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from config import config


class DeepResearchLauncher:
    """Launcher for Deep Research system."""
    
    def __init__(self):
        self.monitor_process = None
        self.main_process = None
    
    def start_monitor_server(self, port: int = 5678):
        """Start the monitor server in background."""
        print(f"🚀 Starting monitor server on port {port}...")
        
        cmd = [sys.executable, "-m", "core.monitor_server", "--port", str(port)]
        self.monitor_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Wait for server to start
        time.sleep(2)
        
        if self.monitor_process.poll() is None:
            print(f"✅ Monitor server started successfully on http://localhost:{port}")
            return True
        else:
            print("❌ Failed to start monitor server")
            return False
    
    def start_main_app(self, args):
        """Start the main application."""
        print("\n🔬 Starting Deep Research System...")
        
        cmd = [sys.executable, "multi_turn_demo.py"]
        if args.example:
            cmd.append("--example")
        if args.no_colors:
            cmd.append("--no-colors")
        if args.no_icons:
            cmd.append("--no-icons")
        if args.monitor:
            cmd.append("--monitor")
        
        try:
            self.main_process = subprocess.run(cmd)
        except KeyboardInterrupt:
            print("\n\n👋 Shutting down gracefully...")
    
    def cleanup(self):
        """Clean up processes."""
        if self.monitor_process and self.monitor_process.poll() is None:
            print("\n🛑 Stopping monitor server...")
            self.monitor_process.terminate()
            self.monitor_process.wait(timeout=5)
    
    def signal_handler(self, sig, frame):
        """Handle interrupt signals."""
        self.cleanup()
        sys.exit(0)
    
    def run(self, args):
        """Run the launcher."""
        # Set up signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        try:
            # Validate configuration
            try:
                config.validate()
            except ValueError as e:
                print(f"❌ Configuration error: {e}")
                print("\n💡 Please check config.json:")
                print("   1. Make sure config.json exists")
                print("   2. Set your api_key in the 'llm' section")
                return 1
            
            # Start monitor if not disabled
            if not args.no_monitor:
                if not self.start_monitor_server(args.port):
                    return 1
                
                # Open browser if requested
                if args.open_browser:
                    time.sleep(1)
                    webbrowser.open(f"http://localhost:{args.port}")
            
            # Start main application
            self.start_main_app(args)
            
        finally:
            self.cleanup()
        
        return 0


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Deep Research System - AI-powered research assistant',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                    # Start with default settings
  %(prog)s --no-monitor       # Start without monitor server
  %(prog)s --port 8080        # Use custom port for monitor
  %(prog)s --example          # Run example queries
  %(prog)s --open-browser     # Auto-open monitor in browser
        """
    )
    
    # Monitor options
    parser.add_argument('--no-monitor', action='store_true',
                        help='Disable monitor server')
    parser.add_argument('--port', type=int, default=5678,
                        help='Port for monitor server (default: 5678)')
    parser.add_argument('--open-browser', action='store_true',
                        help='Automatically open monitor in browser')
    
    # Display options
    parser.add_argument('--no-colors', action='store_true',
                        help='Disable colored output')
    parser.add_argument('--no-icons', action='store_true',
                        help='Disable icons in output')
    
    # Demo options
    parser.add_argument('--example', action='store_true',
                        help='Run example conversation')
    parser.add_argument('--monitor', action='store_true',
                        help='Enable monitoring by default')
    
    args = parser.parse_args()
    
    # Print banner
    print("""
    ╔══════════════════════════════════════════════════════════════╗
    ║                                                              ║
    ║     🔬 Prism — From complexity to clarity 🔬                 ║
    ║                                                              ║
    ║          An AI-powered Deep Research System                  ║
    ║                                                              ║
    ╚══════════════════════════════════════════════════════════════╝
    """)
    
    launcher = DeepResearchLauncher()
    return launcher.run(args)


if __name__ == "__main__":
    sys.exit(main())