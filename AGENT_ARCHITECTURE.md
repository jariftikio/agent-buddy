# Hermes Agent Architecture
## Lead Software Architect Design Document

### Overview

Hermes is a sophisticated agent execution system that demonstrates professional-grade architecture for natural language task routing and execution. The design prioritizes **separation of concerns**, **extensibility**, **robustness**, and **clarity**.

---

## 1. Architectural Layers

```
┌─────────────────────────────────────────────────────┐
│         User Interface Layer (HermesUI)             │
│  Presents results, prompts, formatting              │
└──────────────────┬──────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────┐
│      Execution Layer (HermesExecutor)               │
│  Orchestrates agent + formats responses             │
└──────────────────┬──────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────┐
│      Core Agent Layer (HermesAgent)                 │
│  Routes tasks to handlers, manages context          │
└──────────────────┬──────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────┐
│    Intent Classification (IntentClassifier)         │
│  Analyzes user input, determines task type          │
└──────────────────┬──────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────┐
│      Module Handlers (Task Executors)               │
│  WebSearchClient • SystemMonitor • Port Checker     │
└─────────────────────────────────────────────────────┘
```

---

## 2. Core Components

### 2.1 IntentClassifier
**Purpose:** Convert natural language into structured task types.

**How it works:**
```
User Input
    ↓
Keyword Matching (search, cpu, port, memory, etc.)
    ↓
Task Type Inference (WEB_SEARCH, SYSTEM_MONITOR, etc.)
    ↓
Parameter Extraction (port numbers, search queries)
    ↓
Confidence Scoring (0.5 to 1.0)
    ↓
Intent Object (task type + parameters)
```

**Example Classifications:**
```
"Search for Python tutorials"
  → TaskType.WEB_SEARCH, primary_query="Python tutorials"

"Check CPU usage"
  → TaskType.SYSTEM_MONITOR, parameters={include_load_average: true}

"Is port 8080 listening?"
  → TaskType.PORT_CHECK, parameters={port: 8080}

"Monitor CPU and search for optimization tips"
  → TaskType.COMBINED, handles both search + monitoring
```

### 2.2 AgentContext
**Purpose:** Maintains execution state throughout a user session.

**Responsibilities:**
- Tracks session ID for audit trails
- Stores original user input
- Holds classified intent
- Accumulates task results
- Carries metadata for extensibility

**Structure:**
```python
AgentContext
├── session_id: str              # Unique identifier
├── user_input: str              # Original query
├── intent: Intent               # Classified task
├── results: List[TaskResult]    # Execution results
└── metadata: Dict               # Custom data
```

### 2.3 HermesAgent
**Purpose:** Central orchestrator for task execution.

**Key Methods:**
- `register_handler(task_type, callable)` - Register execution handlers
- `process_input(user_input)` - Main entry point for user queries
- `_execute_tasks(context)` - Routes to appropriate handlers
- `_execute_task(context, task_type)` - Executes single task

**Design Pattern:** Strategy Pattern (handlers per task type)

### 2.4 Task Result
**Purpose:** Standardized execution result format.

**Structure:**
```python
TaskResult
├── task_type: TaskType          # What was executed
├── success: bool                # Did it succeed?
├── data: Dict[str, Any]         # Result data
├── error: Optional[str]         # Error message (if failed)
├── execution_time_ms: float     # How long it took
└── timestamp: datetime          # When it executed
```

---

## 3. Data Flow

### 3.1 Complete Request Flow

```
┌─ User types: "Search for Python and check system health"
│
├─ PARSE & CLASSIFY
│  ├─ IntentClassifier.classify()
│  └─ Returns: Intent(TaskType.COMBINED, primary_query="Python")
│
├─ CREATE CONTEXT
│  ├─ AgentContext(user_input, intent)
│  └─ Assign unique session_id
│
├─ EXECUTE TASKS (both for COMBINED)
│  ├─ Call handler for WEB_SEARCH
│  │  ├─ Extract "Python" from intent
│  │  ├─ WebSearchClient.search("Python")
│  │  └─ TaskResult(success=true, data=results, time=125ms)
│  │
│  └─ Call handler for SYSTEM_MONITOR
│     ├─ SystemMonitor.get_cpu_usage()
│     ├─ SystemMonitor.get_memory_usage()
│     └─ TaskResult(success=true, data=metrics, time=45ms)
│
├─ FORMAT & DISPLAY
│  ├─ HermesExecutor._format_response()
│  ├─ HermesExecutor._generate_summary()
│  ├─ HermesUI.display_response()
│  └─ Print formatted results to user
│
└─ READY FOR NEXT INPUT
```

---

## 4. Extensibility

### 4.1 Adding a New Task Type

**Step 1:** Define task type in TaskType enum
```python
class TaskType(Enum):
    MY_CUSTOM_TASK = "my_custom_task"
```

**Step 2:** Add keywords to IntentClassifier
```python
CUSTOM_KEYWORDS = {"custom", "my task", "special"}

# In classify() method:
has_custom_intent = any(kw in lower_input for kw in cls.CUSTOM_KEYWORDS)
if has_custom_intent:
    task_type = TaskType.MY_CUSTOM_TASK
```

**Step 3:** Create handler function
```python
def handle_custom_task(context: AgentContext, params: Dict) -> TaskResult:
    start_time = time.time()
    try:
        # Do work here
        result_data = {"key": "value"}
        return TaskResult(
            task_type=TaskType.MY_CUSTOM_TASK,
            success=True,
            data=result_data,
            execution_time_ms=(time.time() - start_time) * 1000,
        )
    except Exception as e:
        return TaskResult(
            task_type=TaskType.MY_CUSTOM_TASK,
            success=False,
            data={},
            error=str(e),
        )
```

**Step 4:** Register handler with agent
```python
agent.register_handler(TaskType.MY_CUSTOM_TASK, handle_custom_task)
```

---

## 5. Design Patterns Used

### 5.1 Strategy Pattern
Different execution strategies per task type, registered at runtime.
```python
agent.register_handler(TaskType.WEB_SEARCH, search_handler)
agent.register_handler(TaskType.SYSTEM_MONITOR, monitor_handler)
```

### 5.2 Factory Pattern
Creating fully configured agent with all handlers pre-registered.
```python
agent, _ = create_hermes_agent_with_modules()
```

### 5.3 Context Pattern
Maintaining execution state through task pipeline.
```python
context = AgentContext(session_id, user_input)
context.intent = classified_intent
context.add_result(task_result)
```

### 5.4 Builder Pattern (Implicit)
Constructing AgentContext step-by-step through agent flow.

---

## 6. Error Handling Strategy

### 6.1 Graceful Degradation
- Missing API keys don't crash the agent
- Failed tasks are reported but don't stop other tasks
- Port access denied is expected and handled

### 6.2 Error Propagation
```
User Query
    ↓
Task Execution
    ↓
Exception Caught
    ↓
TaskResult(success=false, error=message)
    ↓
User Sees Friendly Error Message
```

### 6.3 Structured Error Data
```python
TaskResult(
    task_type=TaskType.WEB_SEARCH,
    success=False,
    data={},  # Empty when failed
    error="SERPAPI_API_KEY not configured",
)
```

---

## 7. Performance Considerations

### 7.1 Execution Timing
Each task records execution time:
```
Web Search: 125ms
System Monitor: 45ms
Total Session: 170ms
```

### 7.2 Concurrent Execution (Future)
Combined tasks could be parallelized:
```python
async def process_combined(context):
    search_task = asyncio.create_task(handle_web_search(...))
    monitor_task = asyncio.create_task(handle_system_monitor(...))
    
    results = await asyncio.gather(search_task, monitor_task)
    # Both run in parallel
```

---

## 8. Configuration & Customization

### 8.1 Confidence Thresholds
```python
# In IntentClassifier._calculate_confidence()
# Adjust these to change task detection sensitivity
```

### 8.2 Keyword Expansion
```python
# Add more keywords for better detection
SEARCH_KEYWORDS.add("research")
MONITOR_KEYWORDS.add("diagnostics")
```

### 8.3 Handler Registration
```python
# Custom handlers can replace defaults
agent.register_handler(TaskType.WEB_SEARCH, my_custom_search_handler)
```

---

## 9. Testing Strategy

### 9.1 Unit Testing Layers
```
IntentClassifier Tests
├─ Test keyword detection
├─ Test parameter extraction
└─ Test confidence scoring

HermesAgent Tests
├─ Test handler registration
├─ Test task execution
└─ Test context management

Handler Tests
├─ Test each handler independently
├─ Test error handling
└─ Test data format
```

### 9.2 Integration Testing
```
End-to-End Tests
├─ Full user query → result flow
├─ Combined task execution
└─ Error recovery
```

---

## 10. Usage Examples

### 10.1 Direct Agent Usage
```python
from hermes_modules.agent_core import create_hermes_agent_with_modules

agent, _ = create_hermes_agent_with_modules()

context = agent.process_input("Search for Docker tutorials")
print(context.to_dict())  # Full execution data
```

### 10.2 CLI Usage
```bash
python3 main.py

# Then type:
# "Search for Python best practices"
# "Check system health"
# "Is port 8080 listening?"
```

### 10.3 JSON API (Future)
```python
# Could be exposed as REST API
POST /execute
{
    "user_input": "Search for Docker"
}

Response:
{
    "session_id": "session_1",
    "intent": {...},
    "results": [...],
    "summary": "..."
}
```

---

## 11. Monitoring & Observability

### 11.1 Logging
- DEBUG: Full execution trace
- INFO: Task execution, classification
- WARNING: Missing config, failed tasks
- ERROR: Exceptions with context

### 11.2 Metrics
- Execution time per task type
- Success/failure rates
- Intent classification accuracy
- Handler registration audit

---

## 12. Security Considerations

### 12.1 Input Validation
- User input sanitized before processing
- Port numbers validated (0-65535)
- Search queries limited length

### 12.2 API Key Protection
- Never logged (redacted as `***REDACTED***`)
- Environment variable isolation
- No hardcoded secrets

### 12.3 Execution Limits
- Request timeouts (10s default)
- Max results limits (10 default)
- Safe search enabled by default

---

## 13. Scaling & Future Enhancements

### 13.1 Async Execution
- Convert to asyncio for parallel task execution
- Implement async handlers
- Support long-running operations with callbacks

### 13.2 ML-Based Intent Classification
- Replace keyword matching with small LLM
- Better handling of ambiguous queries
- Confidence scoring via model

### 13.3 Persistent Storage
- Session history
- Query/result caching
- User preferences

### 13.4 Distributed Execution
- Remote handler execution
- Load balancing across workers
- Federated agent networks

---

## 14. Architecture Diagram

```
main.py
│
├─ HermesUI
│  └─ User interface & formatting
│
├─ HermesExecutor
│  ├─ Orchestrates execution
│  ├─ Formats responses
│  └─ Manages display
│
└─ HermesAgent
   ├─ IntentClassifier
   │  └─ Keyword-based classification
   │
   ├─ Handler Registry
   │  ├─ WEB_SEARCH → WebSearchClient
   │  ├─ SYSTEM_MONITOR → SystemMonitor
   │  ├─ PORT_CHECK → SystemMonitor.is_port_listening
   │  └─ HEALTH_REPORT → SystemMonitor.get_system_health
   │
   └─ Execution Engine
      ├─ AgentContext management
      ├─ TaskResult creation
      └─ Error handling
```

---

## Conclusion

This architecture provides:
- ✅ **Clarity**: Clear separation of concerns, easy to understand
- ✅ **Extensibility**: Add new tasks without modifying core
- ✅ **Robustness**: Comprehensive error handling
- ✅ **Scalability**: Ready for async, distributed, ML enhancements
- ✅ **Maintainability**: Well-documented, testable, clear patterns

The system demonstrates professional-grade software design suitable for production environments while remaining approachable for educational purposes.
