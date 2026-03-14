# 🚀 Quick Start Guide - AI Employee

**Version:** 0.1.0
**Last Updated:** 2026-03-12

---

## ⚡ 5-Minute Setup

### Step 1: Verify Prerequisites

```bash
# Check Python version (need 3.13+)
python --version

# Check UV installation
uv --version

# Check Claude Code installation
claude --version
```

**If missing:**
- Python: https://www.python.org/downloads/
- UV: `pip install uv` or https://github.com/astral-sh/uv
- Claude Code: `npm install -g @anthropic/claude-code`

---

### Step 2: Install Dependencies

```bash
cd GeneralAgentWithCursor

# Install with UV (recommended)
uv sync

# Or with pip
pip install -r requirements.txt
```

---

### Step 3: Configure Environment

```bash
# Copy example config (already done)
cp .env.example .env

# Edit .env with your settings
# VAULT_PATH=./vault  (default is fine)
# DRY_RUN=true        (keep true for testing)
```

---

### Step 4: Test the System

```bash
# Run test script
uv run python test_flow.py
```

**Expected output:**
```
✅ Vault path: ...
✅ Drop folder: ...
📁 Created test file: test_file_...
✅ TEST COMPLETE
```

---

### Step 5: Run the Orchestrator

**Option A: Quick Test (Foreground)**
```bash
# Start orchestrator
uv run python orchestrator.py --vault ./vault
```

**Option B: Development Mode (with logging)**
```bash
# Start with debug logging
uv run python orchestrator.py --vault ./vault --config config.json
```

**Expected output:**
```
======================================================================
🤖 AI EMPLOYEE ORCHESTRATOR
======================================================================
Vault: D:\...\GeneralAgentWithCursor\vault
Database: ...\tasks.db
======================================================================
👁️  Starting folder monitors...
   ✅ Monitoring: Needs_Action/
   ✅ Monitoring: Approved/
✅ Filesystem watcher started (Inbox/Drop)
======================================================================
✅ System is now running. Press Ctrl+C to stop.
======================================================================
```

---

### Step 6: Test File Processing

**In a NEW terminal window:**

```bash
cd GeneralAgentWithCursor

# Drop a test file
echo "This is a test document for processing" > vault/Inbox/Drop/test_doc.txt

# Or create a more complex test file
cat > vault/Inbox/Drop/invoice_test.txt << EOF
INVOICE #12345

From: Acme Corp
To: Your Company
Amount: $1,500.00
Due Date: 2026-03-25

Services:
- Consulting (March 2026)
- Strategy session

Please process this invoice for payment.
EOF
```

**Watch the orchestrator terminal for:**
```
📁 New file detected: invoice_test.txt
✅ Created task: file_20260312_...
📥 Processing: FILE_20260312_...md
   Type: file_drop
   Priority: high
   Skill: file-processor
🤖 Triggering Claude skill: file-processor
```

---

### Step 7: Check Results

**Check vault folders:**
```bash
# See what's in Needs_Action
ls -la vault/Needs_Action/

# See what's in Processing
ls -la vault/Processing/

# See what's completed
ls -la vault/Done/

# Check database
ls -la database/

# Check logs
cat logs/orchestrator_*.log
```

**ilExpected fes:**
- Metadata file in `Needs_Action/` or `Processing/`
- Database file in `database/tasks.db`
- Log file in `logs/orchestrator_YYYYMMDD.log`

---

## 🎯 Test Scenarios

### Scenario 1: Simple File Drop

```bash
# Create a simple text file
echo "Meeting notes from today's standup" > vault/Inbox/Drop/meeting_notes.txt
```

**Expected:**
- Metadata file created in `Needs_Action/`
- Task recorded in database
- File moved to `Processing/` when orchestrator detects it

---

### Scenario 2: Invoice Processing

```bash
cat > vault/Inbox/Drop/invoice_march.txt << EOF
INVOICE

Vendor: Tech Supplies Inc
Invoice #: TS-2026-0342
Amount: $450.00
Due: March 25, 2026

Items:
- Office supplies
- Printer paper (10 boxes)

Payment terms: Net 30
EOF
```

**Expected:**
- Priority set to "high" (contains "invoice")
- Claude skill triggered: `file-processor`
- Approval request may be created (if over threshold)

---

### Scenario 3: Urgent Document

```bash
cat > vault/Inbox/Drop/URGENT_contract.txt << EOF
URGENT: Contract Review Needed

Client: Big Client Corp
Deadline: Tomorrow EOD
Value: $10,000

Please review the attached contract terms
and provide feedback ASAP.
EOF
```

**Expected:**
- Priority set to "urgent" (contains "URGENT")
- High-priority alert in logs
- Fast-tracked processing

---

## 📊 Monitor the System

### View Live Logs

```bash
# Windows PowerShell
Get-Content logs/orchestrator_*.log -Wait -Tail 50

# Or just
type logs\orchestrator_*.log
```

### Check Database

```bash
# Start Python REPL
uv run python

# In Python:
from database import TaskDatabase
db = TaskDatabase('database/tasks.db')

# Get stats
stats = db.get_dashboard_stats()
print(stats)

# Get pending tasks
pending = db.get_pending_tasks()
print(f"Pending: {len(pending)}")

# Get today's completions
print(f"Done today: {stats['today_completions']}")
```

### Check Dashboard

```bash
# View current dashboard
type vault\Dashboard.md
```

---

## 🛠️ Troubleshooting

### "Claude Code not found"

```bash
# Install Claude Code
npm install -g @anthropic/claude-code

# Verify
claude --version
```

### "Database is locked"

```bash
# Check for other processes
# Windows: Check Task Manager for python.exe

# Or just wait a moment and retry
```

### "File not detected"

```bash
# Verify orchestrator is running
# Check logs for errors
cat logs/orchestrator_*.log

# Verify drop folder path
ls vault/Inbox/Drop/

# Try dropping file again
echo "test" > vault/Inbox/Drop/test.txt
```

### "Module not found"

```bash
# Reinstall dependencies
uv sync --force

# Or
pip install -r requirements.txt --force-reinstall
```

---

## ✅ Success Checklist

**Bronze Tier (Current Phase):**

- [ ] Orchestrator starts without errors
- [ ] File dropped in `Inbox/Drop/` is detected
- [ ] Metadata file created in `Needs_Action/`
- [ ] Task recorded in database
- [ ] File moved to `Processing/`
- [ ] Claude Code triggered (if installed)
- [ ] Logs show successful processing

**Next Phase (Silver):**

- [ ] Gmail watcher integrated
- [ ] Email drafting working
- [ ] Approval workflow functional
- [ ] Dashboard auto-updates

---

## 📚 What's Next?

### Learn More

- Read `CLAUDE.md` for Claude Code context
- Review `skills/file-processor.md` for skill details
- Check `Company_Handbook.md` for business rules

### Customize

1. Edit `vault/Company_Handbook.md` with your rules
2. Update `vault/Business_Goals.md` with your targets
3. Modify `config.json` for watcher settings

### Extend

- Add new watchers (WhatsApp, banking)
- Create new skills (invoice-generator, meeting-processor)
- Integrate MCP servers for actions

---

## 🆘 Getting Help

**Documentation:**
- Main guide: `../PersonalAIEmployee_Hackathon_0.md`
- Claude Code docs: https://platform.claude.com/docs
- Obsidian: https://obsidian.md

**Logs:**
- Orchestrator logs: `logs/orchestrator_*.log`
- Database: `database/tasks.db`

**Community:**
- Wednesday Research Meeting (Zoom link in main guide)
- YouTube: https://www.youtube.com/@panaversity

---

*Ready to build your AI Employee! 🚀*
