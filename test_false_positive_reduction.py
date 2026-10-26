#!/usr/bin/env python3
"""
Test suite for false positive reduction in LogMonitor.

Verifies that common non-malicious patterns are no longer flagged:
- Health checks and monitoring pings
- Legitimate crawler traffic
- Documentation and error traces
- Internal IP requests
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from services.log_monitor import AnomalyDetector


class FalsePositiveReductionTests:
    """Test improved filtering logic"""

    def __init__(self):
        self.detector = AnomalyDetector()
        self.passed = 0
        self.failed = 0

    def test_health_checks_excluded(self):
        """Health checks should NOT trigger auth anomalies"""
        print("\n" + "="*70)
        print("TEST 1: Health Check Exclusion")
        print("="*70)

        health_check_logs = [
            "2026-10-26 14:25:00 [INFO] Health check request from 192.168.1.50",
            "2026-10-26 14:25:30 [INFO] Heartbeat ping from 192.168.1.50",
            "2026-10-26 14:26:00 [INFO] Status check from 192.168.1.50",
            "2026-10-26 14:26:30 [INFO] Liveness probe from 192.168.1.50",
            "2026-10-26 14:27:00 [INFO] Readiness check from 192.168.1.50",
        ]

        anomalies = []
        for log in health_check_logs:
            detected = self.detector.analyze_line(log)
            anomalies.extend(detected)

        if not anomalies:
            print("✅ Health checks NOT flagged as anomalies")
            print(f"   Processed {len(health_check_logs)} health check logs")
            print(f"   Anomalies detected: {len(anomalies)} (expected: 0)")
            self.passed += 1
        else:
            print(f"❌ Health checks incorrectly flagged: {len(anomalies)}")
            self.failed += 1

    def test_crawler_traffic_excluded(self):
        """Legitimate crawler traffic should NOT trigger rate anomalies"""
        print("\n" + "="*70)
        print("TEST 2: Legitimate Crawler Exclusion")
        print("="*70)

        crawler_logs = [
            f"2026-10-26 14:25:{i%60:02d} GET /robots.txt HTTP/1.1 bot crawler from 203.0.113.50"
            for i in range(250)  # Many requests, but from crawler
        ]

        anomalies = []
        for log in crawler_logs:
            detected = self.detector.analyze_line(log)
            anomalies.extend(detected)

        rate_anomalies = [a for a in anomalies if a.get("type") == "rate_anomaly"]

        if not rate_anomalies:
            print("✅ Crawler traffic NOT flagged as rate anomaly")
            print(f"   Processed {len(crawler_logs)} crawler requests")
            print(f"   Rate anomalies: {len(rate_anomalies)} (expected: 0)")
            self.passed += 1
        else:
            print(f"❌ Crawler traffic incorrectly flagged: {len(rate_anomalies)}")
            self.failed += 1

    def test_internal_ip_excluded(self):
        """Internal IP requests should NOT trigger rate anomalies"""
        print("\n" + "="*70)
        print("TEST 3: Internal IP Exclusion")
        print("="*70)

        internal_ip_logs = [
            f"2026-10-26 14:25:{i%60:02d} GET /api/status HTTP/1.1 from 192.168.1.100"
            for i in range(250)  # Many requests from internal IP
        ]

        anomalies = []
        for log in internal_ip_logs:
            detected = self.detector.analyze_line(log)
            anomalies.extend(detected)

        rate_anomalies = [a for a in anomalies if a.get("type") == "rate_anomaly"]

        if not rate_anomalies:
            print("✅ Internal IP traffic NOT flagged as rate anomaly")
            print(f"   Processed {len(internal_ip_logs)} requests from 192.168.1.100")
            print(f"   Rate anomalies: {len(rate_anomalies)} (expected: 0)")
            self.passed += 1
        else:
            print(f"❌ Internal IP traffic incorrectly flagged: {len(rate_anomalies)}")
            self.failed += 1

    def test_documentation_queries_excluded(self):
        """Documentation queries should NOT trigger injection anomalies"""
        print("\n" + "="*70)
        print("TEST 4: Documentation Query Exclusion")
        print("="*70)

        doc_queries = [
            "2026-10-26 14:25:00 [INFO] User searched documentation for: UNION documentation",
            "2026-10-26 14:25:30 [INFO] Query: SELECT FROM tutorial",
            "2026-10-26 14:26:00 [INFO] Help search: <script> in JavaScript guide",
            "2026-10-26 14:26:30 [INFO] README: Use ../ for relative paths",
            "2026-10-26 14:27:00 [INFO] Example code: exec() system call",
        ]

        anomalies = []
        for log in doc_queries:
            detected = self.detector.analyze_line(log)
            anomalies.extend(detected)

        injection_anomalies = [a for a in anomalies if a.get("type") == "invalid_param_anomaly"]

        if not injection_anomalies:
            print("✅ Documentation queries NOT flagged as injection")
            print(f"   Processed {len(doc_queries)} documentation queries")
            print(f"   Injection anomalies: {len(injection_anomalies)} (expected: 0)")
            self.passed += 1
        else:
            print(f"❌ Documentation incorrectly flagged: {len(injection_anomalies)}")
            self.failed += 1

    def test_404_logs_not_auth_anomaly(self):
        """404 errors should NOT trigger auth anomalies"""
        print("\n" + "="*70)
        print("TEST 5: 404 Error Logs Exclusion")
        print("="*70)

        # Crawler getting 404s (normal, not a threat)
        not_found_logs = [
            f"2026-10-26 14:25:{i%60:02d} GET /nonexistent-{i} HTTP/1.1 404 from 203.0.113.50"
            for i in range(15)  # Many 404s from external IP
        ]

        anomalies = []
        for log in not_found_logs:
            detected = self.detector.analyze_line(log)
            anomalies.extend(detected)

        if not anomalies:
            print("✅ 404 logs NOT flagged as anomalies")
            print(f"   Processed {len(not_found_logs)} 404 responses")
            print(f"   Anomalies detected: {len(anomalies)} (expected: 0)")
            self.passed += 1
        else:
            print(f"❌ 404 logs incorrectly flagged: {len(anomalies)}")
            self.failed += 1

    def test_legitimate_auth_retries(self):
        """Legitimate auth retries (up to threshold) should NOT trigger"""
        print("\n" + "="*70)
        print("TEST 6: Legitimate Auth Retries (Below Threshold)")
        print("="*70)

        # 9 attempts from external IP (below new threshold of 10)
        retry_logs = [
            f"2026-10-26 14:25:{i*5:02d} [WARN] Authentication failed from 203.0.113.60 (attempt {i+1})"
            for i in range(9)
        ]

        anomalies = []
        for log in retry_logs:
            detected = self.detector.analyze_line(log)
            anomalies.extend(detected)

        auth_anomalies = [a for a in anomalies if a.get("type") == "auth_anomaly"]

        if not auth_anomalies:
            print("✅ Legitimate retries (9 attempts) NOT flagged")
            print(f"   Processed {len(retry_logs)} auth failure logs")
            print(f"   Auth anomalies: {len(auth_anomalies)} (expected: 0)")
            print(f"   Threshold: 10 attempts (increased from 5)")
            self.passed += 1
        else:
            print(f"❌ Legitimate retries incorrectly flagged: {len(auth_anomalies)}")
            self.failed += 1

    def test_real_attack_still_detected(self):
        """Real attacks SHOULD still be detected (verify sensitivity not lost)"""
        print("\n" + "="*70)
        print("TEST 7: Real Attack Detection (Sensitivity Maintained)")
        print("="*70)

        # 15 actual failed attempts (exceeds new threshold of 10)
        attack_logs = [
            f"2026-10-26 14:25:{i*2:02d} [ERROR] Authentication failed from 203.0.113.70"
            for i in range(15)
        ]

        anomalies = []
        for log in attack_logs:
            detected = self.detector.analyze_line(log)
            anomalies.extend(detected)

        auth_anomalies = [a for a in anomalies if a.get("type") == "auth_anomaly"]

        if auth_anomalies:
            print("✅ Real brute force attack DETECTED")
            anomaly = auth_anomalies[0]
            print(f"   Source IP: {anomaly.get('source_ip')}")
            print(f"   Failed attempts: {anomaly.get('failed_attempts')}")
            print(f"   Threshold: {anomaly.get('threshold')}")
            self.passed += 1
        else:
            print(f"❌ Real attack NOT detected: {len(auth_anomalies)}")
            self.failed += 1

    def run_all_tests(self):
        """Run full test suite"""
        print("\n" + "╔" + "="*68 + "╗")
        print("║" + " "*68 + "║")
        print("║" + "  FALSE POSITIVE REDUCTION - ANOMALY DETECTION TESTS".center(68) + "║")
        print("║" + " "*68 + "║")
        print("╚" + "="*68 + "╝")

        self.test_health_checks_excluded()
        self.test_crawler_traffic_excluded()
        self.test_internal_ip_excluded()
        self.test_documentation_queries_excluded()
        self.test_404_logs_not_auth_anomaly()
        self.test_legitimate_auth_retries()
        self.test_real_attack_still_detected()

        # Summary
        print("\n" + "="*70)
        print("TEST SUMMARY")
        print("="*70)
        total = self.passed + self.failed
        print(f"Total tests: {total}")
        print(f"✅ Passed: {self.passed}")
        print(f"❌ Failed: {self.failed}")
        print(f"Success rate: {(self.passed/total)*100:.1f}%")
        print("="*70)

        if self.failed == 0:
            print("\n✅ ALL TESTS PASSED - FALSE POSITIVE REDUCTION VERIFIED\n")
        else:
            print(f"\n⚠️  {self.failed} TEST(S) FAILED - REVIEW REQUIRED\n")


if __name__ == "__main__":
    tester = FalsePositiveReductionTests()
    tester.run_all_tests()
