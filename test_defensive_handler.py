#!/usr/bin/env python3
"""
Test script for defensive input handler.

Demonstrates input sanitization and routing to local handlers.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from services.defensive_handler import InputSanitizer, DefensiveRouter, SensitivityLevel


def test_input_sanitizer():
    """Test input sanitization and sensitivity detection."""
    print("=" * 70)
    print("TEST: Input Sanitizer")
    print("=" * 70)

    sanitizer = InputSanitizer()

    test_cases = [
        ("Check system status", "System monitoring request"),
        ("Is https://example.com safe?", "URL check request"),
        ("Tell me about Python", "Normal web search"),
        ("What is my password?", "Sensitive request - password keyword"),
        ("eval('malicious code')", "Code injection attempt"),
        ("SELECT * FROM users; DROP DATABASE;", "SQL injection attempt"),
        ("সিস্টেমের অবস্থা দেখাও", "Bengali system status request"),
        ("হ্যাক করো", "Bengali critical keyword"),
    ]

    for text, description in test_cases:
        sensitivity, keyword, is_bengali = sanitizer.analyze_input(text)
        print(f"\n  Input: {text}")
        print(f"  Description: {description}")
        print(f"  Sensitivity: {sensitivity.value}")
        if keyword:
            print(f"  Detected Keyword: {keyword}")
        print(f"  Language: {'Bengali' if is_bengali else 'English'}")


def test_defensive_router():
    """Test routing to appropriate local handlers."""
    print("\n" + "=" * 70)
    print("TEST: Defensive Router - Local Handler Routing")
    print("=" * 70)

    router = DefensiveRouter()

    test_cases = [
        ("Check this URL: https://phishing-site.com", "URL security handler"),
        ("What is the system health?", "System monitor handler"),
        ("Is port 8080 listening?", "Port check handler"),
        ("Search for Python tutorials", "No local handler - use LLM"),
        ("দেখাও সিস্টেমের অবস্থা", "Bengali system status"),
        ("এই লিঙ্কটি পরীক্ষা করো: https://example.com", "Bengali URL check"),
    ]

    for text, description in test_cases:
        should_use_local, handler_type = router.should_use_local_handler(text)
        print(f"\n  Input: {text}")
        print(f"  Description: {description}")
        print(f"  Use Local Handler: {should_use_local}")
        if handler_type:
            print(f"  Handler Type: {handler_type}")


def test_rejection_responses():
    """Test rejection responses for critical inputs."""
    print("\n" + "=" * 70)
    print("TEST: Rejection Responses")
    print("=" * 70)

    router = DefensiveRouter()

    # Test English rejection
    print("\n  English Rejection Response:")
    response = router.generate_rejection_response(
        SensitivityLevel.CRITICAL,
        "password",
        is_bengali=False
    )
    print(f"    OK: {response.get('ok')}")
    print(f"    Blocked: {response.get('blocked')}")
    print(f"    Error:\n{response.get('error')}")

    # Test Bengali rejection
    print("\n  Bengali Rejection Response:")
    response = router.generate_rejection_response(
        SensitivityLevel.CRITICAL,
        "হ্যাক",
        is_bengali=True
    )
    print(f"    OK: {response.get('ok')}")
    print(f"    Language: {'Bengali' if response.get('is_bengali') else 'English'}")
    print(f"    Error:\n{response.get('error')}")


def test_safe_responses():
    """Test safe responses from local handlers."""
    print("\n" + "=" * 70)
    print("TEST: Safe Responses from Local Handlers")
    print("=" * 70)

    router = DefensiveRouter()

    # Test URL handler English
    print("\n  URL Security Handler (English):")
    response = router.generate_safe_response("url_security", "https://example.com", False)
    print(f"    Handler: {response.get('handler')}")
    print(f"    Is Local: {response.get('is_local')}")
    print(f"    Response:\n{response.get('response')}")

    # Test System Monitor Bengali
    print("\n  System Monitor (Bengali):")
    response = router.generate_safe_response("system_monitor", "সিস্টেম অবস্থা", True)
    print(f"    Handler: {response.get('handler')}")
    print(f"    Language: Bengali")
    print(f"    Response:\n{response.get('response')}")

    # Test Port Check English
    print("\n  Port Check Handler (English):")
    response = router.generate_safe_response("port_check", "port 8080", False)
    print(f"    Handler: {response.get('handler')}")
    print(f"    Response:\n{response.get('response')}")


def test_sensitivity_levels():
    """Test different sensitivity levels."""
    print("\n" + "=" * 70)
    print("TEST: Sensitivity Level Detection")
    print("=" * 70)

    sanitizer = InputSanitizer()

    safe_inputs = [
        "What is machine learning?",
        "Tell me about Python",
        "সিস্টেম পর্যবেক্ষণ করো"
    ]

    warning_inputs = [
        "eval('code')",
        "<script>alert('xss')</script>",
        "DROP DATABASE users"
    ]

    critical_inputs = [
        "Give me the database password",
        "Bypass security restrictions",
        "হ্যাক করার পদ্ধতি",
        "system prompt override",
        "API key: sk-1234567890"
    ]

    print("\n  SAFE Inputs:")
    for inp in safe_inputs:
        sensitivity, _, _ = sanitizer.analyze_input(inp)
        print(f"    '{inp[:40]}...' → {sensitivity.value}")

    print("\n  WARNING Inputs:")
    for inp in warning_inputs:
        sensitivity, keyword, _ = sanitizer.analyze_input(inp)
        print(f"    '{inp[:40]}...' → {sensitivity.value} ({keyword})")

    print("\n  CRITICAL Inputs:")
    for inp in critical_inputs:
        sensitivity, keyword, _ = sanitizer.analyze_input(inp)
        print(f"    '{inp[:40]}...' → {sensitivity.value} ({keyword})")


def test_bengali_detection():
    """Test Bengali language detection."""
    print("\n" + "=" * 70)
    print("TEST: Bengali Language Detection")
    print("=" * 70)

    sanitizer = InputSanitizer()

    test_cases = [
        ("English only text", False),
        ("সম্পূর্ণ বাংলা পাঠ্য", True),
        ("Mixed English এবং Bengali text", False),  # Less than 20%
        ("এটি বাংলা mixed with some English words text", True),  # More than 20%
    ]

    for text, expected_bengali in test_cases:
        _, _, is_bengali = sanitizer.analyze_input(text)
        result = "✓" if is_bengali == expected_bengali else "✗"
        print(f"  {result} '{text[:40]}...' → Bengali: {is_bengali}")


if __name__ == "__main__":
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 68 + "║")
    print("║" + "  DEFENSIVE INPUT HANDLER TEST SUITE".center(68) + "║")
    print("║" + " " * 68 + "║")
    print("╚" + "=" * 68 + "╝")
    print()

    test_input_sanitizer()
    test_defensive_router()
    test_rejection_responses()
    test_safe_responses()
    test_sensitivity_levels()
    test_bengali_detection()

    print("\n" + "=" * 70)
    print("ALL TESTS COMPLETED")
    print("=" * 70)
    print()
