# URL Security Handler Integration Guide
## Defensive Security Module (Layer 1)

---

## Architecture Overview

The `URLSecurityHandler` integrates into **Layer 1 (Modules Layer)** of the 5-layer Hermes architecture:

```
┌─────────────────────────────────────────┐
│  Layer 5: User Interface (HermesUI)    │
├─────────────────────────────────────────┤
│  Layer 4: Result Formatting             │
├─────────────────────────────────────────┤
│  Layer 3: Agent Orchestration           │
├─────────────────────────────────────────┤
│  Layer 2: Intent Classification         │
├─────────────────────────────────────────┤
│  Layer 1: MODULES (Defensive)           │
│  ├─ WebSearchClient                     │
│  ├─ SystemMonitor                       │
│  └─ URLSecurityHandler ← NEW            │
└─────────────────────────────────────────┘
```

---

## Quick Start

### 1. Import and Initialize

```python
from hermes_modules.url_security import URLSecurityHandler

handler = URLSecurityHandler()
```

### 2. Assess a URL

```python
result = handler.check_url("https://evil.com/phishing")

print(f"Risk Level: {result['risk_level']}")
print(f"Safe: {result['safe_to_visit']}")
print(f"Defanged: {result['defanged_url']}")
print(f"Recommendations: {result['recommendations']}")
```

### 3. Output

```
Risk Level: warning
Safe: False
Defanged: hxxps://evil[.]com/phishing
Recommendations: 
  - Domain matches suspicious pattern: ...
  - Punycode detected (xn--). Verify the actual domain...
```

---

## Integration with HermesAgent

### Step 1: Add URL_CHECK to Intent Classifiers

Update `hermes_modules/intent_classifiers.py`:

```python
class TaskType(Enum):
    # ... existing types ...
    URL_CHECK = "url_check"  # NEW: Security assessment
    UNKNOWN = "unknown"
```

Add keywords to `IntentClassifier`:

```python
URL_KEYWORDS = {
    "url",
    "check",
    "link",
    "domain",
    "security",
    "safe",
    "verify",
    "phishing",
    "malicious",
}

# In classify() method:
has_url_intent = any(kw in lower_input for kw in cls.URL_KEYWORDS)
if has_url_intent:
    task_type = TaskType.URL_CHECK
    # Extract URL from input
```

### Step 2: Register Handler in Agent

Update `hermes_modules/agent_core_v2.py`:

```python
from .url_security import URLSecurityHandler
import time

# In create_hermes_agent_with_modules():

# Initialize security handler
url_handler = URLSecurityHandler(enable_logging=False)

# URL Check Handler
def handle_url_check(context: AgentContext, intent: Intent) -> TaskResult:
    """Handle URL security assessment tasks."""
    start_time = time.time()
    try:
        # Extract URL from intent
        url = intent.parameters.get("url", intent.primary_query)
        
        # Assess URL
        result = url_handler.check_url(url)
        execution_time_ms = (time.time() - start_time) * 1000

        return TaskResult(
            task_type=TaskType.URL_CHECK,
            success=True,
            data={
                "url": url,
                "defanged_url": result["defanged_url"],
                "risk_level": result["risk_level"],
                "safe_to_visit": result["safe_to_visit"],
                "assessment": result["assessment"],
                "recommendations": result["recommendations"],
                "entities": [
                    {
                        "entity_type": "url",
                        "value": url,
                        "confidence": 0.95,
                    }
                ],
            },
            execution_time_ms=execution_time_ms,
        )
    except Exception as e:
        return TaskResult(
            task_type=TaskType.URL_CHECK,
            success=False,
            data={},
            error=str(e),
        )

# Register handler
agent.register_handler(TaskType.URL_CHECK, handle_url_check)
```

### Step 3: Use It

```python
from hermes_modules.agent_core_v2 import create_hermes_agent_with_modules

agent, _ = create_hermes_agent_with_modules()

# User queries URL security
context = agent.process_input("Is this URL safe? https://suspicious-domain.com")

# Access security assessment
for result in context.results:
    if result.task_type.value == "url_check":
        print(f"Risk: {result.data['risk_level']}")
        print(f"Safe: {result.data['safe_to_visit']}")
        print(f"Defanged: {result.data['defanged_url']}")
```

---

## Core Components

### URLAssessment

Result of security assessment:

```python
@dataclass
class URLAssessment:
    url: str                          # Original URL
    risk_level: RiskLevel             # SAFE, WARNING, CRITICAL
    indicators: List[URLIndicator]    # Detected issues
    confidence: float                 # 0.0-1.0
    reasoning: str                    # Explanation
    recommendations: List[str]        # What to do
    parsed_url: ParseResult           # Components
```

### RiskLevel

```python
class RiskLevel(Enum):
    SAFE = "safe"           # Standard domain, low risk
    WARNING = "warning"     # Suspicious, manual review
    CRITICAL = "critical"   # High-risk, require caution
```

### URLIndicator

Detected security issues:

```python
PUNYCODE               # xn-- (IDN homograph)
PERCENT_ENCODING       # %xx characters
UNICODE_CHARS          # Non-ASCII in hostname
RAW_IP_ADDRESS         # 192.168.1.1 instead of domain
PRIVATE_IP             # RFC1918 ranges
LOOPBACK_IP            # 127.0.0.1, ::1
SUSPICIOUS_DOMAIN      # Unusual patterns
SUSPICIOUS_PORT        # Unexpected port numbers
EMBEDDED_CREDENTIALS   # user:pass in URL
LONG_DOMAIN            # >63 character hostname
```

---

## Security Checks Performed

### 1. Encoding Analysis

```
Input:  "http://münchen.example.com"
Check:  Unicode characters detected
Risk:   WARNING - verify domain is expected

Input:  "http://xn--mnchen-3ya.example.com"
Check:  Punycode (IDN) detected
Risk:   CRITICAL - potential homograph attack
Advice: Verify actual domain matches expected
```

### 2. IP Address Detection

```
Input:  "http://192.168.1.1"
Check:  Raw IP instead of domain name
Risk:   WARNING - if not expected

Input:  "http://10.0.0.1"
Check:  Private IP (RFC1918)
Risk:   CRITICAL - verify internal network access is intended

Input:  "http://127.0.0.1"
Check:  Loopback address
Risk:   CRITICAL - only valid for local testing
```

### 3. Domain Structural Analysis

```
Input:  "http://a-very-long-domain-name-that-exceeds-63-characters.com"
Check:  Domain exceeds DNS label limit
Risk:   WARNING - unusual length
```

### 4. Port Verification

```
Input:  "http://example.com:25"
Check:  Port 25 (SMTP) with HTTP
Risk:   WARNING - unusual for HTTP
Advice: Verify service on port 25
```

### 5. Credential Detection

```
Input:  "http://admin:password@example.com"
Check:  Embedded credentials in URL
Risk:   CRITICAL - insecure authentication
Advice: Use headers, never embed credentials
```

---

## Indicator Defanging

### URL Defanging

```python
from hermes_modules.url_security import IndicatorDefanger

defanger = IndicatorDefanger()

# Before
url = "http://evil.com/malware"

# After
defanged = defanger.defang_url(url)
print(defanged)  # "hxxp://evil[.]com/malware"
```

### Other Defang Operations

```python
# IP address
"192.168.1.1" → "192[.]168[.]1[.]1"

# Domain
"google.com" → "google[.]com"

# Email
"attacker@evil.com" → "attacker[at]evil[.]com"

# Arbitrary text
defanger.defang_string("Check http://bad.com and 10.0.0.1")
# "Check hxxp://bad[.]com and 10[.]0[.]0[.]1"
```

---

## Integration Patterns

### Pattern 1: Query-Based URL Check

```
User: "Check if this domain is safe: suspicious-site.com"
         ↓
Intent: URL_CHECK
         ↓
Handler: assess_url("suspicious-site.com")
         ↓
Output: Risk assessment with recommendations
```

### Pattern 2: Link Extraction from Search Results

```python
# After web search, automatically check discovered URLs
from hermes_modules.url_security import assess_url

search_results = [...]
for result in search_results:
    url = result.get("url")
    assessment = assess_url(url)
    if assessment.risk_level == RiskLevel.CRITICAL:
        logger.warning(f"Risky URL in results: {assessment.url}")
```

### Pattern 3: Log Defanging

```python
# Defang IoCs before writing to logs
from hermes_modules.url_security import defang_string

log_message = f"Suspicious activity: {user_input}"
safe_log = defang_string(log_message)
logger.info(safe_log)  # Safe to log/display
```

---

## Configuration

### Enable/Disable Logging

```python
# Quiet mode (no security logs)
handler = URLSecurityHandler(enable_logging=False)

# Verbose mode (detailed logs)
handler = URLSecurityHandler(enable_logging=True)
```

### Customize Trust List

```python
# Add trusted domains
analyzer = URLSecurityAnalyzer()
analyzer.TRUSTED_DOMAINS.add("company-internal.local")
analyzer.TRUSTED_DOMAINS.add("trusted-vendor.com")
```

### Adjust Suspicious Port List

```python
# Add ports suspicious for HTTPS
analyzer.SUSPICIOUS_PORTS["https"].append(8080)  # Unusual for HTTPS
```

---

## Error Handling

### Graceful Degradation

```python
try:
    assessment = handler.check_url(url)
except Exception as e:
    logger.error(f"URL assessment failed: {e}")
    # Fall back to WARNING level
    return {
        "risk_level": "warning",
        "error": str(e),
    }
```

### Malformed URLs

```
Input:  "not a valid url at all"
Result: CRITICAL risk
Reason: "URL parsing failed"
Advice: "Use standard URL format (http://domain.com)"
```

---

## Example Output

### Safe URL

```json
{
  "original_url": "https://github.com/user/repo",
  "defanged_url": "hxxps://github[.]com/user/repo",
  "assessment": {
    "risk_level": "safe",
    "indicators": [],
    "confidence": 1.0,
    "reasoning": "URL structure is standard. No security concerns detected."
  },
  "safe_to_visit": true,
  "recommendations": []
}
```

### Suspicious URL

```json
{
  "original_url": "http://münchen.example.com",
  "defanged_url": "hxxp://münchen[.]example[.]com",
  "assessment": {
    "risk_level": "warning",
    "indicators": ["unicode_chars"],
    "confidence": 0.9,
    "reasoning": "Hostname contains non-ASCII characters"
  },
  "safe_to_visit": false,
  "recommendations": [
    "Hostname contains non-ASCII characters. Verify against expected domain."
  ]
}
```

### Critical Risk URL

```json
{
  "original_url": "http://admin:secret@127.0.0.1:8080",
  "defanged_url": "hxxp://admin:secret@127[.]0[.]0[.]1:8080",
  "assessment": {
    "risk_level": "critical",
    "indicators": [
      "loopback_ip",
      "embedded_credentials",
      "suspicious_port"
    ],
    "confidence": 0.95,
    "reasoning": "IP is loopback (localhost) | URL contains embedded credentials | Port 8080 is unusual for http"
  },
  "safe_to_visit": false,
  "recommendations": [
    "IP is loopback (127.0.0.1 or ::1). Only valid for local testing.",
    "URL contains embedded credentials (username/password). This is insecure. Use authentication headers instead.",
    "Port 8080 is unusual for http. Verify the service running on this port."
  ]
}
```

---

## Zero Breaking Changes

✅ **Backward Compatible**
- New TaskType (URL_CHECK) doesn't affect existing types
- Optional handler registration (can skip if not needed)
- Agent works fine without URL security handler
- Existing code unchanged

✅ **Integrates Seamlessly**
- Follows existing handler pattern
- Uses same TaskResult format
- Respects logging configuration
- No dependency on other modules

---

## Defense-in-Depth

This module implements **multiple overlapping security checks**:

1. **Encoding Analysis** — IDN, Punycode, percent-encoding
2. **IP Detection** — Raw IPs, private ranges, loopback
3. **Domain Structural** — Unusual patterns, length limits
4. **Protocol Verification** — Port appropriateness
5. **Credential Detection** — Embedded auth data
6. **Defanging** — Safe display of indicators

No single check is sufficient. Multiple indicators increase confidence.

---

## Standards & References

- RFC 1918 — Private IP address ranges
- RFC 3492 — Punycode (IDN encoding)
- RFC 3986 — URI syntax
- OWASP — Phishing prevention
- Unicode Security — Homograph attacks

---

## Usage Examples

### Direct Assessment

```python
from hermes_modules.url_security import assess_url, defang_url

# Quick assessment
assessment = assess_url("https://suspicious.com")
print(f"Risk: {assessment.risk_level.value}")

# Defang for logs
safe_url = defang_url("http://malware.com")
print(safe_url)  # "hxxp://malware[.]com"
```

### Batch Processing

```python
from hermes_modules.url_security import URLSecurityHandler

handler = URLSecurityHandler()

urls = [
    "https://github.com",
    "http://192.168.1.1",
    "https://münchen.example.com",
]

for url in urls:
    result = handler.check_url(url)
    if result["risk_level"] == "critical":
        print(f"ALERT: {result['defanged_url']}")
        print(f"  {result['recommendations']}")
```

### Integration in Search Results

```python
# After web search
def safe_search_results(results):
    handler = URLSecurityHandler()
    safe_results = []
    
    for result in results:
        assessment = handler.check_url(result["url"])
        
        if assessment.risk_level != "critical":
            # Add safety metadata
            result["risk_level"] = assessment.risk_level
            result["safe"] = assessment.risk_level == "safe"
            safe_results.append(result)
    
    return safe_results
```

---

**Your Hermes agent now includes defensive security analysis! 🛡️**

For implementation details, see `hermes_modules/url_security.py`.
