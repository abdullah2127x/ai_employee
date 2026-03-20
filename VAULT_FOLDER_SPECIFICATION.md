# Vault Folder & File Architecture Specification

**Document Version:** 1.0  
**Last Updated:** 2026-03-19  
**Status:** Active

---

## 📋 Overview

This document specifies the complete folder and file architecture for the AI Employee Obsidian vault. Every folder has a specific purpose, owner, and workflow stage.

---

## 🗂️ Folder Structure

```
vault/
├── Inbox/
│   ├── Drop/                    ← User input folder
│   └── Drop_History/            ← Processed files archive
├── Needs_Action/                ← Main task queue (PENDING)
├── Processing/                  ← Currently being processed
├── Pending_Approval/            ← Awaiting human approval
├── Approved/                    ← Approved, ready to execute
├── Rejected/                    ← Human rejected
├── Needs_Revision/              ← Needs rework/correction
├── Plans/                       ← Claude's action plans
├── Done/                        ← Completed tasks archive
├── Briefings/                   ← CEO briefings
├── Logs/                        ← System audit logs
│   ├── timeline/                ← Daily activity timeline
│   ├── tasks/                   ← Per-task detailed logs
│   └── errors/                  ← Error logs with stack traces
├── Accounting/                  ← Financial records
└── [Configuration Files]        ← Business_Goals.md, etc.
```

---

## 📁 Detailed Folder Specifications

### **1. Inbox/Drop/**

| Attribute | Specification |
|-----------|---------------|
| **Purpose** | User input folder - where humans drop files for AI processing |
| **Created By** | N/A (pre-existing) |
| **Used By** | **Human** (drops files), **Filesystem Watcher** (monitors) |
| **When Used** | When user wants AI to process a file |
| **File Types** | Any (PDF, DOCX, TXT, images, etc.) |
| **Retention** | Files moved to Drop_History/ immediately after detection |
| **Monitoring** | Filesystem Watcher monitors continuously |

**Example Files:**
- `invoice.pdf`
- `contract.docx`
- `meeting_notes.txt`

**Flow:**
```
Human drops: invoice.pdf
    ↓
Filesystem Watcher detects (within 0.5 seconds)
    ↓
Creates metadata in Needs_Action/
    ↓
Moves file to Drop_History/
```

---

### **2. Inbox/Drop_History/**

| Attribute | Specification |
|-----------|---------------|
| **Purpose** | Archive of all processed files from Drop/ |
| **Created By** | Filesystem Watcher (moves files here) |
| **Used By** | **Filesystem Watcher** (writes), **Human** (reference) |
| **When Used** | After file is processed and metadata created |
| **File Naming** | `{original_filename}.md5_{hash}` (for deduplication) |
| **Retention** | Indefinite (audit trail) |
| **Why** | Audit trail, prevent reprocessing, rollback capability |

**Example Files:**
```
Drop_History/
├── invoice.pdf.md5_a1b2c3d4e5f6...
├── contract.docx.md5_e5f6g7h8i9j0...
└── meeting_notes.txt.md5_k1l2m3n4o5p6...
```

**Flow:**
```
File processed from Drop/
    ↓
Moved to Drop_History/ with hash in name
    ↓
Hash recorded in .hash_registry.json
    ↓
Future duplicates detected via hash comparison
```

---

### **3. Needs_Action/**

| Attribute | Specification |
|-----------|---------------|
| **Purpose** | **MAIN TASK QUEUE** - All pending tasks wait here |
| **Created By** | Watchers (Filesystem, Gmail, WhatsApp, etc.) |
| **Used By** | **Watchers** (create), **Orchestrator** (scans), **Claude** (processes) |
| **When Used** | When new task is detected |
| **File Format** | Markdown with YAML frontmatter |
| **Status Values** | `pending`, `claimed`, `failed` |
| **Priority Values** | `urgent`, `high`, `normal`, `low` |
| **Retention** | Until task is processed (moved to next stage) |

**File Naming Convention:**
```
{TYPE}_{YYYYMMDD_HHMMSS}_{original_filename}.md

Examples:
- FILE_20260319_103000_invoice.pdf.md
- EMAIL_20260319_104500_urgent_client.md
- WHATSAPP_20260319_110000_payment_request.md
```

**Metadata Format:**
```markdown
---
type: file_drop
task_id: file_20260319_103000_invoice.pdf
original_name: invoice.pdf
file_hash: a1b2c3d4e5f6...
size: 1024
priority: high
status: pending
detected: 2026-03-19T10:30:00
---

# File Drop: invoice.pdf

**Detected:** 2026-03-19 10:30:00
**Priority:** High

## File Content

[Invoice content embedded here]

## Suggested Actions

- [ ] Review invoice
- [ ] Process payment
- [ ] Archive after processing
```

**Flow:**
```
Watcher creates task file
    ↓
Orchestrator scans (every 60 seconds by default)
    ↓
Moves to Processing/
    ↓
Claude processes
    ↓
Moves to Done/ or Pending_Approval/
```

---

### **4. Processing/**

| Attribute | Specification |
|-----------|---------------|
| **Purpose** | Tasks currently being processed by Claude |
| **Created By** | Orchestrator (moves from Needs_Action/) |
| **Used By** | **Orchestrator** (manages), **Claude** (works on) |
| **When Used** | When Claude starts working on a task |
| **Why** | Prevents multiple agents working on same task |
| **Retention** | Duration of processing (typically 1-5 minutes) |

**Flow:**
```
Task in Needs_Action/
    ↓
Orchestrator claims task
    ↓
Moves to Processing/
    ↓
Claude works on it (creates plan, executes actions)
    ↓
Moves to Done/ or Pending_Approval/
```

---

### **5. Pending_Approval/**

| Attribute | Specification |
|-----------|---------------|
| **Purpose** | Tasks requiring human approval before execution |
| **Created By** | Claude (creates approval request) |
| **Used By** | **Claude** (creates), **Human** (reviews/decides) |
| **When Used** | When sensitive action needed (payments, emails, etc.) |
| **Why** | Human-in-the-loop safety |
| **Retention** | Until human approves/rejects |

**Approval Thresholds (Default):**
| Action Type | Auto-Approve | Require Approval |
|-------------|--------------|------------------|
| Payments | < $50 recurring | All new payees, ≥ $100 |
| Emails | To known contacts | New contacts, bulk sends |
| Social Media | Scheduled posts | Replies, DMs |
| File Operations | Create, read | Delete, move outside vault |

**File Naming Convention:**
```
APPROVAL_{action_type}_{description}.md

Examples:
- APPROVAL_payment_client_A_invoice123.md
- APPROVAL_email_new_client_proposal.md
- APPROVAL_social_media_linkedin_post.md
```

**Approval Request Format:**
```markdown
---
type: approval_request
action: payment
amount: 500.00
recipient: Client A
created: 2026-03-19T10:30:00
expires: 2026-03-20T10:30:00
status: pending
---

# Approval Required: Payment to Client A

**Amount:** $500.00  
**Reason:** Invoice #123 payment  
**Due:** 2026-03-20

## Details

- Vendor: Client A (approved vendor since 2025)
- PO Number: PO-12345
- Budget Category: Software licenses
- Notes: Recurring monthly payment

## To Approve
Move this file to `/Approved/` folder

## To Reject
Move this file to `/Rejected/` folder

## To Request Changes
Move this file to `/Needs_Revision/` folder with comments
```

**Flow:**
```
Claude detects sensitive action
    ↓
Creates approval request in Pending_Approval/
    ↓
Human reviews (notification sent)
    ↓
Human moves to Approved/ or Rejected/
    ↓
Orchestrator executes if approved
```

---

### **6. Approved/**

| Attribute | Specification |
|-----------|---------------|
| **Purpose** | Human-approved tasks ready for execution |
| **Created By** | Human (moves from Pending_Approval/) |
| **Used By** | **Human** (moves here), **Orchestrator** (executes) |
| **When Used** | After human approves sensitive action |
| **Why** | Clear signal to execute approved actions |
| **Retention** | Until executed (typically < 1 minute) |

**Flow:**
```
Human moves file from Pending_Approval/ to Approved/
    ↓
Orchestrator detects (within 5 seconds)
    ↓
Executes action (send email, make payment, etc.)
    ↓
Moves to Done/
    ↓
Logs action in Logs/
```

---

### **7. Rejected/**

| Attribute | Specification |
|-----------|---------------|
| **Purpose** | Human-rejected tasks |
| **Created By** | Human (moves from Pending_Approval/) |
| **Used By** | **Human** (moves here), **Orchestrator** (logs) |
| **When Used** | When human rejects action |
| **Why** | Track rejected actions, learn from rejections |
| **Retention** | Indefinite (audit trail) |

**Flow:**
```
Human moves file from Pending_Approval/ to Rejected/
    ↓
Orchestrator logs rejection
    ↓
May notify Claude to learn from rejection
    ↓
Task archived with rejection reason
```

---

### **8. Needs_Revision/**

| Attribute | Specification |
|-----------|---------------|
| **Purpose** | Tasks that need rework or correction |
| **Created By** | Human (moves here with comments) |
| **Used By** | **Human** (moves here), **Claude** (revises) |
| **When Used** | When output is incorrect or incomplete |
| **Why** | Quality control, iterative improvement |
| **Retention** | Until revised and approved |

**Flow:**
```
Human reviews Claude's output (email draft, plan, etc.)
    ↓
Finds errors or issues
    ↓
Moves to Needs_Revision/
    ↓
Adds comment: "Fix tone, add signature, verify numbers"
    ↓
Claude picks up and revises
    ↓
Resubmits for approval or moves to Done/
```

---

### **9. Plans/**

| Attribute | Specification |
|-----------|---------------|
| **Purpose** | **Claude's action plans** - step-by-step strategies |
| **Created By** | Claude (creates when analyzing complex tasks) |
| **Used By** | **Claude** (creates/follows), **Human** (reviews), **Orchestrator** (tracks) |
| **When Used** | When Claude analyzes complex task |
| **Why** | Transparency, human oversight, audit trail |
| **Retention** | 90 days (then archived) |

**File Naming Convention:**
```
PLAN_{task_id}_{description}.md

Examples:
- PLAN_file_20260319_103000_invoice.pdf.md
- PLAN_email_20260319_104500_client_proposal.md
```

**Plan Format:**
```markdown
# Plan: Process Invoice from Client A

**Task ID:** file_20260319_103000_invoice.pdf  
**Created:** 2026-03-19 10:30:00  
**Created By:** Claude Code  
**Status:** In Progress

## Analysis

- Invoice amount: $500
- Due date: 2026-03-30
- Vendor: Client A (approved vendor)
- Budget category: Software licenses
- PO matches: Yes (PO-12345)

## Steps

- [x] Read invoice file
- [x] Extract amount and due date
- [x] Verify against purchase order
- [ ] Check budget availability
- [ ] Create payment approval request
- [ ] Schedule payment if approved

## Reasoning

This invoice is for recurring software licenses. 
Vendor is approved. Budget is available.
Recommend approval.

## Potential Issues

- Payment requires human approval (>$100)
- Need to verify PO #12345 matches
- Payment due in 11 days (not urgent)

## Timeline

- Estimated completion: 2026-03-19 11:00:00
- Dependencies: Human approval
- Risks: None identified
```

**When Plans Are Created:**

1. **Complex Tasks** - Multi-step actions (≥ 3 steps)
2. **High Priority** - Urgent tasks need clear plan
3. **First Time** - New type of task
4. **Human Request** - Human asks for plan before execution
5. **High Value** - Payments over $500

**Flow:**
```
Claude receives complex task
    ↓
Analyzes requirements
    ↓
Creates plan in Plans/
    ↓
Human reviews plan (optional for high-value tasks)
    ↓
Claude executes plan step by step
    ↓
Updates plan with checkmarks [x]
    ↓
Moves to Done/ when complete
```

---

### **10. Done/**

| Attribute | Specification |
|-----------|---------------|
| **Purpose** | Completed tasks archive |
| **Created By** | Orchestrator (moves here after completion) |
| **Used By** | **Orchestrator** (moves here), **Human** (reviews) |
| **When Used** | After task is successfully completed |
| **Why** | Audit trail, metrics, weekly reports |
| **Retention** | 90 days (then auto-archived) |

**File Naming:**
```
Same as source file in Needs_Action/

Example:
- FILE_20260319_103000_invoice.pdf.md (from Needs_Action/)
```

**Flow:**
```
Task completed successfully
    ↓
Orchestrator moves to Done/
    ↓
Updates Dashboard.md metrics
    ↓
File stays here for 90 days
    ↓
Auto-archived after retention period
```

---

### **11. Briefings/**

| Attribute | Specification |
|-----------|---------------|
| **Purpose** | CEO briefings - scheduled business summaries |
| **Created By** | Orchestrator (automated), Claude (assists) |
| **Used By** | **Orchestrator** (creates), **Human** (reads) |
| **When Used** | Scheduled (Monday morning, Friday evening) |
| **Why** | Business oversight, decision support |
| **Retention** | Indefinite (business records) |

**File Naming Convention:**
```
{YYYY-MM-DD}_{Day}_{Type}.md

Examples:
- 2026-03-19_Monday_Briefing.md
- 2026-03-21_Wednesday_Briefing.md
- 2026-03-Q1_Quarterly_Report.md
```

**Briefing Format:**
```markdown
# Monday Morning CEO Briefing

**Period:** 2026-03-12 to 2026-03-19  
**Generated:** 2026-03-19 08:00:00

## Executive Summary

Strong week with revenue ahead of target. One bottleneck identified.

## Revenue

- **This Week:** $2,450
- **MTD:** $4,500 (45% of $10,000 target)
- **Trend:** On track

## Completed Tasks

- [x] Client A invoice sent and paid ($500)
- [x] Project Alpha milestone 2 delivered
- [x] Weekly social media posts scheduled

## Bottlenecks

| Task | Expected | Actual | Delay |
|------|----------|--------|-------|
| Client B proposal | 2 days | 5 days | +3 days |

## Proactive Suggestions

### Cost Optimization
- **Notion:** No team activity in 45 days. Cost: $15/month.
  - [ACTION] Cancel subscription? Move to Pending_Approval

### Upcoming Deadlines
- Project Alpha final delivery: Jan 15 (9 days)
- Quarterly tax prep: Jan 31 (25 days)
```

**Schedule:**
| Briefing Type | Frequency | When Generated |
|---------------|-----------|----------------|
| Daily Briefing | Daily | 8:00 AM PKT |
| Monday Briefing | Weekly | Monday 8:00 AM PKT |
| Friday Summary | Weekly | Friday 6:00 PM PKT |
| Monthly Report | Monthly | 1st of month |
| Quarterly Report | Quarterly | Start of quarter |

---

### **12. Logs/**

| Attribute | Specification |
|-----------|---------------|
| **Purpose** | System audit logs |
| **Created By** | LoggingManager (automatic) |
| **Used By** | **LoggingManager** (writes), **Human** (debugs) |
| **When Used** | Every system action |
| **Retention** | 90 days (then auto-deleted) |

**Subfolder Structure:**
```
Logs/
├── timeline/
│   └── {YYYY-MM-DD}.md          ← Daily activity timeline
├── tasks/
│   ├── task-{type}_{timestamp}_{id}.md  ← Per-task detailed logs
│   └── ...
└── errors/
    └── errors_{YYYY-MM-DD}.md    ← Error log with stack traces
```

**Timeline Format:** `Logs/timeline/2026-03-19.md`
```markdown
# 2026-03-19 Activity Log

08:00:00 [orchestrator] → 🔄 Started daily briefing generation
09:00:00 [filesystem_watcher] → 📁 New file detected: invoice.pdf
09:00:05 [orchestrator] → 🔒 Claimed task: FILE_20260319_090000_invoice.pdf.md
09:00:10 [orchestrator] → 📋 Claude created plan
09:00:15 [orchestrator] → ⚠️ Approval requested: Payment $500
09:05:00 [human] → ✅ Human approved
09:05:05 [orchestrator] → 💰 Payment drafted
09:05:10 [orchestrator] → ✅ Task completed
```

**Task Log Format:** `Logs/tasks/task-file_drop_20260319_090000_....md`
```markdown
# Task file_drop_20260319_090000_invoice.pdf

trigger_file:    D:/.../Drop/invoice.pdf
created:         2026-03-19T09:00:00
status:          completed
final_result:    payment processed
duration_sec:    310

## Event Timeline

09:00:00 [filesystem_watcher] 📁 New file detected
09:00:01 [filesystem_watcher] 🔍 Hash: abc123...
09:00:02 [filesystem_watcher] 📝 Created metadata
09:00:03 [orchestrator] 🔒 Claimed task
09:00:05 [orchestrator] 📋 Claude plan created
09:00:10 [orchestrator] ⚠️ Approval requested
09:05:00 [orchestrator] ✅ Human approved
09:05:05 [orchestrator] 💰 Payment drafted
09:05:10 [orchestrator] ✅ Task completed
```

---

### **13. Accounting/**

| Attribute | Specification |
|-----------|---------------|
| **Purpose** | Financial records and transactions |
| **Created By** | Finance Watcher (automated), Claude (assists) |
| **Used By** | **Finance Watcher** (writes), **Claude** (analyzes), **Human** (reviews) |
| **When Used** | When transactions detected |
| **Retention** | 7 years (legal requirement) |

**File Structure:**
```
Accounting/
├── Current_Month.md              ← Current month transactions
├── 2026-03.md                    ← Monthly archive
├── 2026-Q1_Summary.md            ← Quarterly summary
└── 2026_Annual.md                ← Annual summary
```

**Current Month Format:** `Accounting/Current_Month.md`
```markdown
# March 2026 Transactions

## Income

| Date | Description | Amount | Status | Category |
|------|-------------|--------|--------|----------|
| 2026-03-05 | Client A - Invoice #123 | $500 | Paid | Services |
| 2026-03-10 | Client B - Invoice #124 | $750 | Pending | Services |

## Expenses

| Date | Description | Amount | Status | Category |
|------|-------------|--------|--------|----------|
| 2026-03-01 | Software licenses | $150 | Paid | Operations |
| 2026-03-15 | Office supplies | $75 | Paid | Operations |

## Summary

- **Total Income:** $1,250
- **Total Expenses:** $225
- **Net:** $1,025
- **Outstanding:** $750 (Client B)
```

---

## 📄 Configuration Files

### **1. Business_Goals.md**

| Attribute | Specification |
|-----------|---------------|
| **Purpose** | Company objectives and targets |
| **Created By** | Human (business owner) |
| **Used By** | **Human** (writes/updates), **Claude** (references for decisions) |
| **When Used** | When making decisions, prioritizing tasks |
| **Update Frequency** | Quarterly (or as business goals change) |

**Content:**
```markdown
# Q1 2026 Business Goals

## Revenue Targets
- Monthly: $10,000
- Quarterly: $30,000

## Key Metrics
- Client response time: < 24 hours
- Invoice payment rate: > 90%
- Software costs: < $500/month

## Active Projects
1. Project Alpha - Due Jan 15 - Budget $2,000
2. Project Beta - Due Jan 30 - Budget $3,500

## Rules
- Flag any payment over $500 for approval
- Respond to all client emails within 24 hours
- Review software subscriptions monthly
```

**How Claude Uses It:**
```
Task: "Should we buy new software for $100/month?"
    ↓
References Business_Goals.md
    ↓
Checks: Software costs limit is $500/month
    ↓
Checks: Current spending is $450/month
    ↓
Decision: Can approve (under limit: $450 + $100 = $550... exceeds!)
    ↓
Creates approval request with warning
```

---

### **2. Company_Handbook.md**

| Attribute | Specification |
|-----------|---------------|
| **Purpose** | Rules of engagement, policies, procedures |
| **Created By** | Human (business owner) |
| **Used By** | **Human** (writes/updates), **Claude** (follows) |
| **When Used** | When deciding how to act |
| **Update Frequency** | As policies change |

**Content:**
```markdown
# Company Handbook

## Communication Rules
- Always be polite and professional
- Use formal tone with clients
- Use casual tone internally

## Payment Rules
- All payments over $100 require approval
- Recurring payments under $50 auto-approved
- New vendors require manual approval

## Email Rules
- Respond within 24 hours
- CC manager on all proposals
- Never promise delivery dates without approval

## Working Hours
- Business hours: 9 AM - 6 PM PKT
- Emergency contact: +92-XXX-XXXXXXX
```

**How Claude Uses It:**
```
Task: Reply to client email
    ↓
References Company_Handbook.md
    ↓
Finds: "Use formal tone with clients"
    ↓
Drafts email with formal tone
    ↓
Checks: "Respond within 24 hours"
    ↓
Prioritizes task as urgent
```

---

### **3. Dashboard.md**

| Attribute | Specification |
|-----------|---------------|
| **Purpose** | Real-time business overview |
| **Created By** | Orchestrator (auto-updates) |
| **Used By** | **Orchestrator** (updates), **Human** (reads) |
| **When Used** | Continuously updated |
| **Update Frequency** | Real-time (after each task) |

**Content:**
```markdown
# Business Dashboard

**Last Updated:** 2026-03-19 10:30:00

## Queue Status
| Status | Count |
|--------|-------|
| Pending | 5 |
| Processing | 2 |
| Pending Approval | 1 |
| Done Today | 12 |

## Revenue MTD
- Target: $10,000
- Actual: $4,500
- Progress: 45%

## Active Projects
- Project Alpha: 70% complete
- Project Beta: 30% complete

## Recent Activity
- 10:30 AM: Invoice from Client A processed
- 10:15 AM: Email to Client B sent
- 09:45 AM: Payment approved for Vendor C
```

**Update Triggers:**
- Task completed → Update "Done Today" counter
- Payment received → Update revenue
- Project milestone → Update project progress
- New task → Update queue status

---

### **4. CLAUDE.md**

| Attribute | Specification |
|-----------|---------------|
| **Purpose** | Claude-specific instructions and context |
| **Created By** | Human (business owner) |
| **Used By** | **Claude** (reads on every invocation) |
| **When Used** | Every time Claude Code is invoked |
| **Update Frequency** | As needed |

**Content:**
```markdown
# Claude Code Instructions

## Your Role
You are the AI Employee for this business. You handle:
- Email processing
- Invoice management
- Social media posting
- Customer support

## Important Rules
1. NEVER make payments without approval
2. ALWAYS log your actions
3. ASK when uncertain
4. PREFER draft mode for sensitive actions

## Working Style
- Be concise in communications
- Double-check numbers
- Cite sources for information
- Create plans for complex tasks

## Current Priorities
1. Process all pending invoices
2. Respond to urgent client emails
3. Prepare Q1 tax documents
```

**How Claude Uses It:**
```
Claude Code starts
    ↓
Reads CLAUDE.md first (before any task)
    ↓
Understands role and constraints
    ↓
Processes tasks according to instructions
    ↓
Follows rules (e.g., "ALWAYS log actions")
```

---

## 🔄 Complete Task Flow Examples

### **Example 1: File Drop → Payment**

```
1. Human drops file
   Location: Inbox/Drop/invoice.pdf
   Time: 09:00:00

2. Filesystem Watcher detects
   Action: Creates metadata file
   Location: Needs_Action/FILE_20260319_090000_invoice.pdf.md
   Time: 09:00:05

3. Orchestrator scans
   Action: Detects pending task
   Moves: Needs_Action/ → Processing/
   Time: 09:01:00

4. Claude processes
   Action: Reads invoice, extracts data
   Creates: Plans/PLAN_invoice_20260319.md
   Decision: Payment requires approval (>$100)
   Time: 09:01:30

5. Claude creates approval request
   Location: Pending_Approval/APPROVAL_payment_invoice.md
   Time: 09:02:00

6. Human reviews
   Action: Reviews invoice details
   Decision: Approves
   Moves: Pending_Approval/ → Approved/
   Time: 09:05:00

7. Orchestrator executes
   Action: Processes payment via MCP server
   Moves: Approved/ → Done/
   Time: 09:05:10

8. System updates
   Updates: Dashboard.md (revenue, counters)
   Logs: Logs/timeline/2026-03-19.md
   Logs: Logs/tasks/task-file_drop_....md
   Time: 09:05:15
```

---

### **Example 2: Email → Response**

```
1. Gmail Watcher detects
   Action: New important email
   Location: Needs_Action/EMAIL_20260319_100000_client_inquiry.md
   Time: 10:00:00

2. Orchestrator scans
   Action: Detects urgent email (from VIP client)
   Moves: Needs_Action/ → Processing/
   Time: 10:01:00

3. Claude processes
   Action: Reads email, analyzes intent
   Creates: Plans/PLAN_email_response.md
   Decision: Can respond directly (known client)
   Time: 10:01:30

4. Claude drafts response
   Action: Creates email draft
   References: Company_Handbook.md (tone, rules)
   Time: 10:02:00

5. Human reviews (optional for VIP)
   Action: Reviews draft
   Decision: Approves with minor edits
   Time: 10:03:00

6. Orchestrator sends
   Action: Sends email via Gmail MCP
   Moves: Processing/ → Done/
   Time: 10:03:10

7. System updates
   Updates: Dashboard.md (response time metric)
   Logs: Logs/timeline/2026-03-19.md
   Time: 10:03:15
```

---

## 📊 Folder Usage Summary

| Folder | Created By | Read By | Write Access | Retention |
|--------|------------|---------|--------------|-----------|
| `Inbox/Drop/` | Human | Watcher | Human | < 1 minute |
| `Inbox/Drop_History/` | Watcher | Human, Watcher | Watcher | Indefinite |
| `Needs_Action/` | Watchers | Orchestrator, Claude | Watchers | < 5 minutes |
| `Processing/` | Orchestrator | Claude | Orchestrator | < 5 minutes |
| `Pending_Approval/` | Claude | Human | Claude, Human | < 24 hours |
| `Approved/` | Human | Orchestrator | Human | < 1 minute |
| `Rejected/` | Human | Orchestrator | Human | Indefinite |
| `Needs_Revision/` | Human | Claude | Human, Claude | < 24 hours |
| `Plans/` | Claude | Human, Claude | Claude | 90 days |
| `Done/` | Orchestrator | Human | Orchestrator | 90 days |
| `Briefings/` | Orchestrator | Human | Orchestrator | Indefinite |
| `Logs/` | LoggingManager | Human | LoggingManager | 90 days |
| `Accounting/` | Finance Watcher | Claude, Human | Finance Watcher | 7 years |

---

## 🎯 Key Design Principles

1. **Single Source of Truth** - Each task exists in ONE folder at a time
2. **Clear Ownership** - Each folder has specific owner(s)
3. **Audit Trail** - Every action is logged
4. **Human Oversight** - Sensitive actions require approval
5. **Automatic Cleanup** - Old files auto-archived
6. **Consistent Naming** - Predictable file naming conventions
7. **Status Tracking** - Clear status at every stage

---

**End of Vault Folder & File Architecture Specification**

*For questions or updates, refer to RULES.md or contact the project maintainer.*
