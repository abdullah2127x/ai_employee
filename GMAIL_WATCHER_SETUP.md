# Gmail Watcher Setup Guide

**Version:** 2.0 (v2 Architecture)  
**Last Updated:** 2026-03-23

---

## Overview

The Gmail Watcher automatically monitors your Gmail inbox for new unread/important messages and creates task files in the AI Employee system for automated processing.

**What it does:**
1. Connects to Gmail API (OAuth2 authenticated)
2. Checks for new messages every 2 minutes (configurable)
3. Filters by Gmail query (default: `is:unread is:important`)
4. Creates task files in `Needs_Action/` folder
5. Orchestrator moves tasks to `Processing/` for Claude Code AI processing
6. AI categorizes, responds, and takes action based on email content

---

## Prerequisites

### 1. Google Cloud Project Setup

**Step 1: Create Google Cloud Project**

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click "Create Project"
3. Name it (e.g., "AI Employee Gmail")
4. Click "Create"

**Step 2: Enable Gmail API**

1. In your project, go to **APIs & Services** → **Library**
2. Search for "Gmail API"
3. Click on it and press **Enable**

**Step 3: Create OAuth Credentials**

1. Go to **APIs & Services** → **Credentials**
2. Click **+ CREATE CREDENTIALS** → **OAuth client ID**
3. If prompted, configure "OAuth consent screen":
   - User Type: **External**
   - App name: AI Employee
   - User support email: Your email
   - Developer contact: Your email
   - Click **Save and Continue**
   - Scopes: Skip this step
   - Test users: Add your Gmail address
   - Click **Save and Continue**

4. Back to **Create OAuth Client ID**:
   - Application type: **Desktop app**
   - Name: AI Employee Gmail Watcher
   - Click **Create**

5. Download the credentials:
   - Click **Download JSON**
   - Save as `credentials.json`

---

### 2. Install Gmail API Libraries

```bash
# From project root directory
pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client

# Or with uv (if using uv package manager)
uv add google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client
```

---

### 3. Place Credentials File

**Option A: Default Location (Recommended)**
```
vault/credentials.json
```

**Option B: Custom Location**
Place anywhere and set path in `.env` (see Configuration section)

---

## Configuration

### Enable Gmail Watcher in `.env`

Create or edit `.env` file in project root:

```env
# ============================================================================
# Gmail Watcher Configuration
# ============================================================================

# Enable/disable Gmail watcher (true/false)
ENABLE_GMAIL_WATCHER=true

# How often to check Gmail for new messages (in seconds)
# Minimum: 60, Maximum: 600, Default: 120
GMAIL_WATCHER_CHECK_INTERVAL=120

# Gmail search query for filtering messages
# Examples:
#   "is:unread is:important" - Unread + Important (default)
#   "is:unread from:boss@company.com" - Unread emails from specific sender
#   "is:unread subject:invoice" - Unread emails with "invoice" in subject
#   "label:inbox is:unread" - All unread inbox emails
GMAIL_WATCHER_QUERY=is:unread is:important

# Path to Gmail API credentials (optional, defaults to vault/credentials.json)
# GMAIL_CREDENTIALS_PATH=vault/credentials.json
# GMAIL_CREDENTIALS_PATH=C:\path\to\credentials.json
```

---

## First Run - OAuth Authorization

When you run the orchestrator for the first time:

1. **Start the orchestrator:**
   ```bash
   python orchestrator.py
   ```

2. **Browser window opens automatically** showing Google OAuth consent screen

3. **Sign in** with your Gmail account

4. **Grant permissions** when prompted:
   - "View and manage your Gmail messages"
   - This is required for the watcher to read emails

5. **Authorization complete** - browser shows "Success!" message

6. **Token saved** to `~/.gmail_token.json` (hidden file in your home directory)

7. **Orchestrator continues** running with Gmail watcher active

---

## How It Works

### Architecture Flow

```
┌─────────────────────────────────────────────────────────────┐
│  Gmail Servers                                              │
│  - New email arrives                                        │
│  - Marked as unread + important                             │
└─────────────────────────────────────────────────────────────┘
                          │
                          │ Gmail API Polling (every 2 min)
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  GmailWatcher (watchers/gmail_watcher.py)                   │
│  1. check_for_updates()                                     │
│     - Query: is:unread is:important                         │
│     - Returns: List of new message IDs                      │
│  2. create_action_file()                                    │
│     - Fetch full message                                    │
│     - Extract headers (From, Subject, Date)                 │
│     - Decode body (plain text or HTML)                      │
│     - Determine priority (normal/high/urgent)               │
└─────────────────────────────────────────────────────────────┘
                          │
                          │ create_email_task()
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  Needs_Action/EMAIL_<task_id>.md                            │
│  ---                                                        │
│  type: email                                                │
│  from: sender@example.com                                   │
│  subject: Invoice #123                                      │
│  priority: high                                             │
│  ---                                                        │
│  [Email content]                                            │
└─────────────────────────────────────────────────────────────┘
                          │
                          │ Orchestrator FolderWatcher detects
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  Processing/EMAIL_<task_id>.md                              │
│  (File moved by orchestrator)                               │
└─────────────────────────────────────────────────────────────┘
                          │
                          │ claude_runner.py invoked
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  Claude Code Processing                                     │
│  1. Reads CLAUDE.md (auto-loaded)                           │
│  2. Reads .claude/skills/process-email/SKILL.md             │
│  3. Reads Business_Goals.md + Company_Handbook.md           │
│  4. Analyzes email content                                  │
│  5. Returns JSON decision                                   │
└─────────────────────────────────────────────────────────────┘
                          │
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  Output Files                                               │
│  - Done/RESULT_<task_id>.md         (complete_task)         │
│  - Pending_Approval/RESULT_*.md     (create_approval_request)│
│  - Needs_Revision/<task_id>.md      (needs_revision)        │
└─────────────────────────────────────────────────────────────┘
```

---

### Email Processing Examples

**Example 1: Invoice Under $50 (Auto-Approved)**

```
Email Received:
  From: vendor@acme.com
  Subject: Invoice #456 - $35.00
  Content: "Please find attached invoice for services..."

AI Decision (via Claude Code):
  - Reads Company_Handbook.md: Payments under $50 auto-approved
  - Checks vendor in approved list
  - Decision: complete_task

Result:
  - Task file → Done/
  - Response logged in RESULT_*.md
```

**Example 2: Invoice Over $100 (Requires Approval)**

```
Email Received:
  From: newvendor@example.com
  Subject: Invoice #789 - $250.00
  Content: "Payment due in 30 days..."

AI Decision (via Claude Code):
  - Reads Company_Handbook.md: Payments over $100 need approval
  - Vendor not in approved list
  - Decision: create_approval_request

Result:
  - Task file → Pending_Approval/
  - Human must review and approve/reject
```

**Example 3: Client Inquiry (Auto-Response)**

```
Email Received:
  From: prospect@company.com
  Subject: Consulting Rates Inquiry
  Content: "What are your rates for strategy consulting?"

AI Decision (via Claude Code):
  - Reads Company_Handbook.md: Approved rates $150/hr
  - Decision: complete_task with response

Result:
  - Task file → Done/
  - Response sent (future: via email integration)
```

---

## Monitoring & Logs

### Timeline Logs

View real-time activity:
```
vault/Logs/timeline/YYYY-MM-DD.md
```

Gmail watcher entries look like:
```
10:30:00 [gmail_watcher] → GmailWatcher initialized | Query: is:unread is:important | Interval: 120s
10:32:15 [gmail_watcher] → Found 3 messages, 2 new
10:32:16 [gmail_watcher] → Created task file: EMAIL_20260323_103216_abc123.md | From: sender@example.com
```

### Task Logs

Detailed per-task logs:
```
vault/Logs/tasks/task-email_*.md
```

### Error Logs

Errors with stack traces:
```
vault/Logs/errors/errors_YYYY-MM-DD.md
```

---

## Troubleshooting

### Problem: "Gmail credentials not found"

**Solution:**
1. Verify `credentials.json` exists in `vault/` folder
2. Check filename is exactly `credentials.json` (not `credentials.json.txt`)
3. Verify file is valid JSON (open in text editor)

---

### Problem: "Gmail API libraries not installed"

**Solution:**
```bash
pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client
```

---

### Problem: Browser doesn't open for OAuth

**Solution:**
1. Check console output for URL
2. Manually copy/paste URL into browser
3. Complete OAuth flow
4. Token will be saved automatically

---

### Problem: No emails being processed

**Check:**
1. Is Gmail watcher enabled?
   ```bash
   # Check .env file
   ENABLE_GMAIL_WATCHER=true
   ```

2. Is the Gmail query too restrictive?
   ```bash
   # Try broader query
   GMAIL_WATCHER_QUERY=is:unread
   ```

3. Check Gmail API quota
   - Gmail API has daily limits
   - Check [Google Cloud Console](https://console.cloud.google.com/)

4. Check logs for errors
   ```
   vault/Logs/timeline/YYYY-MM-DD.md
   ```

---

### Problem: Same email processed multiple times

**Solution:**
- Processed IDs are tracked in `.gmail_processed_ids.json`
- File may be corrupted - delete it to reset:
  ```bash
  rm vault/.gmail_processed_ids.json
  ```

---

## Advanced Configuration

### Custom Gmail Queries

**Filter by sender:**
```env
GMAIL_WATCHER_QUERY=is:unread from:boss@company.com
```

**Filter by subject:**
```env
GMAIL_WATCHER_QUERY=is:unread subject:invoice
```

**Filter by label:**
```env
GMAIL_WATCHER_QUERY=label:Projects is:unread
```

**Exclude newsletters:**
```env
GMAIL_WATCHER_QUERY=is:unread is:important -category:promotions -category:updates
```

**Multiple conditions:**
```env
GMAIL_WATCHER_QUERY=is:unread (from:client.com OR from:partner.com)
```

---

### Change Check Interval

**Check every 5 minutes:**
```env
GMAIL_WATCHER_CHECK_INTERVAL=300
```

**Check every 30 seconds (not recommended):**
```env
GMAIL_WATCHER_CHECK_INTERVAL=30
```

**Minimum:** 60 seconds (Gmail API quota friendly)  
**Maximum:** 600 seconds (10 minutes)

---

### Multiple Gmail Accounts

Run separate orchestrator instances with different credential paths:

**Instance 1 (Work Email):**
```env
ENABLE_GMAIL_WATCHER=true
GMAIL_CREDENTIALS_PATH=vault/work_credentials.json
GMAIL_WATCHER_QUERY=is:unread is:important
```

**Instance 2 (Personal Email):**
```env
ENABLE_GMAIL_WATCHER=true
GMAIL_CREDENTIALS_PATH=vault/personal_credentials.json
GMAIL_WATCHER_QUERY=is:unread from:family.com
```

---

## Security Best Practices

### 1. Protect Credentials

- Never commit `credentials.json` to Git (already in `.gitignore`)
- Store in secure location
- Use separate Google Cloud project for production

### 2. Limit OAuth Scopes

Current scope (read-only):
```
https://www.googleapis.com/auth/gmail.readonly
```

**Do NOT modify** to send emails unless you understand security implications.

### 3. Revoke Access

To revoke Gmail access:
1. Go to [Google Account Security](https://myaccount.google.com/security)
2. **Third-party apps with account access**
3. Find "AI Employee"
4. Click **Remove Access**

### 4. Token Storage

OAuth token stored in:
- Windows: `C:\Users\<username>\.gmail_token.json`
- macOS/Linux: `~/.gmail_token.json`

Delete this file to force re-authentication.

---

## Future Enhancements

**Planned features:**
- [ ] Email reply capability (via Gmail API send)
- [ ] Attachment download and processing
- [ ] Email labeling/mark as read
- [ ] Advanced filtering rules (per sender/domain)
- [ ] Multiple account support in single orchestrator
- [ ] Email threading/conversation tracking

---

## Support

**Documentation:**
- `README.md` - Project overview
- `QUICKSTART.md` - Quick start guide
- `SETTINGS_AND_WORKFLOW.md` - Settings reference

**Logs:**
- `vault/Logs/timeline/` - Activity logs
- `vault/Logs/errors/` - Error logs

**Skill Files:**
- `vault/.claude/skills/process-email/SKILL.md` - Email processing rules
- `vault/CLAUDE.md` - AI Employee instructions

---

*Last updated: 2026-03-23 | Version: 2.0*
