# AI Employee - Claude Code Context

**Project:** Personal AI Employee (Autonomous FTE)
**Version:** 0.1.0
**Last Updated:** 2026-03-12

---

## 🎯 Project Overview

This is a **Personal AI Employee** system that autonomously manages personal and business affairs using:
- **Claude Code** as the reasoning engine
- **Obsidian** as the knowledge base (vault)
- **Python watchers** for event detection
- **SQLite** for task tracking

---

## 📁 Project Structure

```
GeneralAgentWithCursor/
├── orchestrator.py          # Main coordination process
├── database/
│   └── database.py          # SQLite task tracking
├── watchers/
│   ├── filesystem_watcher.py # File drop monitoring
│   └── base_watcher.py      # Base class for watchers
├── skills/
│   ├── file-processor.md    # Skill: Process files
│   └── email-triage.md      # Skill: Handle emails
├── vault/                   # Obsidian vault
│   ├── Dashboard.md         # Main status dashboard
│   ├── Company_Handbook.md  # Rules & guidelines
│   ├── Business_Goals.md    # Objectives & metrics
│   ├── Inbox/Drop/          # File drop folder
│   ├── Needs_Action/        # Items requiring action
│   ├── Processing/          # Currently being handled
│   ├── Pending_Approval/    # Awaiting human decision
│   ├── Approved/            # Ready to execute
│   ├── Done/                # Completed
│   └── Logs/                # Audit trail
├── templates/               # Markdown templates
└── logs/                    # Application logs
```

---

## 🤖 Available Skills

When triggered, use these skills based on the task type:

### `file-processor`
**Use when:** Processing files from `/Processing/` with type `file_drop`
**Actions:**
- Read and analyze file content
- Categorize (invoice, contract, reference, etc.)
- Extract key information (dates, amounts, action items)
- Create summary or action plan
- Move to appropriate folder

### `email-triage`
**Use when:** Processing emails from `/Processing/` with type `email`
**Actions:**
- Analyze email content and sender
- Categorize (inquiry, invoice, meeting, etc.)
- Assess priority and urgency
- Draft response (if needed)
- Create approval request for sensitive emails

### `invoice-generator`
**Use when:** Creating invoices from project data
**Actions:**
- Extract project details and rates
- Generate invoice PDF
- Create approval request
- Log in accounting

### `dashboard-updater`
**Use when:** Updating the main dashboard
**Actions:**
- Count items in each queue
- Calculate today's metrics
- Update Dashboard.md with current stats

---

## 📋 Workflow Patterns

### Pattern 1: File Processing

1. File dropped in `/Inbox/Drop/`
2. Watcher creates metadata in `/Needs_Action/`
3. Orchestrator moves to `/Processing/`
4. **You use `file-processor` skill**
5. Output: Summary/Plan/Approval in appropriate folder
6. Move to `/Done/`

### Pattern 2: Email Handling

1. Gmail watcher saves email to `/Needs_Action/`
2. Orchestrator moves to `/Processing/`
3. **You use `email-triage` skill**
4. Draft response created in `/Approved/`
5. Human reviews and approves
6. Email sent via MCP

### Pattern 3: Approval Workflow

1. Skill creates approval request in `/Pending_Approval/`
2. Human reviews and moves to `/Approved/`
3. Orchestrator detects and executes action
4. Moves to `/Done/` with result logged

---

## 📖 Key Documents

### Company Handbook (`vault/Company_Handbook.md`)
**Contains:**
- Communication guidelines
- Financial approval thresholds
- Task priority rules
- Security policies

**Always follow these rules when making decisions.**

### Business Goals (`vault/Business_Goals.md`)
**Contains:**
- Revenue targets
- Key metrics
- Active projects
- Subscription list

**Reference this for context on business priorities.**

### Dashboard (`vault/Dashboard.md`)
**Contains:**
- Real-time queue status
- Today's activity
- Financial overview
- Alerts

**Update this after significant actions.**

---

## 🔧 How to Use

### As a Developer (Building the System)

When working on this project:

1. **Read existing code first** - Check `orchestrator.py`, `database.py`, watchers
2. **Follow patterns** - Use existing watcher/handler structure
3. **Test incrementally** - Run orchestrator, drop test files, verify behavior
4. **Log everything** - Use the logging system
5. **Update docs** - Keep skills and this file current

### As Claude Code (Running the System)

When the orchestrator triggers you:

1. **Read the task file** in `/Processing/`
2. **Identify the skill** to use (from metadata or filename)
3. **Follow the skill workflow** documented in `/skills/`
4. **Create output files** in appropriate folders
5. **Move task to `/Done/`** with summary
6. **Update dashboard** if significant

---

## 🚨 Important Rules

### Safety First
- **NEVER** execute payments without approval file in `/Approved/`
- **NEVER** send emails to new contacts without human approval
- **NEVER** delete files without explicit permission
- **ALWAYS** log actions in `/Logs/`

### Approval Required For:
- Payments ≥ $100
- Emails containing financial commitments
- Any irreversible action
- New API integrations

### Can Auto-Execute:
- File analysis and categorization
- Draft creation (emails, documents)
- Dashboard updates
- Archive operations

---

## 🧪 Testing

### Test File Drop Flow

```bash
# 1. Start orchestrator
python orchestrator.py --vault ./vault

# 2. Drop a test file
echo "Test content" > vault/Inbox/Drop/test.txt

# 3. Watch logs for processing
tail -f logs/orchestrator_20260312.log

# 4. Check vault folders for results
ls -la vault/Needs_Action/
ls -la vault/Processing/
ls -la vault/Done/
```

### Test Claude Integration

```bash
# Manually trigger Claude
cd vault
claude "Use file-processor skill to process: FILE_20260312_120000_test.txt.md"
```

---

## 📊 Database Schema

### Tasks Table
```sql
tasks (
    id TEXT PRIMARY KEY,
    type TEXT,              -- 'file_drop', 'email', 'payment'
    status TEXT,            -- 'pending', 'processing', 'done', 'failed'
    priority TEXT,          -- 'urgent', 'high', 'normal', 'low'
    assigned_skill TEXT,    -- Which skill is handling it
    approval_required BOOLEAN,
    approved_by TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
)
```

### Task Events Table (Audit Trail)
```sql
task_events (
    task_id TEXT,
    event_type TEXT,        -- 'created', 'processed', 'approved'
    timestamp TIMESTAMP,
    details JSON
)
```

---

## 🔍 Troubleshooting

### Claude Code not found
```
Error: Claude Code not found. Is it installed?
Solution: npm install -g @anthropic/claude-code
```

### Database locked
```
Error: database is locked
Solution: Check no other process is using tasks.db
```

### Watcher not detecting files
```
Issue: Files dropped but no response
Check: 
  - Is orchestrator running?
  - Is Inbox/Drop folder correct?
  - Check logs/orchestrator_*.log for errors
```

---

## 📚 Resources

- **Claude Code Docs:** https://platform.claude.com/docs
- **Obsidian:** https://obsidian.md
- **Model Context Protocol:** https://modelcontextprotocol.io
- **Hackathon Guide:** ../PersonalAIEmployee_Hackathon_0.md

---

## 🎯 Success Criteria

**Bronze Tier (Current Phase):**
- [x] Vault structure created
- [x] Filesystem watcher working
- [x] Orchestrator routing events
- [ ] Claude processing files successfully
- [ ] Tasks tracked in database

**Next Phase (Silver):**
- [ ] Gmail watcher integrated
- [ ] Email drafting working
- [ ] Approval workflow functional
- [ ] MCP server for email sending

---

*This document is auto-updated as the system evolves.*
