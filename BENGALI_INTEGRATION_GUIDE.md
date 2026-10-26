# Hermes Agent - Bengali Language Integration Guide

## Overview

Hermes Agent v2.0+ now includes comprehensive Bengali language support through:

1. **Automatic Language Detection** - Detects English vs Bengali via Unicode analysis
2. **Bengali Intent Classification** - Native Bengali keyword mapping to TaskTypes
3. **OpenRouter Llama Integration** - Semantic understanding for complex Bengali queries
4. **Localized System Prompts** - Bengali-specific instructions for Llama models
5. **Unicode-Safe Output** - Proper Bengali display in terminal/console

---

## Architecture: Bengali Support Layer

```
User Input (English or Bengali)
     ↓
Language Detection (Unicode analysis)
     ├─ English (0-20% Bengali chars)
     └─ Bengali (>20% Bengali chars)
     ↓
Intent Classification
  ├─ Bengali Keywords (keyword-based)
  └─ OpenRouter Llama (LLM-based for complex queries)
     ↓
Handler Execution
     ↓
Language-Aware Output Formatting
     └─ Bengali text → UTF-8 terminal display
```

---

## Quick Start: Bengali Usage

### Command Line

```bash
# Start Hermes Agent
python main.py

# Bengali queries (examples):
🔮 Hermes > সিস্টেমের অবস্থা দেখাও
🔮 Hermes > এই লিংকটি নিরাপদ কিনা দেখাও
🔮 Hermes > পোর্ট 8080 শুনছে কিনা জানুন
```

### Programmatic Usage

```python
from hermes_modules.language_config import (
    Language,
    LanguageDetector,
    SystemPromptManager,
)
from hermes_modules.agent_core_v2 import create_hermes_agent_with_modules

# Create agent
agent, _ = create_hermes_agent_with_modules(use_llm=False)

# Bengali query
bengali_input = "সিস্টেমের অবস্থা দেখাও"

# Detect language
language = LanguageDetector.detect_language(bengali_input)
# Returns: Language.BENGALI

# Process
context = agent.process_input(bengali_input)

# Get results
for result in context.results:
    print(f"Task: {result.task_type.value}")
    print(f"Data: {result.data}")
```

---

## Bengali Keywords by Task Type

### Web Search / Information Retrieval
```
খোঁজ, খোঁজো, খুঁজ, অনুসন্ধান, গবেষণা, জানুন, শিখুন, সার্চ
Example: "Python সম্পর্কে খোঁজ করো"
```

### System Monitoring
```
সিস্টেম, অবস্থা, দেখাও, পরীক্ষা, স্বাস্থ্য, সিপিইউ, মেমরি, পারফরম্যান্স
Example: "সিস্টেমের অবস্থা দেখাও"
```

### Port Checking
```
পোর্ট, সংযোগ, নেটওয়ার্ক, শোনা, চলছে, শুনছে
Example: "পোর্ট 8080 শুনছে কিনা জানুন"
```

### URL Security
```
লিঙ্ক, লিংক, ইউআরএল, ডোমেইন, নিরাপদ, নিরাপত্তা, ফিশিং
Example: "এই লিংকটি নিরাপদ কিনা দেখাও"
```

### System Health Report
```
স্বাস্থ্য, রিপোর্ট, সম্পূর্ণ, সামগ্রিক
Example: "সিস্টেম স্বাস্থ্য রিপোর্ট দেখাও"
```

---

## Language Detection Algorithm

The `LanguageDetector` uses Unicode range analysis:

```
Bengali Unicode Range: U+0980 to U+09FF

Detection Logic:
1. Count Bengali characters in input
2. If Bengali chars > 20% of total length
   → Classify as Language.BENGALI
3. Else
   → Classify as Language.ENGLISH
```

Example:
```python
from hermes_modules.language_config import LanguageDetector, Language

# English
text1 = "Check the system status"
lang1 = LanguageDetector.detect_language(text1)
# Returns: Language.ENGLISH

# Bengali
text2 = "সিস্টেমের অবস্থা দেখাও"
lang2 = LanguageDetector.detect_language(text2)
# Returns: Language.BENGALI

# Mixed (>20% Bengali)
text3 = "দয়া করে Check the system"
lang3 = LanguageDetector.detect_language(text3)
# Returns: Language.BENGALI (because "দয়া করে" is enough for >20%)
```

---

## OpenRouter Llama Integration

### Setup

1. **Install OpenRouter API Client**:
```bash
pip install requests  # Already included
```

2. **Get API Key**:
- Visit https://openrouter.ai/
- Create account and get API key
- Set environment variable:
```bash
export OPENROUTER_API_KEY=your_key_here
```

### Usage

```python
from hermes_modules.openrouter_client import OpenRouterClient
from hermes_modules.language_config import SystemPromptManager, Language

# Initialize client
client = OpenRouterClient()

# Get Bengali system prompt
system_prompt = SystemPromptManager.get_system_prompt(
    Language.BENGALI,
    backend="openrouter"
)

# Classify Bengali intent using LLM
result = client.classify_intent_bengali(
    "সিস্টেম পরীক্ষা করুন এবং স্থিতি রিপোর্ট করুন",
    system_prompt
)
# Returns: {
#     "task_type": "health_report",
#     "confidence": 0.95,
#     "reasoning": "User requested system status and report"
# }
```

### Available Models

```python
models = OpenRouterClient.list_available_models()
# [
#   "meta-llama/llama-2-70b-chat",
#   "meta-llama/llama-2-13b-chat",
#   "gryphe/mythomax-l2-13b",
#   ...
# ]
```

---

## System Prompts

### Bengali Keyword Classifier Prompt

```
আপনি হার্মিস, একটি স্থানীয়করণ ভার্চুয়াল সহায়ক...

নির্দেশাবলী:
1. সমস্ত ইনপুট বাংলায় পড়ুন
2. সমস্ত আউটপুট বাংলায় প্রদান করুন
3. প্রতিটি কাজের ডেটা স্পষ্টভাবে রিপোর্ট করুন
```

### OpenRouter Llama Prompt

```
আপনি হার্মিস, একটি বাংলা-সক্ষম স্থানীয় অটোমেশন এজেন্ট।

প্রতিটি উত্তরে:
1. সম্পূর্ণভাবে এবং শুধুমাত্র বাংলায় সাড়া দিন
2. প্রযুক্তিগত বিস্তারিত স্পষ্ট করুন
3. ত্রুটি হ্যান্ডল করুন স্পষ্টভাবে
```

---

## Bengali Output Formatting

The UI layer handles Bengali UTF-8 output automatically:

```python
from hermes_modules.language_config import Language

# Bengali output example:
print("✅ স্থিতি: সিপিইউ ব্যবহার ৪৫%, মেমরি ৬০%")
print("🔍 নিরাপত্তা মূল্যায়ন: নিরাপদ")
print("⚠️  সতর্কতা: পোর্ট 8080 শুনছে না")
```

---

## Feature Parity

All Hermes v2.0 features work identically in Bengali:

| Feature | English | Bengali | Status |
|---------|---------|---------|--------|
| Web Search | ✅ | ✅ | Full Support |
| System Monitor | ✅ | ✅ | Full Support |
| Port Check | ✅ | ✅ | Full Support |
| URL Security | ✅ | ✅ | Full Support |
| Health Report | ✅ | ✅ | Full Support |
| LLM Classification | ✅ | ✅ | Via OpenRouter |
| Error Messages | ✅ | ⏳ | In Progress |
| Documentation | ✅ | ⏳ | In Progress |

---

## Common Bengali Queries

### System Administration
```
সিস্টেমের অবস্থা দেখাও
সিপিইউ ব্যবহার কত
মেমরি খালি আছে
সিস্টেম স্বাস্থ্য রিপোর্ট দেখাও
পোর্ট 8080 শুনছে কিনা জানুন
```

### Security & Verification
```
এই লিংকটি নিরাপদ কিনা দেখাও
ইউআরএল চেক করো: https://example.com
এই ডোমেইন বিশ্বস্ত কিনা যাচাই করো
ফিশিং সাইট আছে কিনা চেক করুন
```

### Research & Information
```
Python সম্পর্কে তথ্য খুঁজ করো
মেশিন লার্নিং বেসিক্স জানুন
ডকার কী তা জানতে খুঁজ দাও
প্রোগ্রামিং সেরা অনুশীলন খোঁজ করো
```

---

## Error Handling

Bengali error messages are provided for common issues:

```python
try:
    client = OpenRouterClient()
except ValueError as e:
    # Bengali error message
    print("❌ ত্রুটি: OpenRouter API কী সেট করা হয়নি")
    print("   OPENROUTER_API_KEY পরিবেশ পরিবর্তনশীল সেট করুন")
```

---

## Backward Compatibility

✅ **Fully Backward Compatible**

- Existing English code works unchanged
- Bengali support is additive
- No breaking changes to agent architecture
- All 8 design patterns maintained
- Defensive validation rules unchanged

---

## Future Enhancements

1. **Bengali Error Messages** - Localize all error outputs
2. **Bengali Documentation** - Full documentation in Bengali
3. **Multi-Language UI** - Language selection in interactive mode
4. **Bengali Logging** - Optional Bengali debug logs
5. **Bengali Test Suite** - Full test coverage in Bengali

---

## Example: Complete Bengali Workflow

```python
from hermes_modules.agent_core_v2 import create_hermes_agent_with_modules
from hermes_modules.language_config import (
    Language,
    LanguageDetector,
    SystemPromptManager,
)

# Create agent
agent, _ = create_hermes_agent_with_modules(enable_logging=False, use_llm=False)

# Bengali query
query = "সিস্টেমের অবস্থা দেখাও"

# Detect language
language = LanguageDetector.detect_language(query)
assert language == Language.BENGALI

# Get localized prompt
prompt = SystemPromptManager.get_system_prompt(language, backend="anthropic")

# Process through agent
context = agent.process_input(query)

# Access results
for result in context.results:
    print(f"Task: {result.task_type.value}")
    print(f"Success: {result.success}")
    
    if result.task_type.value == "health_report":
        print(f"Alerts: {result.data.get('alerts', [])}")
        print(f"Ports: {len(result.data.get('ports', []))}")
```

---

## Support & Issues

For Bengali-specific issues:
1. Check language detection: `LanguageDetector.detect_language(text)`
2. Verify Bengali keywords in `language_config.py`
3. Test with English equivalent to isolate issue
4. Enable logging: `enable_logging=True` in agent creation

---

**Hermes Agent v2.0 - Now Bilingual! 🇬🇧 🇧🇩**

For complete documentation, see:
- [HERMES_COMPLETE_INTEGRATION.md](HERMES_COMPLETE_INTEGRATION.md)
- [QUICK_REFERENCE.md](QUICK_REFERENCE.md)
- [HERMES_SYSTEM_COMPLETE.txt](HERMES_SYSTEM_COMPLETE.txt)
