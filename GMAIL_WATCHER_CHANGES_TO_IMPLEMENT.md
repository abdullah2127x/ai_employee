# Gmail Watcher IMAP - Implementation Plan

**Date:** 2026-03-25  
**Goal:** Centralize email template while keeping Gmail-specific functionality in watcher  
**Status:** Ready to implement

---

## 📊 Architecture Decision

### What Goes Where

| Component | Location | Reason |
|-----------|----------|--------|
| **Email template format** | `utils/task_template.py` | Central - consistent format |
| **Gmail filtering logic** | `watchers/gmail_watcher_imap.py` | Watcher - Gmail-specific |
| **X-GM-MSGID extraction** | `watchers/gmail_watcher_imap.py` | Watcher - IMAP-specific |
| **Priority detection** | `watchers/gmail_watcher_imap.py` | Watcher - email-specific |
| **Thread detection** | `watchers/gmail_watcher_imap.py` | Watcher - email headers |
| **Task file writing** | `watchers/gmail_watcher_imap.py` | Watcher - file management |
| **Processed tracking** | `watchers/gmail_watcher_imap.py` | Watcher - state management |
| **Logging reports** | `watchers/gmail_watcher_imap.py` | Watcher - Gmail-specific logs |

---

## 🎯 Changes to Make

### Phase 1: Add Enhanced Email Template to `task_template.py`

**File:** `utils/task_template.py`

**Add new function:**
```python
def create_email_task_enhanced(
    from_address: str,
    to_address: str,
    subject: str,
    content: str,
    timestamp: datetime,
    priority: str,
    filter_reason: str = "",
    is_reply: bool = False,
    gmail_message_id: str = "",
    gmail_link: str = "",
) -> Tuple[str, str]:
    """
    Enhanced email task template with Gmail-specific metadata.
    
    Includes:
    - filter_reason: Why this email was selected
    - is_reply: Thread detection
    - gmail_message_id: Permanent Gmail ID
    - gmail_link: Direct link to email (for humans)
    - Quick Actions section (for humans)
    - Email Information table (for humans)
    
    Excludes:
    - AI Processing Status (OUTPUT, not INPUT)
    - Instructions for AI (Claude uses CLAUDE.md)
    - [PENDING] placeholders (file is INPUT-ONLY)
    
    Returns:
        (task_id, markdown_content)
    """
```

**Implementation details:**
- Use existing helpers: `_make_safe_stem()`, `_truncate_content()`
- Generate task_id: `email_{timestamp}_{subject}`
- Include frontmatter with all Gmail-specific fields
- Include Quick Actions section
- Include Email Information table
- Include Body section with truncated content
- Return task_id and complete markdown string

---

### Phase 2: Update `gmail_watcher_imap.py`

**File:** `watchers/gmail_watcher_imap.py`

#### Change 1: Import Central Template

**Add import:**
```python
from utils.task_template import create_email_task_enhanced
```

#### Change 2: Simplify `create_action_file()` Method

**Current:** ~200 lines with full template  
**After:** ~50 lines calling central template

**Remove from `create_action_file()`:**
- ❌ Task ID generation logic (use central function)
- ❌ Template string construction (use central function)
- ❌ Quick Actions section (in central template)
- ❌ Email Information table (in central template)
- ❌ Body truncation logic (central function handles)

**Keep in `create_action_file()`:**
- ✅ Fetch email from IMAP
- ✅ Extract headers (from, to, subject, etc.)
- ✅ Priority detection (urgent/high/normal)
- ✅ Thread detection (In-Reply-To, References)
- ✅ Call `create_email_task_enhanced()` with extracted data
- ✅ Write task file to disk
- ✅ Mark email as read
- ✅ Update processed_ids tracking
- ✅ Log creation

**New structure:**
```python
def create_action_file(self, message: Dict[str, Any]) -> Optional[Path]:
    # 1. Fetch email
    # 2. Extract headers
    # 3. Detect priority
    # 4. Detect thread
    # 5. Call central template
    task_id, task_content = create_email_task_enhanced(
        from_address=headers['from'],
        to_address=headers['to'],
        subject=headers['subject'],
        content=body,
        timestamp=received_date,
        priority=priority,
        filter_reason=filter_reason,
        is_reply=is_reply,
        gmail_message_id=gmail_msgid,
        gmail_link=gmail_link,
    )
    # 6. Write file
    # 7. Mark as read
    # 8. Update tracking
    # 9. Log
```

#### Change 3: Keep Watcher-Specific Logic

**Keep these methods unchanged in watcher:**
- ✅ `check_for_updates()` - Gmail IMAP specific
- ✅ `should_process_email()` - Gmail filtering logic
- ✅ `_decode_body()` - Email decoding
- ✅ `_parse_email_headers()` - Header parsing
- ✅ `_generate_skipped_report()` - Gmail logging
- ✅ `_generate_processing_index()` - Gmail logging
- ✅ `_generate_status_dashboard()` - Gmail logging
- ✅ `_load_processed_ids()` - State management
- ✅ `_save_processed_ids()` - State management
- ✅ `_cleanup_old_processed_ids()` - State management

**These are Gmail-specific and should NOT be centralized.**

---

### Phase 3: Update Imports in `gmail_watcher_imap.py`

**Current imports:**
```python
from utils.logging_manager import LoggingManager
```

**Add:**
```python
from utils.task_template import create_email_task_enhanced
```

---

## 📝 Detailed Code Changes

### File 1: `utils/task_template.py`

**Location:** After `create_email_task()` function (around line 220)

**Add:**
```python
def create_email_task_enhanced(
    from_address: str,
    to_address: str,
    subject: str,
    content: str,
    timestamp: datetime,
    priority: str,
    filter_reason: str = "",
    is_reply: bool = False,
    gmail_message_id: str = "",
    gmail_link: str = "",
) -> Tuple[str, str]:
    """
    Enhanced email task template with Gmail-specific metadata.
    
    Includes:
    - filter_reason: Why this email was selected
    - is_reply: Thread detection
    - gmail_message_id: Permanent Gmail ID
    - gmail_link: Direct link to email (for humans)
    - Quick Actions section (for humans)
    - Email Information table (for humans)
    
    Excludes:
    - AI Processing Status (OUTPUT, not INPUT)
    - Instructions for AI (Claude uses CLAUDE.md)
    - [PENDING] placeholders (file is INPUT-ONLY)
    
    Returns:
        (task_id, markdown_content)
    """
    timestamp_str = timestamp.strftime("%Y%m%d_%H%M%S")
    safe_stem = _make_safe_stem(subject)
    task_id = f"email_{timestamp_str}_{safe_stem}"
    
    # Convert decimal Gmail ID to hex for URL
    gmail_msgid_hex = format(int(gmail_message_id), 'x') if gmail_message_id else ""
    gmail_url = f"https://mail.google.com/mail/u/0/#inbox/{gmail_msgid_hex}" if gmail_msgid_hex else gmail_link
    
    # Thread info
    thread_text = "Yes (reply)" if is_reply else "No (original)"
    
    # Truncate content
    truncated_content = _truncate_content(content)
    
    task_content = f"""---
type: email
task_id: {task_id}
from: "{from_address}"
to: "{to_address}"
subject: "{subject}"
received: {timestamp.isoformat()}
priority: {priority}
status: pending
retry_count: 0
filter_reason: {filter_reason}
is_reply: {str(is_reply).lower()}
gmail_message_id: {gmail_message_id}
---

# Email: {subject}

## Quick Actions

📧 **[Open in Gmail]({gmail_url})**
📋 **Task ID:** `{task_id}`
🧵 **Thread:** {thread_text}

---

## Email Information

| Property | Value |
|----------|-------|
| From | `{from_address}` |
| To | `{to_address}` |
| Received | {timestamp.strftime('%Y-%m-%d %H:%M:%S')} |
| Priority | {priority.title()} |
| Filter Reason | {filter_reason} |

---

## Body

{truncated_content}

---

*Generated by AI Employee Gmail Watcher*
*Task ID: `{task_id}`*
"""
    
    return task_id, task_content
```

---

### File 2: `watchers/gmail_watcher_imap.py`

#### Change 1: Add Import

**Location:** Line ~45 (after other imports)

**Add:**
```python
from utils.task_template import create_email_task_enhanced
```

#### Change 2: Update `create_action_file()` Method

**Location:** Line ~690

**Replace entire method with:**
```python
def create_action_file(self, message: Dict[str, Any]) -> Optional[Path]:
    """
    Create a task file for a Gmail message.
    
    Uses central template (create_email_task_enhanced) for consistent format.
    
    Args:
        message: Message dict with 'id', 'gmail_msgid', 'gmail_msgid_hex', 'reason'
    
    Returns:
        Path to created file, or None on error
    """
    if self.mail is None:
        return None
    
    try:
        # Fetch full message
        status, msg_data = self.mail.uid('FETCH', message['id'], '(RFC822)')
        
        if status != 'OK':
            logger.log_warning(
                f"Could not fetch message {message['id']}",
                actor="gmail_watcher_imap",
            )
            return None
        
        # Get Gmail message IDs from message dict
        gmail_msgid = message.get('gmail_msgid', message['id'])
        gmail_msgid_hex = message.get('gmail_msgid_hex', format(int(gmail_msgid), 'x'))
        
        # Parse email
        email_data = self._parse_email_headers(msg_data[0][1], gmail_msgid_hex)
        headers = email_data['headers']
        body = email_data['body']
        received_date = email_data['received_date']
        
        # Get filter reason
        filter_reason = message.get('reason', 'Unknown')
        
        # Determine priority based on subject/content
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
        
        # Build Gmail link
        gmail_link = f"https://mail.google.com/mail/u/0/#inbox/{gmail_msgid_hex}"
        
        # Create task file using central enhanced template
        task_id, task_content = create_email_task_enhanced(
            from_address=headers['from'],
            to_address=headers['to'],
            subject=headers['subject'],
            content=body,
            timestamp=received_date,
            priority=priority,
            filter_reason=filter_reason,
            is_reply=is_reply,
            gmail_message_id=gmail_msgid,
            gmail_link=gmail_link,
        )
        
        # Write task file
        filepath = self.needs_action / f"{task_id}.md"
        temp_path = filepath.with_suffix('.tmp')
        
        # Atomic write
        temp_path.write_text(task_content, encoding='utf-8')
        temp_path.rename(filepath)
        
        # Mark as processed in Gmail
        try:
            self.mail.uid('STORE', message['id'], '+FLAGS', '\\Seen')
            logger.write_to_timeline(
                f"Marked message {message['id']} as READ",
                actor="gmail_watcher_imap",
                message_level="DEBUG",
            )
        except Exception as e:
            logger.log_warning(
                f"Could not mark message as read: {e}",
                actor="gmail_watcher_imap",
            )
        
        # Save to processed_ids with status
        self.processed_ids[gmail_msgid] = {
            "status": "processed",
            "timestamp": datetime.now().isoformat(),
            "reason": filter_reason,
            "task_file": task_id,
        }
        self._save_processed_ids()
        
        # Track processed email details for logging
        self.processed_email_details.append({
            'task_id': task_id,
            'message_id': message['id'],
            'gmail_msgid': gmail_msgid,
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
        
    except Exception as e:
        logger.log_error(
            f'Error creating action file for message {message["id"]}: {e}',
            actor="gmail_watcher_imap",
        )
        return None
```

**Line reduction:** ~200 lines → ~150 lines (25% reduction)

---

## ✅ What Stays in Watcher (Gmail-Specific)

Keep these methods **unchanged** in `gmail_watcher_imap.py`:

### Core Gmail Logic
- ✅ `check_for_updates()` - IMAP search, X-GM-MSGID extraction, early skip
- ✅ `should_process_email()` - Gmail filtering rules (categories, domains, keywords)
- ✅ `_decode_body()` - Email body decoding (plain text/HTML)
- ✅ `_parse_email_headers()` - Header parsing with X-GM-MSGID

### State Management
- ✅ `_load_processed_ids()` - Load from JSON file
- ✅ `_save_processed_ids()` - Save to JSON file
- ✅ `_cleanup_old_processed_ids()` - Remove old entries
- ✅ `processed_ids` dict - Track processed/skipped emails

### Logging & Reports
- ✅ `_generate_skipped_report()` - Gmail skipped emails log
- ✅ `_generate_processing_index()` - Gmail processed emails log
- ✅ `_generate_status_dashboard()` - Gmail status dashboard

### Connection Management
- ✅ `_connect()` - IMAP connection
- ✅ `_reconnect_if_needed()` - Connection recovery

**These are Gmail-specific and should NOT be centralized.**

---

## ❌ What Moves to Central Template

### From `create_action_file()` in Watcher

**Remove:**
- ❌ Task ID generation (moved to `create_email_task_enhanced()`)
- ❌ Template string construction (moved to `create_email_task_enhanced()`)
- ❌ Quick Actions section (in central template)
- ❌ Email Information table (in central template)
- ❌ Body truncation logic (central function uses `_truncate_content()`)

**Keep:**
- ✅ Email fetching from IMAP
- ✅ Header extraction
- ✅ Priority detection
- ✅ Thread detection
- ✅ File writing
- ✅ Mark as read
- ✅ Tracking updates
- ✅ Logging

---

## 🎯 Benefits of This Approach

### Code Reduction
- **`create_action_file()` method:** 200 lines → 150 lines (25% reduction)
- **Template logic:** Centralized in one place
- **Easier maintenance:** Update template in one place

### Consistency
- ✅ Same format as other watchers (file system, WhatsApp, etc.)
- ✅ Central template for all email tasks
- ✅ Consistent output via `build_output_file()`

### Flexibility
- ✅ Gmail-specific logic stays in watcher
- ✅ Central template for format only
- ✅ Easy to add new watchers

### Clarity
- ✅ Clear separation: format (central) vs. logic (watcher)
- ✅ No duplication of template code
- ✅ Easy to understand what's where

---

## 🧪 Testing Checklist

After implementation:

### Template Test
- [ ] Call `create_email_task_enhanced()` directly
- [ ] Verify output has all Gmail-specific fields
- [ ] Verify Quick Actions section present
- [ ] Verify Email Information table present
- [ ] Verify NO AI Processing Status section
- [ ] Verify NO Instructions for AI section

### Watcher Test
- [ ] Run `gmail_watcher_imap.py`
- [ ] Verify emails are fetched
- [ ] Verify filtering works (skip/promotions/etc.)
- [ ] Verify task files created in `Needs_Action/`
- [ ] Verify task files have correct format
- [ ] Verify Gmail links work
- [ ] Verify thread detection works
- [ ] Verify processed tracking works

### Integration Test
- [ ] Orchestrator moves task to `Processing/`
- [ ] Claude Runner processes task
- [ ] Output file created in `Done/` or `Pending_Approval/`
- [ ] Output file has correct format (via `build_output_file()`)

---

## 📊 Summary

### What to Centralize
- ✅ Email template format → `create_email_task_enhanced()` in `task_template.py`

### What to Keep in Watcher
- ✅ All Gmail filtering logic
- ✅ All IMAP operations
- ✅ All state management
- ✅ All logging/reporting
- ✅ Email fetching and parsing
- ✅ Priority detection
- ✅ Thread detection
- ✅ File writing

### Code Changes
- **File 1:** Add `create_email_task_enhanced()` to `utils/task_template.py`
- **File 2:** Update `create_action_file()` in `watchers/gmail_watcher_imap.py`
- **File 3:** Add import in `watchers/gmail_watcher_imap.py`

### Result
- ✅ Cleaner code (25% reduction in watcher)
- ✅ Central template (consistent format)
- ✅ Gmail logic preserved (all filtering, tracking, logging)
- ✅ Easy to maintain (template in one place)

---

**Ready to implement?** Start with Phase 1 (add template to `task_template.py`), then Phase 2 (update watcher).
