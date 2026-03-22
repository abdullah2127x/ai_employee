# Claude Runner Architecture - Complete Explanation

**Date:** 2026-03-22  
**Version:** 2.0

---

## ❓ **Question 1: How Does Claude Runner Detect Files in Processing/?**

### **Current Architecture: Orchestrator-Triggered (NOT Watcher-Based)**

```
┌─────────────────────────────────────────────────────────────┐
│ CURRENT FLOW                                                │
└─────────────────────────────────────────────────────────────┘

Filesystem Watcher
    ↓ (detects file in Drop/)
Creates metadata in Needs_Action/
    ↓
Folder Watcher (Needs_Action/)
    ↓ (detects metadata creation)
Orchestrator.on_needs_action_change()
    ↓
Moves file to Processing/
    ↓
Orchestrator.call_claude_runner(file_path)
    ↓
Subprocess.Popen(["python", "claude_runner.py", "Processing/FILE_....md"])
    ↓
Claude Runner starts (as separate process)
    ↓
Processes the specific file passed as argument
    ↓
Returns JSON → Fills template → Moves file
```

---

### **Key Points:**

**1. Claude Runner Does NOT Watch/Detect Files**

```python
# claude_runner.py - Line 465
def main():
    if len(sys.argv) < 2:
        print("Usage: python claude_runner.py <task_file>")
        sys.exit(1)
    
    task_file = Path(sys.argv[1])  # ← Passed as argument!
    process_task(task_file)
```

**Claude Runner is:**
- ❌ NOT a watcher/daemon
- ❌ NOT scanning folders
- ❌ NOT detecting files automatically
- ✅ A **command-line tool** that processes ONE file at a time
- ✅ **Called by Orchestrator** with specific file path

---

**2. Orchestrator Manages Everything**

```python
# orchestrator.py - Line 346
def call_claude_runner(self, file_path: Path):
    """Call Claude Runner to process task."""
    
    # Build command
    cmd = [
        sys.executable,
        str(project_root / "claude_runner.py"),
        str(file_path)  # ← Specific file path
    ]
    
    # Start Claude Runner as subprocess
    process = subprocess.Popen(
        cmd,
        stdout=None,  # Show output in console
        stderr=None,
    )
    
    # Keep reference to prevent garbage collection
    if not hasattr(self, 'claude_processes'):
        self.claude_processes = []
    self.claude_processes.append(process)
```

**Orchestrator:**
- ✅ Detects when file moves to Processing/
- ✅ Calls Claude Runner with file path
- ✅ Keeps process reference (prevents garbage collection)
- ✅ Does NOT wait for completion (fire-and-forget)

---

**3. Why This Architecture?**

| Aspect | Current (Orchestrator-Triggered) | Alternative (Watcher-Based) |
|--------|----------------------------------|----------------------------|
| **Detection** | Orchestrator detects | Claude Runner would need watcher |
| **Control** | Orchestrator manages all | Claude Runner would be independent |
| **Complexity** | Simple (one caller) | Complex (needs coordination) |
| **Error Handling** | Orchestrator handles errors | Claude Runner would need its own error handling |
| **Scalability** | Orchestrator can queue tasks | Multiple watchers could conflict |

**Current approach is SIMPLER and more CONTROLLED.**

---

## ❓ **Question 2: How Does Claude Generate Responses?**

### **Current Prompt Structure:**

```python
# claude_runner.py - Line 304
prompt = f"""You are an AI Employee WORKER. Process the task and return ONLY JSON.

CRITICAL RULES:
1. Output ONLY JSON - no markdown, no text before or after
2. Do not include any explanations
3. Do not use code blocks or formatting
4. Just raw JSON

Task file: {task_file.name}

Task content:
{task_content}

Output ONLY this JSON format (no other text):
{{
  "decision": "complete_task" | "create_approval_request" | "needs_revision",
  "category": "general" | "important" | "urgent" | "invoice" | "payment",
  "ai_action_taken": "What you did",
  "ai_response": "Your full response text"
}}

Examples:
Input: "Hey I am abdullah"
Output: {{"decision": "complete_task", "category": "general", "ai_action_taken": "Added greeting response", "ai_response": "Hello! Nice to meet you."}}

Input: "Please categorize this as important"
Output: {{"decision": "complete_task", "category": "important", "ai_action_taken": "Categorized as important", "ai_response": "This has been marked as important per your request."}}

Output ONLY the JSON."""
```

---

### **Rules & Restrictions:**

#### **1. Output Format Rules:**

| Rule | Description | Why |
|------|-------------|-----|
| **JSON ONLY** | No markdown, no text before/after | Easy parsing |
| **No explanations** | Just the JSON object | Consistency |
| **No code blocks** | No \`\`\`json ... \`\`\` | Direct parsing |
| **Raw JSON** | Just `{"key": "value"}` | `json.loads()` ready |

**Enforced by:**
- Prompt instructions
- Validation in `parse_and_validate_json()`

---

#### **2. JSON Schema Rules:**

**Required Fields:**
```python
required_fields = ['decision', 'category', 'ai_action_taken', 'ai_response']
```

**Valid Decisions:**
```python
valid_decisions = [
    'complete_task',           # Task done, move to Done/
    'create_approval_request', # Need human approval
    'needs_revision'           # Needs rework
]
```

**Valid Categories:**
```python
valid_categories = [
    'general',     # General task
    'important',   # Important but not urgent
    'urgent',      # Needs immediate attention
    'invoice',     # Invoice/billing related
    'payment'      # Payment processing
]
```

**Validation:**
```python
# claude_runner.py - Line 146
def parse_and_validate_json(stdout: str) -> dict:
    decision = json.loads(json_str)
    
    # Validate required fields
    for field in required_fields:
        if field not in decision:
            raise ValueError(f"Missing required field: {field}")
    
    # Validate decision value
    if decision['decision'] not in valid_decisions:
        raise ValueError(f"Invalid decision: {decision['decision']}")
    
    # Validate category value
    if decision['category'] not in valid_categories:
        raise ValueError(f"Invalid category: {decision['category']}")
    
    return decision
```

---

#### **3. Context Rules:**

**What Claude Receives:**

```python
# claude_runner.py - Line 313
# Read task file
task_content = task_file.read_text(encoding='utf-8')

# Load system prompt (CLAUDE.md)
system_prompt = load_system_prompt()

# Load context files (Business_Goals.md, Company_Handbook.md)
context = load_context_files()

# Build prompt with task content
prompt = f"""...Task content:\n{task_content}..."""
```

**Claude Sees:**
1. ✅ **Task metadata** (from YAML frontmatter)
   - type, task_id, original_name, priority, etc.
2. ✅ **Task content** (the actual file/email/message)
3. ✅ **System prompt** (CLAUDE.md - role, rules, priorities)
4. ✅ **Business goals** (if loaded)
5. ✅ **Company handbook** (if loaded)

**Claude Does NOT See:**
- ❌ Other tasks in the queue
- ❌ Previous task results
- ❌ System file paths (except what's in metadata)
- ❌ Orchestrator internals

---

#### **4. Decision Logic (Guidelines for Claude):**

**When to use each decision:**

```markdown
## Decision Guidelines (from prompt examples)

### complete_task
Use when:
- Task is straightforward
- No approval needed
- Can be completed autonomously

Examples:
- Greeting files → Respond and archive
- Simple categorization → Categorize and archive
- Information requests → Provide information

### create_approval_request
Use when:
- Payment over $100 (per Company Handbook)
- Sensitive actions (delete, move outside vault)
- New vendor/payee
- Large commitments

Examples:
- Invoice payment → Create approval file
- Software purchase → Create approval file

### needs_revision
Use when:
- Task is unclear
- Missing information
- Contradictory instructions

Examples:
- "Handle this thing" → Unclear
- File corrupted → Can't read
```

---

#### **5. Response Guidelines:**

**What Goes in `ai_response`:**

```python
# Good examples:
"Hello! Nice to meet you. I've processed this greeting file."
"This has been categorized as important per your request."
"Invoice #123 has been processed and queued for payment approval."

# Bad examples:
"Done"  # ← Too brief
"I think this might be important but I'm not sure..."  # ← Uncertain
"See attached document for details"  # ← No attachment exists
```

**Best Practices:**
- ✅ Be clear and specific
- ✅ Mention what action was taken
- ✅ Reference relevant details (invoice numbers, amounts, etc.)
- ✅ Professional tone (per Company Handbook)
- ✅ Concise but complete

---

### **Current Limitations:**

| Limitation | Impact | Workaround |
|------------|--------|------------|
| **No memory** | Claude doesn't remember previous tasks | Each task is independent |
| **No file system access** | Can't read other files | Only sees task file content |
| **No external APIs** | Can't check bank, email, etc. | Human must provide context |
| **Single pass** | One JSON response only | Can't iterate/refine |
| **No validation before return** | Invalid JSON = error | Prompt tries to prevent this |

---

### **Error Handling:**

**If Claude Violates Rules:**

```python
# Invalid JSON
try:
    decision = json.loads(claude_output)
except json.JSONDecodeError as e:
    raise ValueError(f"Claude did not return valid JSON: {e}")
    # → File moved to Needs_Revision

# Missing field
if 'decision' not in decision:
    raise ValueError("Missing required field: decision")
    # → File moved to Needs_Revision

# Invalid decision value
if decision['decision'] == 'invalid_value':
    raise ValueError(f"Invalid decision: invalid_value")
    # → File moved to Needs_Revision
```

**All errors → File moved to `Needs_Revision/` with error message**

---

## 📊 **Complete Flow Diagram**

```
┌─────────────────────────────────────────────────────────────┐
│ 1. ORCHESTRATOR DETECTS FILE                                │
│ - Folder Watcher detects metadata in Needs_Action/          │
│ - Moves file to Processing/                                 │
│ - Calls orchestrator.call_claude_runner(file_path)          │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. ORCHESTRATOR CALLS CLAUDE RUNNER                         │
│ - Builds command: python claude_runner.py <file_path>       │
│ - Starts subprocess.Popen (non-blocking)                    │
│ - Keeps process reference                                   │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. CLAUDE RUNNER PROCESSES FILE                             │
│ - Reads task file (metadata + content)                      │
│ - Loads system prompt (CLAUDE.md)                           │
│ - Builds prompt with task content                           │
│ - Invokes Claude Code (ccr code -p "...")                   │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. CLAUDE GENERATES JSON                                    │
│ - Analyzes task content                                     │
│ - Applies rules from prompt                                 │
│ - Returns strict JSON (no markdown, no text)                │
│ - Follows schema (decision, category, ai_action_taken,      │
│   ai_response)                                              │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. CLAUDE RUNNER VALIDATES                                  │
│ - Parses JSON                                               │
│ - Validates schema (required fields, valid values)          │
│ - Fills template placeholders                               │
│ - Validates all [PENDING] replaced                          │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ 6. CLAUDE RUNNER EXECUTES DECISION                          │
│ - complete_task → Move to Done/                             │
│ - create_approval_request → Create approval file            │
│ - needs_revision → Move to Needs_Revision/                  │
│ - error → Move to Needs_Revision/ with error message        │
└─────────────────────────────────────────────────────────────┘
```

---

## 🎯 **Summary**

### **Detection:**
- ❌ Claude Runner does NOT detect files
- ✅ Orchestrator detects and calls Claude Runner
- ✅ File path passed as command-line argument
- ✅ Fire-and-forget (non-blocking)

### **Response Generation:**
- ✅ Strict JSON-only prompt
- ✅ Schema validation (required fields, valid values)
- ✅ Context from task file + system prompt
- ✅ Guidelines via examples in prompt
- ✅ Error handling with Needs_Revision fallback

### **Restrictions:**
- ✅ JSON only (no markdown, no text)
- ✅ Specific schema (4 required fields)
- ✅ Valid decisions (3 options)
- ✅ Valid categories (5 options)
- ✅ No file system access (except task file)
- ✅ No memory (each task independent)

---

**This architecture ensures:**
- ✅ Consistent output format
- ✅ Easy validation
- ✅ Clear error handling
- ✅ Scalable design
- ✅ Separation of concerns

---

*Last Updated: 2026-03-22*  
*Version: 2.0*
