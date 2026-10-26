"""
URL Security Handler Module - Defensive Security for Hermes Agent

Layer 1: Modules Layer (Defensive Security)

This module provides:
1. Architectural Risk Assessment - Evaluate URLs for security risks
2. Indicator Defanging - Safe printing of suspicious indicators
3. TaskType Integration - Plugs into CompositeIntentClassifier & HermesAgent

Design Principles:
- Standard library only (urllib.parse, ipaddress, re)
- Fail-safe defaults (assume suspicious until proven safe)
- Defense-in-depth (multiple checks)
- Non-blocking (assessment doesn't break agent)
- Comprehensive logging
- Zero breaking changes
"""

import logging
import re
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
from urllib.parse import urlparse, ParseResult
import ipaddress

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """Security risk classification."""

    SAFE = "safe"  # Standard domain, low risk
    WARNING = "warning"  # Suspicious characteristics, manual review recommended
    CRITICAL = "critical"  # High-risk indicators, require caution


class URLIndicator(Enum):
    """Types of security indicators found in URLs."""

    # Encoding risks
    PUNYCODE = "punycode_detected"  # xn-- prefix (IDN homograph attacks)
    PERCENT_ENCODING = "percent_encoding"  # %xx encoded characters
    UNICODE_CHARS = "unicode_chars"  # Non-ASCII characters

    # IP-based risks
    RAW_IP_ADDRESS = "raw_ip_address"  # Direct IP instead of domain
    PRIVATE_IP = "private_ip"  # RFC1918 private range
    LOOPBACK_IP = "loopback_ip"  # 127.0.0.1, ::1

    # Structural risks
    SUSPICIOUS_DOMAIN = "suspicious_domain"  # Unusual patterns
    SUSPICIOUS_PORT = "suspicious_port"  # Non-standard ports
    OBFUSCATED_PROTOCOL = "obfuscated_protocol"  # Unusual URL schemes

    # Content risks
    EMBEDDED_CREDENTIALS = "embedded_credentials"  # user:pass in URL
    EXCESSIVE_REDIRECTS = "excessive_redirects"  # Many redirects chained
    LONG_DOMAIN = "long_domain"  # Unusually long domain name


@dataclass
class URLAssessment:
    """Result of URL security assessment."""

    url: str
    risk_level: RiskLevel
    indicators: List[URLIndicator] = field(default_factory=list)
    confidence: float = 1.0
    reasoning: str = ""
    recommendations: List[str] = field(default_factory=list)
    parsed_url: Optional[ParseResult] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "url": self.url,
            "risk_level": self.risk_level.value,
            "indicators": [i.value for i in self.indicators],
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "recommendations": self.recommendations,
            "parsed_url": {
                "scheme": self.parsed_url.scheme,
                "netloc": self.parsed_url.netloc,
                "path": self.parsed_url.path,
                "hostname": self.parsed_url.hostname,
                "port": self.parsed_url.port,
            }
            if self.parsed_url
            else None,
        }


class URLSecurityAnalyzer:
    """Analyzes URLs for architectural and security risks."""

    # Suspicious domain patterns
    SUSPICIOUS_PATTERNS = [
        r"^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$",  # IPv4
        r"^xn--",  # Punycode (IDN)
        r"[a-zA-Z0-9]{50,}",  # Very long labels
        r"[0-9]{1,5}-[0-9]{1,5}",  # Unusual numeric patterns
        r"[^\w.-]",  # Invalid characters
    ]

    # Non-standard ports (suspicious for common protocols)
    SUSPICIOUS_PORTS = {
        "http": [25, 53, 110, 143, 3389, 5900],  # Mail, DNS, RDP, VNC
        "https": [25, 53, 110, 143, 3389, 5900],
        "ftp": [80, 443, 3389],  # Web, HTTPS, RDP
    }

    # Safe/common domains
    TRUSTED_DOMAINS = {
        "github.com",
        "google.com",
        "amazon.com",
        "microsoft.com",
        "apple.com",
        "python.org",
        "stackoverflow.com",
    }

    def __init__(self, enable_logging: bool = True):
        """
        Initialize analyzer.

        Args:
            enable_logging: Enable security logging
        """
        self.enable_logging = enable_logging
        if enable_logging:
            logger.info("URLSecurityAnalyzer initialized")

    def assess(self, url: str) -> URLAssessment:
        """
        Perform comprehensive security assessment of URL.

        Args:
            url: URL to assess

        Returns:
            URLAssessment with risk level and indicators
        """
        logger.debug(f"Assessing URL: {url}")

        # Parse URL
        try:
            parsed = urlparse(url)
            if not parsed.netloc:
                # Try with protocol prefix
                parsed = urlparse(f"http://{url}")
        except Exception as e:
            logger.warning(f"Failed to parse URL: {e}")
            return URLAssessment(
                url=url,
                risk_level=RiskLevel.CRITICAL,
                indicators=[URLIndicator.SUSPICIOUS_DOMAIN],
                confidence=0.9,
                reasoning="URL parsing failed",
                recommendations=["Use standard URL format (http://domain.com)"],
            )

        indicators: List[URLIndicator] = []
        recommendations: List[str] = []

        # Run security checks
        self._check_encoding(parsed, indicators, recommendations)
        self._check_ip_address(parsed, indicators, recommendations)
        self._check_domain(parsed, indicators, recommendations)
        self._check_port(parsed, indicators, recommendations)
        self._check_credentials(parsed, indicators, recommendations)

        # Determine risk level
        risk_level = self._calculate_risk_level(indicators)
        reasoning = self._build_reasoning(parsed, indicators)

        assessment = URLAssessment(
            url=url,
            risk_level=risk_level,
            indicators=indicators,
            confidence=self._calculate_confidence(indicators),
            reasoning=reasoning,
            recommendations=recommendations,
            parsed_url=parsed,
        )

        if self.enable_logging:
            logger.info(
                f"URL assessment: {risk_level.value} "
                f"({len(indicators)} indicators, confidence: {assessment.confidence:.0%})"
            )

        return assessment

    def _check_encoding(
        self,
        parsed: ParseResult,
        indicators: List[URLIndicator],
        recommendations: List[str],
    ) -> None:
        """Check for encoding-based attacks (IDN homographs, etc.)"""
        hostname = parsed.hostname or ""

        # Punycode detection (IDN homograph attacks)
        if "xn--" in hostname.lower():
            indicators.append(URLIndicator.PUNYCODE)
            recommendations.append(
                "Punycode detected (xn--). Verify the actual domain represents "
                "the expected service"
            )
            logger.warning(f"Punycode marker detected in: {hostname}")

        # Percent encoding in hostname
        if "%" in parsed.netloc:
            indicators.append(URLIndicator.PERCENT_ENCODING)
            recommendations.append("URL contains percent-encoded characters. Decode and verify.")
            logger.warning(f"Percent encoding detected in: {parsed.netloc}")

        # Unicode characters in hostname
        try:
            hostname.encode("ascii")
        except UnicodeEncodeError:
            indicators.append(URLIndicator.UNICODE_CHARS)
            recommendations.append(
                "Hostname contains non-ASCII characters. "
                "Verify against expected domain."
            )
            logger.warning(f"Unicode characters detected in: {hostname}")

    def _check_ip_address(
        self,
        parsed: ParseResult,
        indicators: List[URLIndicator],
        recommendations: List[str],
    ) -> None:
        """Check for IP-based risks (raw IPs, private ranges, etc.)"""
        hostname = parsed.hostname or ""

        try:
            ip = ipaddress.ip_address(hostname)

            # Raw IP address
            indicators.append(URLIndicator.RAW_IP_ADDRESS)
            recommendations.append(
                "Using raw IP address instead of domain name. "
                "Verify IP is expected and controlled."
            )

            # Private IP (RFC1918)
            if ip.is_private:
                indicators.append(URLIndicator.PRIVATE_IP)
                recommendations.append(
                    "IP is in private range (RFC1918). "
                    "Verify this is expected (internal network)."
                )
                logger.warning(f"Private IP detected: {ip}")

            # Loopback
            if ip.is_loopback:
                indicators.append(URLIndicator.LOOPBACK_IP)
                recommendations.append(
                    "IP is loopback (127.0.0.1 or ::1). "
                    "Only valid for local testing."
                )
                logger.warning(f"Loopback IP detected: {ip}")

        except ValueError:
            # Not an IP address (expected case for normal domains)
            pass

    def _check_domain(
        self,
        parsed: ParseResult,
        indicators: List[URLIndicator],
        recommendations: List[str],
    ) -> None:
        """Check for suspicious domain patterns."""
        hostname = parsed.hostname or ""

        # Check against trusted domains
        if hostname not in self.TRUSTED_DOMAINS:
            # Check for suspicious patterns
            for pattern in self.SUSPICIOUS_PATTERNS:
                if re.match(pattern, hostname):
                    indicators.append(URLIndicator.SUSPICIOUS_DOMAIN)
                    recommendations.append(
                        f"Domain matches suspicious pattern: {pattern}"
                    )
                    logger.debug(f"Suspicious domain pattern in: {hostname}")
                    break

        # Unusually long domain
        if len(hostname) > 63:  # DNS label limit
            indicators.append(URLIndicator.LONG_DOMAIN)
            recommendations.append(
                f"Domain name is unusually long ({len(hostname)} chars). "
                "Verify it matches expected domain."
            )
            logger.warning(f"Long domain detected: {hostname} ({len(hostname)} chars)")

    def _check_port(
        self,
        parsed: ParseResult,
        indicators: List[URLIndicator],
        recommendations: List[str],
    ) -> None:
        """Check for suspicious ports."""
        scheme = parsed.scheme or "http"
        port = parsed.port

        if port is None:
            return

        # Check against suspicious port list
        suspicious = self.SUSPICIOUS_PORTS.get(scheme.lower(), [])
        if port in suspicious:
            indicators.append(URLIndicator.SUSPICIOUS_PORT)
            recommendations.append(
                f"Port {port} is unusual for {scheme}. "
                "Verify the service running on this port."
            )
            logger.warning(f"Suspicious port {port} for scheme {scheme}")

        # Port out of valid range
        if not (0 < port < 65536):
            indicators.append(URLIndicator.SUSPICIOUS_PORT)
            recommendations.append(f"Port {port} is invalid (must be 1-65535).")
            logger.warning(f"Invalid port number: {port}")

    def _check_credentials(
        self,
        parsed: ParseResult,
        indicators: List[URLIndicator],
        recommendations: List[str],
    ) -> None:
        """Check for embedded credentials."""
        if parsed.username or parsed.password:
            indicators.append(URLIndicator.EMBEDDED_CREDENTIALS)
            recommendations.append(
                "URL contains embedded credentials (username/password). "
                "This is insecure. Use authentication headers instead."
            )
            logger.warning(
                f"Embedded credentials detected in URL. User: {parsed.username}"
            )

    @staticmethod
    def _calculate_risk_level(indicators: List[URLIndicator]) -> RiskLevel:
        """Calculate overall risk level from indicators."""
        critical_indicators = {
            URLIndicator.PRIVATE_IP,
            URLIndicator.LOOPBACK_IP,
            URLIndicator.EMBEDDED_CREDENTIALS,
            URLIndicator.PUNYCODE,
        }

        if any(ind in critical_indicators for ind in indicators):
            return RiskLevel.CRITICAL
        elif indicators:
            return RiskLevel.WARNING
        else:
            return RiskLevel.SAFE

    @staticmethod
    def _calculate_confidence(indicators: List[URLIndicator]) -> float:
        """Calculate confidence in assessment (0.0-1.0)."""
        # More indicators = higher confidence
        if len(indicators) == 0:
            return 1.0
        elif len(indicators) <= 2:
            return 0.9
        elif len(indicators) <= 4:
            return 0.85
        else:
            return 0.8

    @staticmethod
    def _build_reasoning(parsed: ParseResult, indicators: List[URLIndicator]) -> str:
        """Build human-readable reasoning for assessment."""
        if not indicators:
            return "URL structure is standard. No security concerns detected."

        parts = []
        if URLIndicator.RAW_IP_ADDRESS in indicators:
            parts.append(f"URL uses IP address {parsed.hostname} instead of domain name")
        if URLIndicator.PUNYCODE in indicators:
            parts.append("Domain uses Punycode (IDN), susceptible to homograph attacks")
        if URLIndicator.PRIVATE_IP in indicators:
            parts.append("IP is in private RFC1918 range")
        if URLIndicator.LOOPBACK_IP in indicators:
            parts.append("IP is loopback address (localhost)")
        if URLIndicator.SUSPICIOUS_PORT in indicators:
            parts.append(f"Port {parsed.port} is unusual for {parsed.scheme}")
        if URLIndicator.EMBEDDED_CREDENTIALS in indicators:
            parts.append("URL contains embedded credentials")
        if URLIndicator.LONG_DOMAIN in indicators:
            parts.append("Domain name is unusually long")

        return " | ".join(parts) if parts else "Multiple security indicators detected"


class IndicatorDefanger:
    """Defangs indicators of compromise (IoCs) for safe logging/display."""

    @staticmethod
    def defang_url(url: str) -> str:
        """
        Defang URL for safe display in logs/markdown.

        Examples:
            http://evil.com → hxxp://evil[.]com
            https://test.co.uk → hxxps://test[.]co[.]uk
            ftp://host → fxxp://host
        """
        # Defang protocol
        url = re.sub(r"^(https?)://", lambda m: m.group(1)[0] + "xxp" + "s" * (len(m.group(1)) - 1) + "://", url)
        url = re.sub(r"^(ftp)://", r"fxxp://", url, flags=re.IGNORECASE)

        # Defang domain separators (dots)
        url = url.replace(".", "[.]")

        return url

    @staticmethod
    def defang_ip(ip: str) -> str:
        """
        Defang IP address for safe display.

        Examples:
            192.168.1.1 → 192[.]168[.]1[.]1
            ::1 → ::[::1
        """
        # IPv4
        ip = ip.replace(".", "[.]")
        # IPv6
        ip = ip.replace("::", "::[:")
        return ip

    @staticmethod
    def defang_domain(domain: str) -> str:
        """Defang domain name for safe display."""
        return domain.replace(".", "[.]")

    @staticmethod
    def defang_email(email: str) -> str:
        """
        Defang email address for safe display.

        Examples:
            attacker@evil.com → attacker[at]evil[.]com
        """
        email = email.replace("@", "[at]")
        email = email.replace(".", "[.]")
        return email

    @staticmethod
    def defang_string(text: str) -> str:
        """
        Defang common IoC patterns in arbitrary text.

        Handles:
            - URLs
            - IPs
            - Domains
            - Emails
        """
        # URLs
        text = re.sub(
            r"(https?|ftp)://",
            lambda m: m.group(1)[0] + "xxp" + "s" * (len(m.group(1)) - 1) + "://",
            text,
            flags=re.IGNORECASE,
        )

        # Domain separators
        text = text.replace(".", "[.]")

        # Email addresses (@ symbol)
        text = text.replace("@", "[at]")

        return text


class URLSecurityHandler:
    """Handler integration for URL_CHECK task type."""

    def __init__(self, enable_logging: bool = True):
        """
        Initialize handler.

        Args:
            enable_logging: Enable security logging
        """
        self.analyzer = URLSecurityAnalyzer(enable_logging=enable_logging)
        self.defanger = IndicatorDefanger()
        self.enable_logging = enable_logging

        if enable_logging:
            logger.info("URLSecurityHandler initialized")

    def check_url(self, url: str) -> Dict[str, Any]:
        """
        Perform URL security check.

        Args:
            url: URL to check

        Returns:
            Dictionary with assessment and defanged output
        """
        # Analyze URL
        assessment = self.analyzer.assess(url)

        # Defang for safe display
        defanged_url = self.defanger.defang_url(url)

        return {
            "original_url": url,
            "defanged_url": defanged_url,
            "assessment": assessment.to_dict(),
            "safe_to_visit": assessment.risk_level == RiskLevel.SAFE,
            "risk_level": assessment.risk_level.value,
            "recommendations": assessment.recommendations,
        }

    def check_string(self, text: str) -> Dict[str, Any]:
        """
        Check arbitrary text for IoCs and defang.

        Args:
            text: Text to check

        Returns:
            Dictionary with defanged text and detected indicators
        """
        defanged_text = self.defanger.defang_string(text)

        # Simple IoC detection
        has_urls = bool(re.search(r"https?://\S+", text))
        has_ips = bool(re.search(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", text))
        has_emails = bool(re.search(r"\S+@\S+\.\S+", text))

        return {
            "original_text": text,
            "defanged_text": defanged_text,
            "detected_indicators": {
                "urls": has_urls,
                "ip_addresses": has_ips,
                "email_addresses": has_emails,
            },
        }


# Convenience functions
def assess_url(url: str) -> URLAssessment:
    """Quick assessment of a single URL."""
    analyzer = URLSecurityAnalyzer(enable_logging=False)
    return analyzer.assess(url)


def defang_url(url: str) -> str:
    """Quick defang of a URL."""
    return IndicatorDefanger.defang_url(url)


def defang_string(text: str) -> str:
    """Quick defang of arbitrary text."""
    return IndicatorDefanger.defang_string(text)
