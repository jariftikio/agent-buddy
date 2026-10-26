# Hermes Agent - Quick Reference Card

## Start Here

```bash
# 1. Install dependencies
pip install -r hermes_modules/requirements.txt

# 2. Configure API key (optional, for web search)
cp .env.example .env
# Edit .env and add SERPAPI_API_KEY or TAVILY_API_KEY

# 3. Run agent
python3 main.py

# 4. Try commands
🔮 Hermes > Search for Python tutorials
🔮 Hermes > Check system health  
🔮 Hermes > Is port 8080 listening?
🔮 Hermes > exit
```

---

## Natural Language Examples

### Web Search
```
"Search for Python best practices"
"Find information about machine learning"
"What is Docker?"
"Look up Node.js tutorials"
```

### System Monitoring
```
"Check CPU usage"
"What's the memory usage?"
"Monitor system health"
"Generate health report"
```

### Port Checking
```
"Is port 8080 listening?"
"Check port 3000"
"Port 22 status?"
```

### Combined
```
"Search for optimization and check system"
"Monitor CPU and find cooling solutions"
```

---

## Code Usage

### Basic Usage
```python
from hermes_modules.agent_core import create_hermes_agent_with_modules

agent, _ = create_hermes_agent_with_modules()
context = agent.process_input("Check system health")

for result in context.results:
    print(f"{result.task_type.value}: {result.success}")
```

### Direct Module Access
```python
from hermes_modules import WebSearchClient, SystemMonitor

# Web search
search = WebSearchClient()
results = search.search("Python tutorials", max_results=5)

# System monitoring  
monitor = SystemMonitor()
cpu = monitor.get_cpu_usage()
memory = monitor.get_memory_usage()
health = monitor.get_system_health()
```

### Custom Handlers
```python
from hermes_modules.agent_core import HermesAgent, TaskType, TaskResult

agent = HermesAgent()

def my_handler(context, params):
    return TaskResult(
        task_type=TaskType.SYSTEM_MONITOR,
        success=True,
        data={"result": "value"}
    )

agent.register_handler(TaskType.SYSTEM_MONITOR, my_handler)
```

---

## Architecture Layers

```
Input → Classification → Routing → Execution → Formatting → Output
```

**Components:**
- **IntentClassifier**: Natural language → Task type
- **HermesAgent**: Routes to handlers
- **AgentContext**: Tracks execution state
- **Handlers**: Execute tasks (Search, Monitor, Port)
- **HermesUI**: Formats output

---

## Task Types

| Type | Keywords | Handler |
|------|----------|---------|
| WEB_SEARCH | search, find, query | WebSearchClient |
| SYSTEM_MONITOR | cpu, memory, usage | SystemMonitor |
| HEALTH_REPORT | health, report | SystemMonitor |
| PORT_CHECK | port, listening | SystemMonitor |
| COMBINED | mixed keywords | Multiple |

---

## Configuration

**Environment Variables (.env):**
```bash
HERMES_SEARCH_PROVIDER=serpapi        # or 'tavily'
SERPAPI_API_KEY=your_key_here
TAVILY_API_KEY=your_key_here
HERMES_LOG_LEVEL=INFO                 # DEBUG, INFO, WARNING, ERROR
```

**Thresholds (hermes_modules/config.py):**
```python
MONITOR_CPU_THRESHOLD = 80.0          # %
MONITOR_MEMORY_THRESHOLD = 85.0       # %
SEARCH_TIMEOUT = 10                   # seconds
SEARCH_MAX_RESULTS = 10
```

---

## Data Structures

### Intent
```python
Intent(
    task_type: TaskType,
    primary_query: str,
    parameters: Dict,
    confidence: float  # 0.5-1.0
)
```

### TaskResult
```python
TaskResult(
    task_type: TaskType,
    success: bool,
    data: Dict,           # Result data
    error: Optional[str], # Error message
    execution_time_ms: float,
    timestamp: datetime
)
```

### AgentContext
```python
AgentContext(
    session_id: str,
    user_input: str,
    intent: Intent,
    results: List[TaskResult],
    metadata: Dict
)
```

---

## Adding New Task Type (4 Steps)

```python
# 1. Add enum
class TaskType(Enum):
    MY_TASK = "my_task"

# 2. Add keywords
MY_KEYWORDS = {"keyword1", "keyword2"}
if any(k in input for k in MY_KEYWORDS):
    task_type = TaskType.MY_TASK

# 3. Create handler
def handle_my_task(context, params):
    return TaskResult(
        task_type=TaskType.MY_TASK,
        success=True,
        data={"key": "value"}
    )

# 4. Register
agent.register_handler(TaskType.MY_TASK, handle_my_task)
```

---

## Performance

| Task | Time | Note |
|------|------|------|
| Web Search | 100-500ms | Network dependent |
| System Monitor | 500-2000ms | Sampling delays |
| Port Check | 1-10ms | Instant |
| Combined | 1500-2500ms | Sequential |

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| 401 API Error | Configure API key in .env |
| Port access denied | Run with `sudo` |
| Intent not recognized | Check keywords in IntentClassifier |
| Slow performance | Network latency (search) or sampling |

---

## Design Patterns

- **Strategy**: Different handlers per task type
- **Factory**: `create_hermes_agent_with_modules()`
- **Context**: AgentContext maintains state
- **Builder**: Incremental context construction

---

## Testing

```bash
python3 test_hermes_modules.py
```

Tests:
- ✓ Module imports
- ✓ System monitoring (CPU, memory)
- ✓ Configuration validation
- ✓ Error handling

---

## Documentation

| Document | Purpose |
|----------|---------|
| AGENT_ARCHITECTURE.md | Technical design (patterns, patterns) |
| AGENT_INTEGRATION_GUIDE.md | Usage examples & integration |
| HERMES_SETUP.md | Setup & configuration |
| hermes_modules/README.md | API reference |
| AGENT_ARCHITECTURE_SUMMARY.txt | Visual overview |

---

## Key Files

```
main.py                          Main execution loop
hermes_modules/
├── agent_core.py               Agent orchestration
├── web_search.py               Search client
├── system_monitor.py           System metrics
├── config.py                   Configuration
└── examples.py                 Usage examples
```

---

## API Reference (Quick)

### IntentClassifier
```python
intent = IntentClassifier.classify("user query")
# Returns: Intent(task_type, primary_query, parameters, confidence)
```

### HermesAgent
```python
agent = HermesAgent()
agent.register_handler(TaskType.X, handler_func)
context = agent.process_input("query")
```

### WebSearchClient
```python
client = WebSearchClient()
results = client.search("query", max_results=5)
json_results = client.search_as_json("query")
```

### SystemMonitor
```python
monitor = SystemMonitor()
cpu = monitor.get_cpu_usage()
memory = monitor.get_memory_usage()
health = monitor.get_system_health()
ports = monitor.get_listening_ports()
listening = monitor.is_port_listening(8080)
```

---

## JSON Output Example

```json
{
  "session_id": "session_1",
  "intent": {
    "task_type": "web_search",
    "primary_query": "Python",
    "confidence": 0.95
  },
  "results": [
    {
      "task_type": "web_search",
      "success": true,
      "data": {
        "results": [
          {
            "title": "...",
            "url": "...",
            "snippet": "..."
          }
        ]
      },
      "execution_time_ms": 125.5
    }
  ],
  "summary": "✅ Web Search: Found 5 results"
}
```

---

## Environment Variables

```bash
# API Keys (choose one)
export SERPAPI_API_KEY=your_key
export TAVILY_API_KEY=your_key

# Configuration
export HERMES_LOG_LEVEL=INFO
export HERMES_LOG_FILE=hermes.log
export HERMES_SEARCH_PROVIDER=serpapi
```

---

## Common Patterns

### Process & Inspect Results
```python
context = agent.process_input(query)
if context.results[0].success:
    data = context.results[0].data
else:
    error = context.results[0].error
```

### Error Handling
```python
try:
    context = agent.process_input(query)
except ValueError as e:
    print(f"Configuration: {e}")
except Exception as e:
    print(f"Execution: {e}")
```

### Batch Processing
```python
queries = [
    "Search for Python",
    "Check system health",
    "Is port 8080 listening?"
]
for query in queries:
    context = agent.process_input(query)
    print(context.to_dict())
```

---

## Production Checklist

- ✓ Configure API keys
- ✓ Enable logging
- ✓ Set up monitoring
- ✓ Add rate limiting
- ✓ Implement error recovery
- ✓ Add health checks
- ✓ Performance monitoring
- ✓ Security review

---

**For detailed documentation, see:**
- `AGENT_ARCHITECTURE.md` - Design deep dive
- `AGENT_INTEGRATION_GUIDE.md` - Complete integration guide
- `hermes_modules/README.md` - Full API reference

---

🔮 **Ready to build?** Start with `python3 main.py` and try a query!
