# Hermes Agent v2.0 - Quick Start Guide

## Installation

```bash
# Clone and setup
git clone <repo>
cd agent-buddy-main

# Install dependencies
pip install -r hermes_modules/requirements.txt

# Configure API keys
cp .env.example .env
# Edit .env with your API keys (SerpApi, Tavily optional)
```

## Run the Agent

```bash
python main.py
```

## Example Queries

### Web Search
```
🔮 Hermes > Search for Python async best practices
```

### System Monitoring
```
🔮 Hermes > Check CPU and memory usage
```

### Port Checking
```
🔮 Hermes > Is port 8080 listening?
```

### URL Security (NEW)
```
🔮 Hermes > Is https://example.com safe?
🔮 Hermes > Check if this URL is malicious: https://suspicious.com
🔮 Hermes > Verify domain https://phishing-attempt.com
```

### System Health
```
🔮 Hermes > Generate system health report
```

### Combined Tasks
```
🔮 Hermes > Check system health and search for optimization tips
```

## Programmatic Usage

### Keyword-Only Classification (Fast)
```python
from hermes_modules.agent_core_v2 import create_hermes_agent_with_modules

agent, _ = create_hermes_agent_with_modules(use_llm=False)
context = agent.process_input("Is https://github.com safe?")

for result in context.results:
    print(f"Task: {result.task_type.value}")
    print(f"Success: {result.success}")
    if result.task_type.value == "url_check":
        print(f"Risk: {result.data['risk_level']}")
```

### With LLM Classification (Semantic)
```python
from anthropic import Anthropic
from hermes_modules.agent_core_v2 import create_hermes_agent_with_modules

client = Anthropic()
agent, _ = create_hermes_agent_with_modules(
    llm_client=client,
    use_llm=True
)
context = agent.process_input("Can you verify if that domain is safe?")
```

## URL Security Features

### Risk Levels
- **SAFE**: No security indicators detected (confidence: 1.0)
- **WARNING**: 1-4 indicators detected, manual review recommended (confidence: 0.85-0.90)
- **CRITICAL**: Critical indicators found (confidence: 0.80-0.95)

### Security Checks
1. **Encoding Analysis**: Punycode, Unicode, percent-encoding
2. **IP Detection**: Raw IPs, RFC1918 private ranges, loopback
3. **Domain Structure**: Suspicious patterns, DNS label limits
4. **Port Verification**: Unusual port/protocol combinations
5. **Credential Detection**: Embedded authentication (insecure)

### Example Output
```json
{
  "url": "https://example.com",
  "risk_level": "safe",
  "safe_to_visit": true,
  "defanged_url": "hxxps://example[.]com",
  "assessment": {
    "indicators": [],
    "confidence": 1.0,
    "recommendations": []
  }
}
```

## Direct URLSecurityHandler Usage

```python
from hermes_modules.url_security import assess_url, defang_url

# Quick assessment
assessment = assess_url("https://suspicious.com")
print(f"Risk: {assessment.risk_level.value}")

# Defang for safe display
safe_url = defang_url("http://evil.com")
print(f"Defanged: {safe_url}")  # "hxxp://evil[.]com"
```

## Configuration

### Environment Variables
```bash
# Web Search API
SERPAPI_API_KEY=your_key
TAVILY_API_KEY=your_key

# Optional: LLM Configuration
ANTHROPIC_API_KEY=your_key

# Optional: System Settings
HERMES_LOG_LEVEL=INFO
HERMES_TIMEOUT=10
```

## Architecture at a Glance

```
User Input
    ↓
Intent Classification (Keyword or LLM)
    ↓
Handler Dispatch
    ├─ WebSearchClient (external API)
    ├─ SystemMonitor (local metrics)
    ├─ URLSecurityHandler (security checks) ← NEW
    └─ Port/Health checks
    ↓
Result Formatting
    ↓
User Interface Display
```

## Available Tasks

| Task | Keywords | What It Does |
|------|----------|-------------|
| WEB_SEARCH | search, find, query, research | Query SerpApi/Tavily |
| SYSTEM_MONITOR | cpu, memory, monitor, health | Get system metrics |
| PORT_CHECK | port, listening, connection | Check listening ports |
| HEALTH_REPORT | health, report, status | Full system diagnostics |
| URL_CHECK | url, link, safe, phishing | Security assessment |
| COMBINED | any combination | Execute multiple tasks |

## Troubleshooting

### "URL assessment failed"
→ Invalid URL format or parsing error. Ensure URL starts with `http://` or `https://`

### "No handler registered for url_check"
→ Using old `agent_core.py`. Switch to `agent_core_v2.py` in main.py

### "Web search not configured"
→ Missing SERPAPI_API_KEY. Set via .env or environment variable

### "Permission denied: psutil"
→ macOS requires `sudo` for network connection enumeration. Run with `sudo python main.py`

## Documentation

- **QUICK_REFERENCE.md** - Full API reference
- **HERMES_SETUP.md** - Detailed configuration
- **HERMES_COMPLETE_INTEGRATION.md** - Complete workflow guide
- **DEFENSIVE_SECURITY_ARCHITECTURE.txt** - Security design details
- **HERMES_SYSTEM_COMPLETE.txt** - Full architecture overview

## Key Features

✅ Intelligent intent classification (LLM + Keyword fallback)
✅ Defensive security with defense-in-depth checks
✅ Safe indicator defanging (hxxp, [.], [at])
✅ Graceful error handling and logging
✅ Production-ready with comprehensive testing
✅ Zero breaking changes on upgrades
✅ Standard library only (no security dependencies)

---

**Hermes Agent v2.0 - Ready for Production** 🚀
