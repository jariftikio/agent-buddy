#!/usr/bin/env python3
"""
Test suite for LogMonitor security auditing module.

Tests:
1. Log stream parsing with file I/O safety
2. Authentication anomaly detection
3. Injection pattern detection
4. Rate limiting violation detection
5. Bengali alert formatting
"""

import sys
import json
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from services.log_monitor import (
    LogStreamParser,
    AnomalyDetector,
    SecureReporter,
    LogMonitor,
    AnomalyLevel,
)


class LogMonitorTestSuite:
    """Comprehensive test suite for log monitoring"""

    def __init__(self):
        self.test_count = 0
        self.passed = 0
        self.failed = 0

    def test_log_stream_parsing(self):
        """Test safe log file I/O"""
        print("\n" + "="*70)
        print("TEST 1: Log Stream Parsing")
        print("="*70)

        self.test_count += 1

        try:
            # Create temporary log file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
                log_file = f.name
                f.write("2026-10-26 14:23:45 [INFO] Application started\n")
                f.write("2026-10-26 14:24:00 [INFO] User login successful\n")
                f.write("2026-10-26 14:25:00 [ERROR] Error occurred\n")

            # Test parser
            parser = LogStreamParser(log_file)
            lines = parser.stream_lines()

            assert len(lines) == 3, f"Expected 3 lines, got {len(lines)}"
            assert "Application started" in lines[0]
            assert "User login" in lines[1]
            assert "Error occurred" in lines[2]

            print("✅ Log parsing: Read 3 lines successfully")
            print(f"   Line 1: {lines[0][:50]}...")
            print(f"   Line 2: {lines[1][:50]}...")
            print(f"   Line 3: {lines[2][:50]}...")

            # Clean up
            Path(log_file).unlink()
            self.passed += 1

        except Exception as e:
            print(f"❌ Log parsing failed: {e}")
            self.failed += 1

    def test_auth_anomaly_detection(self):
        """Test repeated authentication failure detection"""
        print("\n" + "="*70)
        print("TEST 2: Authentication Anomaly Detection")
        print("="*70)

        self.test_count += 1

        try:
            detector = AnomalyDetector()

            # Simulate repeated failed auth attempts
            test_logs = [
                "2026-10-26 14:23:45 [ERROR] Authentication failed for user admin from 192.168.1.100",
                "2026-10-26 14:23:50 [ERROR] Invalid credentials attempt from 192.168.1.100",
                "2026-10-26 14:24:01 [ERROR] Access denied - authentication failed from 192.168.1.100",
                "2026-10-26 14:24:15 [ERROR] Login failed for 192.168.1.100",
                "2026-10-26 14:24:30 [ERROR] Unauthorized from 192.168.1.100",
            ]

            anomalies = []
            for log_line in test_logs:
                detected = detector.analyze_line(log_line)
                anomalies.extend(detected)

            # Should detect at least one auth anomaly
            auth_anomalies = [a for a in anomalies if a.get("type") == "auth_anomaly"]

            if auth_anomalies:
                print(f"✅ Auth anomaly detected after {len(test_logs)} attempts")
                anomaly = auth_anomalies[0]
                print(f"   Source IP: {anomaly.get('source_ip')}")
                print(f"   Failed attempts: {anomaly.get('failed_attempts')}")
                print(f"   Threshold: {anomaly.get('threshold')}")
                self.passed += 1
            else:
                print("❌ No auth anomaly detected")
                self.failed += 1

        except Exception as e:
            print(f"❌ Auth anomaly detection failed: {e}")
            self.failed += 1

    def test_injection_pattern_detection(self):
        """Test detection of SQL/XSS/path traversal attempts"""
        print("\n" + "="*70)
        print("TEST 3: Injection Pattern Detection")
        print("="*70)

        self.test_count += 1

        try:
            detector = AnomalyDetector()

            # Test cases with injection patterns
            test_cases = [
                ("Path traversal", "GET /api/file?path=../../etc/passwd HTTP/1.1"),
                ("SQL injection", "POST /api/query - q=UNION SELECT * FROM users"),
                ("XSS attempt", "GET /search?q=<script>alert('xss')</script>"),
                ("Command injection", "GET /admin?cmd=exec(/bin/bash)"),
            ]

            detected_patterns = 0
            for pattern_name, log_line in test_cases:
                anomalies = detector.analyze_line(log_line)
                param_anomalies = [a for a in anomalies if a.get("type") == "invalid_param_anomaly"]

                if param_anomalies:
                    print(f"✅ {pattern_name}: Detected")
                    detected_patterns += 1
                else:
                    print(f"⚠️  {pattern_name}: Not detected")

            if detected_patterns >= 2:
                print(f"\n✅ Injection pattern detection working ({detected_patterns}/4 patterns)")
                self.passed += 1
            else:
                print(f"\n❌ Limited pattern detection ({detected_patterns}/4 patterns)")
                self.failed += 1

        except Exception as e:
            print(f"❌ Injection detection failed: {e}")
            self.failed += 1

    def test_rate_anomaly_detection(self):
        """Test rate limiting violation detection"""
        print("\n" + "="*70)
        print("TEST 4: Rate Limiting Anomaly Detection")
        print("="*70)

        self.test_count += 1

        try:
            detector = AnomalyDetector()

            # Simulate rapid requests from same IP
            anomalies = []
            for i in range(55):  # Above threshold of 50
                log_line = f"2026-10-26 14:25:{i%60:02d} GET /api/search HTTP/1.1 from 192.168.1.110"
                detected = detector.analyze_line(log_line)
                anomalies.extend(detected)

            rate_anomalies = [a for a in anomalies if a.get("type") == "rate_anomaly"]

            if rate_anomalies:
                print(f"✅ Rate anomaly detected")
                anomaly = rate_anomalies[0]
                print(f"   Source IP: {anomaly.get('source_ip')}")
                print(f"   Request count: {anomaly.get('request_count')}")
                print(f"   Threshold: {anomaly.get('threshold')}")
                self.passed += 1
            else:
                print("❌ No rate anomaly detected")
                self.failed += 1

        except Exception as e:
            print(f"❌ Rate anomaly detection failed: {e}")
            self.failed += 1

    def test_bengali_alert_formatting(self):
        """Test Bengali-formatted security alerts"""
        print("\n" + "="*70)
        print("TEST 5: Bengali Alert Formatting")
        print("="*70)

        self.test_count += 1

        try:
            detector = AnomalyDetector()
            reporter = SecureReporter()

            # Create an anomaly
            test_log = "2026-10-26 14:23:45 [ERROR] Authentication failed from 192.168.1.100"

            # Simulate multiple attempts to trigger anomaly
            for _ in range(5):
                detector.analyze_line(test_log)

            # Get the anomaly
            anomalies = detector.analyze_line(test_log)

            if anomalies:
                anomaly = anomalies[0]

                # Generate Bengali alert
                alert_bn = reporter.generate_alert(
                    anomaly,
                    AnomalyLevel.CRITICAL,
                    language="bn"
                )

                # Generate English alert
                alert_en = reporter.generate_alert(
                    anomaly,
                    AnomalyLevel.CRITICAL,
                    language="en"
                )

                # Check Bengali content
                assert "প্রমাণীকরণ" in alert_bn["title"] or "🔐" in alert_bn["title"], "Bengali title missing"
                assert "bengali" not in alert_bn["language"] or alert_bn["language"] == "bn", "Language mismatch"

                print("✅ Bengali alert generated")
                print(f"   Title: {alert_bn['title']}")
                print(f"   Severity: {alert_bn['severity']}")

                # Check markdown formatting
                markdown_bn = reporter.format_markdown_alert(alert_bn)
                assert len(markdown_bn) > 0, "Markdown formatting failed"
                assert "সময়" in markdown_bn, "Bengali markdown missing Bengali text"

                print("✅ Bengali markdown formatted")
                print(f"   Length: {len(markdown_bn)} characters")

                # Check English alert
                assert "Authentication" in alert_en["title"] or "🔐" in alert_en["title"], "English title missing"
                print("✅ English alert generated")
                print(f"   Title: {alert_en['title']}")

                self.passed += 1
            else:
                print("❌ No anomaly generated for alert test")
                self.failed += 1

        except Exception as e:
            print(f"❌ Bengali alert formatting failed: {e}")
            self.failed += 1

    def test_full_monitoring_pipeline(self):
        """Test complete monitoring workflow"""
        print("\n" + "="*70)
        print("TEST 6: Full Monitoring Pipeline")
        print("="*70)

        self.test_count += 1

        try:
            # Create temporary log file with mixed content
            with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
                log_file = f.name
                f.write("""2026-10-26 14:23:45 [INFO] Application started
2026-10-26 14:23:50 [ERROR] Authentication failed from 192.168.1.100
2026-10-26 14:24:00 [ERROR] Invalid credentials from 192.168.1.100
2026-10-26 14:24:15 [ERROR] Access denied from 192.168.1.100
2026-10-26 14:24:30 [ERROR] Login failed from 192.168.1.100
2026-10-26 14:24:45 [ERROR] Auth error from 192.168.1.100
2026-10-26 14:25:00 [WARN] GET /api?q=../../etc/passwd
2026-10-26 14:25:30 [WARN] POST /search?q=UNION SELECT *
2026-10-26 14:26:00 [INFO] Normal request processed
""")

            # Run monitoring pipeline
            monitor = LogMonitor(log_file)
            lines = monitor.parser.stream_lines()

            assert len(lines) > 0, "No lines parsed"

            report = monitor.process_batch(lines, language="bn")

            # Verify report structure
            assert "alerts" in report, "No alerts in report"
            assert "anomalies_detected" in report, "No anomaly count"

            # Check for detected anomalies
            anomalies_found = report.get("anomalies_detected", 0)
            alerts_generated = len(report.get("alerts", []))

            if alerts_generated > 0:
                print(f"✅ Full pipeline executed")
                print(f"   Lines processed: {report['lines_processed']}")
                print(f"   Anomalies detected: {anomalies_found}")
                print(f"   Alerts generated: {alerts_generated}")

                # Display sample alert
                if report["alerts"]:
                    alert = report["alerts"][0]
                    print(f"   Sample alert: {alert['title']}")

                summary = monitor.get_summary()
                print(f"   Total alerts: {summary['total_alerts']}")
                print(f"   Critical: {summary['critical_alerts']}")
                print(f"   Warnings: {summary['warning_alerts']}")

                self.passed += 1
            else:
                print("❌ No alerts generated")
                self.failed += 1

            # Clean up
            Path(log_file).unlink()

        except Exception as e:
            print(f"❌ Full pipeline failed: {e}")
            import traceback
            traceback.print_exc()
            self.failed += 1

    def run_all_tests(self):
        """Run all test suites"""
        print("\n" + "╔" + "="*68 + "╗")
        print("║" + " "*68 + "║")
        print("║" + "  LOG MONITOR - SECURITY AUDITING TEST SUITE".center(68) + "║")
        print("║" + " "*68 + "║")
        print("╚" + "="*68 + "╝")

        self.test_log_stream_parsing()
        self.test_auth_anomaly_detection()
        self.test_injection_pattern_detection()
        self.test_rate_anomaly_detection()
        self.test_bengali_alert_formatting()
        self.test_full_monitoring_pipeline()

        # Summary
        print("\n" + "="*70)
        print("TEST SUMMARY")
        print("="*70)
        print(f"Total tests: {self.test_count}")
        print(f"✅ Passed: {self.passed}")
        print(f"❌ Failed: {self.failed}")
        print(f"Success rate: {(self.passed/self.test_count)*100:.1f}%")
        print("="*70)

        if self.failed == 0:
            print("\n✅ ALL TESTS PASSED - LOG MONITOR READY FOR DEPLOYMENT\n")
        else:
            print(f"\n⚠️  {self.failed} TEST(S) FAILED - REVIEW REQUIRED\n")


if __name__ == "__main__":
    tester = LogMonitorTestSuite()
    tester.run_all_tests()
