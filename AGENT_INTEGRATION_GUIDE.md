# Hermes Agent Integration Guide
## Complete Workflow & Usage Examples

---

## Quick Start (2 minutes)

### 1. Install Dependencies
```bash
pip install -r hermes_modules/requirements.txt
```

### 2. Run the Agent
```bash
python3 main.py
```

### 3. Try Commands
```
🔮 Hermes > Check system health
🔮 Hermes > Is port 8080 listening?
🔮 Hermes > Search for Python tutorials
🔮 Hermes > type 'exit' to quit
```

---

## System Architecture Overview

```
USER INPUT (Natural Language)
    ↓
┌─────────────────────────────────────────┐
│  IntentClassifier                       │
│  "Search for X" → WEB_SEARCH            │
│  "Check CPU" → SYSTEM_MONITOR           │
│  "Port 8080?" → PORT_CHECK              │
│  "Search AND check" → COMBINED          │
└─────────────────────┬───────────────────┘
                      ↓
┌─────────────────────────────────────────┐
│  AgentContext                           │
│  - session_id: unique identifier        │
│  - intent: classified task              │
│  - results: accumulates outcomes        │
└─────────────────────┬───────────────────┘
                      ↓
┌─────────────────────────────────────────┐
│  HermesAgent Task Router                │
│  Executes appropriate handlers          │
└─────────────────────┬───────────────────┘
                      ↓
        ┌─────────────┼─────────────┐
        ↓             ↓             ↓
    ┌────────┐  ┌──────────┐  ┌──────────┐
    │ Search │  │ Monitor  │  │   Port   │
    │ Client │  │ System   │  │  Check   │
    └────────┘  └──────────┘  └──────────┘
        ↓             ↓             ↓
        └─────────────┼─────────────┘
                      ↓
           STRUCTURED RESULTS (JSON)
```

---

## Detailed Execution Flow

### Example 1: Web Search

```
User Input: "Search for Python best practices"
    ↓
IntentClassifier.classify()
    ├─ Detects keywords: "Search", "for"
    ├─ Extracts query: "Python best practices"
    └─ Returns: Intent(
         task_type=WEB_SEARCH,
         primary_query="Python best practices",
         parameters={"search_query": "...", "max_results": 5},
         confidence=0.95
       )
    ↓
AgentContext created with session_id="session_1"
    ↓
HermesAgent._execute_tasks()
    └─ Routes to handler for WEB_SEARCH
       ↓
       WebSearchClient handler
       ├─ Calls search API
       ├─ Returns 5 results
       └─ Creates TaskResult(
            task_type=WEB_SEARCH,
            success=true,
            data={"query": "...", "results": [...]},
            execution_time_ms=125
          )
    ↓
HermesExecutor._format_response()
    └─ Converts to structured JSON
    ↓
HermesUI.display_response()
    └─ Pretty-prints for user:

  ┌─ EXECUTION SUMMARY
  │ ✅ Web Search: Found 5 results for 'Python best practices'
  │
  ├─ CLASSIFIED INTENT
  │ Task Type: WEB_SEARCH
  │ Primary Query: Python best practices
  │ Confidence: 95%
  │
  ├─ RESULT 1: WEB SEARCH
  │ Query: Python best practices
  │ Results: 5
  │
  │   1. PEP 20 -- The Zen of Python
  │      URL: https://www.python.org/dev/peps/pep-0020/
  │      The Zen of Python is a collection of 19 "guiding principles"...
  │
  │   [more results...]
  │
  │ Execution Time: 125.3ms
  └──
```

### Example 2: System Monitoring

```
User Input: "Check CPU and memory"
    ↓
IntentClassifier.classify()
    ├─ Detects keywords: "Check", "CPU", "memory"
    └─ Returns: Intent(
         task_type=SYSTEM_MONITOR,
         primary_query="Check CPU and memory usage",
         confidence=0.95
       )
    ↓
HermesAgent._execute_tasks()
    └─ Routes to SYSTEM_MONITOR handler
       ↓
       SystemMonitor handler
       ├─ Calls monitor.get_cpu_usage()
       │  └─ Returns: CPUInfo(percent_used=45.2, cores=6, ...)
       │
       ├─ Calls monitor.get_memory_usage()
       │  └─ Returns: MemoryInfo(percent_used=72.3, used_gb=5.78, ...)
       │
       └─ Creates TaskResult(
            task_type=SYSTEM_MONITOR,
            success=true,
            data={"cpu": {...}, "memory": {...}},
            execution_time_ms=1200
          )
    ↓
Display:

  ┌─ EXECUTION SUMMARY
  │ ✅ System Monitor: CPU 45.2% | Memory 72.3%
  │
  ├─ RESULT 1: SYSTEM MONITOR
  │ CPU Usage:
  │   Overall: 45.2%
  │   Cores: 6
  │   Load Avg: 2.34
  │
  │ Memory Usage:
  │   Used: 72.3%
  │   5.78GB / 8.00GB
  │
  │ Execution Time: 1200.5ms
  └──
```

### Example 3: Combined Task

```
User Input: "Check system and search for optimization tips"
    ↓
IntentClassifier.classify()
    ├─ Detects both search AND monitor keywords
    └─ Returns: Intent(
         task_type=COMBINED,
         primary_query="optimization tips",
         confidence=0.85
       )
    ↓
HermesAgent._execute_tasks()
    ├─ Detects COMBINED type
    ├─ Executes WEB_SEARCH handler
    │  └─ Returns search results (125ms)
    │
    └─ Executes SYSTEM_MONITOR handler
       └─ Returns system metrics (1200ms)
    ↓
Both results are accumulated in context
    ↓
Display: Shows both results with combined summary
```

---

## Code Integration Examples

### 1. Direct Library Usage

```python
from hermes_modules.agent_core import create_hermes_agent_with_modules

# Create agent with all handlers pre-configured
agent, _ = create_hermes_agent_with_modules()

# Process user input
context = agent.process_input("Check system health")

# Access results
for result in context.results:
    print(f"Task: {result.task_type.value}")
    print(f"Success: {result.success}")
    print(f"Data: {result.data}")
    print(f"Time: {result.execution_time_ms}ms")
```

### 2. Custom Handler Registration

```python
from hermes_modules.agent_core import HermesAgent, TaskType, TaskResult
import time

agent = HermesAgent()

# Define custom handler
def my_custom_handler(context, params):
    start = time.time()
    try:
        # Do custom work
        result = {"custom": "data"}
        return TaskResult(
            task_type=TaskType.SYSTEM_MONITOR,  # or custom type
            success=True,
            data=result,
            execution_time_ms=(time.time() - start) * 1000
        )
    except Exception as e:
        return TaskResult(
            task_type=TaskType.SYSTEM_MONITOR,
            success=False,
            error=str(e)
        )

# Register it
agent.register_handler(TaskType.SYSTEM_MONITOR, my_custom_handler)

# Use it
context = agent.process_input("Check status")
```

### 3. Context Inspection

```python
context = agent.process_input("Search for something")

# Full execution data as JSON
import json
print(json.dumps(context.to_dict(), indent=2))

# Programmatic access
print(f"Session: {context.session_id}")
print(f"Intent Type: {context.intent.task_type.value}")
print(f"Confidence: {context.intent.confidence}")

for result in context.results:
    if result.success:
        # Process result data
        if result.task_type.value == "web_search":
            results = result.data.get("results", [])
            for r in results:
                print(f"- {r['title']}: {r['url']}")
```

### 4. Error Handling

```python
context = agent.process_input("Search for X")

# Check if tasks succeeded
for result in context.results:
    if not result.success:
        print(f"⚠️  {result.task_type.value} failed: {result.error}")
    else:
        print(f"✅ {result.task_type.value} succeeded")

# Handle specific errors
if context.results[0].error and "API_KEY" in context.results[0].error:
    print("Configure API key in .env")
```

---

## Intent Classification Reference

### Keyword Mapping

```
WEB_SEARCH Keywords:
  search, find, look up, query, web, internet, latest, 
  trending, how to, what is, tell me about

SYSTEM_MONITOR Keywords:
  cpu, memory, ram, usage, load, performance, monitor,
  check system, health, status

PORT_CHECK Keywords:
  port, listening, connection, network, process, service

COMBINED Triggers:
  Multiple keywords from different groups in one query
```

### Confidence Scoring

```
Task Type               Confidence  Reason
─────────────────────────────────────────────────
COMBINED                0.85        Multiple intents
WEB_SEARCH (match)      0.95        Clear keywords
SYSTEM_MONITOR (match)  0.95        Clear keywords
PORT_CHECK              0.70        Numbers are ambiguous
UNKNOWN                 0.50        No clear intent
```

---

## Performance Metrics

### Typical Execution Times

```
Task Type          Time Range    Comment
──────────────────────────────────────────
WEB_SEARCH         100-500ms     Network dependent
SYSTEM_MONITOR     500-2000ms    Sampling intervals
HEALTH_REPORT      1000-3000ms   Sampling + port check
PORT_CHECK         1-10ms        Instant check
COMBINED           1500-2500ms   Parallel would be better
```

### Optimization Opportunities

```
Current Sequential:      ~2200ms
  - WEB_SEARCH:   200ms
  - SYSTEM_MONITOR: 2000ms

With Parallel Execution: ~2000ms  (10% faster)
```

---

## Troubleshooting

### Web Search Not Working

**Problem:** 401 Unauthorized error

**Solution:** Configure API key
```bash
# 1. Copy .env.example to .env
cp .env.example .env

# 2. Get API key
# SerpApi: https://serpapi.com/dashboard
# Tavily: https://app.tavily.com/dashboard

# 3. Add to .env
SERPAPI_API_KEY=your_key_here

# 4. Test
python3 main.py
```

### Port Check Returns Empty/Errors

**Problem:** Access denied on macOS/Linux

**Solution:** Run with sudo
```bash
sudo python3 main.py
```

### Intent Not Classified Correctly

**Problem:** Custom query not recognized

**Solution:** Check intent classification manually
```python
from hermes_modules.agent_core import IntentClassifier

intent = IntentClassifier.classify("Your custom query")
print(f"Detected: {intent.task_type.value}")
print(f"Confidence: {intent.confidence}")

# Add keywords if needed (modify IntentClassifier.py)
```

---

## Extending the Agent

### Adding a New Module

**Step 1:** Create module in hermes_modules/
```
hermes_modules/
├── my_module.py        # New module
└── ...
```

**Step 2:** Define handler in main.py or agent_core.py
```python
def handle_my_module(context: AgentContext, params: Dict) -> TaskResult:
    # Implementation
    pass

# Register
agent.register_handler(TaskType.MY_MODULE, handle_my_module)
```

**Step 3:** Add keywords to IntentClassifier
```python
MY_KEYWORDS = {"my", "custom", "keyword"}

# In classify() method:
has_my_intent = any(kw in lower_input for kw in cls.MY_KEYWORDS)
if has_my_intent:
    task_type = TaskType.MY_MODULE
```

### Custom Response Formatting

**Override HermesUI methods:**
```python
class CustomUI(HermesUI):
    @staticmethod
    def print_item(text: str, indent: int = 2) -> None:
        # Custom formatting
        print(f"[CUSTOM] {text}")

executor.ui = CustomUI()
```

---

## JSON API Response Format

Complete example of agent context serialization:

```json
{
  "session_id": "session_1",
  "user_input": "Search for Python and check system",
  "intent": {
    "task_type": "combined",
    "primary_query": "Python",
    "secondary_queries": [],
    "parameters": {
      "search_query": "Python",
      "check_system": true
    },
    "confidence": 0.85
  },
  "results": [
    {
      "task_type": "web_search",
      "success": true,
      "data": {
        "query": "Python",
        "results_count": 5,
        "results": [
          {
            "title": "Welcome to Python.org",
            "snippet": "...",
            "url": "https://www.python.org",
            "position": 1
          }
        ]
      },
      "error": null,
      "execution_time_ms": 125.5,
      "timestamp": "2026-10-26T15:30:45.123456"
    },
    {
      "task_type": "system_monitor",
      "success": true,
      "data": {
        "cpu": {
          "percent_used": 45.2,
          "core_count": 6,
          "core_usage": [50.0, 40.0, ...],
          "load_average": {
            "one_minute": 2.34,
            "five_minutes": 2.10,
            "fifteen_minutes": 1.98
          }
        },
        "memory": {
          "percent_used": 72.3,
          "total_gb": 8.0,
          "used_gb": 5.78,
          "available_gb": 2.22
        }
      },
      "error": null,
      "execution_time_ms": 2010.3,
      "timestamp": "2026-10-26T15:30:46.200000"
    }
  ],
  "summary": "✅ Web Search: Found 5 results for 'Python' | ✅ System Monitor: CPU 45.2% | Memory 72.3%"
}
```

---

## Production Considerations

### Logging Configuration
```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('hermes.log'),
        logging.StreamHandler()
    ]
)
```

### Monitoring & Alerting
```python
for result in context.results:
    if not result.success:
        # Send alert
        send_alert(f"Task {result.task_type.value} failed: {result.error}")
    
    if result.execution_time_ms > 5000:
        # Performance warning
        log_slow_task(result.task_type.value, result.execution_time_ms)
```

### Rate Limiting
```python
# Implement token bucket for API calls
from collections import defaultdict
import time

class RateLimiter:
    def __init__(self, calls_per_minute=60):
        self.calls_per_minute = calls_per_minute
        self.calls = defaultdict(list)
    
    def is_allowed(self, key):
        now = time.time()
        minute_ago = now - 60
        self.calls[key] = [t for t in self.calls[key] if t > minute_ago]
        
        if len(self.calls[key]) < self.calls_per_minute:
            self.calls[key].append(now)
            return True
        return False
```

---

## Next Steps

1. ✅ Run `python3 main.py` and try examples
2. ✅ Review `AGENT_ARCHITECTURE.md` for design details
3. ✅ Integrate into your own application
4. ✅ Add custom task types and handlers
5. ✅ Deploy to production with monitoring

Enjoy Hermes! 🔮
