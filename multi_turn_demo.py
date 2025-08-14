#!/usr/bin/env python3
"""Multi-turn conversation demo using refactored V2 agent with proper memory mechanism."""

import sys
sys.path.append('.')

from core.agent_with_memory_content_monitor import DeepResearchAgentV2WithMemoryContentMonitor as DeepResearchAgentV2
from core.models import SessionConfig
from core.ids import generate_id
from core.logger import logger, LoggerConfig


class MemoryBasedMultiTurnChatV2:
    """Multi-turn research using the refactored V2 agent with new architecture."""
    
    def __init__(self, enable_monitor=False):
        # Configure logger for beautiful output
        try:
            from config import config as global_config
            logger.config = LoggerConfig(
                enable_colors=global_config.system.enable_colors,
                enable_icons=global_config.system.enable_icons,
                show_timestamp=global_config.system.show_timestamp,
                show_module=global_config.system.show_module
            )
        except ImportError:
            logger.config = LoggerConfig(
                enable_colors=True,
                enable_icons=True,
                show_timestamp=True,
                show_module=True
            )
        
        self.agent = DeepResearchAgentV2()
        self.session_id = generate_id("session")
        self.turn_count = 0
        self.enable_monitor = enable_monitor
        
        # Monitor will be handled by the agent itself
        # No need to initialize monitor client here
        
        # Load configuration
        try:
            from config import config as global_config
            # Configuration with settings from config
            self.config = SessionConfig(
                prefs=global_config.research.prefs,
                thresholds=global_config.research.thresholds,
                budget_state={
                    "remaining_calls": global_config.research.initial_budget_calls,
                    "max_evidence": global_config.research.max_evidence
                },
                stance_enabled=False
            )
        except ImportError:
            # Fallback configuration
            self.config = SessionConfig(
                prefs={
                    "source_preference": "variety",
                    "time_preference": "recent"
                },
                thresholds={
                    "sufficiency": 0.75,
                    "reliability": 0.70,
                    "consistency": 0.65,
                    "recency": 0.70,
                    "diversity": 0.60
                },
                budget_state={
                    "remaining_calls": 100,
                    "max_evidence": 200
                },
                stance_enabled=False
            )
        
        # Set session config once
        self.agent.memory.set_session_config(self.session_id, self.config)
    
    def run_turn(self, query: str) -> str:
        """Run a single research turn."""
        self.turn_count += 1
        
        logger.section(f"轮次 {self.turn_count}", "▶", 70)
        logger.info("MultiTurn", f"用户问题: {query}")
        
        # Run turn with context enabled for turn 2+
        result = self.agent.run_turn(
            session_id=self.session_id,
            user_query=query,
            config=None,  # Use existing session config
            max_loops=12,
            verbose=True,
            include_context=self.turn_count > 1,  # Enable context from turn 2
            enable_memory_monitor=self.enable_monitor  # Changed parameter name
        )
        
        # Show result
        logger.subsection("研究回答")
        print("\n" + "─"*70)
        print(result)
        print("─"*70)
        
        # Show session memory status
        self._show_memory_status()
        
        return result
    
    def _show_memory_status(self):
        """Display current memory status."""
        try:
            # Get session archive using the proper method
            archive_text = self.agent.memory.get_session_archive(self.session_id)
            
            # Get all high-confidence claims from the session
            all_claims = self.agent.memory.get_all_session_claims(self.session_id, min_confidence=0.7)
            
            # Get all evidences from the session
            all_evidences = self.agent.memory.get_all_session_evidences(self.session_id)
            
            logger.subsection("记忆状态")
            logger.info("Memory", "会话统计:", {
                "高置信观点数": len(all_claims),
                "收集证据总数": len(all_evidences),
                "当前轮次": self.turn_count
            })
            
            # Show session archive
            if archive_text:
                logger.info("Memory", f"会话摘要: {archive_text}")
            
            # Show high-confidence claims
            if all_claims:
                claim_items = []
                for claim in all_claims[:5]:  # Show top 5 claims
                    # Handle both Claim objects and dictionaries
                    if isinstance(claim, dict):
                        claim_text = claim.get('text', str(claim))
                        confidence = claim.get('confidence', 'N/A')
                        claim_id = claim.get('id', 'N/A')
                    else:
                        claim_text = getattr(claim, 'text', str(claim))
                        confidence = getattr(claim, 'confidence', 'N/A')
                        claim_id = getattr(claim, 'id', 'N/A')
                    
                    # Truncate text if too long
                    if len(claim_text) > 60:
                        claim_text = claim_text[:60] + "..."
                    
                    status = "completed" if confidence > 0.8 else "in_progress"
                    claim_items.append({
                        "text": f"[{claim_id}] {claim_text} (置信度: {confidence})",
                        "status": status
                    })
                
                logger.tree(claim_items, "高置信观点摘要")
                    
        except Exception as e:
            logger.error("Memory", f"读取失败: {e}")
    
    def run_interactive(self):
        """Run interactive multi-turn conversation."""
        # Print beautiful banner
        print("\n" + "═"*80)
        print("║" + " "*78 + "║")
        print("║" + "🔬 Prism — From complexity to clarity 🔬".center(78) + "║")
        print("║" + " "*78 + "║")
        print("║" + "An AI-powered Deep Research System".center(68) + "║")
        print("║" + " "*78 + "║")
        print("═"*80)
        
        logger.info("System", "输入你的研究问题，或输入 'exit' 退出")
        
        # Ask if user wants monitoring
        if not self.enable_monitor:
            enable_str = input("\n启用实时监控? (y/N): ").strip().lower()
            if enable_str == 'y':
                # Check if monitor server is running
                try:
                    import requests
                    response = requests.get("http://localhost:5678/api/sessions", timeout=1)
                    if response.status_code == 200:
                        self.enable_monitor = True
                        logger.success("System", "实时监控已启动")
                        # 如果使用记忆监控服务器，使用 /memory/ 路径
                        logger.info("System", f"📊 监控面板: http://localhost:5678/memory/{self.session_id}")
                        # 如果使用旧的监控服务器，使用 /session/ 路径
                        # logger.info("System", f"📊 监控面板: http://localhost:5678/session/{self.session_id}")
                    else:
                        raise Exception("Monitor server not responding")
                except:
                    logger.warning("System", "监控服务未启动！请先运行: python -m core.monitor_server")
        
        while True:
            try:
                query = input(f"\n问题 {self.turn_count + 1}: ").strip()
                
                if query.lower() in ['exit', 'quit', '退出']:
                    logger.success("System", "感谢使用! 再见! 👋")
                    break
                
                if not query:
                    logger.warning("System", "请输入有效的问题")
                    continue
                
                self.run_turn(query)
                
            except KeyboardInterrupt:
                logger.warning("System", "会话中断")
                break
            except Exception as e:
                logger.error("System", f"错误: {e}")
                import traceback
                traceback.print_exc()


def run_example_conversation():
    """Run an example multi-turn conversation about AI deep research."""
    
    logger.section("示例: AI深度研究系统多轮对话", "🎯", 80)
    
    chat = MemoryBasedMultiTurnChatV2(enable_monitor=False)
    
    # Example queries showcasing different V2 features
    queries = [
        "什么是检索增强生成(RAG)技术？",
        "RAG技术在大模型应用中有哪些具体的实现方式？",  # Tests continuity and deeper dive
        "这些方式各有什么优缺点？需要最新的对比分析",     # Tests conflict resolution & freshness
        "在企业级应用中，应该如何选择合适的RAG方案？"     # Tests synthesis of previous knowledge
    ]
    
    # Show all queries first
    logger.subsection("示例问题序列")
    query_items = [{"text": f"Q{i+1}: {q}"} for i, q in enumerate(queries)]
    logger.tree(query_items, "研究问题")
    
    for i, query in enumerate(queries):
        if i > 0:
            print("\n" + "─"*70)
            input("按Enter继续下一个问题...")
        chat.run_turn(query)


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Deep Research V2 Multi-Turn Demo')
    parser.add_argument('--example', action='store_true', help='Run example conversation')
    parser.add_argument('--no-colors', action='store_true', help='Disable colored output')
    parser.add_argument('--no-icons', action='store_true', help='Disable icons')
    parser.add_argument('--monitor', action='store_true', help='Enable monitoring by default')
    
    args = parser.parse_args()
    
    # Configure logger based on arguments
    if args.no_colors or args.no_icons:
        logger.config = LoggerConfig(
            enable_colors=not args.no_colors,
            enable_icons=not args.no_icons,
            show_timestamp=True,
            show_module=True
        )
    
    if args.example:
        run_example_conversation()
    else:
        chat = MemoryBasedMultiTurnChatV2(enable_monitor=args.monitor)
        chat.run_interactive()


if __name__ == "__main__":
    try:
        main()
    finally:
        # Cleanup handled by agent
        pass