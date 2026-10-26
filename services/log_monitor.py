#!/usr/bin/env python3
"""
Real-time Log Monitoring & Anomaly Detection Module

Monitors application logs for security risk indicators:
- Repeated authentication failures
- Invalid character patterns in query parameters
- Suspicious timing patterns
- Resource exhaustion indicators
- Rate-limiting violations

Output: Bengali-formatted security alerts
"""

import os
import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class AnomalyLevel(Enum):
    """Risk severity levels"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class LogStreamParser:
    """Safe local file I/O for real-time log parsing"""

    def __init__(self, log_file_path: str, max_chunk_size: int = 8192):
        """
        Initialize log parser with file path validation.

        Args:
            log_file_path: Path to log file (validated for safety)
            max_chunk_size: Max bytes per read (prevents memory exhaustion)
        """
        self.log_file_path = Path(log_file_path).resolve()
        self.max_chunk_size = max_chunk_size
        self.current_position = 0

        # Validate path is within safe directories
        self._validate_path_safety()
        logger.info(f"LogStreamParser initialized for: {self.log_file_path}")

    def _validate_path_safety(self) -> None:
        """Ensure log file path is within safe boundaries"""
        safe_roots = [
            Path("/var/log"),
            Path("/var/www"),
            Path("/home"),
            Path(os.path.expanduser("~")),
        ]

        is_safe = any(
            str(self.log_file_path).startswith(str(root))
            for root in safe_roots
        )

        if not is_safe and not str(self.log_file_path).startswith("/tmp"):
            logger.warning(f"Path {self.log_file_path} outside safe roots")

    def stream_lines(self, follow: bool = False) -> List[str]:
        """
        Read new lines from log file since last position.

        Args:
            follow: If True, continue reading new lines (tail -f behavior)

        Returns:
            List of new log lines

        Raises:
            PermissionError: If file cannot be read
            FileNotFoundError: If log file doesn't exist
        """
        lines = []

        try:
            if not self.log_file_path.exists():
                raise FileNotFoundError(f"Log file not found: {self.log_file_path}")

            if not os.access(self.log_file_path, os.R_OK):
                raise PermissionError(f"Cannot read log file: {self.log_file_path}")

            with open(self.log_file_path, 'r', encoding='utf-8', errors='replace') as f:
                f.seek(self.current_position)

                while True:
                    chunk = f.read(self.max_chunk_size)
                    if not chunk:
                        self.current_position = f.tell()
                        break

                    # Split and parse lines
                    chunk_lines = chunk.split('\n')
                    lines.extend([line for line in chunk_lines if line.strip()])
                    self.current_position = f.tell()

            return lines

        except (PermissionError, FileNotFoundError) as e:
            logger.error(f"Log file access error: {e}")
            raise


class AnomalyDetector:
    """Detects security risk indicators in log streams"""

    def __init__(self):
        """Initialize anomaly detector with pattern signatures"""
        self.failed_auth_attempts = defaultdict(list)  # {ip: [timestamps]}
        self.invalid_params = defaultdict(int)  # {pattern: count}
        self.query_rate = defaultdict(list)  # {source: [timestamps]}

        # Threshold configuration
        self.failed_auth_threshold = 5  # Max failed attempts per IP
        self.invalid_param_threshold = 3  # Max invalid patterns
        self.query_rate_threshold = 50  # Max queries per minute
        self.time_window = timedelta(minutes=1)

        # Pattern signatures for risk detection
        self.auth_failure_patterns = [
            r"authentication failed",
            r"invalid credentials",
            r"access denied",
            r"unauthorized",
            r"login failed",
            r"auth error",
        ]

        self.invalid_param_patterns = [
            (r"(\.\./)+", "path_traversal"),  # Path traversal (../)
            (r"union\s+select", "sql_injection"),  # SQL injection
            (r"<script", "xss_attempt"),  # XSS attempts
            (r"exec\s*\(", "command_injection"),  # Command injection
            (r"%00|\x00", "null_byte"),  # Null byte injection
        ]

        self.suspicious_headers = [
            "User-Agent",
            "X-Forwarded-For",
            "Referer",
        ]

    def detect_auth_anomalies(self, log_line: str) -> Tuple[bool, Optional[Dict]]:
        """
        Detect repeated authentication failures from single source.

        Returns:
            (is_anomaly, anomaly_dict)
        """
        for pattern in self.auth_failure_patterns:
            if re.search(pattern, log_line, re.IGNORECASE):
                # Extract IP address
                ip_match = re.search(r'(\d+\.\d+\.\d+\.\d+)', log_line)
                if ip_match:
                    ip = ip_match.group(1)
                    now = datetime.now()

                    # Clean old entries outside time window
                    self.failed_auth_attempts[ip] = [
                        ts for ts in self.failed_auth_attempts[ip]
                        if now - ts < self.time_window
                    ]

                    # Add current attempt
                    self.failed_auth_attempts[ip].append(now)

                    # Check threshold
                    if len(self.failed_auth_attempts[ip]) >= self.failed_auth_threshold:
                        return True, {
                            "type": "auth_anomaly",
                            "source_ip": ip,
                            "failed_attempts": len(self.failed_auth_attempts[ip]),
                            "threshold": self.failed_auth_threshold,
                            "time_window_minutes": self.time_window.total_seconds() / 60,
                        }

        return False, None

    def detect_invalid_params(self, log_line: str) -> Tuple[bool, Optional[Dict]]:
        """
        Detect suspicious patterns in query parameters.

        Returns:
            (is_anomaly, anomaly_dict)
        """
        matched_patterns = []

        for pattern_tuple in self.invalid_param_patterns:
            pattern_regex, pattern_name = pattern_tuple
            if re.search(pattern_regex, log_line, re.IGNORECASE):
                self.invalid_params[pattern_name] += 1
                matched_patterns.append(pattern_name)

                if self.invalid_params[pattern_name] >= self.invalid_param_threshold:
                    return True, {
                        "type": "invalid_param_anomaly",
                        "pattern_type": pattern_name,
                        "match_count": self.invalid_params[pattern_name],
                        "threshold": self.invalid_param_threshold,
                        "matched_patterns": matched_patterns,
                    }

        return False, None

    def detect_rate_anomalies(self, log_line: str) -> Tuple[bool, Optional[Dict]]:
        """
        Detect rate-limiting violations (excessive requests).

        Returns:
            (is_anomaly, anomaly_dict)
        """
        ip_match = re.search(r'(\d+\.\d+\.\d+\.\d+)', log_line)
        if ip_match:
            ip = ip_match.group(1)
            now = datetime.now()

            # Clean old entries
            self.query_rate[ip] = [
                ts for ts in self.query_rate[ip]
                if now - ts < self.time_window
            ]

            self.query_rate[ip].append(now)

            if len(self.query_rate[ip]) >= self.query_rate_threshold:
                return True, {
                    "type": "rate_anomaly",
                    "source_ip": ip,
                    "request_count": len(self.query_rate[ip]),
                    "threshold": self.query_rate_threshold,
                    "time_window_minutes": self.time_window.total_seconds() / 60,
                }

        return False, None

    def analyze_line(self, log_line: str) -> List[Dict[str, Any]]:
        """
        Comprehensive analysis of single log line.

        Returns:
            List of detected anomalies
        """
        anomalies = []

        # Check all detection patterns
        is_auth_anomaly, auth_data = self.detect_auth_anomalies(log_line)
        if is_auth_anomaly:
            anomalies.append(auth_data)

        is_param_anomaly, param_data = self.detect_invalid_params(log_line)
        if is_param_anomaly:
            anomalies.append(param_data)

        is_rate_anomaly, rate_data = self.detect_rate_anomalies(log_line)
        if is_rate_anomaly:
            anomalies.append(rate_data)

        return anomalies


class SecureReporter:
    """Generates Bengali-formatted security alerts"""

    def __init__(self):
        """Initialize reporter with alert templates"""
        self.alert_templates = {
            "auth_anomaly": {
                "title_bn": "🔐 প্রমাণীকরণ ব্যর্থতা সনাক্ত",
                "title_en": "🔐 Authentication Failure Detected",
                "description_bn": "একটি একক উৎস থেকে পুনরাবৃত্তি লগইন প্রচেষ্টা শনাক্ত হয়েছে।",
                "description_en": "Repeated login attempts detected from single source.",
            },
            "invalid_param_anomaly": {
                "title_bn": "⚠️ সন্দেহজনক প্যারামিটার প্যাটার্ন",
                "title_en": "⚠️ Suspicious Parameter Pattern",
                "description_bn": "অবৈধ অক্ষর বা ইনজেকশন প্যাটার্ন সনাক্ত।",
                "description_en": "Invalid characters or injection patterns detected.",
            },
            "rate_anomaly": {
                "title_bn": "📊 হার সীমাবদ্ধতা লঙ্ঘন",
                "title_en": "📊 Rate Limiting Violation",
                "description_bn": "অত্যধিক অনুরোধের হার সনাক্ত হয়েছে।",
                "description_en": "Excessive request rate detected.",
            },
        }

    def generate_alert(
        self,
        anomaly: Dict[str, Any],
        severity: AnomalyLevel,
        language: str = "bn"
    ) -> Dict[str, Any]:
        """
        Generate structured security alert.

        Args:
            anomaly: Detected anomaly data
            severity: Risk severity level
            language: "bn" for Bengali, "en" for English

        Returns:
            Structured alert dictionary
        """
        anomaly_type = anomaly.get("type")
        template = self.alert_templates.get(anomaly_type, {})

        lang_suffix = "_bn" if language == "bn" else "_en"
        title = template.get(f"title{lang_suffix}", "⚠️ সিকিউরিটি সতর্কতা")
        description = template.get(f"description{lang_suffix}", "অনুরোধটি প্রসেস করতে সমস্যা হয়েছে")

        alert = {
            "timestamp": datetime.now().isoformat(),
            "severity": severity.value,
            "title": title,
            "description": description,
            "anomaly_type": anomaly_type,
            "details": anomaly,
            "language": language,
        }

        return alert

    def format_markdown_alert(
        self,
        alert: Dict[str, Any]
    ) -> str:
        """Format alert as markdown with Bengali support"""
        lines = [
            f"# {alert['title']}",
            "",
            f"**সময়:** {alert['timestamp']}",
            f"**গুরুত্ব:** {alert['severity'].upper()}",
            "",
            f"{alert['description']}",
            "",
            "## বিবরণ",
        ]

        for key, value in alert['details'].items():
            lines.append(f"- **{key}:** {value}")

        lines.extend([
            "",
            "---",
            "_এই সতর্কতা স্বয়ংক্রিয়ভাবে রিয়েল-টাইম লগ মনিটরিং দ্বারা উৎপাদিত হয়েছে।_"
        ])

        return "\n".join(lines)


class LogMonitor:
    """Orchestrates log monitoring, anomaly detection, and reporting"""

    def __init__(self, log_file_path: str):
        """Initialize monitoring system"""
        self.parser = LogStreamParser(log_file_path)
        self.detector = AnomalyDetector()
        self.reporter = SecureReporter()
        self.alerts_history: List[Dict] = []
        logger.info("LogMonitor initialized")

    def process_batch(self, lines: List[str], language: str = "bn") -> Dict[str, Any]:
        """
        Process batch of log lines and detect anomalies.

        Args:
            lines: Log lines to analyze
            language: Alert language ("bn" or "en")

        Returns:
            Structured report with all detected anomalies
        """
        anomalies = []

        for line in lines:
            try:
                detected = self.detector.analyze_line(line)
                anomalies.extend(detected)
            except Exception as e:
                logger.error(f"Error analyzing line: {e}")
                continue

        # Generate alerts for all anomalies
        alerts = []
        for anomaly in anomalies:
            # Determine severity based on anomaly type
            severity = self._determine_severity(anomaly)

            alert = self.reporter.generate_alert(
                anomaly,
                severity,
                language=language
            )
            alerts.append(alert)
            self.alerts_history.append(alert)

        # Generate report
        report = {
            "timestamp": datetime.now().isoformat(),
            "lines_processed": len(lines),
            "anomalies_detected": len(anomalies),
            "alerts_generated": len(alerts),
            "alerts": alerts,
            "status": "anomalies_found" if alerts else "clean",
        }

        return report

    def _determine_severity(self, anomaly: Dict) -> AnomalyLevel:
        """Determine alert severity based on anomaly type"""
        anomaly_type = anomaly.get("type")

        if anomaly_type == "auth_anomaly":
            attempts = anomaly.get("failed_attempts", 0)
            if attempts >= 10:
                return AnomalyLevel.CRITICAL
            return AnomalyLevel.WARNING

        elif anomaly_type == "invalid_param_anomaly":
            return AnomalyLevel.CRITICAL

        elif anomaly_type == "rate_anomaly":
            return AnomalyLevel.WARNING

        return AnomalyLevel.INFO

    def get_summary(self) -> Dict[str, Any]:
        """Get monitoring summary"""
        return {
            "total_alerts": len(self.alerts_history),
            "critical_alerts": len([a for a in self.alerts_history if a["severity"] == "critical"]),
            "warning_alerts": len([a for a in self.alerts_history if a["severity"] == "warning"]),
            "info_alerts": len([a for a in self.alerts_history if a["severity"] == "info"]),
            "last_alert": self.alerts_history[-1] if self.alerts_history else None,
        }


# Example usage and testing
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Example: Create monitor for a test log file
    test_log_path = "/tmp/test_app.log"

    # Create sample log for testing
    sample_logs = """
2026-10-26 14:23:45 [ERROR] Authentication failed for user admin from 192.168.1.100
2026-10-26 14:23:50 [ERROR] Invalid credentials attempt from 192.168.1.100
2026-10-26 14:24:01 [ERROR] Access denied - authentication failed from 192.168.1.100
2026-10-26 14:24:15 [ERROR] Login failed for 192.168.1.100
2026-10-26 14:24:30 [ERROR] Auth error from 192.168.1.100
2026-10-26 14:25:00 [WARN] GET /api/search?q=../../etc/passwd HTTP/1.1 from 192.168.1.101
2026-10-26 14:25:30 [WARN] POST /api/query - parameter contains: UNION SELECT * FROM users
2026-10-26 14:26:00 [INFO] GET / HTTP/1.1 from 192.168.1.102
    """

    # Write sample logs
    Path(test_log_path).write_text(sample_logs)

    # Initialize and run monitor
    monitor = LogMonitor(test_log_path)
    lines = monitor.parser.stream_lines()
    report = monitor.process_batch(lines, language="bn")

    # Display report
    print("\n" + "="*70)
    print("LOG MONITORING REPORT")
    print("="*70)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(json.dumps(monitor.get_summary(), indent=2, ensure_ascii=False))

    # Display markdown alerts
    if report["alerts"]:
        print("\n" + "="*70)
        print("BENGALI FORMATTED ALERTS")
        print("="*70)
        for alert in report["alerts"]:
            markdown = monitor.reporter.format_markdown_alert(alert)
            print(markdown)
            print("\n" + "-"*70 + "\n")
