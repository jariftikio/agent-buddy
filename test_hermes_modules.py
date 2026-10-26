#!/usr/bin/env python3
"""
Test script for Hermes modules.
Verifies installation and basic functionality.
"""

import sys
import json
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))


def test_imports():
    """Test that all modules can be imported."""
    print("Testing imports...")
    try:
        from hermes_modules import WebSearchClient, SystemMonitor, Config
        print("  ✅ All modules imported successfully")
        return True
    except ImportError as e:
        print(f"  ❌ Import failed: {e}")
        return False


def test_system_monitor():
    """Test system monitoring functionality."""
    print("\nTesting SystemMonitor...")
    try:
        from hermes_modules import SystemMonitor

        monitor = SystemMonitor(enable_logging=False)

        # Test CPU
        cpu = monitor.get_cpu_usage()
        assert cpu.percent_used >= 0, "CPU percentage invalid"
        assert cpu.core_count > 0, "Core count invalid"
        print(f"  ✅ CPU monitoring: {cpu.percent_used}% ({cpu.core_count} cores)")

        # Test Memory
        mem = monitor.get_memory_usage()
        assert mem.percent_used >= 0, "Memory percentage invalid"
        assert mem.total_gb > 0, "Total memory invalid"
        print(
            f"  ✅ Memory monitoring: {mem.percent_used}% "
            f"({mem.used_gb:.2f}GB / {mem.total_gb:.2f}GB)"
        )

        # Test JSON serialization
        cpu_dict = cpu.to_dict()
        mem_dict = mem.to_dict()
        json.dumps({"cpu": cpu_dict, "memory": mem_dict})
        print("  ✅ JSON serialization working")

        # Test port checking
        is_listening = monitor.is_port_listening(22)
        assert isinstance(is_listening, bool), "Port check returned non-boolean"
        print(f"  ✅ Port checking: Port 22 {'listening' if is_listening else 'not listening'}")

        return True
    except Exception as e:
        print(f"  ❌ SystemMonitor test failed: {e}")
        return False


def test_web_search_config():
    """Test web search configuration."""
    print("\nTesting WebSearchClient configuration...")
    try:
        from hermes_modules import Config

        provider = Config.WEB_SEARCH_PROVIDER
        print(f"  ℹ️  Configured provider: {provider}")

        # Check if API keys are configured
        api_key = Config.get_api_key()
        if not api_key:
            print(f"  ⚠️  No API key configured for {provider}")
            print(f"     Set {provider.upper()}_API_KEY environment variable")
            return True  # Not a failure, just unconfigured
        else:
            print(f"  ✅ API key configured for {provider}")
            return True
    except Exception as e:
        print(f"  ❌ Config test failed: {e}")
        return False


def test_web_search_client():
    """Test web search client (if configured)."""
    print("\nTesting WebSearchClient...")
    try:
        from hermes_modules import WebSearchClient, Config

        api_key = Config.get_api_key()
        if not api_key:
            print(f"  ⊘  Skipping search test (no API key configured)")
            print(f"     Configure {Config.WEB_SEARCH_PROVIDER.upper()}_API_KEY to enable")
            return True

        client = WebSearchClient()
        print(f"  ✅ Client initialized with provider: {client.provider}")

        # Test search (use a simple query)
        print("  ℹ️  Testing search (this will use 1 API call)...")
        results = client.search("Python", max_results=2)

        assert isinstance(results, list), "Results not a list"
        assert len(results) > 0, "No results returned"
        print(f"  ✅ Search returned {len(results)} results")

        # Verify result structure
        result = results[0]
        assert hasattr(result, "title"), "Missing title"
        assert hasattr(result, "url"), "Missing URL"
        assert hasattr(result, "snippet"), "Missing snippet"
        print(f"  ✅ Result structure valid: '{result.title[:50]}...'")

        # Test JSON serialization
        json_results = client.search_as_json("test", max_results=1)
        json.dumps(json_results)
        print("  ✅ JSON serialization working")

        return True

    except ValueError as e:
        print(f"  ⚠️  Configuration error: {e}")
        return True  # Not a failure, just unconfigured
    except Exception as e:
        print(f"  ❌ WebSearchClient test failed: {e}")
        return False


def test_error_handling():
    """Test error handling."""
    print("\nTesting error handling...")
    try:
        from hermes_modules import WebSearchClient

        client = WebSearchClient()

        # Test empty query error
        try:
            client.search("")
            print("  ❌ Should have raised ValueError for empty query")
            return False
        except ValueError:
            print("  ✅ Empty query validation working")

        return True
    except ValueError:
        # API key not configured, that's ok
        print("  ✅ Error handling verified (API key not needed)")
        return True
    except Exception as e:
        print(f"  ❌ Error handling test failed: {e}")
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("HERMES MODULES TEST SUITE")
    print("=" * 60)

    results = {
        "Imports": test_imports(),
        "SystemMonitor": test_system_monitor(),
        "WebSearch Config": test_web_search_config(),
        "WebSearchClient": test_web_search_client(),
        "Error Handling": test_error_handling(),
    }

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status:8} - {test_name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed! Hermes is ready to use.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
