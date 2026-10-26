# Hermes Agent Modules

A comprehensive, modular system for local automation with real-time web search and system monitoring capabilities.

## Features

### 🔍 Web Search Module
- Query public web search APIs (SerpApi or Tavily)
- Clean, structured JSON results with titles, snippets, and URLs
- Support for multiple languages and safe search filtering
- Comprehensive error handling and logging
- Secure API key management via environment variables

### 🖥️ System Monitor Module
- Real-time CPU usage and per-core metrics
- Memory usage tracking with GB conversions
- Active network port monitoring with process information
- System health alerts for threshold violations
- Lightweight and easy to integrate

## Installation

### 1. Install Dependencies

```bash
pip install -r hermes_modules/requirements.txt
```

### 2. Configure API Keys

Copy `.env.example` to `.env` and add your API keys:

```bash
cp .env.example .env
```

**Choose one search provider:**

#### Option A: SerpApi (Recommended for ease)
- Sign up: https://serpapi.com/users/sign_up (free tier available)
- Add to `.env`:
  ```
  HERMES_SEARCH_PROVIDER=serpapi
  SERPAPI_API_KEY=your_key_here
  ```

#### Option B: Tavily (Free for research)
- Sign up: https://app.tavily.com (free tier)
- Add to `.env`:
  ```
  HERMES_SEARCH_PROVIDER=tavily
  TAVILY_API_KEY=your_key_here
  ```

## Quick Start

### Web Search

```python
from hermes_modules import WebSearchClient

client = WebSearchClient()
results = client.search("Python best practices", max_results=5)

for result in results:
    print(f"{result.title}")
    print(f"URL: {result.url}")
    print(f"Snippet: {result.snippet}\n")

# Get results as JSON
json_results = client.search_as_json("your query")
```

### System Monitoring

```python
from hermes_modules import SystemMonitor

monitor = SystemMonitor()

# CPU usage
cpu = monitor.get_cpu_usage()
print(f"CPU: {cpu.percent_used}%")

# Memory usage
memory = monitor.get_memory_usage()
print(f"Memory: {memory.percent_used}%")

# Listening ports
ports = monitor.get_listening_ports()
for port in ports[:5]:
    print(f"{port.local_address}:{port.local_port}")

# Full health report
health = monitor.get_system_health()
print(health)
```

## API Reference

### WebSearchClient

#### `__init__(provider=None, api_key=None, timeout=10)`
Initialize the search client. Uses config/env variables if parameters not specified.

#### `search(query, max_results=None, language="en", safe_mode=True) -> List[SearchResult]`
Execute a web search and return structured results.

**Parameters:**
- `query` (str): Search query
- `max_results` (int): Maximum results to return (default: 10)
- `language` (str): Language code (default: "en")
- `safe_mode` (bool): Enable safe search (default: True)

**Returns:** List of `SearchResult` objects with `title`, `snippet`, `url`, and `position`

#### `search_as_json(...) -> List[Dict]`
Same as `search()` but returns JSON-serializable dictionaries.

### SystemMonitor

#### `__init__(enable_logging=True, log_level="INFO")`
Initialize the system monitor with optional logging.

#### `get_cpu_usage(interval=1.0) -> CPUInfo`
Get current CPU usage with per-core breakdown and load averages.

#### `get_memory_usage() -> MemoryInfo`
Get memory usage in GB and percentage.

#### `get_listening_ports(address_family="all") -> List[NetworkPort]`
Get all listening network ports with process information.

**Parameters:**
- `address_family` (str): "all", "inet" (IPv4), or "inet6" (IPv6)

#### `get_system_health() -> Dict`
Comprehensive health report including CPU, memory, ports, and alerts.

#### `is_port_listening(port, address="0.0.0.0") -> bool`
Check if a specific port is currently listening.

#### `get_listening_ports_json(address_family="all") -> List[Dict]`
Get ports as JSON-serializable dictionaries.

## Data Structures

### SearchResult
```python
@dataclass
class SearchResult:
    title: str          # Result title
    snippet: str        # Result snippet/description
    url: str            # Result URL
    position: int       # Rank position (0-indexed)
```

### CPUInfo
```python
@dataclass
class CPUInfo:
    percent_used: float     # Overall CPU percentage
    core_count: int         # Number of cores
    core_usage: List[float] # Per-core percentages
    load_average: tuple     # (1min, 5min, 15min)
```

### MemoryInfo
```python
@dataclass
class MemoryInfo:
    percent_used: float     # Memory percentage
    total_gb: float         # Total memory in GB
    used_gb: float          # Used memory in GB
    available_gb: float     # Available memory in GB
```

### NetworkPort
```python
@dataclass
class NetworkPort:
    local_address: str      # Listening address
    local_port: int         # Listening port
    remote_address: str     # Remote address (if connected)
    remote_port: Optional[int]  # Remote port (if connected)
    status: str             # Connection status
    pid: Optional[int]      # Process ID
    process_name: Optional[str]  # Process name
```

## Configuration

Edit `hermes_modules/config.py` to customize thresholds and defaults:

```python
# CPU/Memory alert thresholds
MONITOR_CPU_THRESHOLD = 80.0       # percentage
MONITOR_MEMORY_THRESHOLD = 85.0    # percentage

# Search defaults
SEARCH_TIMEOUT = 10                # seconds
SEARCH_MAX_RESULTS = 10
SEARCH_LANGUAGE = "en"
SEARCH_SAFE_MODE = True
```

## Examples

Run the examples file:

```bash
cd hermes_modules
python examples.py
```

Uncomment the example functions you want to run:
- `example_web_search()` - Basic search usage
- `example_system_monitor()` - System monitoring
- `example_integrated_workflow()` - Combined workflow

## Error Handling

All modules include comprehensive error handling:

```python
from hermes_modules import WebSearchClient
from requests.exceptions import RequestException, Timeout

try:
    client = WebSearchClient()
    results = client.search("query")
except ValueError as e:
    print(f"Configuration error: {e}")
except Timeout:
    print("Request timed out")
except RequestException as e:
    print(f"API request failed: {e}")
```

## Security Considerations

✅ **Safe defaults implemented:**
- API keys never logged (redacted in logs)
- No credentials stored in code
- Environment variable protection
- Safe search enabled by default
- Timeout on API requests
- Input validation on all queries

⚠️ **Best practices:**
- Never commit `.env` file (ignored in .gitignore)
- Rotate API keys regularly
- Use separate keys for dev/production
- Monitor API usage and rate limits
- Run network monitoring with `sudo` for full port information

## Network Ports & Permissions

On Linux/macOS, listing all network ports may require elevated privileges:

```bash
# With sudo for full access
sudo python -c "from hermes_modules import SystemMonitor; m = SystemMonitor(); print(m.get_listening_ports())"

# Without sudo (limited output)
python examples.py
```

## Logging

Configure logging via environment variables:

```bash
export HERMES_LOG_LEVEL=DEBUG      # DEBUG, INFO, WARNING, ERROR
export HERMES_LOG_FILE=hermes.log
```

## License

Personal use and local automation. Respect API provider terms of service.

## Support

For issues or questions:
1. Check the examples in `examples.py`
2. Review configuration in `config.py`
3. Enable DEBUG logging: `HERMES_LOG_LEVEL=DEBUG`
