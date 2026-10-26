# Hermes Agent - Complete Integration Guide

## Overview

The Hermes agent now includes **full end-to-end URL security checking** integrated into the 5-layer architecture. Users can ask natural language questions about URL safety, and the system automatically classifies the intent, extracts the URL, and performs comprehensive security assessment.

---

## Data Flow: User Query → URL Assessment

```
User Input: "Is this URL safe? https://suspicious.com"
     ↓
CompositeIntentClassifier (Layer 2)
  ├─ Keyword tier detects: url, safe → URL_CHECK intent
  └─ Extracts entity: {type: "url", value: "https://suspicious.com"}
     ↓
HermesAgent Routing (Layer 3)
  ├─ Matches TaskType.URL_CHECK
  └─ Dispatches to handler
     ↓
URLSecurityHandler (Layer 1 - Modules)
  ├─ URLSecurityAnalyzer performs:
  │  ├─ Encoding analysis
  │  ├─ IP detection
  │  ├─ Domain structure check
  │  ├─ Port verification
  │  └─ Credential detection
  ├─ IndicatorDefanger creates safe display version
  └─ Returns assessment
     ↓
TaskResult (Layer 4 - Formatting)
  ├─ task_type: "url_check"
  ├─ risk_level: "safe"|"warning"|"critical"
  ├─ indicators: [URLIndicator, ...]
  ├─ defanged_url: "hxxps://suspicious[.]com"
  └─ recommendations: ["...", "..."]
     ↓
HermesUI Display (Layer 5)
  └─ Formatted output with risk assessment and recommendations
```

---

## Quick Start

### 1. Create Agent with URL_CHECK Support

```python
from hermes_modules.agent_core_v2 import create_hermes_agent_with_modules

# Keyword-only (fast)
agent, _ = create_hermes_agent_with_modules(use_llm=False)

# With LLM semantic understanding
from anthropic import Anthropic
client = Anthropic()
agent, _ = create_hermes_agent_with_modules(
    llm_client=client,
    use_llm=True
)
```

### 2. Process URL Security Query

```python
context = agent.process_input("Is https://example.com safe?")

# Access results
for result in context.results:
    if result.task_type.value == "url_check":
        print(f"Risk: {result.data['risk_level']}")
        print(f"Safe: {result.data['safe_to_visit']}")
        print(f"Defanged: {result.data['defanged_url']}")
```

### 3. Example Queries

**Safe URL:**
```
"Check if https://github.com is safe"
→ risk_level: "safe", confidence: 1.0, recommendations: []
```

**Suspicious URL:**
```
"Is https://münchen.example.com phishing?"
→ risk_level: "warning", indicators: [PUNYCODE], 
  recommendations: ["Verify domain against expected..."]
```

**Critical Risk:**
```
"Verify http://admin:password@127.0.0.1"
→ risk_level: "critical", indicators: [EMBEDDED_CREDENTIALS, LOOPBACK_IP],
  recommendations: ["Use headers, not embedded auth...", "Loopback only for local testing..."]
```

---

## Intent Classification Examples

The keyword classifier automatically detects URL check requests:

| Input | Task Type | Confidence | Extracted URL |
|-------|-----------|-----------|---|
| "Is this URL safe: https://site.com" | url_check | 70% | https://site.com |
| "Check if https://link.com is malicious" | url_check | 70% | https://link.com |
| "Verify domain https://example.com" | url_check | 70% | https://example.com |

**URL Keywords Detected:**
- url, link, domain, website, check, safe, phishing, malicious, security, verify, suspicious

---

## Security Assessment Details

### 1. Encoding Analysis (Punycode, Unicode)
Detects IDN homograph attacks and obfuscation techniques.

**Example:**
```
Input: "http://münchen.example.com"
Risk: WARNING
Reason: "Hostname contains non-ASCII characters"
Action: "Verify against expected domain"
```

### 2. IP Address Detection (RFC1918, Loopback)
Identifies raw IPs and private network ranges.

**Example:**
```
Input: "http://192.168.1.1"
Risk: CRITICAL
Reason: "IP is private (RFC1918)"
Action: "Verify internal network access intended"
```

### 3. Domain Structural Analysis
Checks unusual patterns and DNS label limits (>63 chars).

**Example:**
```
Input: "http://extremely-long-domain-name-exceeds-63-chars.com"
Risk: WARNING
Reason: "Domain exceeds DNS label limit"
Action: "Verify against expected domain"
```

### 4. Port Verification
Detects unusual port/protocol combinations.

**Example:**
```
Input: "http://example.com:25"
Risk: WARNING
Reason: "Port 25 (SMTP) unusual for HTTP"
Action: "Verify service running on port 25"
```

### 5. Credential Detection
Flags embedded authentication in URLs (insecure).

**Example:**
```
Input: "http://admin:password@example.com"
Risk: CRITICAL
Reason: "Embedded credentials detected"
Action: "Use authentication headers instead"
```

---

## Risk Level Determination

### CRITICAL
- ANY indicator in: PRIVATE_IP, LOOPBACK_IP, EMBEDDED_CREDENTIALS, PUNYCODE
- Confidence: 0.80-0.95

### WARNING
- 1-2 security indicators detected
- Confidence: 0.85-0.90

### SAFE
- No security indicators
- Confidence: 1.0

---

## Indicator Defanging Examples

Safe display format for logs, markdown, terminals:

| Original | Defanged |
|----------|----------|
| http://evil.com | hxxp://evil[.]com |
| https://phishing.site | hxxps://phishing[.]site |
| admin@attacker.com | admin[at]attacker[.]com |
| 192.168.1.1 | 192[.]168[.]1[.]1 |

---

## Integration with Other Tasks

The URL_CHECK task can be combined with other Hermes capabilities:

```python
# Web search then check results
context = agent.process_input(
    "Search for 'security alerts' and verify the URLs found"
)

# Check system and security
context = agent.process_input(
    "Check system health and verify if my IP is safe"
)
```

---

## Architecture Layers

```
┌─────────────────────────────────────────┐
│  Layer 5: User Interface                │
│  • HermesUI banner & formatting          │
│  • Display risk assessment               │
│  • Show recommendations                  │
└─────────────────────────────────────────┘
             ↑
┌─────────────────────────────────────────┐
│  Layer 4: Result Formatting             │
│  • TaskResult with structured data       │
│  • Execution timing                      │
│  • Entity extraction                     │
└─────────────────────────────────────────┘
             ↑
┌─────────────────────────────────────────┐
│  Layer 3: Agent Orchestration           │
│  • HermesAgent with routing              │
│  • Handler registration & dispatch       │
│  • Context management                    │
└─────────────────────────────────────────┘
             ↑
┌─────────────────────────────────────────┐
│  Layer 2: Intent Classification         │
│  • CompositeIntentClassifier             │
│  • LLM tier (optional semantic)          │
│  • Keyword tier (fast fallback)          │
│  • Entity extraction with confidence     │
└─────────────────────────────────────────┘
             ↑
┌─────────────────────────────────────────┐
│  Layer 1: MODULES (Defensive Security)  │
│  • WebSearchClient                       │
│  • SystemMonitor                         │
│  • URLSecurityHandler ← NEW              │
│    ├─ URLSecurityAnalyzer                │
│    └─ IndicatorDefanger                  │
└─────────────────────────────────────────┘
```

---

## Code Examples

### Direct URLSecurityHandler Usage

```python
from hermes_modules.url_security import assess_url, defang_url

# Quick assessment
assessment = assess_url("https://suspicious.com")
print(f"Risk: {assessment.risk_level.value}")
print(f"Confidence: {assessment.confidence:.0%}")

# Defang for logs
safe_url = defang_url("http://malware.com")
logger.info(f"Flagged: {safe_url}")  # "hxxp://malware[.]com"
```

### Full Agent Flow

```python
from hermes_modules.agent_core_v2 import create_hermes_agent_with_modules

agent, _ = create_hermes_agent_with_modules(enable_logging=True, use_llm=False)

# Process user input
context = agent.process_input("Is this URL safe? https://example.com")

# Inspect results
for result in context.results:
    if result.success:
        data = result.data
        print(f"Risk Level: {data['risk_level']}")
        print(f"Safe: {data['safe_to_visit']}")
        print(f"Defanged: {data['defanged_url']}")
        print(f"Recommendations:")
        for rec in data['recommendations']:
            print(f"  - {rec}")
    else:
        print(f"Error: {result.error}")
```

### LLM-Based Classification

```python
from anthropic import Anthropic
from hermes_modules.agent_core_v2 import create_hermes_agent_with_modules

client = Anthropic()
agent, _ = create_hermes_agent_with_modules(
    llm_client=client,
    use_llm=True,  # Enable LLM tier
    llm_confidence_threshold=0.7
)

# LLM will provide semantic understanding of intent
# Falls back to keyword classifier if LLM confidence < 0.7
context = agent.process_input("Can you check if that domain is legit?")
```

---

## Features Summary

✅ **Automatic Intent Detection**
- Keyword-based fast classification
- Optional LLM-based semantic understanding
- Automatic URL extraction from input

✅ **Defense-in-Depth Security**
- 5 categories of security checks
- Multiple overlapping indicators
- No single check is sufficient

✅ **Safe Display**
- Indicator defanging (hxxp, [.], [at])
- Safe for logs, terminals, markdown
- Prevents accidental link clicks

✅ **Architectural Integration**
- Layer 1 module (no higher-layer dependencies)
- Clean handler registration pattern
- Backward compatible with existing code

✅ **Production Ready**
- Comprehensive logging
- Graceful error handling
- Fail-safe defaults (assume suspicious)

✅ **Zero Breaking Changes**
- New TaskType is additive
- Existing agent works without URL handler
- All other features unchanged

---

## Next Steps

1. **Deploy**: Use the integrated agent in your environment
2. **Monitor**: Check logs for security assessments
3. **Extend**: Add custom URL classification rules if needed
4. **Integrate**: Connect to your security tools (SIEM, ticketing)

---

**Your Hermes agent now includes comprehensive URL security analysis! 🛡️**

For detailed integration instructions, see [URL_SECURITY_INTEGRATION.md](URL_SECURITY_INTEGRATION.md)

For architecture details, see [DEFENSIVE_SECURITY_ARCHITECTURE.txt](DEFENSIVE_SECURITY_ARCHITECTURE.txt)

For quick reference, see [QUICK_REFERENCE.md](QUICK_REFERENCE.md)
