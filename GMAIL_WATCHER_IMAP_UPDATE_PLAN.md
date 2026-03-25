# Gmail Watcher IMAP Update Plan

## Overview

Update `gmail_watcher_imap.py` to incorporate the advanced filtering logic and comprehensive logging features from `gmail_filter_processor.py`, while preserving the existing continuous watching loop and logging infrastructure.

---

## What to KEEP from `gmail_watcher_imap.py`

### 1. **Core Architecture**
- ✅ Continuous watching loop (`run()` method with `while True`)
- ✅ Check interval configuration (default 120 seconds)
- ✅ IMAP connection management with auto-reconnect
- ✅ Context manager support (`__enter__`/`__exit__`)
- ✅ Processed IDs persistence with timestamps (7-day cleanup)

### 2. **Logging Infrastructure**
- ✅ `LoggingManager` integration for timeline logging
- ✅ `logger.write_to_timeline()` calls throughout
- ✅ `logger.log_warning()` and `logger.log_error()` for error tracking
- ✅ Log levels: INFO, DEBUG, WARNING, ERROR

### 3. **Configuration**
- ✅ Constructor-based configuration (email, password, interval, query)
- ✅ Integration with `core.config.settings`
- ✅ `.gmail_imap_processed_ids.json` for persistence

### 4. **Email Fetching Logic**
- ✅ `check_for_updates()` method structure
- ✅ UID SEARCH for unread emails
- ✅ X-GM-MSGID extraction for Gmail URLs
- ✅ Processed ID filtering

### 5. **Task File Creation**
- ✅ Integration with `utils.task_template.create_email_task()`
- ✅ Atomic file writing (temp file + rename)
- ✅ Marking emails as READ after processing

---

## What to UPDATE from `gmail_filter_processor.py`

### 1. **FILTER_CONFIG Integration** ⭐ PRIORITY

**Location:** Add as class-level constant or module-level constant

```python
FILTER_CONFIG = {
    # Categories to SKIP (Gmail's automatic categorization)
    "skip_categories": [
        "promotions",    # Marketing emails, deals, coupons
        "social",        # Social media notifications
        "updates",       # Newsletters, automated updates
        "forums",        # Forum notifications
    ],
    
    # Sender domains to SKIP (common automated senders)
    "skip_domains": [
        "linkedin.com",
        "github.com",
        "facebook.com",
        "twitter.com",
        "instagram.com",
        "youtube.com",
        "medium.com",
        "substack.com",
        "reddit.com",
        "quora.com",
    ],
    
    # Sender domains to ALWAYS PROCESS (business-critical)
    "business_domains": [
        "amazon.com",
        "aws.amazon.com",
        "google.com",
        "microsoft.com",
        "apple.com",
        "paypal.com",
        "stripe.com",
        "bank",  # Any bank domain
        "gov",  # Government domains
    ],
    
    # Subject keywords to SKIP
    "skip_subject_keywords": [
        "newsletter",
        "digest",
        "weekly roundup",
        "daily digest",
        "unsub",
        "unsubscribe",
        "marketing",
        "promo",
        "discount",
        "sale",
        "offer",
    ],
    
    # Subject keywords to PRIORITIZE (always process)
    "priority_keywords": [
        "urgent",
        "asap",
        "important",
        "action required",
        "payment",
        "invoice",
        "interview",
        "meeting",
        "job",
        "career",
    ],
    
    # Priority sender domains (always process)
    "priority_domains": [
        "gmail.com",  # Personal emails
        "yahoo.com",
        "outlook.com",
        "hotmail.com",
        "icloud.com",
    ],
}
```

### 2. **New Method: `should_process_email()`** ⭐ PRIORITY

**Location:** Add to `GmailWatcherIMAP` class

**Purpose:** Apply smart filtering before creating task files

**Implementation:**
```python
def should_process_email(self, msg: email.message.Message, msg_id: str) -> Tuple[bool, str]:
    """
    Determine if an email should be processed based on filtering rules.
    
    Args:
        msg: Email message object
        msg_id: Message ID
        
    Returns:
        Tuple of (should_process: bool, reason: str)
    """
    # Extract headers
    from_addr = msg.get('From', '')
    subject = msg.get('Subject', '')
    x_gmail_labels = msg.get('X-Gmail-Labels', '')
    
    # Check if already processed
    if msg_id in self.processed_ids:
        return False, "Already processed"
    
    # Check Gmail labels (skip if has promotion/social label)
    labels_lower = x_gmail_labels.lower()
    for category in FILTER_CONFIG['skip_categories']:
        if category.lower() in labels_lower:
            return False, f"Skipped: {category.title()} category"
    
    # Check sender domain
    from_domain = from_addr.split('@')[-1].strip('>').lower() if '@' in from_addr else ''
    
    # BUSINESS DOMAINS - Always process (Amazon, Google, Microsoft, banks, gov)
    for business_domain in FILTER_CONFIG['business_domains']:
        if business_domain in from_domain:
            return True, f"Business domain: {business_domain}"
    
    # Skip known automated senders
    for domain in FILTER_CONFIG['skip_domains']:
        if domain in from_domain:
            return False, f"Skipped: {domain} (automated sender)"
    
    # Priority check - always process these
    subject_lower = subject.lower()
    
    # Check priority keywords
    for keyword in FILTER_CONFIG['priority_keywords']:
        if keyword in subject_lower:
            return True, f"Priority: '{keyword}' in subject"
    
    # Check priority domains (personal emails)
    for domain in FILTER_CONFIG['priority_domains']:
        if domain in from_domain:
            return True, f"Priority: {domain} (personal email)"
    
    # Check skip keywords
    for keyword in FILTER_CONFIG['skip_subject_keywords']:
        if keyword in subject_lower:
            return False, f"Skipped: '{keyword}' in subject"
    
    # Default: process if from individual (not obvious automated sender)
    if '<' not in from_addr and '.' not in from_domain:
        return True, "Individual sender"
    
    # Default: skip if unclear
    return False, "Skipped: No priority indicators"
```

### 3. **Update `check_for_updates()` Method** ⭐ PRIORITY

**Current behavior:** Returns all unread messages

**New behavior:** Fetch all unread, but filter using `should_process_email()`

**Changes:**
```python
def check_for_updates(self) -> List[Dict[str, Any]]:
    # ... existing connection logic ...
    
    # Search for unread messages
    status, messages = self.mail.uid('SEARCH', None, 'UNSEEN')
    message_ids = messages[0].split()
    
    # Filter and categorize messages
    new_messages = []
    skipped_emails = []  # Track for logging
    
    for msg_id in message_ids:
        msg_id_str = msg_id.decode('utf-8')
        
        # Skip if already processed
        if msg_id_str in self.processed_ids:
            continue
        
        # Fetch email to apply filtering
        status, msg_data = self.mail.uid('FETCH', msg_id, '(RFC822 X-GM-MSGID X-GM-LABELS)')
        raw_email = msg_data[0][1]
        msg = email.message_from_bytes(raw_email)
        
        # Apply smart filtering
        should_process, reason = self.should_process_email(msg, msg_id_str)
        
        if should_process:
            # Extract X-GM-MSGID for Gmail URL
            # ... existing X-GM-MSGID extraction logic ...
            
            new_messages.append({
                'id': msg_id_str,
                'gmail_msgid_hex': gmail_msgid_hex,
                'reason': reason,  # Why this email was selected
                'raw_msg': msg,  # Keep for filtering
            })
        else:
            # Track skipped email for logging
            skipped_emails.append({
                'message_id': msg_id_str,
                'from': msg.get('From', 'Unknown'),
                'subject': msg.get('Subject', 'No Subject'),
                'reason': reason,
                'processed_at': datetime.now().isoformat(),
            })
            
            # Mark as read (don't process again)
            self.mail.uid('STORE', msg_id, '+FLAGS', '\\Seen')
    
    # Store skipped emails for logging
    self.skipped_emails = skipped_emails
    
    logger.write_to_timeline(
        f"Found {len(message_ids)} unread, {len(new_messages)} to process, "
        f"{len(skipped_emails)} skipped",
        actor="gmail_watcher_imap",
        message_level="INFO",
    )
    
    return new_messages
```

### 4. **Update `create_action_file()` Method** ⭐ PRIORITY

**Changes:**
- Accept `reason` parameter for filtering explanation
- Include filter reason in task file metadata
- Include thread detection (reply/original)
- Include comprehensive YAML frontmatter

**New Task File Format:**
```python
def create_action_file(self, message: Dict[str, Any]) -> Optional[Path]:
    """
    Create a task file for a Gmail message.
    
    Args:
        message: Message dict with 'id', 'gmail_msgid_hex', 'reason', 'raw_msg'
        
    Returns:
        Path to created file, or None on error
    """
    # ... existing fetch logic ...
    
    # Parse email
    email_data = self._parse_email_headers(msg_data[0][1], gmail_msgid_hex)
    headers = email_data['headers']
    body = email_data['body']
    received_date = email_data['received_date']
    msg = email_data['raw_msg']
    
    # Get filter reason
    filter_reason = message.get('reason', 'Unknown')
    
    # Determine priority
    priority = "normal"
    subject_lower = headers['subject'].lower()
    
    if any(word in subject_lower for word in ['urgent', 'asap', 'emergency']):
        priority = "urgent"
    elif any(word in subject_lower for word in ['invoice', 'payment', 'billing']):
        priority = "high"
    elif 'interview' in subject_lower or 'meeting' in subject_lower:
        priority = "high"
    
    # Detect if this is part of a thread
    is_reply = bool(headers.get('in_reply_to') or headers.get('references'))
    thread_info = ""
    if is_reply:
        in_reply_to = headers.get('in_reply_to', '')
        thread_info = f"\n**Thread:** This is a reply (In-Reply-To: {in_reply_to[:50] if in_reply_to else 'N/A'})"
    
    # Generate task ID (truncate subject to avoid Windows path length issues)
    timestamp = received_date.strftime('%Y%m%d_%H%M%S')
    clean_subject = headers['subject'].replace('Re:', '').replace('Fwd:', '').strip()
    safe_subject = clean_subject[:30].replace(' ', '_').replace('/', '_').replace('\\', '_')
    safe_subject = ''.join(c for c in safe_subject if c.isalnum() or c in ['_', '-'])
    task_id = f"email_{timestamp}_{safe_subject}"
    
    # Truncate body for task file (max 3000 chars)
    truncated_body = body[:3000] + "\n\n[Content truncated...]" if len(body) > 3000 else body
    
    # Build Gmail link
    gmail_link = f"https://mail.google.com/mail/u/0/#inbox/{gmail_msgid_hex}"
    
    # Build comprehensive task content
    task_content = f"""---
type: email
task_id: {task_id}
from: {headers['from']}
to: {headers['to']}
subject: {headers['subject']}
received: {received_date.isoformat()}
priority: {priority}
status: pending
filter_reason: {filter_reason}
is_reply: {str(is_reply).lower()}
gmail_message_id: {gmail_msgid_hex}
gmail_link: {gmail_link}

# AI Processing Status
ai_status: pending  # pending, in_progress, completed, pending_approval, needs_revision
ai_processed_at: [PENDING]
ai_decision: [PENDING]
ai_category: [PENDING]
ai_summary: [PENDING]
---

# Email: {headers['subject']}

## Quick Actions

📧 **[Open in Gmail]({gmail_link})**
📋 **Task ID:** `{task_id}`
🧵 **Thread:** {"Yes (reply)" if is_reply else "No (original)"}
📊 **AI Status:** `pending`

---

## Email Information

| Property | Value |
|----------|-------|
| From | `{headers['from']}` |
| To | `{headers['to']}` |
| Received | {received_date.strftime('%Y-%m-%d %H:%M:%S')} |
| Priority | {priority.title()} |
| Filter Reason | {filter_reason} |{thread_info}

---

## Email Content

{truncated_body}

---

## Instructions for AI

1. **Identify the email type** (request, invoice, informational, reply, etc.)
2. **Check if this is part of a thread** (see "Thread" info above)
3. **Classify urgency and category** based on content
4. **Apply business rules** from Business_Goals.md and Company_Handbook.md
5. **Return JSON decision** as defined in CLAUDE.md

### Thread Handling:
- If this is a **reply**, review the quoted conversation below
- Consider the full conversation context in your response
- If action items span multiple emails, consolidate them

---

*Generated by AI Employee Gmail Watcher (IMAP)*
*Task ID: `{task_id}`*
*Message ID: `{message['id']}`*
*Thread: {"Yes (reply)" if is_reply else "No (original)"}*
"""
    
    # Write task file (atomic write)
    filepath = self.needs_action / f"{task_id}.md"
    temp_path = filepath.with_suffix('.tmp')
    temp_path.write_text(task_content, encoding='utf-8')
    temp_path.rename(filepath)
    
    # Mark as processed
    self.processed_ids[message['id']] = datetime.now()
    self._save_processed_ids()
    
    # Mark email as READ
    self.mail.uid('STORE', message['id'], '+FLAGS', '\\Seen')
    
    # Track processed email details for logging
    self.processed_email_details.append({
        'task_id': task_id,
        'message_id': message['id'],
        'from': headers['from'],
        'subject': headers['subject'],
        'received': received_date.isoformat(),
        'priority': priority,
        'filter_reason': filter_reason,
        'is_reply': is_reply,
        'gmail_link': gmail_link,
        'task_file': filepath.name,
        'processed_at': datetime.now().isoformat(),
    })
    
    logger.write_to_timeline(
        f"Created task file: {filepath.name} | From: {headers['from'][:50]} | "
        f"Reason: {filter_reason}",
        actor="gmail_watcher_imap",
        message_level="INFO",
    )
    
    return filepath
```

### 5. **Add Logging Methods** ⭐ PRIORITY

**Location:** Add to `GmailWatcherIMAP` class

#### 5.1 Skipped Emails Report
```python
def _generate_skipped_report(self):
    """Append skipped emails to master skipped file (no overwrite)."""
    LOGS_PATH = self.vault_path / "Logs"
    LOGS_PATH.mkdir(parents=True, exist_ok=True)
    
    skipped_path = LOGS_PATH / "gmail_skipped.md"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Create file with header if it doesn't exist
    if not skipped_path.exists():
        skipped_path.write_text("""# Gmail Skipped Emails

**Auto-generated by Gmail Watcher IMAP**

This file contains a complete log of all skipped emails.
Entries are appended, never overwritten.

---

""", encoding='utf-8')
    
    # Append new skipped emails
    new_entries = f"""## {timestamp} - Run Summary
- **Total Skipped:** {len(self.skipped_emails)}

| # | From | Subject | Reason | Gmail Link |
|---|------|---------|--------|------------|
"""
    
    for i, email in enumerate(self.skipped_emails, 1):
        subject = email['subject'][:50].replace('|', '-')
        from_addr = email['from'][:50].replace('|', '-')
        new_entries += f"| {i} | {from_addr} | {subject} | {email['reason']} | [Open]({email['gmail_link']}) |\n"
    
    new_entries += "\n---\n\n"
    
    # Append to file
    with open(skipped_path, 'a', encoding='utf-8') as f:
        f.write(new_entries)
    
    logger.write_to_timeline(
        f"Skipped report updated: {len(self.skipped_emails)} emails logged",
        actor="gmail_watcher_imap",
        message_level="INFO",
    )
```

#### 5.2 Processed Emails Index
```python
def _generate_processing_index(self):
    """Append processed emails to master processed file (no overwrite)."""
    LOGS_PATH = self.vault_path / "Logs"
    LOGS_PATH.mkdir(parents=True, exist_ok=True)
    
    processed_path = LOGS_PATH / "gmail_processed.md"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Create file with header if it doesn't exist
    if not processed_path.exists():
        processed_path.write_text("""# Gmail Processed Emails

**Auto-generated by Gmail Watcher IMAP**

This file contains a complete log of all processed emails.
Entries are appended, never overwritten.

---

""", encoding='utf-8')
    
    # Append new processed emails
    new_entries = f"""## {timestamp} - Run Summary
- **Total Processed:** {len(self.processed_email_details)}

| # | Task ID | From | Subject | Priority | Status | Gmail Link |
|---|---------|------|---------|----------|--------|------------|
"""
    
    for i, email in enumerate(self.processed_email_details, 1):
        time_str = email['processed_at'].split('T')[1].split('.')[0][:5]  # HH:MM
        task_id_short = email['task_id'][:30]
        subject_short = email['subject'][:40].replace('|', '-')
        from_short = email['from'].split('<')[-1].strip('>').split('@')[0][:20]
        new_entries += f"| {time_str} | {task_id_short} | {from_short} | {subject_short} | {email['priority'].title()} | ⏳ Pending | [Open]({email['gmail_link']}) |\n"
    
    new_entries += "\n---\n\n"
    
    # Append to file
    with open(processed_path, 'a', encoding='utf-8') as f:
        f.write(new_entries)
    
    logger.write_to_timeline(
        f"Processing index updated: {len(self.processed_email_details)} emails logged",
        actor="gmail_watcher_imap",
        message_level="INFO",
    )
```

#### 5.3 Status Dashboard
```python
def _generate_status_dashboard(self):
    """Generate status dashboard showing all emails by status."""
    LOGS_PATH = self.vault_path / "Logs"
    LOGS_PATH.mkdir(parents=True, exist_ok=True)
    
    dashboard_path = LOGS_PATH / "gmail_status_dashboard.md"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Count by status (from processed emails)
    status_counts = {
        'pending': len(self.processed_email_details),
        'in_progress': 0,
        'completed': 0,
        'pending_approval': 0,
        'needs_revision': 0,
    }
    
    total = sum(status_counts.values())
    
    def pct(count):
        return round((count / total) * 100) if total > 0 else 0
    
    dashboard = f"""# Gmail Processing Status Dashboard

**Generated:** {timestamp}

## Summary

| Status | Count | Percentage |
|--------|-------|------------|
| ✅ Completed | {status_counts['completed']} | {pct(status_counts['completed'])}% |
| 🔄 In Progress | {status_counts['in_progress']} | {pct(status_counts['in_progress'])}% |
| ⏸️ Pending Approval | {status_counts['pending_approval']} | {pct(status_counts['pending_approval'])}% |
| ⏳ Pending | {status_counts['pending']} | {pct(status_counts['pending'])}% |
| ❌ Needs Revision | {status_counts['needs_revision']} | {pct(status_counts['needs_revision'])}% |
| **Total** | **{total}** | **100%** |

## Processing Statistics

| Metric | Value |
|--------|-------|
| Total Processed This Run | {len(self.processed_email_details)} |
| Total Skipped This Run | {len(self.skipped_emails)} |
| Pending AI Processing | {status_counts['pending']} |
| Ready for Review | {status_counts['pending_approval']} |

## Recent Processed Emails

| Task ID | From | Subject | Priority | Status |
|---------|------|---------|----------|--------|
"""
    
    for email in self.processed_email_details[-10:]:  # Show last 10
        task_id_short = email['task_id'][:30]
        subject_short = email['subject'][:40].replace('|', '-')
        from_short = email['from'].split('<')[-1].strip('>').split('@')[0][:20]
        dashboard += f"| {task_id_short} | {from_short} | {subject_short} | {email['priority'].title()} | ⏳ Pending |\n"
    
    dashboard += """
---

## How to Update Status

1. **AI processes email** → Updates `ai_status` field in task file
2. **Status changes:**
   - `pending` → Email arrived, awaiting AI processing
   - `in_progress` → AI is currently processing
   - `completed` → AI finished, task done
   - `pending_approval` → Needs human approval
   - `needs_revision` → AI needs clarification

3. **Manual override:** Edit task file's YAML frontmatter

---

*Auto-generated by Gmail Watcher IMAP*
*Dashboard updates after each processing cycle*
"""
    
    # Write dashboard
    dashboard_path.write_text(dashboard, encoding='utf-8')
    
    logger.write_to_timeline(
        f"Status dashboard updated: {dashboard_path}",
        actor="gmail_watcher_imap",
        message_level="INFO",
    )
```

### 6. **Update `__init__()` Method**

**Add tracking lists:**
```python
def __init__(self, ...):
    # ... existing initialization ...
    
    # Track processed and skipped emails for logging
    self.processed_email_details: List[Dict] = []
    self.skipped_emails: List[Dict] = []
    
    # ... rest of initialization ...
```

### 7. **Update `run()` Method** ⭐ PRIORITY

**Add periodic logging generation:**
```python
def run(self):
    """
    Main loop - runs continuously checking for new messages.
    """
    logger.write_to_timeline(
        f"Starting Gmail Watcher IMAP | Check interval: {self.check_interval}s | "
        f"Smart filtering: ENABLED",
        actor="gmail_watcher_imap",
        message_level="INFO",
    )
    
    if self.mail is None:
        logger.write_to_timeline(
            "Gmail Watcher IMAP cannot start - connection failed",
            actor="gmail_watcher_imap",
            message_level="WARNING",
        )
        return
    
    # Counter for periodic logging
    run_counter = 0
    
    try:
        while True:
            run_counter += 1
            items = self.check_for_updates()
            
            if items:
                logger.write_to_timeline(
                    f"Processing {len(items)} new message(s)",
                    actor="gmail_watcher_imap",
                    message_level="INFO",
                )
                
                for item in items:
                    self.create_action_file(item)
                
                # Generate logs after processing
                if self.processed_email_details:
                    self._generate_processing_index()
                if self.skipped_emails:
                    self._generate_skipped_report()
                # Update dashboard every time
                self._generate_status_dashboard()
            else:
                logger.write_to_timeline(
                    "No new messages to process",
                    actor="gmail_watcher_imap",
                    message_level="DEBUG",
                )
                
                # Update dashboard even when no new messages
                if run_counter % 10 == 0:  # Every 10 cycles
                    self._generate_status_dashboard()
            
            # Wait for next check
            import time
            time.sleep(self.check_interval)
            
    except KeyboardInterrupt:
        logger.write_to_timeline(
            "Gmail Watcher IMAP stopped by user",
            actor="gmail_watcher_imap",
            message_level="INFO",
        )
    finally:
        # Generate final reports
        if self.processed_email_details or self.skipped_emails:
            self._generate_status_dashboard()
        
        # Close IMAP connection
        if self.mail:
            try:
                self.mail.close()
                self.mail.logout()
            except Exception:
                pass
```

### 8. **Update Body Decoding** (Optional Enhancement)

**Replace `_decode_message_body()` with enhanced version:**

```python
def _decode_body(self, msg: email.message.Message) -> str:
    """Decode email body (plain text or HTML) - Enhanced version."""
    body = ""
    
    if msg.is_multipart():
        # Prefer plain text
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                try:
                    charset = part.get_content_charset() or 'utf-8'
                    payload = part.get_payload(decode=True)
                    if payload:
                        body = payload.decode(charset, errors='replace')
                        break
                except:
                    pass
        
        # Fallback to HTML
        if not body:
            for part in msg.walk():
                if part.get_content_type() == "text/html":
                    try:
                        charset = part.get_content_charset() or 'utf-8'
                        payload = part.get_payload(decode=True)
                        if payload:
                            body = payload.decode(charset, errors='replace')
                            # Simple HTML to text conversion
                            body = body.replace('<br>', '\n').replace('<p>', '\n')
                            body = ''.join(c for c in body if ord(c) < 128 or c.isprintable())
                    except:
                        pass
    else:
        try:
            charset = msg.get_content_charset() or 'utf-8'
            payload = msg.get_payload(decode=True)
            if payload:
                body = payload.decode(charset, errors='replace')
        except:
            body = msg.get_payload() or "[Could not decode]"
    
    return body if body else "[No content available]"
```

---

## Files to Modify

### Primary File
- `watchers/gmail_watcher_imap.py` - Main update target

### No Changes Needed
- `gmail_filter_processor.py` - Keep as reference/standalone tool
- `core/config/settings.py` - Existing config sufficient
- `utils/logging_manager.py` - Existing logging sufficient
- `utils/task_template.py` - Existing template sufficient

---

## Implementation Order

### Phase 1: Core Filtering (Priority: HIGH)
1. ✅ Add `FILTER_CONFIG` constant
2. ✅ Add `should_process_email()` method
3. ✅ Update `check_for_updates()` to use filtering
4. ✅ Update tracking lists in `__init__()`

### Phase 2: Enhanced Task Files (Priority: HIGH)
5. ✅ Update `create_action_file()` with comprehensive format
6. ✅ Add thread detection
7. ✅ Add filter reason tracking

### Phase 3: Logging & Reporting (Priority: MEDIUM)
8. ✅ Add `_generate_skipped_report()` method
9. ✅ Add `_generate_processing_index()` method
10. ✅ Add `_generate_status_dashboard()` method
11. ✅ Update `run()` to call logging methods

### Phase 4: Polish & Testing (Priority: LOW)
12. ✅ Update body decoding (optional)
13. ✅ Test with various email types
14. ✅ Verify logging output
15. ✅ Test continuous watching with filtering

---

## Testing Checklist

### Filtering Tests
- [ ] Promotions category emails are skipped
- [ ] Social category emails are skipped
- [ ] Personal emails (gmail.com) are processed
- [ ] Business emails (amazon.com, google.com) are processed
- [ ] Emails with "urgent" in subject are processed
- [ ] Newsletters are skipped
- [ ] LinkedIn/GitHub notifications are skipped

### Logging Tests
- [ ] Skipped emails logged to `vault/Logs/gmail_skipped.md`
- [ ] Processed emails logged to `vault/Logs/gmail_processed.md`
- [ ] Dashboard updated at `vault/Logs/gmail_status_dashboard.md`
- [ ] Timeline logging shows filter decisions
- [ ] Logs append (not overwrite)

### Task File Tests
- [ ] Task files created in `vault/Needs_Action/`
- [ ] YAML frontmatter includes filter_reason
- [ ] YAML frontmatter includes is_reply
- [ ] Gmail links are correct (hex format)
- [ ] Thread detection works (In-Reply-To headers)
- [ ] Priority detection works (urgent, invoice, meeting)

### Continuous Watching Tests
- [ ] Loop runs every 120 seconds
- [ ] Already processed emails not processed again
- [ ] Reconnect works if connection lost
- [ ] Graceful shutdown on Ctrl+C
- [ ] Processed IDs persisted across restarts

---

## Key Differences Summary

| Feature | gmail_watcher_imap.py (Current) | gmail_filter_processor.py (Reference) | gmail_watcher_imap.py (Updated) |
|---------|--------------------------------|--------------------------------------|--------------------------------|
| **Execution** | Continuous loop | Run once & exit | Continuous loop ✅ |
| **Filtering** | Basic (UNREAD IMPORTANT) | Advanced (categories, domains, keywords) | Advanced ✅ |
| **Logging** | Timeline only | Timeline + Files (skipped/processed/dashboard) | Timeline + Files ✅ |
| **Task Format** | Simple (via task_template) | Comprehensive (YAML + metadata) | Comprehensive ✅ |
| **Thread Detection** | No | Yes | Yes ✅ |
| **Filter Reason** | No | Yes | Yes ✅ |
| **Skip Reports** | No | Yes | Yes ✅ |
| **LoggingManager** | Yes | No (print statements) | Yes ✅ |

---

## Migration Notes

### Important Considerations

1. **Processed IDs Format:** 
   - Current: Dict with timestamps (`{msg_id: datetime}`)
   - Filter processor: Dict with reasons (`{msg_id: "reason"}`)
   - **Solution:** Keep timestamp format for cleanup, add separate tracking lists for details

2. **Logging Approach:**
   - Current: `LoggingManager` timeline
   - Filter processor: `print()` statements
   - **Solution:** Use `LoggingManager` for timeline + file logging for reports

3. **Task File Creation:**
   - Current: Uses `create_email_task()` from task_template
   - Filter processor: Custom template
   - **Solution:** Use custom template (from filter_processor) for richer metadata

4. **Connection Mode:**
   - Current: `readonly=True` (safe)
   - Filter processor: `readonly=False` (needed for marking as read)
   - **Solution:** Change to `readonly=False` in `_connect()` method

5. **Search Query:**
   - Current: Configurable (`gmail_watcher_query` setting)
   - Filter processor: Hardcoded `UNSEEN`
   - **Solution:** Use `UNSEEN` for fetching all unread, then apply smart filtering

---

## Expected Outcomes

After this update:

1. ✅ **Smart Filtering:** Only important emails create task files
2. ✅ **Comprehensive Logging:** Skipped and processed emails tracked in files
3. ✅ **Status Dashboard:** Real-time view of email processing status
4. ✅ **Thread Awareness:** Reply detection for better context
5. ✅ **Filter Transparency:** Clear reasons why emails were processed/skipped
6. ✅ **Continuous Watching:** Maintains existing loop architecture
7. ✅ **Logging Integration:** Preserves LoggingManager timeline integration

---

## Standalone vs Integrated

### `gmail_filter_processor.py` (Standalone)
- Use for: One-time bulk processing, testing, manual runs
- Pros: Simple, immediate results, detailed console output
- Keep as: Separate utility script

### `gmail_watcher_imap.py` (Integrated)
- Use for: Continuous background monitoring
- Pros: Always-on, integrated with logging system, periodic reports
- Update to: Include smart filtering from filter_processor

Both tools serve different purposes - keep both, with feature parity on filtering.
