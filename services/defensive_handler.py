"""
Defensive Input Handler - Input Sanitization & Safe Routing

Prevents sensitive requests from reaching the LLM tier and routes them to
secure local modules instead. Maintains full backward compatibility with
5-layer architecture.
"""

import logging
import re
from typing import Optional, Dict, Any, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class SensitivityLevel(Enum):
    """Risk level of user input."""
    SAFE = "safe"
    WARNING = "warning"
    CRITICAL = "critical"


class InputSanitizer:
    """Sanitizes user input and detects high-risk keywords."""

    # High-risk keywords that should not be sent to LLM
    CRITICAL_KEYWORDS = {
        # Injection attacks
        "system prompt", "ignore instructions", "override", "jailbreak",
        "bypass", "disable safety", "remove restrictions",

        # Credential/Auth attempts
        "password", "api key", "secret", "token", "credential",
        "authentication", "authorize", "login", "oauth",

        # Internal system access
        "backend access", "admin panel", "database", "server",
        "execute code", "run command", "shell", "terminal",

        # Data exfiltration
        "extract data", "dump database", "export", "leak",
        "user information", "private data", "confidential",

        # Malicious intent
        "malware", "virus", "ransomware", "exploit",
        "vulnerability", "ddos", "attack", "hack"
    }

    # Bengali critical keywords
    BENGALI_CRITICAL_KEYWORDS = {
        "পাসওয়ার্ড", "এপিআই কী", "গোপন", "টোকেন", "শংসাপত্র",
        "ডাটাবেস", "সার্ভার", "কোড চালাও", "কমান্ড চালান",
        "ডেটা বের করো", "লিক করো", "হ্যাক করো", "আক্রমণ"
    }

    # Suspicious patterns
    SUSPICIOUS_PATTERNS = [
        r"(?:eval|exec|subprocess|os\.system)\(",  # Code execution
        r"<\s*script[^>]*>.*?</\s*script\s*>",     # XSS
        r"--\s*|;\s*DROP|DELETE|UPDATE|INSERT",     # SQL injection
        r"\.\.\/",                                   # Path traversal
        r"\${.*}",                                   # Template injection
    ]

    def __init__(self):
        """Initialize sanitizer with compiled regex patterns."""
        self.critical_pattern = re.compile(
            "|".join(re.escape(kw) for kw in self.CRITICAL_KEYWORDS),
            re.IGNORECASE
        )
        self.bengali_pattern = re.compile(
            "|".join(self.BENGALI_CRITICAL_KEYWORDS)
        )
        self.suspicious_pattern_list = [
            re.compile(pattern) for pattern in self.SUSPICIOUS_PATTERNS
        ]

    def analyze_input(self, text: str) -> Tuple[SensitivityLevel, Optional[str], bool]:
        """
        Analyze input for sensitivity.

        Returns:
            Tuple of (SensitivityLevel, detected_keyword, is_bengali)
        """
        if not text:
            return SensitivityLevel.SAFE, None, False

        # Check if input is Bengali
        is_bengali = self._is_bengali(text)

        # Check for critical keywords
        if is_bengali:
            match = self.bengali_pattern.search(text)
            if match:
                return SensitivityLevel.CRITICAL, match.group(), is_bengali

        match = self.critical_pattern.search(text)
        if match:
            return SensitivityLevel.CRITICAL, match.group(), is_bengali

        # Check for suspicious patterns
        for pattern in self.suspicious_pattern_list:
            if pattern.search(text):
                return SensitivityLevel.WARNING, "suspicious_pattern", is_bengali

        return SensitivityLevel.SAFE, None, is_bengali

    @staticmethod
    def _is_bengali(text: str) -> bool:
        """Check if text contains significant Bengali content."""
        BENGALI_UNICODE_RANGE = (0x0980, 0x09FF)
        bengali_count = sum(
            1 for char in text
            if BENGALI_UNICODE_RANGE[0] <= ord(char) <= BENGALI_UNICODE_RANGE[1]
        )
        return bengali_count > len(text) * 0.2

    def sanitize_output(self, text: str) -> str:
        """Remove or obfuscate sensitive data from output."""
        # Obfuscate credentials-like patterns
        text = re.sub(r'(password|token|secret|key)\s*[:=]\s*\S+',
                      r'\1: ***REDACTED***', text, flags=re.IGNORECASE)
        return text


class DefensiveRouter:
    """Routes requests to appropriate handlers, bypassing LLM for sensitive inputs."""

    def __init__(self):
        """Initialize router with handler mappings."""
        self.sanitizer = InputSanitizer()
        self._setup_route_keywords()

    def _setup_route_keywords(self):
        """Setup keywords for routing to specific handlers."""
        self.routes = {
            "url_check": {
                "keywords": {"url", "link", "domain", "safe", "phishing", "security", "লিঙ্ক", "নিরাপদ"},
                "handler": "url_security",
                "bengali_keywords": {"লিঙ্ক", "লিংক", "ইউআরএল", "ডোমেইন", "নিরাপদ", "নিরাপত্তা"}
            },
            "system_monitor": {
                "keywords": {"cpu", "memory", "system", "health", "monitor", "status", "সিস্টেম", "অবস্থা"},
                "handler": "system_monitor",
                "bengali_keywords": {"সিস্টেম", "অবস্থা", "দেখাও", "চেক", "পরীক্ষা", "স্বাস্থ্য"}
            },
            "port_check": {
                "keywords": {"port", "listening", "connection", "network", "পোর্ট", "সংযোগ"},
                "handler": "port_check",
                "bengali_keywords": {"পোর্ট", "সংযোগ", "নেটওয়ার্ক", "শোনা", "চলছে"}
            }
        }

    def should_use_local_handler(self, text: str) -> Tuple[bool, Optional[str]]:
        """
        Check if input should use local handler instead of LLM.

        Returns:
            Tuple of (should_use_local, handler_type)
        """
        lower_text = text.lower()

        # Check each route
        for route_name, route_config in self.routes.items():
            keywords = route_config["keywords"]
            bengali_keywords = route_config.get("bengali_keywords", set())

            # Check English keywords
            if any(kw in lower_text for kw in keywords):
                return True, route_config["handler"]

            # Check Bengali keywords
            if any(kw in text for kw in bengali_keywords):
                return True, route_config["handler"]

        return False, None

    def generate_safe_response(self, handler_type: str, query: str, is_bengali: bool) -> Dict[str, Any]:
        """
        Generate a safe response using local modules.

        This is called when input is routed to a local handler instead of LLM.
        """
        response_text = ""

        if handler_type == "url_security":
            response_text = self._handle_url_check(query, is_bengali)
        elif handler_type == "system_monitor":
            response_text = self._handle_system_monitor(query, is_bengali)
        elif handler_type == "port_check":
            response_text = self._handle_port_check(query, is_bengali)
        else:
            response_text = self._handle_fallback(is_bengali)

        return {
            "ok": True,
            "response": response_text,
            "handler": handler_type,
            "is_local": True,
            "is_bengali": is_bengali
        }

    @staticmethod
    def _handle_url_check(query: str, is_bengali: bool) -> str:
        """Handle URL security check request."""
        if is_bengali:
            return (
                "🔒 ইউআরএল নিরাপত্তা পরীক্ষা সক্রিয়\n\n"
                "আপনার অনুরোধটি আমাদের নিরাপদ স্থানীয় মডিউলের মাধ্যমে পরিচালিত হয়েছে "
                "(URLSecurityHandler)। এটি কোনো বাহ্যিক এআই মডেল ব্যবহার করে না।\n\n"
                "URLSecurityHandler বৈশিষ্ট্য:\n"
                "✅ ফিশিং সাইট সনাক্তকরণ\n"
                "✅ দূষিত ডোমেইন চেক করুন\n"
                "✅ নিরাপদ সূচক defang করুন\n\n"
                "আপনার নির্দিষ্ট URL সহ আবার চেষ্টা করুন।"
            )
        else:
            return (
                "🔒 URL Security Check Activated\n\n"
                "Your request has been routed to our secure local module (URLSecurityHandler). "
                "This does NOT use any external LLM.\n\n"
                "URLSecurityHandler Features:\n"
                "✅ Phishing site detection\n"
                "✅ Malicious domain identification\n"
                "✅ Safe indicator defanging\n\n"
                "Please try again with your specific URL."
            )

    @staticmethod
    def _handle_system_monitor(query: str, is_bengali: bool) -> str:
        """Handle system monitoring request."""
        if is_bengali:
            return (
                "📊 সিস্টেম পর্যবেক্ষণ সক্রিয়\n\n"
                "আপনার অনুরোধটি আমাদের স্থানীয় সিস্টেম মডিউলের মাধ্যমে পরিচালিত হয়েছে "
                "(SystemMonitor)। এটি সম্পূর্ণ নিরাপদ এবং কোনো বাহ্যিক এআই ব্যবহার করে না।\n\n"
                "উপলব্ধ পর্যবেক্ষণ বৈশিষ্ট্য:\n"
                "✅ সিপিইউ ব্যবহার\n"
                "✅ মেমরি ব্যবহার\n"
                "✅ নেটওয়ার্ক স্ট্যাটাস\n"
                "✅ সিস্টেম স্বাস্থ্য রিপোর্ট"
            )
        else:
            return (
                "📊 System Monitoring Activated\n\n"
                "Your request has been routed to our local system module (SystemMonitor). "
                "This is completely safe and does NOT use any external LLM.\n\n"
                "Available Monitoring Features:\n"
                "✅ CPU usage metrics\n"
                "✅ Memory consumption\n"
                "✅ Network status\n"
                "✅ System health reports"
            )

    @staticmethod
    def _handle_port_check(query: str, is_bengali: bool) -> str:
        """Handle port checking request."""
        if is_bengali:
            return (
                "🔌 পোর্ট পরীক্ষা সক্রিয়\n\n"
                "আপনার অনুরোধটি আমাদের পোর্ট চেক মডিউলের মাধ্যমে পরিচালিত হয়েছে। "
                "এটি সম্পূর্ণ স্থানীয় এবং নিরাপদ।\n\n"
                "পোর্ট চেক বৈশিষ্ট্য:\n"
                "✅ শোনা পোর্ট সনাক্তকরণ\n"
                "✅ নেটওয়ার্ক সংযোগ যাচাই\n"
                "✅ সেবা অবস্থা পরীক্ষা"
            )
        else:
            return (
                "🔌 Port Check Activated\n\n"
                "Your request has been routed to our port checking module. "
                "This is completely local and safe.\n\n"
                "Port Check Features:\n"
                "✅ Listening port detection\n"
                "✅ Network connection verification\n"
                "✅ Service status checks"
            )

    @staticmethod
    def _handle_fallback(is_bengali: bool) -> str:
        """Fallback response when no specific handler matched."""
        if is_bengali:
            return (
                "⚠️ সংরক্ষণমূলক মোড সক্রিয়\n\n"
                "আপনার অনুরোধ সংবেদনশীল হিসাবে চিহ্নিত হয়েছে এবং "
                "সরাসরি এলএলএম-এ পাঠানো যায় না।\n\n"
                "আরও নির্দিষ্ট অনুরোধ করুন:\n"
                "• 'সিস্টেমের অবস্থা দেখাও' (সিস্টেম পর্যবেক্ষণের জন্য)\n"
                "• 'এই লিঙ্কটি পরীক্ষা করো' (ইউআরএল চেকের জন্য)\n"
                "• 'পোর্ট 8080 শুনছে কিনা জানুন' (পোর্ট চেকের জন্য)"
            )
        else:
            return (
                "⚠️ Defensive Mode Activated\n\n"
                "Your request has been identified as sensitive and cannot be "
                "sent directly to the LLM.\n\n"
                "Please try a more specific request:\n"
                "• \"Check system status\" (for system monitoring)\n"
                "• \"Check this link\" (for URL security)\n"
                "• \"Is port 8080 listening?\" (for port checking)"
            )

    def generate_rejection_response(self, sensitivity: SensitivityLevel,
                                   keyword: Optional[str], is_bengali: bool) -> Dict[str, Any]:
        """Generate a rejection response for high-risk input."""
        if is_bengali:
            if sensitivity == SensitivityLevel.CRITICAL:
                message = (
                    f"🚫 অনুরোধ প্রত্যাখ্যান করা হয়েছে\n\n"
                    f"সংবেদনশীল কীওয়ার্ড সনাক্ত করা হয়েছে: '{keyword}'\n"
                    f"আমরা নিরাপত্তার কারণে এই ধরনের অনুরোধ প্রক্রিয়া করতে পারি না।\n\n"
                    f"আমাদের নিরাপদ স্থানীয় মডিউল ব্যবহার করার চেষ্টা করুন।"
                )
            else:  # WARNING
                message = (
                    "⚠️ সন্দেহজনক প্যাটার্ন সনাক্ত করা হয়েছে\n\n"
                    "আপনার অনুরোধটি সম্ভাব্য নিরাপত্তা সমস্যা ধারণ করে।\n"
                    "আরও স্পষ্ট পুনঃপ্রণয়ন করুন।"
                )
        else:
            if sensitivity == SensitivityLevel.CRITICAL:
                message = (
                    f"🚫 Request Rejected\n\n"
                    f"Sensitive keyword detected: '{keyword}'\n"
                    f"We cannot process requests containing this for security reasons.\n\n"
                    f"Try using our secure local modules instead."
                )
            else:  # WARNING
                message = (
                    "⚠️ Suspicious Pattern Detected\n\n"
                    "Your request contains a potential security issue.\n"
                    "Please rephrase your request more clearly."
                )

        return {
            "ok": False,
            "error": message,
            "sensitivity": sensitivity.value,
            "is_bengali": is_bengali,
            "blocked": True
        }


def create_defensive_handler() -> Tuple[InputSanitizer, DefensiveRouter]:
    """Factory function to create sanitizer and router."""
    return InputSanitizer(), DefensiveRouter()
