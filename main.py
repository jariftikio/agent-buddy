#!/usr/bin/env python3
"""
Hermes Main Agent Loop
Lead Software Architect Design

A sophisticated agent execution system that:
1. Accepts natural language input from users
2. Classifies intent (web search, system monitoring, or combined)
3. Executes appropriate modules
4. Returns structured, formatted results

Architectural Principles:
- Separation of Concerns: Intent classification, execution, output are isolated
- Extensibility: Easy to add new task types and handlers
- Robustness: Comprehensive error handling and logging
- Clarity: Clean interfaces and explicit data flows
"""

import sys
import json
import logging
from pathlib import Path
from typing import Optional

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from hermes_modules.agent_core_v2 import (
    HermesAgent,
    create_hermes_agent_with_modules,
    TaskType,
)
from hermes_modules.language_config import (
    Language,
    LanguageDetector,
    SystemPromptManager,
    BengaliKeywordNormalizer,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class HermesUI:
    """User interface for Hermes agent."""

    BANNER = """
    ╔═══════════════════════════════════════════════════════════════╗
    ║                                                               ║
    ║                    🔮 HERMES AGENT v2.0                      ║
    ║           Intelligent Local Automation & Monitoring           ║
    ║                                                               ║
    ║  Capabilities: Web Search • System Monitoring • URL Security ║
    ║  Enhanced: LLM-Based Intent Classification • Risk Assessment ║
    ║                                                               ║
    ╚═══════════════════════════════════════════════════════════════╝
    """

    HELP_TEXT = """
    ┌─ USAGE ─────────────────────────────────────────────────────┐
    │                                                              │
    │  ENGLISH Examples:                                           │
    │                                                              │
    │  Web Search:                                               │
    │    • "Search for Python best practices"                    │
    │    • "Find information about machine learning"             │
    │                                                              │
    │  System Monitoring:                                        │
    │    • "Check CPU and memory usage"                          │
    │    • "Monitor my system health"                            │
    │                                                              │
    │  URL Security:                                             │
    │    • "Is https://example.com safe?"                        │
    │    • "Check if this URL is malicious"                      │
    │                                                              │
    │  ─────────────────────────────────────────────────────────│
    │                                                              │
    │  বাংলা (BENGALI) Examples:                                  │
    │                                                              │
    │  Web Search:                                               │
    │    • "Python সম্পর্কে খোঁজ করো"                            │
    │    • "মেশিন লার্নিং সম্পর্কে তথ্য খুঁজ"                    │
    │                                                              │
    │  System Status:                                            │
    │    • "সিস্টেমের অবস্থা দেখাও"                              │
    │    • "সিপিইউ এবং মেমরি চেক করো"                           │
    │    • "সিস্টেম স্বাস্থ্য রিপোর্ট দেখাও"                     │
    │                                                              │
    │  URL Security:                                             │
    │    • "এই লিংকটি নিরাপদ কিনা দেখাও"                       │
    │    • "ইউআরএল চেক করো: https://example.com"               │
    │                                                              │
    │  Commands:                                                  │
    │    • help   - এই সাহায্য বার্তা দেখাও                      │
    │    • exit   - বেরিয়ে যান                                   │
    │    • clear  - স্ক্রিন পরিষ্কার করুন                        │
    │                                                              │
    └──────────────────────────────────────────────────────────────┘
    """

    @staticmethod
    def print_banner() -> None:
        """Print welcome banner."""
        print(HermesUI.BANNER)

    @staticmethod
    def print_help() -> None:
        """Print help text."""
        print(HermesUI.HELP_TEXT)

    @staticmethod
    def print_header(text: str) -> None:
        """Print a formatted header."""
        print(f"\n{'═' * 60}")
        print(f"  {text}")
        print(f"{'═' * 60}\n")

    @staticmethod
    def print_section(title: str) -> None:
        """Print a section header."""
        print(f"\n  ┌─ {title}")
        print(f"  │")

    @staticmethod
    def print_item(text: str, indent: int = 2) -> None:
        """Print an indented item."""
        prefix = "  │ " if indent > 0 else ""
        print(f"{prefix}{text}")

    @staticmethod
    def print_footer() -> None:
        """Print section footer."""
        print(f"  │")
        print(f"  └──────────────────────────────────────────\n")


class HermesExecutor:
    """Executes Hermes agent and formats output."""

    def __init__(self):
        """Initialize executor with configured agent."""
        self.agent, _ = create_hermes_agent_with_modules(enable_logging=False)
        self.ui = HermesUI()
        self.current_language = Language.ENGLISH

    def process_user_input(self, user_input: str, language: Language = Language.ENGLISH) -> dict:
        """
        Process user input through the agent.

        Args:
            user_input: User's natural language input (English or Bengali).
            language: Detected language (ENGLISH or BENGALI).

        Returns:
            Dictionary with execution results and metadata.
        """
        # Skip empty input
        if not user_input.strip():
            return None

        # Store language for response formatting
        self.current_language = language

        # Handle commands
        if user_input.lower() == "help":
            self.ui.print_help()
            return None
        elif user_input.lower() == "clear":
            import os

            os.system("clear" if sys.platform != "win32" else "cls")
            return None
        elif user_input.lower() == "exit":
            return {"command": "exit"}

        # Process through agent
        logger.info(f"User input: {user_input}")
        context = self.agent.process_input(user_input)

        return self._format_response(context)

    def _format_response(self, context) -> dict:
        """Format agent context into structured response."""
        response = {
            "session_id": context.session_id,
            "intent": context.intent.to_dict(),
            "results": [r.to_dict() for r in context.results],
            "summary": self._generate_summary(context),
        }
        return response

    def _generate_summary(self, context) -> str:
        """Generate human-readable summary of results."""
        if not context.results:
            return "No tasks executed."

        summaries = []
        for result in context.results:
            if result.success:
                task_type = result.task_type.value.replace("_", " ").title()
                data = result.data

                if result.task_type == TaskType.WEB_SEARCH:
                    count = data.get("results_count", 0)
                    query = data.get("query", "")
                    summaries.append(
                        f"✅ Web Search: Found {count} results for '{query}'"
                    )

                elif result.task_type == TaskType.SYSTEM_MONITOR:
                    cpu = data.get("cpu", {})
                    mem = data.get("memory", {})
                    summaries.append(
                        f"✅ System Monitor: CPU {cpu.get('percent_used', 0):.1f}% | "
                        f"Memory {mem.get('percent_used', 0):.1f}%"
                    )

                elif result.task_type == TaskType.HEALTH_REPORT:
                    alerts = data.get("alerts", [])
                    if alerts:
                        summaries.append(
                            f"⚠️  Health Report: {len(alerts)} alert(s) detected"
                        )
                    else:
                        summaries.append("✅ Health Report: System healthy")

                elif result.task_type == TaskType.PORT_CHECK:
                    port = data.get("port")
                    listening = data.get("is_listening", False)
                    status = "listening" if listening else "not listening"
                    summaries.append(f"✅ Port Check: Port {port} is {status}")
            else:
                error = result.error or "Unknown error"
                summaries.append(f"❌ {result.task_type.value}: {error}")

        return " | ".join(summaries)

    def display_response(self, response: dict) -> None:
        """Display formatted response to user."""
        if not response:
            return

        if response.get("command") == "exit":
            return

        # Summary
        self.ui.print_section("EXECUTION SUMMARY")
        self.ui.print_item(response["summary"])
        self.ui.print_footer()

        # Intent
        intent = response["intent"]
        self.ui.print_section("CLASSIFIED INTENT")
        self.ui.print_item(f"Task Type: {intent['task_type'].upper()}")
        self.ui.print_item(f"Primary Query: {intent['primary_query']}")
        self.ui.print_item(f"Confidence: {intent['confidence']:.0%}")
        self.ui.print_footer()

        # Results Detail
        for i, result in enumerate(response["results"], 1):
            task_name = result["task_type"].replace("_", " ").title()
            self.ui.print_section(f"RESULT {i}: {task_name}")

            if result["success"]:
                self._display_task_result(result)
            else:
                self.ui.print_item(f"Error: {result['error']}", indent=2)

            self.ui.print_item(f"Execution Time: {result['execution_time_ms']:.1f}ms")
            self.ui.print_footer()

    def _display_task_result(self, result: dict) -> None:
        """Display detailed task result."""
        data = result["data"]
        task_type = result["task_type"]

        if task_type == "web_search":
            results = data.get("results", [])
            self.ui.print_item(f"Query: {data.get('query')}")
            self.ui.print_item(f"Results: {len(results)}\n")

            for res in results[:3]:  # Show top 3
                self.ui.print_item(f"  {res['position']}. {res['title']}")
                self.ui.print_item(f"     URL: {res['url']}")
                self.ui.print_item(f"     {res['snippet'][:100]}...")
                self.ui.print_item("")

        elif task_type == "system_monitor":
            cpu = data.get("cpu", {})
            mem = data.get("memory", {})

            self.ui.print_item("CPU Usage:")
            self.ui.print_item(f"  Overall: {cpu.get('percent_used', 0):.1f}%")
            self.ui.print_item(f"  Cores: {cpu.get('core_count', 0)}")
            self.ui.print_item(f"  Load Avg: {cpu.get('load_average', {}).get('one_minute', 0):.2f}")

            self.ui.print_item("\nMemory Usage:")
            self.ui.print_item(f"  Used: {mem.get('percent_used', 0):.1f}%")
            self.ui.print_item(
                f"  {mem.get('used_gb', 0):.2f}GB / {mem.get('total_gb', 0):.2f}GB"
            )

        elif task_type == "health_report":
            alerts = data.get("alerts", [])
            ports = data.get("ports", [])

            if alerts:
                self.ui.print_item("Alerts:")
                for alert in alerts:
                    self.ui.print_item(f"  ⚠️  {alert}")
            else:
                self.ui.print_item("✅ No alerts")

            self.ui.print_item(f"\nListening Ports: {len(ports)}")

        elif task_type == "port_check":
            port = data.get("port")
            listening = data.get("is_listening", False)
            status = "LISTENING" if listening else "NOT LISTENING"
            self.ui.print_item(f"Port: {port}")
            self.ui.print_item(f"Status: {status}")


def main():
    """Main agent loop."""
    executor = HermesExecutor()
    executor.ui.print_banner()

    print("  Type 'help' for usage information, or start querying:")
    print("  • English: 'Search for Python tutorials'")
    print("  • বাংলা: 'সিস্টেমের অবস্থা দেখাও'\n")

    try:
        while True:
            try:
                # Get user input
                user_input = input("  🔮 Hermes > ").strip()

                if not user_input:
                    continue

                # Detect language
                detected_language = LanguageDetector.detect_language(user_input)
                logger.debug(f"Detected language: {detected_language.value}")

                # Process input
                response = executor.process_user_input(user_input, detected_language)

                # Check for exit command
                if response and response.get("command") == "exit":
                    print("\n  Goodbye! 👋\n")
                    break

                # Display response
                executor.display_response(response)

            except KeyboardInterrupt:
                print("\n\n  Interrupted by user.")
                break
            except Exception as e:
                logger.error(f"Error processing input: {e}", exc_info=True)
                print(f"  ❌ Error: {e}\n")

    except EOFError:
        print("\n\n  Session ended.\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
