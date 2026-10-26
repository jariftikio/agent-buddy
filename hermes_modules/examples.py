"""Examples demonstrating usage of Hermes modules."""

import json
import logging
from hermes_modules import WebSearchClient, SystemMonitor, Config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


def example_web_search():
    """Example: Perform a web search."""
    print("\n" + "=" * 60)
    print("WEB SEARCH EXAMPLE")
    print("=" * 60)

    try:
        # Initialize the client (uses env vars from config)
        client = WebSearchClient()

        # Perform a search
        query = "Python automation best practices 2026"
        print(f"\nSearching for: '{query}'")
        print(f"Provider: {Config.WEB_SEARCH_PROVIDER}")

        results = client.search(query, max_results=5)

        print(f"\nFound {len(results)} results:\n")
        for result in results:
            print(f"[{result.position}] {result.title}")
            print(f"    URL: {result.url}")
            print(f"    Snippet: {result.snippet[:100]}...")
            print()

        # Return as JSON
        print("\nResults as JSON:")
        json_results = client.search_as_json(query, max_results=3)
        print(json.dumps(json_results, indent=2))

    except ValueError as e:
        print(f"Configuration Error: {e}")
        print("Make sure SERPAPI_API_KEY or TAVILY_API_KEY is set in your .env file")
    except Exception as e:
        print(f"Error during search: {e}")


def example_system_monitor():
    """Example: Monitor system health."""
    print("\n" + "=" * 60)
    print("SYSTEM MONITOR EXAMPLE")
    print("=" * 60)

    try:
        monitor = SystemMonitor(enable_logging=True)

        # Get CPU usage
        print("\n--- CPU Usage ---")
        cpu_info = monitor.get_cpu_usage()
        print(f"Overall CPU: {cpu_info.percent_used}%")
        print(f"Cores: {cpu_info.core_count}")
        print(f"Per-core usage: {cpu_info.core_usage}")
        print(f"Load average (1m, 5m, 15m): {cpu_info.load_average}")

        # Get memory usage
        print("\n--- Memory Usage ---")
        mem_info = monitor.get_memory_usage()
        print(f"Memory used: {mem_info.percent_used}%")
        print(f"Total: {mem_info.total_gb:.2f} GB")
        print(f"Used: {mem_info.used_gb:.2f} GB")
        print(f"Available: {mem_info.available_gb:.2f} GB")

        # Get listening ports
        print("\n--- Listening Ports (First 10) ---")
        try:
            ports = monitor.get_listening_ports()[:10]
            for port in ports:
                process_info = f" (PID: {port.pid}, {port.process_name})" if port.pid else ""
                print(
                    f"  {port.local_address}:{port.local_port} "
                    f"- Status: {port.status}{process_info}"
                )
        except Exception as e:
            print(f"  Note: {e}")
            print("  (Run with sudo for complete port information)")

        # Get full health report
        print("\n--- Full System Health Report ---")
        health = monitor.get_system_health()
        print(json.dumps(health, indent=2, default=str))

        # Check specific port
        print("\n--- Port Check Example ---")
        test_port = 22  # SSH
        is_listening = monitor.is_port_listening(test_port)
        print(f"Port {test_port} listening: {is_listening}")

    except Exception as e:
        print(f"Error during monitoring: {e}")


def example_integrated_workflow():
    """Example: Integrated workflow using both modules."""
    print("\n" + "=" * 60)
    print("INTEGRATED WORKFLOW EXAMPLE")
    print("=" * 60)

    try:
        # Step 1: Check system health
        print("\n[Step 1] Checking system health...")
        monitor = SystemMonitor(enable_logging=False)
        health = monitor.get_system_health()

        cpu_usage = health["cpu"]["percent_used"]
        memory_usage = health["memory"]["percent_used"]
        alerts = health["alerts"]

        print(f"  CPU: {cpu_usage}%")
        print(f"  Memory: {memory_usage}%")
        if alerts:
            print(f"  ⚠️  Alerts: {', '.join(alerts)}")

        # Step 2: Search for relevant information if issues detected
        if alerts:
            print("\n[Step 2] Issues detected. Searching for solutions...")

            try:
                search_client = WebSearchClient()

                if any("CPU" in alert for alert in alerts):
                    print("  Searching for: 'How to optimize CPU usage'")
                    cpu_results = search_client.search(
                        "How to optimize CPU usage",
                        max_results=2,
                    )
                    print(f"  Found {len(cpu_results)} results")

                if any("memory" in alert.lower() for alert in alerts):
                    print("  Searching for: 'Memory optimization techniques'")
                    mem_results = search_client.search(
                        "Memory optimization techniques",
                        max_results=2,
                    )
                    print(f"  Found {len(mem_results)} results")
            except ValueError:
                print("  (Search API not configured)")

        print("\n[Step 3] Monitoring complete.")
        print(f"  System health snapshot saved")

    except Exception as e:
        print(f"Error during workflow: {e}")


if __name__ == "__main__":
    # Uncomment the examples you want to run:

    print("\nHermes Agent Modules - Examples")
    print("================================\n")

    # Web Search Example
    # example_web_search()

    # System Monitoring Example
    example_system_monitor()

    # Integrated Workflow Example
    # example_integrated_workflow()

    print("\n" + "=" * 60)
    print("Examples Complete")
    print("=" * 60)
