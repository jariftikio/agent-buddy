# Hermes Agent Setup Guide

## Overview

Hermes is a comprehensive, modular automation system for your local environment with:
- **Web Search Module**: Query public APIs (SerpApi/Tavily) for real-time information
- **System Monitor Module**: Track CPU, memory, and network ports locally

Both modules feature proper error handling, logging, and secure environment variable management.

## Quick Setup (5 minutes)

### Step 1: Install Dependencies

```bash
pip install -r hermes_modules/requirements.txt
```

**Core dependencies:**
- `requests` - HTTP client for API calls
- `psutil` - System monitoring
- `python-dotenv` - Environment variable management

### Step 2: Configure Web Search (Optional)

Choose **one** search provider:

#### SerpApi (Easiest)
1. Sign up: https://serpapi.com/users/sign_up (free tier: 100/month)
2. Copy your API key from dashboard
3. Edit `.env` (copy from `.env.example`):
   ```
   HERMES_SEARCH_PROVIDER=serpapi
   SERPAPI_API_KEY=your_api_key_here
   ```

#### Tavily (Free for research)
1. Sign up: https://app.tavily.com (unlimited free tier)
2. Copy your API key
3. Edit `.env`:
   ```
   HERMES_SEARCH_PROVIDER=tavily
   TAVILY_API_KEY=your_api_key_here
   ```

### Step 3: Verify Installation

```bash
python3 << 'EOF'
import sys
sys.path.insert(0, '.')
from hermes_modules import SystemMonitor

monitor = SystemMonitor()
cpu = monitor.get_cpu_usage()
mem = monitor.get_memory_usage()
print(f"✅ CPU: {cpu.percent_used}% | Memory: {mem.percent_used}%")
EOF
```

## Usage Examples

### Web Search

```python
from hermes_modules import WebSearchClient

# Initialize client (uses config from .env)
client = WebSearchClient()

# Perform search
results = client.search("Python automation best practices", max_results=5)

# Display results
for result in results:
    print(f"{result.position}. {result.title}")
    print(f"   {result.url}")
    print(f"   {result.snippet}\n")

# Get as JSON (for agents/APIs)
json_results = client.search_as_json("your query")
```

### System Monitoring

```python
from hermes_modules import SystemMonitor
import json

monitor = SystemMonitor()

# Get CPU info
cpu_info = monitor.get_cpu_usage()
print(f"CPU: {cpu_info.percent_used}%")
print(f"Cores: {cpu_info.core_count}")
print(f"Load: {cpu_info.load_average}")

# Get memory info
mem_info = monitor.get_memory_usage()
print(f"Memory: {mem_info.percent_used}%")
print(f"Used: {mem_info.used_gb:.2f}GB / {mem_info.total_gb:.2f}GB")

# Full health report
health = monitor.get_system_health()
print(json.dumps(health, indent=2))

# Check specific port
is_listening = monitor.is_port_listening(8080)
```

### Network Ports (Requires sudo)

```bash
# List listening ports with process names
sudo python3 << 'EOF'
from hermes_modules import SystemMonitor

monitor = SystemMonitor()
ports = monitor.get_listening_ports()

for port in ports[:10]:
    print(f"{port.local_address}:{port.local_port} - {port.process_name}")
EOF
```

## Module Architecture

```
hermes_modules/
├── __init__.py           # Package exports
├── config.py             # Configuration and env vars
├── web_search.py         # Web search client (SerpApi/Tavily)
├── system_monitor.py     # System monitoring (psutil)
├── examples.py           # Complete examples
├── requirements.txt      # Python dependencies
└── README.md             # Full API documentation
```

## Configuration

### Environment Variables (.env)

```bash
# Search Provider
HERMES_SEARCH_PROVIDER=serpapi          # or 'tavily'
SERPAPI_API_KEY=your_serpapi_key
TAVILY_API_KEY=your_tavily_key

# Logging
HERMES_LOG_LEVEL=INFO                   # DEBUG, INFO, WARNING, ERROR
HERMES_LOG_FILE=hermes.log
```

### Config File (hermes_modules/config.py)

Customize thresholds and defaults:

```python
# CPU/Memory alert thresholds (%)
MONITOR_CPU_THRESHOLD = 80.0
MONITOR_MEMORY_THRESHOLD = 85.0

# Search defaults
SEARCH_TIMEOUT = 10              # seconds
SEARCH_MAX_RESULTS = 10
SEARCH_LANGUAGE = "en"
SEARCH_SAFE_MODE = True
```

## Error Handling

All modules include comprehensive error handling:

```python
from hermes_modules import WebSearchClient
from requests.exceptions import Timeout, RequestException

try:
    client = WebSearchClient()
    results = client.search("query")
except ValueError as e:
    print(f"Configuration error: {e}")  # Missing API key
except Timeout:
    print("Request timed out")
except RequestException as e:
    print(f"API error: {e}")
```

## Logging

Enable detailed logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

from hermes_modules import SystemMonitor
monitor = SystemMonitor(enable_logging=True, log_level="DEBUG")
```

Or via environment:
```bash
export HERMES_LOG_LEVEL=DEBUG
```

## Security Checklist

✅ **Implemented:**
- API keys never logged (redacted as `***REDACTED***`)
- Environment variable protection
- Safe search enabled by default
- Input validation on all queries
- Timeout on API requests
- Error handling without exposing secrets

⚠️ **Best Practices:**
- Never commit `.env` file (already in .gitignore)
- Rotate API keys periodically
- Use separate keys for dev/production
- Monitor your API usage quota
- Review API provider terms of service

## Troubleshooting

### "No API key found" Error

```bash
# Check .env file exists
ls -la .env

# Verify environment variables
echo $SERPAPI_API_KEY

# Source .env if needed
export $(cat .env | xargs)
```

### Network Port Permission Denied

Normal on macOS/Linux - run with sudo:
```bash
sudo python3 your_script.py
```

Or handle in code:
```python
from hermes_modules import SystemMonitor

monitor = SystemMonitor()
try:
    ports = monitor.get_listening_ports()
except PermissionError:
    print("Run with sudo for full port information")
```

### SSL Warning with urllib3

This is benign on macOS and doesn't affect functionality. To suppress:
```bash
export PYTHONWARNINGS=ignore
```

### API Rate Limiting

- **SerpApi**: 100 free queries/month, then paid
- **Tavily**: Unlimited free tier for research

Monitor usage and upgrade if needed.

## Advanced Usage

### Custom Search Provider Configuration

```python
from hermes_modules import WebSearchClient

# Override config
client = WebSearchClient(
    provider="tavily",
    api_key="your_key",
    timeout=15
)
```

### Integrated Monitoring Workflow

```python
from hermes_modules import SystemMonitor, WebSearchClient

monitor = SystemMonitor()
search = WebSearchClient()

# Check system health
health = monitor.get_system_health()

# If alerts, search for solutions
if health["alerts"]:
    for alert in health["alerts"]:
        print(f"Alert: {alert}")
        results = search.search(alert, max_results=3)
        for r in results:
            print(f"  → {r.title}")
```

## Testing

Run the built-in examples:

```bash
cd hermes_modules
python3 examples.py
```

Uncomment examples in `examples.py` to run:
- `example_system_monitor()` - Local monitoring
- `example_web_search()` - Search API (requires config)
- `example_integrated_workflow()` - Combined example

## Next Steps

1. ✅ Install dependencies: `pip install -r hermes_modules/requirements.txt`
2. ✅ Copy `.env.example` to `.env` and add API key (optional)
3. ✅ Test: `python3 hermes_modules/examples.py`
4. ✅ Integrate into your Hermes agent

## Support & Resources

- **API Docs**: Check README.md in hermes_modules/
- **Examples**: See examples.py for complete usage
- **Config**: Review config.py for all options
- **Logging**: Enable DEBUG logging for troubleshooting

## License

For personal use and local automation. Respect API provider terms.
