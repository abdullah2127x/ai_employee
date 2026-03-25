# Gmail Watcher IMAP - Update Summary

**Date:** 2025-03-25  
**File Updated:** `watchers/gmail_watcher_imap.py`  
**Reference:** `gmail_filter_processor.py`

---

## ✅ Implementation Complete - All Phases

### Phase 1: Core Filtering ✅
- [x] Added `FILTER_CONFIG` constant with comprehensive filtering rules
- [x] Added `should_process_email()` method for smart filtering
- [x] Updated `check_for_updates()` to apply filtering logic
- [x] Added tracking lists in `__init__()` for processed/skipped emails

### Phase 2: Enhanced Task Files ✅
- [x] Updated `create_action_file()` with comprehensive YAML frontmatter
- [x] Added thread detection (In-Reply-To, References headers)
- [x] Added filter reason tracking in task metadata
- [x] Enhanced task file format with Gmail links, priority, status

### Phase 3: Logging & Reporting ✅
- [x] Added `_generate_skipped_report()` method
- [x] Added `_generate_processing_index()` method
- [x] Added `_generate_status_dashboard()` method
- [x] Updated `run()` to call logging methods after processing

### Phase 4: Polish & Enhancements ✅
- [x] Enhanced `_decode_body()` with better HTML-to-text conversion
- [x] Updated `_connect()` to use `readonly=False` for marking as read
- [x] Changed default query from "UNREAD IMPORTANT" to "UNSEEN"
- [x] Added periodic dashboard updates (every 10 cycles)
- [x] Added comprehensive docstrings and inline comments

---

## 📊 New Features

### 1. Smart Filtering
Filters emails based on:
- **Gmail Categories:** Skip promotions, social, updates, forums
- **Sender Domains:** Skip LinkedIn, GitHub, Facebook, etc.
- **Business Domains:** Always process Amazon, Google, Microsoft, banks, gov
- **Subject Keywords:** Skip newsletters, digests, promos
- **Priority Keywords:** Always process urgent, ASAP, invoice, meeting, etc.
- **Personal Domains:** Always process Gmail, Yahoo, Outlook, Hotmail

### 2. Comprehensive Logging
Three auto-generated log files in `vault/Logs/`:
- **gmail_skipped.md** - All skipped emails with reasons
- **gmail_processed.md** - All processed emails with task IDs
- **gmail_status_dashboard.md** - Real-time status overview

### 3. Enhanced Task Files
New task file format includes:
```yaml
---
type: email
task_id: email_20250325_143022_Subject
from: sender @example.com
to: me @gmail.com
subject: Important Meeting
received: 2025-03-25T14:30:22
priority: high
status: pending
filter_reason: Priority: 'meeting' in subject
is_reply: false
gmail_message_id: 18e1a2b3c4d5e6f7
gmail_link: https://mail.google.com/mail/u/0/#inbox/18e1a2b3c4d5e6f7

# AI Processing Status
ai_status: pending
ai_processed_at: [PENDING]
ai_decision: [PENDING]
ai_category: [PENDING]
ai_summary: [PENDING]
---
```

### 4. Thread Detection
- Detects reply emails via `In-Reply-To` and `References` headers
- Adds thread indicator in task file
- Helps AI understand conversation context

### 5. Status Dashboard
Real-time dashboard showing:
- Processing status breakdown (pending, in_progress, completed, etc.)
- Processing statistics (total processed/skipped)
- Recent processed emails table
- Quick links to logs and task files

---

## 🔧 Technical Changes

### Modified Methods

#### `__init__()`
- Added `FILTER_CONFIG` import
- Initialized `processed_email_details` and `skipped_emails` lists
- Updated default query to "UNSEEN"

#### `_connect()`
- Changed `readonly=True` → `readonly=False` (needed for marking as read)

#### `_decode_body()` (renamed from `_decode_message_body`)
- Enhanced HTML-to-text conversion
- Better character filtering for clean text

#### `check_for_updates()`
- **Major rewrite** to include smart filtering
- Fetches full email with `X-GM-LABELS` for category detection
- Calls `should_process_email()` for each email
- Tracks skipped emails for reporting
- Marks skipped emails as read immediately

#### `create_action_file()`
- **Major rewrite** with comprehensive task format
- Accepts `message` dict with 'reason' key
- Generates detailed YAML frontmatter
- Includes thread detection
- Includes Gmail URL
- Tracks processed email details for logging

#### `run()`
- Added `run_counter` for periodic operations
- Calls logging methods after processing batch
- Updates dashboard every 10 cycles even if no new emails
- Generates final dashboard on shutdown

### New Methods

#### `should_process_email(msg, msg_id)`
```python
def should_process_email(self, msg: email.message.Message, msg_id: str) -> Tuple[bool, str]:
    """
    Determine if an email should be processed based on filtering rules.
    
    Returns:
        Tuple of (should_process: bool, reason: str)
    """
```
- Checks if already processed
- Checks Gmail labels (promotions, social, etc.)
- Checks business domains (always process)
- Checks skip domains (LinkedIn, GitHub, etc.)
- Checks priority keywords in subject
- Checks priority domains (Gmail, Yahoo, etc.)
- Checks skip keywords in subject
- Default logic for individual senders

#### `_generate_skipped_report()`
```python
def _generate_skipped_report(self):
    """Append skipped emails to master skipped file (no overwrite)."""
```
- Creates/updates `vault/Logs/gmail_skipped.md`
- Appends new entries (never overwrites)
- Includes timestamp, from, subject, reason, Gmail link

#### `_generate_processing_index()`
```python
def _generate_processing_index(self):
    """Append processed emails to master processed file (no overwrite)."""
```
- Creates/updates `vault/Logs/gmail_processed.md`
- Appends new entries (never overwrites)
- Includes task ID, from, subject, priority, status

#### `_generate_status_dashboard()`
```python
def _generate_status_dashboard(self):
    """Generate status dashboard showing all emails by status."""
```
- Creates/updates `vault/Logs/gmail_status_dashboard.md`
- Shows status breakdown with percentages
- Shows processing statistics
- Lists recent processed emails
- Includes instructions for status updates

---

## 📁 Files Generated

### Log Files (in `vault/Logs/`)
1. **gmail_skipped.md** - Complete log of skipped emails
2. **gmail_processed.md** - Complete log of processed emails
3. **gmail_status_dashboard.md** - Real-time status overview

### Task Files (in `vault/Needs_Action/`)
- Format: `email_YYYYMMDD_HHMMSS_Subject.md`
- Comprehensive YAML frontmatter
- Gmail link for quick access
- Thread detection info
- AI processing status fields

### Tracking File (in `vault/`)
- **.gmail_imap_processed_ids.json** - Tracks processed message IDs with timestamps

---

## 🧪 Testing Checklist

### Filtering Tests
- [ ] Promotions category emails are skipped
- [ ] Social category emails are skipped
- [ ] Updates/newsletters are skipped
- [ ] LinkedIn notifications are skipped
- [ ] GitHub notifications are skipped
- [ ] Personal emails (gmail.com) are processed
- [ ] Business emails (amazon.com, google.com) are processed
- [ ] Emails with "urgent" in subject are processed
- [ ] Emails with "invoice" in subject are processed
- [ ] Emails with "meeting" in subject are processed

### Logging Tests
- [ ] Skipped emails logged to `vault/Logs/gmail_skipped.md`
- [ ] Processed emails logged to `vault/Logs/gmail_processed.md`
- [ ] Dashboard updated at `vault/Logs/gmail_status_dashboard.md`
- [ ] Timeline logging shows filter decisions
- [ ] Logs append (not overwrite)
- [ ] Dashboard updates every 10 cycles when idle

### Task File Tests
- [ ] Task files created in `vault/Needs_Action/`
- [ ] YAML frontmatter includes filter_reason
- [ ] YAML frontmatter includes is_reply
- [ ] YAML frontmatter includes ai_status fields
- [ ] Gmail links are correct (hex format)
- [ ] Thread detection works (In-Reply-To headers)
- [ ] Priority detection works (urgent, invoice, meeting)
- [ ] Body truncated to 3000 chars max

### Continuous Watching Tests
- [ ] Loop runs every 120 seconds (configurable)
- [ ] Already processed emails not processed again
- [ ] Reconnect works if connection lost
- [ ] Graceful shutdown on Ctrl+C
- [ ] Processed IDs persisted across restarts
- [ ] Old processed IDs cleaned up after 7 days

---

## 🚀 Usage

### Start the Watcher
```bash
python watchers/gmail_watcher_imap.py
```

### Or Import in Code
```python
from watchers.gmail_watcher_imap import GmailWatcherIMAP

watcher = GmailWatcherIMAP(
    email_address="your.email@gmail.com",
    app_password="xxxx-xxxx-xxxx-xxxx",
    check_interval=120,  # Check every 2 minutes
)

# Run continuously (Ctrl+C to stop)
watcher.run()
```

### Configuration via .env
```env
GMAIL_IMAP_ADDRESS=your.email@gmail.com
GMAIL_IMAP_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
GMAIL_WATCHER_CHECK_INTERVAL=120
```

---

## 📊 Filtering Configuration

### Skip Categories (Gmail Labels)
- `promotions` - Marketing emails, deals, coupons
- `social` - Social media notifications
- `updates` - Newsletters, automated updates
- `forums` - Forum notifications

### Skip Domains (Automated Senders)
- linkedin.com, github.com, facebook.com
- twitter.com, instagram.com, youtube.com
- medium.com, substack.com, reddit.com, quora.com

### Business Domains (Always Process)
- amazon.com, aws.amazon.com
- google.com, microsoft.com, apple.com
- paypal.com, stripe.com
- bank (any bank domain)
- gov (government domains)

### Priority Keywords (Always Process)
- urgent, asap, important, action required
- payment, invoice, interview, meeting, job, career

### Skip Keywords
- newsletter, digest, weekly roundup
- unsubscribe, marketing, promo, discount, sale, offer

### Priority Domains (Personal Emails)
- gmail.com, yahoo.com, outlook.com, hotmail.com, icloud.com

---

## 🎯 Expected Behavior

### When Email Arrives:
1. **Fetch:** Watcher fetches all UNSEEN emails
2. **Filter:** Each email evaluated against filtering rules
3. **Decision:**
   - **Process:** Create task file, mark as read, log to processed
   - **Skip:** Mark as read, log to skipped
4. **Report:** Update all log files and dashboard
5. **Wait:** Sleep for 120 seconds, repeat

### Example Log Output:
```
[INFO] GmailWatcherIMAP initialized | Email: user@gmail.com | Query: UNSEEN | Interval: 120s | Smart Filtering: ENABLED
[INFO] Gmail IMAP connected | Server: imap.gmail.com:993
[INFO] Found 15 unread, 3 to process, 12 skipped
[INFO] Processing 3 new message(s)
[INFO] Created task file: email_20250325_143022_Meeting_Request.md | From: boss @company.com | Reason: Priority: 'meeting' in subject
[INFO] Created task file: email_20250325_143025_Invoice_Due.md | From: billing @aws.amazon.com | Reason: Business domain: amazon.com
[INFO] Created task file: email_20250325_143030_Quick_Question.md | From: friend@gmail.com | Reason: Priority: gmail.com (personal email)
[INFO] Processing index updated: 3 emails logged
[INFO] Skipped report updated: 12 emails logged
[INFO] Status dashboard updated: vault/Logs/gmail_status_dashboard.md
```

---

## 🔄 Comparison: Before vs After

| Feature | Before | After |
|---------|--------|-------|
| **Filtering** | Basic (UNREAD IMPORTANT only) | Advanced (categories, domains, keywords) |
| **Task Format** | Simple (via task_template) | Comprehensive (YAML + metadata) |
| **Thread Detection** | ❌ No | ✅ Yes (In-Reply-To, References) |
| **Filter Reason** | ❌ No | ✅ Yes (in YAML frontmatter) |
| **Skip Reports** | ❌ No | ✅ Yes (gmail_skipped.md) |
| **Processing Index** | ❌ No | ✅ Yes (gmail_processed.md) |
| **Status Dashboard** | ❌ No | ✅ Yes (gmail_status_dashboard.md) |
| **Logging** | Timeline only | Timeline + Files |
| **Continuous Watch** | ✅ Yes | ✅ Yes (preserved) |
| **Auto-Reconnect** | ✅ Yes | ✅ Yes (preserved) |

---

## 📝 Notes

### Why `readonly=False`?
Changed from `readonly=True` to allow marking emails as read after processing. This prevents re-processing the same emails.

### Why "UNSEEN" instead of "UNREAD IMPORTANT"?
Gmail's "IMPORTANT" flag is unreliable. Better to fetch all UNSEEN emails and apply our own smart filtering logic.

### Append-Only Logging
All log files use append mode (`'a'`) to preserve history. Files are never overwritten.

### Processed IDs Cleanup
Old processed IDs (older than 7 days) are automatically cleaned up to prevent unbounded growth.

### HTML-to-Text Conversion
Simple conversion for HTML emails:
- Replace `<br>` and `<p>` with newlines
- Remove non-printable characters
- Truncate to 3000 chars for task files

---

## 🎉 Success Criteria Met

- ✅ Smart filtering from `gmail_filter_processor.py` integrated
- ✅ Continuous watching loop preserved
- ✅ LoggingManager integration preserved
- ✅ Comprehensive task file format implemented
- ✅ Skip/processed email logging implemented
- ✅ Status dashboard generation implemented
- ✅ Thread detection implemented
- ✅ Filter reason tracking implemented
- ✅ All phases completed in one update

---

**Next Steps:** Test with real Gmail account and verify filtering behavior.
