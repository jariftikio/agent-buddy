# LLM-Based Intent Classifier Integration Guide
## Principal Software Architect Design

---

## Architecture Overview

The upgraded Hermes agent now features a **two-tier intelligent classification system**:

```
┌─────────────────────────────────────────────────────────┐
│  TIER 1: LLM CLASSIFIER (Semantic Understanding)       │
│  ├─ Understands nuanced natural language               │
│  ├─ Extracts structured entities                        │
│  ├─ Returns confidence score                            │
│  └─ Fast failure with fallback                          │
└──────────────┬──────────────────────────────────────────┘
               │
        ┌──────▼──────┐
        │ Confidence  │
        │ Threshold   │
        │ Check?      │
        └──────┬──────┘
         YES  │  NO
             │
    ┌────────▼────────────┐
    │ Use LLM Result      │ Fallback to Tier 2
    └────────┬────────────┘           │
             │                        │
             │    ┌───────────────────┘
             │    │
             ▼    ▼
    ┌─────────────────────────────────────────────────────┐
    │  TIER 2: KEYWORD CLASSIFIER (Fast Fallback)        │
    │  ├─ Keyword pattern matching                       │
    │  ├─ Reliable and deterministic                      │
    │  ├─ No API dependencies                             │
    │  └─ Always available                                │
    └────────┬────────────────────────────────────────────┘
             │
             ▼
    Return Classified Intent
    (with source metadata)
```

**Key Features:**
- ✅ **Semantic Understanding**: LLM grasps context and intent nuance
- ✅ **Entity Extraction**: Structured extraction of parameters (queries, ports, etc.)
- ✅ **Intelligent Fallback**: Automatic fallback to keyword classifier
- ✅ **Confidence-Based**: Only uses LLM when confident
- ✅ **Backward Compatible**: Works with keyword-only mode
- ✅ **Caching**: Reduces redundant LLM calls
- ✅ **Runtime Switching**: Update LLM client without restart

---

## Installation & Setup

### 1. Install Dependencies

```bash
pip install -r hermes_modules/requirements.txt
# Also install LLM client (example: Anthropic)
pip install anthropic
```

### 2. Set Up LLM Client

```python
# Option A: Using Claude (Anthropic)
from anthropic import Anthropic

client = Anthropic(api_key="your_api_key")

# Option B: Using OpenAI
import openai

client = openai.OpenAI(api_key="your_api_key")

# Option C: Using other LLM providers (configure similarly)
```

### 3. Initialize Agent with LLM

```python
from hermes_modules.agent_core_v2 import create_hermes_agent_with_modules

# Create agent with LLM-based classification
agent, _ = create_hermes_agent_with_modules(
    llm_client=client,        # Your LLM API client
    use_llm=True,             # Enable LLM tier
    enable_logging=True
)

# Use the agent
context = agent.process_input("Search for Python tutorials and check system health")
```

---

## Classification Flow

### Example: User Input Processing

**Input:** `"Search for Docker containerization and check if port 8080 is running"`

**Step 1: LLM Classification**
```
LLM receives:
  - User input
  - Supported task types
  - Entity extraction requirements

LLM returns (JSON):
{
  "task_type": "combined",
  "primary_query": "Docker containerization",
  "confidence": 0.92,
  "entities": [
    {
      "entity_type": "search_query",
      "value": "Docker containerization",
      "confidence": 0.95
    },
    {
      "entity_type": "port_number",
      "value": 8080,
      "confidence": 0.98
    }
  ],
  "parameters": {
    "search_query": "Docker containerization",
    "port": 8080,
    "max_results": 5
  }
}
```

**Step 2: Confidence Check**
```
Confidence 0.92 >= Threshold 0.70?
  → YES: Use LLM result ✓
```

**Step 3: Structured Intent**
```
Intent(
  task_type=COMBINED,
  primary_query="Docker containerization",
  entities=[
    Entity(search_query, "Docker containerization", 0.95),
    Entity(port_number, 8080, 0.98)
  ],
  parameters={
    "search_query": "Docker containerization",
    "port": 8080
  },
  confidence=0.92,
  classifier_used="llm",
  reasoning="LLM classified as combined search+port check"
)
```

**Step 4: Task Execution**
```
Execute WEB_SEARCH with:
  - query = "Docker containerization" (from entity extraction)
  - max_results = 5

Execute PORT_CHECK with:
  - port = 8080 (from entity extraction)
```

---

## Code Integration Examples

### Basic Usage (LLM + Keyword Fallback)

```python
from anthropic import Anthropic
from hermes_modules.agent_core_v2 import create_hermes_agent_with_modules

# Initialize LLM client
llm_client = Anthropic(api_key="sk-...")

# Create agent with LLM and keyword fallback
agent, _ = create_hermes_agent_with_modules(
    llm_client=llm_client,
    use_llm=True  # Enable two-tier classification
)

# Process user input
context = agent.process_input("Check my system health")

# Access enhanced intent data
print(f"Intent Type: {context.intent.task_type.value}")
print(f"Confidence: {context.intent.confidence:.0%}")
print(f"Classifier: {context.intent.classifier_used}")
print(f"Entities Extracted: {len(context.intent.entities)}")

for entity in context.intent.entities:
    print(f"  - {entity.entity_type}: {entity.value} ({entity.confidence:.0%})")
```

### Advanced: Custom Confidence Threshold

```python
from hermes_modules.agent_core_v2 import HermesAgent
from hermes_modules.intent_classifiers import CompositeIntentClassifier

# Create agent with custom threshold
agent = HermesAgent(
    llm_client=llm_client,
    llm_confidence_threshold=0.85,  # Only use LLM if >85% confident
    use_llm=True
)

# Now only high-confidence LLM results are used
# Lower confidence falls back to keyword classifier
```

### Runtime LLM Switching

```python
# Start with keyword-only
agent, _ = create_hermes_agent_with_modules(use_llm=False)

# ... later, enable LLM after client setup ...
from anthropic import Anthropic

llm_client = Anthropic()
agent.set_llm_client(llm_client)

# Now uses LLM+keyword combination
context = agent.process_input("Search for examples")
```

### Direct Classifier Usage

```python
from hermes_modules.intent_classifiers import (
    CompositeIntentClassifier,
    KeywordBasedIntentClassifier,
    LLMIntentClassifier
)

# Use composite (recommended)
composite = CompositeIntentClassifier(
    llm_client=llm_client,
    llm_confidence_threshold=0.75
)
intent = composite.classify("Your query here")

# Or use LLM directly
llm_classifier = LLMIntentClassifier(api_client=llm_client)
intent = llm_classifier.classify("Your query")

# Or use keyword-only fallback
keyword = KeywordBasedIntentClassifier()
intent = keyword.classify("Your query")

print(f"Classifier used: {intent.classifier_used}")
print(f"Reasoning: {intent.reasoning}")
```

### Accessing LLM-Extracted Entities

```python
context = agent.process_input("Is port 3000 listening?")

# Access structured entities
for entity in context.intent.entities:
    if entity.entity_type == "port_number":
        print(f"Extracted port: {entity.value}")
        print(f"Confidence: {entity.confidence:.0%}")

# Entities are also in parameters for direct handler use
port = context.intent.parameters.get("port", 80)
print(f"Will check port: {port}")
```

---

## LLM Provider Integration

### Anthropic (Claude)

```python
from anthropic import Anthropic

client = Anthropic(api_key="sk-ant-...")

agent, _ = create_hermes_agent_with_modules(
    llm_client=client,
    use_llm=True
)

# Claude models available:
# - claude-3-5-sonnet-20241022 (recommended)
# - claude-3-opus-20240229
# - claude-3-haiku-20240307
```

### OpenAI (GPT)

```python
import openai

client = openai.OpenAI(api_key="sk-...")

# Need to adapt LLMIntentClassifier for OpenAI's API
# Create wrapper in your integration:

class OpenAILLMIntentClassifier(LLMIntentClassifier):
    def _classify_with_llm(self, user_input):
        response = self.api_client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
            timeout=self.timeout
        )
        return self._parse_llm_response(
            response.choices[0].message.content,
            user_input,
            0.0
        )
```

### Local LLM (Ollama, LLaMA)

```python
# For local LLM running on localhost:11434
import requests

class LocalLLMIntentClassifier(LLMIntentClassifier):
    def __init__(self, base_url="http://localhost:11434", model="llama2"):
        self.base_url = base_url
        self.model = model

    def _classify_with_llm(self, user_input):
        prompt = self._build_classification_prompt(user_input)
        
        response = requests.post(
            f"{self.base_url}/api/generate",
            json={"model": self.model, "prompt": prompt}
        )
        
        return self._parse_llm_response(
            response.text,
            user_input,
            0.0
        )
```

---

## Structured Entity Extraction

The LLM classifier automatically extracts and structures entities:

### Supported Entity Types

| Entity Type | Example | Use Case |
|-------------|---------|----------|
| `search_query` | "Python best practices" | Web search |
| `port_number` | 8080 | Port monitoring |
| `metric_type` | "CPU" | System metrics |
| `monitor_flag` | true | Health check trigger |
| `threshold_value` | 85.0 | Alert threshold |

### Entity Structure

```python
ExtractedEntity(
    entity_type: str,      # Type identifier
    value: Any,            # Extracted value
    confidence: float      # 0.0-1.0 confidence
)
```

### Example Extraction

**Input:** "Alert me if port 8080 CPU usage exceeds 80%"

**Extracted Entities:**
```json
[
  {
    "entity_type": "port_number",
    "value": 8080,
    "confidence": 0.98
  },
  {
    "entity_type": "metric_type",
    "value": "CPU",
    "confidence": 0.95
  },
  {
    "entity_type": "threshold_value",
    "value": 80.0,
    "confidence": 0.92
  }
]
```

### Using Entities in Handlers

```python
def handle_monitoring_task(context, intent):
    # Get LLM-extracted threshold
    for entity in intent.entities:
        if entity.entity_type == "threshold_value":
            threshold = entity.value
            confidence = entity.confidence
            
            if confidence > 0.85:
                # Trust the extracted value
                return check_with_threshold(threshold)
    
    # Fallback to default if not extracted
    return check_with_threshold(80.0)
```

---

## Performance Characteristics

### Classification Times

| Classifier | Time | Reliability | Cost |
|------------|------|-------------|------|
| Keyword | 1-5ms | ⭐⭐⭐ Very High | Free |
| LLM | 100-500ms | ⭐⭐⭐⭐⭐ Very High | API calls |
| Composite (hit cache) | 1-5ms | ⭐⭐⭐⭐⭐ Very High | Free |

### Caching Strategy

```python
# LLM results are cached per unique input
# Hit cache = fast keyword-classifier speed
# Miss cache = LLM speed

Classifier Flow:
1. Check LLM cache for exact input
2. If HIT → return cached Intent (1-5ms)
3. If MISS → call LLM (100-500ms)
4. Cache result
5. Return Intent
```

### Optimization Tips

```python
# 1. Increase confidence threshold to reduce LLM calls
agent = HermesAgent(
    llm_client=client,
    llm_confidence_threshold=0.85  # Only 85%+ trusted
)

# 2. Use keyword-only mode if LLM not critical
agent, _ = create_hermes_agent_with_modules(use_llm=False)

# 3. Batch requests to amortize LLM latency
requests = [
    "Search for Python",
    "Check CPU",
    "Port 8080?"
]
for req in requests:
    context = agent.process_input(req)  # Uses cache for similar inputs
```

---

## Error Handling & Fallback

### LLM Failure Scenarios

```
LLM API Call
    ↓
Success? 
    ├─ YES → Check confidence
    │        ├─ High (>threshold) → Use LLM result
    │        └─ Low → Fall back to keyword
    │
    └─ NO → Exceptions
            ├─ Timeout → Fall back to keyword
            ├─ Parse Error → Fall back to keyword
            ├─ Auth Error → Fall back to keyword
            └─ API Error → Fall back to keyword
```

### Graceful Degradation

```python
# Composite classifier automatically handles failures

try:
    # Tier 1: LLM attempt
    intent = composite.classify(user_input)
    
    # If LLM fails or low confidence:
    # Tier 2: Keyword classifier activates
    
except Exception as e:
    # Ultimate fallback: keyword classifier
    logger.error(f"Classification error: {e}")
    # Still returns valid Intent from keyword tier
```

### Custom Error Handling

```python
context = agent.process_input("Your query")

# Check if classification succeeded
if context.intent.task_type == TaskType.UNKNOWN:
    # Handle unknown intent
    logger.warning(f"Could not classify: {context.intent.reasoning}")
    
# Check classifier confidence
if context.intent.confidence < 0.6:
    # Low confidence, user should confirm
    print("I'm not sure what you mean. Did you mean:")
    print(f"  1. {context.intent.primary_query}")
    
# Check which classifier was used
print(f"Classification method: {context.intent.classifier_used}")
```

---

## Configuration & Customization

### Confidence Thresholds

```python
# Conservative: Only use LLM if very confident
agent = HermesAgent(
    llm_client=client,
    llm_confidence_threshold=0.90  # Strict
)

# Balanced (recommended)
agent = HermesAgent(
    llm_client=client,
    llm_confidence_threshold=0.70  # Default
)

# Aggressive: Trust LLM more
agent = HermesAgent(
    llm_client=client,
    llm_confidence_threshold=0.50  # Lenient
)
```

### Custom Entity Types

To add new entity types, extend the LLM prompt:

```python
# In intent_classifiers.py, update:
def _build_classification_prompt(self, user_input):
    prompt = f"""
    ...existing prompt...
    
    Additional entity types to extract:
    - custom_metric: Application-specific metrics
    - database_name: Database identifiers
    - threshold_value: Alert thresholds
    """
    return prompt
```

### Custom Task Types

```python
# Add to TaskType enum
class TaskType(Enum):
    # ... existing types ...
    DATABASE_QUERY = "database_query"
    LOG_ANALYSIS = "log_analysis"

# Update LLM prompt with new types
# Register handlers
agent.register_handler(TaskType.DATABASE_QUERY, db_handler)
agent.register_handler(TaskType.LOG_ANALYSIS, log_handler)
```

---

## Production Deployment

### Environment Variables

```bash
# .env file
LLM_PROVIDER=anthropic          # or openai, local, etc.
LLM_API_KEY=sk-...
LLM_MODEL=claude-3-5-sonnet-20241022
LLM_TIMEOUT=15
LLM_CONFIDENCE_THRESHOLD=0.70

HERMES_USE_LLM=true
HERMES_LOG_LEVEL=INFO
```

### Load Configuration

```python
import os
from dotenv import load_dotenv

load_dotenv()

# Create LLM client from env
if os.getenv("HERMES_USE_LLM") == "true":
    from anthropic import Anthropic
    llm_client = Anthropic(api_key=os.getenv("LLM_API_KEY"))
else:
    llm_client = None

# Create agent
agent, _ = create_hermes_agent_with_modules(
    llm_client=llm_client,
    use_llm=os.getenv("HERMES_USE_LLM") == "true"
)
```

### Monitoring & Logging

```python
import logging

# Log classification details
logging.basicConfig(level=logging.DEBUG)

context = agent.process_input("Your query")

# Logs will show:
# - Classifier used (LLM or keyword)
# - Confidence score
# - Entities extracted
# - Fallback reasons
# - Execution times
```

### Rate Limiting (for LLM API calls)

```python
from collections import defaultdict
import time

class RateLimitedAgent:
    def __init__(self, agent, max_calls_per_minute=60):
        self.agent = agent
        self.max_calls = max_calls_per_minute
        self.call_times = defaultdict(list)
    
    def process_input(self, user_input):
        # Rate limit LLM calls
        now = time.time()
        minute_ago = now - 60
        
        recent_calls = [
            t for t in self.call_times["llm"]
            if t > minute_ago
        ]
        
        if len(recent_calls) >= self.max_calls:
            # Use keyword-only fallback
            self.agent.set_llm_client(None)
        
        self.call_times["llm"].append(now)
        return self.agent.process_input(user_input)
```

---

## Migration Path from Keyword-Only

### Step 1: Keep Existing Keyword Classifier

```python
# Old code still works
from hermes_modules.agent_core import HermesAgent as OldAgent

agent = OldAgent()  # Keyword-only
```

### Step 2: Upgrade to New Version

```python
# New code with LLM support (backward compatible)
from hermes_modules.agent_core_v2 import create_hermes_agent_with_modules

# Works without LLM (uses keyword-only internally)
agent, _ = create_hermes_agent_with_modules(use_llm=False)
```

### Step 3: Enable LLM Gradually

```python
# Phase 1: Test with small confidence threshold
agent = HermesAgent(
    llm_client=client,
    llm_confidence_threshold=0.90  # Strict, mostly keyword
)

# Phase 2: Increase confidence threshold
agent = HermesAgent(
    llm_client=client,
    llm_confidence_threshold=0.75  # More LLM usage
)

# Phase 3: Full LLM with fallback
agent = HermesAgent(
    llm_client=client,
    llm_confidence_threshold=0.70  # Balanced
)
```

---

## Next Steps

1. ✅ Install LLM client (Anthropic, OpenAI, or local)
2. ✅ Initialize agent with LLM: `create_hermes_agent_with_modules(llm_client=...)`
3. ✅ Test with natural language: `agent.process_input("...")`
4. ✅ Check extraction results: `context.intent.entities`
5. ✅ Monitor classification: `context.intent.classifier_used`
6. ✅ Adjust confidence threshold as needed
7. ✅ Deploy to production with monitoring

---

🚀 **Your agent now understands semantics, not just keywords!**

For questions or issues, check the logs:
```python
logging.basicConfig(level=logging.DEBUG)
```
