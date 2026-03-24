#!/usr/bin/env python3
"""
gmail_filter_processor.py - Standalone Gmail Email Filter & Processor

This script:
1. Connects to Gmail via IMAP
2. Fetches ONLY truly important unread emails (filters out promotions, social, updates)
3. Creates task files for important emails only
4. Marks processed emails as read
5. Runs once and exits (no continuous watching)

Usage:
    python gmail_filter_processor.py

Features:
- Smart filtering using Gmail categories
- Filters out: Promotions, Social, Updates, Newsletters
- Processes only: Important, Personal, Work-related emails
- Marks emails as read after processing
- Detailed logging of what was processed and why
"""

import imaplib
import email
import base64
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import email.message

# Add project root to path
import sys
project_root = Path(__file__).parent.resolve()
sys.path.insert(0, str(project_root))

from core.config import settings

# ============================================================================
# CONFIGURATION (from core.config.settings)
# ============================================================================

# Gmail Account Settings (from .env via settings)
GMAIL_ADDRESS = settings.gmail_imap_address
GMAIL_APP_PASSWORD = settings.gmail_imap_app_password

# Validate credentials
if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
    print("❌ Error: Gmail credentials not configured in .env file")
    print("   Set GMAIL_IMAP_ADDRESS and GMAIL_IMAP_APP_PASSWORD in .env")
    sys.exit(1)

# IMAP Settings
IMAP_SERVER = "imap.gmail.com"
IMAP_PORT = 993

# Vault Settings
VAULT_PATH = Path("./vault")
NEEDS_ACTION_PATH = VAULT_PATH / "Needs_Action"

# Filtering Rules
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


# ============================================================================
# GMAIL FILTER PROCESSOR
# ============================================================================

class GmailFilterProcessor:
    """
    Standalone Gmail filter and processor.
    
    Fetches unread emails, applies smart filtering, creates task files,
    and marks emails as read.
    """
    
    def __init__(self):
        """Initialize the processor."""
        self.mail: Optional[imaplib.IMAP4_SSL] = None
        self.processed_count = 0
        self.skipped_count = 0
        self.error_count = 0
        
        # Track skipped emails for reporting
        self.skipped_emails: List[Dict] = []
        
        # Track processed emails for index
        self.processed_email_details: List[Dict] = []
        
        # Ensure Needs_Action directory exists
        NEEDS_ACTION_PATH.mkdir(parents=True, exist_ok=True)
        
        # Logs directory for reports
        LOGS_PATH = VAULT_PATH / "Logs"
        LOGS_PATH.mkdir(parents=True, exist_ok=True)
        
        # Processed IDs file
        self.processed_file = VAULT_PATH / '.gmail_filter_processed.json'
        self.processed_ids = self._load_processed_ids()
    
    def _load_processed_ids(self) -> Dict[str, str]:
        """Load previously processed message IDs."""
        if self.processed_file.exists():
            try:
                data = json.loads(self.processed_file.read_text(encoding='utf-8'))
                print(f"ℹ️ Loaded {len(data)} previously processed message IDs")
                return data
            except Exception as e:
                print(f"⚠️ Could not load processed IDs: {e}")
                return {}
        return {}
    
    def _save_processed_ids(self):
        """Save processed message IDs to file."""
        try:
            self.processed_file.write_text(
                json.dumps(self.processed_ids, indent=2),
                encoding='utf-8'
            )
        except Exception as e:
            print(f"❌ Could not save processed IDs: {e}")
    
    def connect(self):
        """Connect to Gmail IMAP server."""
        print("\n🔌 Connecting to Gmail IMAP...")
        try:
            self.mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
            clean_password = GMAIL_APP_PASSWORD.replace(' ', '')
            self.mail.login(GMAIL_ADDRESS, clean_password)
            self.mail.select('INBOX', readonly=False)  # Read-write mode so we can mark as read
            print("✅ Connected to Gmail successfully")
            
            # Show capabilities
            caps = self.mail.capabilities
            if b'X-GM-EXT-1' in caps:
                print("   Gmail extensions: Available ✓")
            
            return True
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False
    
    def fetch_unread_emails(self) -> List[str]:
        """
        Fetch list of unread email message IDs.
        
        Returns:
            List of message IDs
        """
        print("\n📬 Fetching unread emails...")
        try:
            # Use UID SEARCH for UNSEEN (unread)
            status, messages = self.mail.uid('SEARCH', None, 'UNSEEN')
            
            if status != 'OK':
                print(f"❌ Search failed: {status}")
                return []
            
            message_ids = messages[0].split()
            print(f"   Found {len(message_ids)} unread emails")
            
            return [msg_id.decode('utf-8') for msg_id in message_ids]
            
        except Exception as e:
            print(f"❌ Error fetching emails: {e}")
            return []
    
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
        from_addr_lower = from_addr.lower()
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
    
    def fetch_email_content(self, msg_id: str) -> Optional[Dict]:
        """
        Fetch full email content by message ID.
        
        Args:
            msg_id: Message ID
            
        Returns:
            Dict with headers and body, or None on error
        """
        try:
            status, msg_data = self.mail.uid('FETCH', msg_id, '(RFC822)')
            
            if status != 'OK':
                return None
            
            # Parse email
            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)
            
            # Extract headers
            headers = {
                'from': msg.get('From', 'Unknown'),
                'to': msg.get('To', 'Unknown'),
                'subject': msg.get('Subject', 'No Subject'),
                'date': msg.get('Date', ''),
                'message_id': msg.get('Message-ID', ''),
                'in_reply_to': msg.get('In-Reply-To', ''),  # Thread tracking
                'references': msg.get('References', ''),     # Thread tracking
            }
            
            # Decode body
            body = self._decode_body(msg)
            
            # Parse date
            try:
                from email.utils import parsedate_to_datetime
                received_date = parsedate_to_datetime(headers['date'])
            except:
                received_date = datetime.now()
            
            return {
                'headers': headers,
                'body': body,
                'received_date': received_date,
                'raw_msg': msg,
            }
            
        except Exception as e:
            print(f"   ⚠️ Error fetching message {msg_id}: {e}")
            return None
    
    def _decode_body(self, msg: email.message.Message) -> str:
        """Decode email body (plain text or HTML)."""
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
    
    def create_task_file(self, email_data: Dict, msg_id: str, reason: str) -> Optional[Path]:
        """
        Create task file for an email.
        
        Args:
            email_data: Email data dict
            msg_id: Message ID
            reason: Why this email was selected
            
        Returns:
            Path to created file, or None on error
        """
        try:
            headers = email_data['headers']
            body = email_data['body']
            received_date = email_data['received_date']
            
            # Determine priority
            priority = "normal"
            subject_lower = headers['subject'].lower()
            
            if any(word in subject_lower for word in ['urgent', 'asap', 'emergency']):
                priority = "urgent"
            elif any(word in subject_lower for word in ['invoice', 'payment', 'billing']):
                priority = "high"
            elif 'interview' in subject_lower or 'meeting' in subject_lower:
                priority = "high"
            
            # Generate task ID (truncate subject to avoid Windows path length issues)
            timestamp = received_date.strftime('%Y%m%d_%H%M%S')
            # Clean subject for filename (remove Re:, Fwd:, etc.)
            clean_subject = headers['subject'].replace('Re:', '').replace('Fwd:', '').strip()
            safe_subject = clean_subject[:30].replace(' ', '_').replace('/', '_').replace('\\', '_')
            # Remove special characters that cause Windows issues
            safe_subject = ''.join(c for c in safe_subject if c.isalnum() or c in ['_', '-'])
            task_id = f"email_{timestamp}_{safe_subject}"
            
            # Detect if this is part of a thread
            is_reply = bool(headers['in_reply_to'] or headers['references'])
            thread_info = ""
            if is_reply:
                thread_info = f"\n**Thread:** This is a reply (In-Reply-To: {headers['in_reply_to'][:50] if headers['in_reply_to'] else 'N/A'})"
            
            # Truncate body for task file (max 3000 chars)
            truncated_body = body[:3000] + "\n\n[Content truncated...]" if len(body) > 3000 else body
            
            # Build task file content
            gmail_link = f"https://mail.google.com/mail/u/0/#inbox/{msg_id}"
            
            task_content = f"""---
type: email
task_id: {task_id}
from: {headers['from']}
to: {headers['to']}
subject: {headers['subject']}
received: {received_date.isoformat()}
priority: {priority}
status: pending
filter_reason: {reason}
is_reply: {str(is_reply).lower()}
gmail_message_id: {msg_id}
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
| Filter Reason | {reason} |{thread_info}

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

*Generated by AI Employee Gmail Filter Processor*
*Task ID: `{task_id}`*
*Message ID: `{msg_id}`*
*Thread: {"Yes (reply)" if is_reply else "No (original)"}*
"""
            
            # Write task file
            filepath = NEEDS_ACTION_PATH / f"{task_id}.md"
            temp_path = filepath.with_suffix('.tmp')
            
            # Atomic write
            temp_path.write_text(task_content, encoding='utf-8')
            temp_path.rename(filepath)
            
            return filepath
            
        except Exception as e:
            print(f"   ❌ Error creating task file: {e}")
            return None
    
    def mark_as_read(self, msg_id: str):
        """Mark email as read (\\Seen flag)."""
        try:
            self.mail.uid('STORE', msg_id, '+FLAGS', '\\Seen')
            return True
        except Exception as e:
            print(f"   ⚠️ Could not mark as read: {e}")
            return False
    
    def process_emails(self, message_ids: List[str]):
        """
        Process list of message IDs.
        
        Args:
            message_ids: List of message IDs to process
        """
        print(f"\n🔄 Processing {len(message_ids)} unread emails...\n")
        
        for i, msg_id in enumerate(message_ids, 1):
            print(f"[{i}/{len(message_ids)}] Processing message {msg_id}...", end=" ")
            
            # Fetch email content
            email_data = self.fetch_email_content(msg_id)
            if not email_data:
                print("⚠️ Failed to fetch")
                self.error_count += 1
                continue
            
            # Apply filtering
            msg = email_data['raw_msg']
            should_process, reason = self.should_process_email(msg, msg_id)
            
            if not should_process:
                print(f"⊘ {reason}")
                self.skipped_count += 1
                
                # Track skipped email for report
                self.skipped_emails.append({
                    'message_id': msg_id,
                    'from': msg.get('From', 'Unknown'),
                    'subject': msg.get('Subject', 'No Subject'),
                    'reason': reason,
                    'gmail_link': f"https://mail.google.com/mail/u/0/#inbox/{msg_id}",
                    'processed_at': datetime.now().isoformat(),
                })
                
                # Still mark as read so we don't keep seeing it
                self.mark_as_read(msg_id)
                self.processed_ids[msg_id] = f"skipped: {reason}"
                continue
            
            # Create task file
            filepath = self.create_task_file(email_data, msg_id, reason)
            
            if filepath:
                # Mark as read
                self.mark_as_read(msg_id)
                self.processed_ids[msg_id] = f"processed: {filepath.name}"
                self.processed_count += 1
                
                # Track processed email details for index
                self.processed_email_details.append({
                    'task_id': task_id,
                    'message_id': msg_id,
                    'from': headers['from'],
                    'subject': headers['subject'],
                    'received': received_date.isoformat(),
                    'priority': priority,
                    'filter_reason': reason,
                    'is_reply': is_reply,
                    'gmail_link': f"https://mail.google.com/mail/u/0/#inbox/{msg_id}",
                    'task_file': filepath.name,
                    'processed_at': datetime.now().isoformat(),
                })
                
                print(f"✅ Created: {filepath.name}")
            else:
                print("❌ Failed to create task file")
                self.error_count += 1
        
        # Save processed IDs
        self._save_processed_ids()
    
    def _generate_skipped_report(self):
        """Generate markdown report of skipped emails."""
        LOGS_PATH = VAULT_PATH / "Logs"
        LOGS_PATH.mkdir(parents=True, exist_ok=True)
        
        report_path = LOGS_PATH / "gmail_skipped_report.md"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        report = f"""# Gmail Skipped Emails Report

**Generated:** {timestamp}

## Summary
- **Total unread emails:** {self.processed_count + self.skipped_count + self.error_count}
- **Processed:** {self.processed_count}
- **Skipped:** {self.skipped_count}
- **Errors:** {self.error_count}

## Skipped Emails

| # | From | Subject | Reason | Gmail Link |
|---|------|---------|--------|------------|
"""
        
        for i, email in enumerate(self.skipped_emails, 1):
            subject = email['subject'][:50].replace('|', '-')  # Escape pipe chars
            from_addr = email['from'][:50].replace('|', '-')
            report += f"| {i} | {from_addr} | {subject} | {email['reason']} | [Open]({email['gmail_link']}) |\n"
        
        report += f"""
---

*Report generated by Gmail Filter Processor*
*Next run will fetch new unread emails only*
"""
        
        # Write report
        report_path.write_text(report, encoding='utf-8')
        print(f"\n📄 Skipped emails report saved to: {report_path}")
        print(f"   Total skipped emails logged: {len(self.skipped_emails)}")
    
    def _generate_processing_index(self):
        """Generate daily master processing index."""
        LOGS_PATH = VAULT_PATH / "Logs"
        LOGS_PATH.mkdir(parents=True, exist_ok=True)
        
        today = datetime.now().strftime("%Y-%m-%d")
        index_path = LOGS_PATH / f"gmail_processing_index_{today}.md"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Build processed emails table
        processed_rows = ""
        for email in self.processed_email_details:
            time_str = email['processed_at'].split('T')[1].split('.')[0][:5]  # HH:MM
            subject = email['subject'][:40].replace('|', '-')
            from_short = email['from'].split('<')[-1].strip('>').split('@')[0][:20]
            processed_rows += f"| {time_str} | {email['task_id'][:30]} | {from_short} | {subject} | ✅ Created | [Open]({email['gmail_link']}) |\n"
        
        # Build skipped emails table
        skipped_rows = ""
        for email in self.skipped_emails:
            time_str = email['processed_at'].split('T')[1].split('.')[0][:5]  # HH:MM
            subject = email['subject'][:40].replace('|', '-')
            from_short = email['from'].split('<')[-1].strip('>').split('@')[0][:20]
            skipped_rows += f"| {time_str} | {email['message_id']} | {from_short} | {subject} | {email['reason']} | [Open]({email['gmail_link']}) |\n"
        
        index = f"""# Gmail Processing Index - {today}

**Generated:** {timestamp}

## Summary
| Metric | Count |
|--------|-------|
| Total Unread | {len(self.processed_email_details) + len(self.skipped_emails) + self.error_count} |
| ✅ Processed | {self.processed_count} |
| ⊘ Skipped | {self.skipped_count} |
| ❌ Errors | {self.error_count} |

## Processed Emails

| Time | Task ID | From | Subject | Status | Gmail Link |
|------|---------|------|---------|--------|------------|
{processed_rows if processed_rows else "| - | - | - | No emails processed | - | - |\n"}

## Skipped Emails

| Time | Message ID | From | Subject | Reason | Gmail Link |
|------|------------|------|---------|--------|------------|
{skipped_rows if skipped_rows else "| - | - | - | No emails skipped | - | - |\n"}

---

*Auto-generated by Gmail Filter Processor*
*File: {index_path.name}*
"""
        
        # Write index
        index_path.write_text(index, encoding='utf-8')
        print(f"📊 Processing index saved to: {index_path}")
    
    def _generate_status_dashboard(self):
        """Generate status dashboard showing all emails by status."""
        LOGS_PATH = VAULT_PATH / "Logs"
        LOGS_PATH.mkdir(parents=True, exist_ok=True)
        
        dashboard_path = LOGS_PATH / "gmail_status_dashboard.md"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Count by status (from processed emails)
        status_counts = {
            'pending': 0,
            'in_progress': 0,
            'completed': 0,
            'pending_approval': 0,
            'needs_revision': 0,
        }
        
        # Note: Real status tracking requires AI processing integration
        # For now, all are 'pending' since they just arrived
        status_counts['pending'] = len(self.processed_email_details)
        
        total = sum(status_counts.values())
        
        # Calculate percentages
        def pct(count):
            if total == 0:
                return 0
            return round((count / total) * 100)
        
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
| Total Processed Today | {len(self.processed_email_details)} |
| Total Skipped Today | {len(self.skipped_emails)} |
| Pending AI Processing | {status_counts['pending']} |
| Ready for Review | {status_counts['pending_approval']} |

## Recent Processed Emails

| Task ID | From | Subject | Priority | Status |
|---------|------|---------|----------|--------|
"""
        
        for email in self.processed_email_details[:10]:  # Show last 10
            task_id_short = email['task_id'][:30]
            subject_short = email['subject'][:40].replace('|', '-')
            from_short = email['from'].split('<')[-1].strip('>').split('@')[0][:20]
            dashboard += f"| {task_id_short} | {from_short} | {subject_short} | {email['priority'].title()} | ⏳ Pending |\n"
        
        dashboard += f"""
---

## How to Update Status

1. **AI processes email** → Claude Runner updates `ai_status` field
2. **Status changes:**
   - `pending` → Email arrived, awaiting AI processing
   - `in_progress` → AI is currently processing
   - `completed` → AI finished, task done
   - `pending_approval` → Needs human approval
   - `needs_revision` → AI needs clarification

3. **Manual override:** Edit task file's YAML frontmatter

---

## Quick Links

- 📊 [Processing Index](gmail_processing_index_{datetime.now().strftime('%Y-%m-%d')}.md)
- 📄 [Skipped Report](gmail_skipped_report.md)
- 📁 [Needs_Action Folder](../Needs_Action/)

---

*Auto-generated by Gmail Filter Processor*
*Dashboard updates after each run*
"""
        
        # Write dashboard
        dashboard_path.write_text(dashboard, encoding='utf-8')
        print(f"📈 Status dashboard saved to: {dashboard_path}")
    
    def run(self):
        """Main processing run."""
        print("=" * 70)
        print("  Gmail Filter Processor - Standalone Email Filter")
        print("=" * 70)
        print(f"\n📧 Account: {GMAIL_ADDRESS}")
        print(f"📁 Output: {NEEDS_ACTION_PATH}")
        print(f"🔍 Filtering {len(FILTER_CONFIG['skip_categories'])} categories")
        print(f"   Skipping: {', '.join(FILTER_CONFIG['skip_categories'])}")
        print(f"   Priority: {', '.join(FILTER_CONFIG['priority_keywords'][:5])}...")
        
        # Connect
        if not self.connect():
            print("\n❌ Failed to connect. Exiting.")
            return
        
        try:
            # Fetch unread emails
            message_ids = self.fetch_unread_emails()
            
            if not message_ids:
                print("\n✅ No unread emails to process!")
                return
            
            # Process emails
            self.process_emails(message_ids)
            
            # Summary
            print("\n" + "=" * 70)
            print("  Processing Summary")
            print("=" * 70)
            print(f"   Total unread emails: {len(message_ids)}")
            print(f"   ✅ Processed: {self.processed_count}")
            print(f"   ⊘ Skipped: {self.skipped_count}")
            print(f"   ❌ Errors: {self.error_count}")
            print("=" * 70)
            
            # Generate skipped emails report
            if self.skipped_emails:
                self._generate_skipped_report()
            
            # Generate master processing index
            self._generate_processing_index()
            
            # Generate status dashboard
            self._generate_status_dashboard()
            
        finally:
            # Disconnect
            if self.mail:
                try:
                    self.mail.close()
                    self.mail.logout()
                    print("\n👋 Disconnected from Gmail")
                except:
                    pass


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Main entry point."""
    processor = GmailFilterProcessor()
    processor.run()


if __name__ == "__main__":
    main()
