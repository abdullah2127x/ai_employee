#!/usr/bin/env python3
"""
gmail_watcher_imap.py - Gmail Watcher using IMAP (Development)

Simple Gmail watcher using IMAP with app password - no OAuth2 complexity.
Perfect for development and testing.

**Requirements:**
- Gmail account with 2FA enabled
- Gmail App Password (not regular password)

**Get App Password:**
1. Go to: https://myaccount.google.com/security
2. Enable 2-Factor Authentication (if not already)
3. Go to: App passwords
4. Select app: "Mail"
5. Select device: "Other (Custom name)"
6. Enter name: "AI Employee Dev"
7. Click "Generate"
8. Copy the 16-character password (save in .env)

Usage:
    Set in .env:
    GMAIL_WATCHER_MODE=imap  # or 'oauth' for production
    GMAIL_IMAP_ADDRESS=your.email@gmail.com
    GMAIL_IMAP_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx

Features:
- Simple setup (just email + app password)
- No OAuth2 flow
- No credentials.json needed
- No browser authorization
- Works immediately for development
- Smart filtering (promotions, social, updates filtered out)
- Comprehensive logging (skipped/processed emails tracked)
- Status dashboard generation
"""

import email
import email.message
import imaplib
import base64
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import re

from core.config import settings
from utils.logging_manager import LoggingManager
from utils.task_template import create_email_task_enhanced

logger = LoggingManager()

# Logs path for append-only logging
VAULT_PATH = settings.vault_path
LOGS_PATH = VAULT_PATH / "Logs"
NEEDS_ACTION_PATH = settings.needs_action_path
LOGS_PATH.mkdir(parents=True, exist_ok=True)
NEEDS_ACTION_PATH.mkdir(parents=True, exist_ok=True)


# ============================================================================
# SMART FILTER CONFIGURATION
# ============================================================================

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


class GmailWatcherIMAP:
    """
    Gmail Watcher using IMAP protocol with app password.

    Simple, development-friendly alternative to OAuth2-based watcher.
    Features smart filtering to process only important emails.
    """

    def __init__(
        self,
        email_address: str,
        app_password: str,
        check_interval: int = 120,
        gmail_query: str = "UNSEEN",
        imap_server: str = "imap.gmail.com",
        imap_port: int = 993,
    ):
        """
        Initialize IMAP Gmail watcher.

        Args:
            email_address: Gmail address (e.g., your.email@gmail.com)
            app_password: Gmail app password (16 characters, from Google security settings)
            check_interval: Seconds between checks (default: 120)
            gmail_query: IMAP search query (default: UNSEEN)
            imap_server: Gmail IMAP server (default: imap.gmail.com)
            imap_port: IMAP port (default: 993 for SSL)
        """
        self.email_address = email_address
        self.app_password = app_password
        self.check_interval = check_interval
        self.gmail_query = gmail_query
        self.imap_server = imap_server
        self.imap_port = imap_port

        # Use settings for vault path
        self.vault_path = VAULT_PATH
        self.needs_action = NEEDS_ACTION_PATH

        # Track processed message IDs with status (processed/skipped)
        # Format: {gmail_msgid: {"status": "processed|skipped", "timestamp": ISO, "reason": str}}
        self.processed_ids: Dict[str, Dict[str, Any]] = {}
        self.processed_file = self.vault_path / '.gmail_imap_processed_ids.json'

        # Track processed and skipped emails for logging
        self.processed_email_details: List[Dict] = []
        self.skipped_emails: List[Dict] = []

        # IMAP connection
        self.mail: Optional[imaplib.IMAP4_SSL] = None

        # Ensure Needs_Action directory exists
        self.needs_action.mkdir(parents=True, exist_ok=True)

        # Load processed message IDs from file
        self._load_processed_ids()

        # Connect to IMAP
        self._connect()

        logger.write_to_timeline(
            f"GmailWatcherIMAP initialized | Email: {email_address} | "
            f"Query: {gmail_query} | Interval: {check_interval}s | "
            f"Smart Filtering: ENABLED",
            actor="gmail_watcher_imap",
            message_level="INFO",
        )

    def _load_processed_ids(self):
        """Load processed message IDs from JSON file."""
        if self.processed_file.exists():
            try:
                data = json.loads(self.processed_file.read_text(encoding='utf-8'))
                # Convert to dict with status tracking
                # Support both old format (simple timestamp) and new format (dict with status)
                self.processed_ids = {}
                for msg_id, value in data.items():
                    if isinstance(value, dict):
                        # New format: {"status": "processed", "timestamp": "...", "reason": "..."}
                        self.processed_ids[msg_id] = value
                    else:
                        # Old format: just timestamp string
                        self.processed_ids[msg_id] = {
                            "status": "processed",
                            "timestamp": value,
                            "reason": "Previously processed"
                        }
                logger.write_to_timeline(
                    f"Loaded {len(self.processed_ids)} processed message IDs",
                    actor="gmail_watcher_imap",
                    message_level="DEBUG",
                )
            except Exception as e:
                logger.log_warning(
                    f"Could not load processed IDs file: {e}",
                    actor="gmail_watcher_imap",
                )
                self.processed_ids = {}

    def _save_processed_ids(self):
        """Save processed message IDs to JSON file."""
        # Data is already in dict format, save as-is
        try:
            self.processed_file.write_text(json.dumps(self.processed_ids, indent=2), encoding='utf-8')
        except Exception as e:
            logger.log_error(
                f"Could not save processed IDs file: {e}",
                actor="gmail_watcher_imap",
            )

    def _cleanup_old_processed_ids(self, max_age_days: int = 7):
        """Remove processed IDs older than max_age_days."""
        cutoff = datetime.now() - timedelta(days=max_age_days)
        old_ids = []
        
        for msg_id, data in self.processed_ids.items():
            try:
                # Extract timestamp from dict format
                timestamp_str = data.get('timestamp', '')
                if isinstance(timestamp_str, str):
                    timestamp = datetime.fromisoformat(timestamp_str)
                    if timestamp < cutoff:
                        old_ids.append(msg_id)
                else:
                    # If timestamp is already a datetime object
                    if timestamp_str < cutoff:
                        old_ids.append(msg_id)
            except Exception:
                # If we can't parse the timestamp, keep it to be safe
                pass

        for msg_id in old_ids:
            del self.processed_ids[msg_id]

        if old_ids:
            self._save_processed_ids()
            logger.write_to_timeline(
                f"Cleaned up {len(old_ids)} old processed IDs",
                actor="gmail_watcher_imap",
                message_level="DEBUG",
            )

    def _connect(self):
        """Connect to Gmail IMAP server and login."""
        try:
            # Connect to IMAP server (SSL)
            self.mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)

            # Login with app password (remove spaces if any)
            clean_password = self.app_password.replace(' ', '')
            self.mail.login(self.email_address, clean_password)

            # Select inbox (read-write mode so we can mark as read)
            self.mail.select('INBOX', readonly=False)

            logger.write_to_timeline(
                f"Gmail IMAP connected | Server: {self.imap_server}:{self.imap_port}",
                actor="gmail_watcher_imap",
                message_level="INFO",
            )
            logger.write_to_timeline(
                f"Gmail IMAP capabilities: {self.mail.capabilities}",
                actor="gmail_watcher_imap",
                message_level="DEBUG",
            )

        except imaplib.IMAP4.error as e:
            logger.log_error(
                f"Gmail IMAP connection failed: {e}",
                actor="gmail_watcher_imap",
            )
            self.mail = None
        except Exception as e:
            logger.log_error(
                f"Unexpected error connecting to Gmail IMAP: {e}",
                actor="gmail_watcher_imap",
            )
            self.mail = None

    def _reconnect_if_needed(self):
        """Reconnect if connection is lost."""
        if self.mail is None:
            self._connect()
            return

        try:
            # Test connection with noop
            self.mail.noop()
        except Exception:
            logger.write_to_timeline(
                "IMAP connection lost, reconnecting...",
                actor="gmail_watcher_imap",
                message_level="WARNING",
            )
            self._connect()

    def _decode_body(self, msg: email.message.Message) -> str:
        """
        Decode email body from IMAP message.

        Handles both plain text and HTML emails.
        Prefers plain text if both are available.
        """
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

    def _parse_email_headers(self, raw_email: bytes, gmail_msgid_hex: str = '') -> Dict[str, Any]:
        """Parse raw email bytes and extract headers and body."""
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
            'gmail_msgid_hex': gmail_msgid_hex,  # For Gmail URL
        }

        # Parse date
        try:
            from email.utils import parsedate_to_datetime
            received_date = parsedate_to_datetime(headers['date'])
        except Exception:
            received_date = datetime.now()

        # Decode body
        body = self._decode_body(msg)

        return {
            'headers': headers,
            'body': body,
            'received_date': received_date,
            'raw_msg': msg,
        }

    def should_process_email(self, msg: email.message.Message, gmail_msgid: str) -> Tuple[bool, str]:
        """
        Determine if an email should be processed based on filtering rules.

        Args:
            msg: Email message object
            gmail_msgid: Gmail's unique message ID (X-GM-MSGID)

        Returns:
            Tuple of (should_process: bool, reason: str)
        """
        # Extract headers
        from_addr = msg.get('From', '')
        subject = msg.get('Subject', '')
        x_gmail_labels = msg.get('X-Gmail-Labels', '')

        # Check if already processed or skipped
        if gmail_msgid in self.processed_ids:
            entry = self.processed_ids[gmail_msgid]
            status = entry.get('status', 'unknown')
            reason = entry.get('reason', 'Unknown reason')
            return False, f"Already {status}: {reason}"

        # Check Gmail labels (skip if has promotion/social label)
        labels_lower = x_gmail_labels.lower() if x_gmail_labels else ''
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

    def check_for_updates(self) -> List[Dict[str, Any]]:
        """
        Check for new unread important messages.

        Returns:
            List of message dicts with 'id', 'gmail_msgid_hex', 'reason'
        """
        if self.mail is None:
            logger.write_to_timeline(
                "IMAP not connected, attempting reconnect...",
                actor="gmail_watcher_imap",
                message_level="WARNING",
            )
            self._connect()
            if self.mail is None:
                return []

        try:
            # Reconnect if needed
            self._reconnect_if_needed()

            # Search for unread messages using UID SEARCH
            logger.write_to_timeline(
                f"IMAP UID SEARCH: UNSEEN",
                actor="gmail_watcher_imap",
                message_level="DEBUG",
            )

            status, messages = self.mail.uid('SEARCH', None, 'UNSEEN')

            if status != 'OK':
                logger.log_error(
                    f"IMAP UID search failed: {status}",
                    actor="gmail_watcher_imap",
                )
                return []

            # Get message IDs
            message_ids = messages[0].split()

            if not message_ids:
                logger.write_to_timeline(
                    "No new messages found",
                    actor="gmail_watcher_imap",
                    message_level="DEBUG",
                )
                return []

            # Filter and categorize messages using smart filtering
            new_messages = []
            skipped_emails = []
            already_processed_count = 0
            already_skipped_count = 0

            for msg_id in message_ids:
                msg_id_str = msg_id.decode('utf-8')

                # Step 1: Fetch X-GM-MSGID first (lightweight fetch)
                try:
                    status, msg_data = self.mail.uid('FETCH', msg_id, '(X-GM-MSGID)')

                    if status != 'OK':
                        continue

                    # Extract X-GM-MSGID from response
                    # Response format: (b'102 (X-GM-MSGID 18f2a3b4c5d6e7f8)', b')')
                    gmail_msgid_decimal = None
                    
                    # msg_data is a list, first element contains the response
                    if msg_data and len(msg_data) > 0:
                        # msg_data[0] is typically a tuple or bytes
                        item = msg_data[0]
                        if isinstance(item, tuple):
                            # Tuple format: (b'102', b'X-GM-MSGID 18f2a3b4c5d6e7f8')
                            for part in item:
                                if isinstance(part, bytes) and b'X-GM-MSGID' in part:
                                    # Decode and extract number
                                    part_str = part.decode('utf-8')
                                    match = re.search(r'X-GM-MSGID\s+(\d+)', part_str)
                                    if match:
                                        gmail_msgid_decimal = match.group(1)
                                        break
                        elif isinstance(item, bytes):
                            # Bytes format: b'102 (X-GM-MSGID 18f2a3b4c5d6e7f8)'
                            item_str = item.decode('utf-8')
                            match = re.search(r'X-GM-MSGID\s+(\d+)', item_str)
                            if match:
                                gmail_msgid_decimal = match.group(1)
                    
                    # Fallback: if we couldn't extract X-GM-MSGID, use IMAP UID
                    if not gmail_msgid_decimal:
                        logger.write_to_timeline(
                            f"Could not extract X-GM-MSGID for UID {msg_id_str}, using UID as fallback",
                            actor="gmail_watcher_imap",
                            message_level="WARNING",
                        )
                        # Debug: log the raw response
                        logger.write_to_timeline(
                            f"Raw msg_data: {msg_data}",
                            actor="gmail_watcher_imap",
                            message_level="DEBUG",
                        )
                    else:
                        logger.write_to_timeline(
                            f"Extracted X-GM-MSGID {gmail_msgid_decimal} for UID {msg_id_str}",
                            actor="gmail_watcher_imap",
                            message_level="DEBUG",
                        )
                    
                    # Use Gmail's permanent message ID (or fallback to UID)
                    gmail_msgid = gmail_msgid_decimal if gmail_msgid_decimal else msg_id_str

                    # Step 2: Check if already processed/skipped (EARLY SKIP)
                    if gmail_msgid in self.processed_ids:
                        entry = self.processed_ids[gmail_msgid]
                        status = entry.get('status', 'unknown')
                        
                        # Mark as read again (in case user marked it unread)
                        self.mail.uid('STORE', msg_id, '+FLAGS', '\\Seen')
                        
                        if status == 'processed':
                            already_processed_count += 1
                        else:  # skipped
                            already_skipped_count += 1
                        continue

                    # Step 3: Fetch full email content only for new emails
                    status, msg_data = self.mail.uid('FETCH', msg_id, '(RFC822 X-GM-LABELS)')

                    if status != 'OK':
                        continue

                    raw_email = msg_data[0][1]
                    msg = email.message_from_bytes(raw_email)

                    # Convert to hex for Gmail URL
                    gmail_msgid_hex = format(int(gmail_msgid), 'x') if gmail_msgid_decimal else msg_id_str

                    # Step 4: Apply smart filtering
                    should_process, reason = self.should_process_email(msg, gmail_msgid)

                    if should_process:
                        new_messages.append({
                            'id': msg_id_str,  # IMAP UID for fetching
                            'gmail_msgid': gmail_msgid,  # Gmail permanent ID for tracking
                            'gmail_msgid_hex': gmail_msgid_hex,  # Hex for URL
                            'reason': reason,
                        })
                    else:
                        # Track skipped email for logging
                        headers = {
                            'from': msg.get('From', 'Unknown'),
                            'subject': msg.get('Subject', 'No Subject'),
                        }
                        skipped_emails.append({
                            'message_id': msg_id_str,
                            'gmail_msgid': gmail_msgid,
                            'from': headers['from'],
                            'subject': headers['subject'],
                            'reason': reason,
                            'gmail_link': f"https://mail.google.com/mail/u/0/#inbox/{gmail_msgid_hex}",
                            'processed_at': datetime.now().isoformat(),
                        })

                        # Mark as read and save to processed_ids
                        self.mail.uid('STORE', msg_id, '+FLAGS', '\\Seen')
                        
                        # Save skipped email to processed_ids for early skip next time
                        self.processed_ids[gmail_msgid] = {
                            "status": "skipped",
                            "timestamp": datetime.now().isoformat(),
                            "reason": reason,
                        }

                except Exception as e:
                    logger.log_warning(
                        f"Error processing message {msg_id_str}: {e}",
                        actor="gmail_watcher_imap",
                    )
                    continue

            # Store skipped emails for logging
            self.skipped_emails = skipped_emails

            logger.write_to_timeline(
                f"Found {len(message_ids)} unread, {len(new_messages)} to process, "
                f"{len(skipped_emails)} skipped, {already_processed_count} already processed, "
                f"{already_skipped_count} already skipped",
                actor="gmail_watcher_imap",
                message_level="INFO",
            )

            # Cleanup old processed IDs periodically
            if len(self.processed_ids) % 10 == 0:
                self._cleanup_old_processed_ids()

            return new_messages

        except Exception as e:
            logger.log_error(
                f'Error checking Gmail IMAP: {e}',
                actor="gmail_watcher_imap",
            )
            return []

    def create_action_file(self, message: Dict[str, Any]) -> Optional[Path]:
        """
        Create a task file for a Gmail message.

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

            # Get Gmail message IDs from message dict (already fetched in check_for_updates)
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

    def _generate_skipped_report(self):
        """Append skipped emails to master skipped file (no overwrite)."""
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

    def _generate_processing_index(self):
        """Append processed emails to master processed file (no overwrite)."""
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

    def _generate_status_dashboard(self):
        """Generate status dashboard showing all emails by status."""
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

    def run(self):
        """
        Main loop - runs continuously checking for new messages.

        Blocks until interrupted (Ctrl+C).
        """
        logger.write_to_timeline(
            f"Starting Gmail Watcher IMAP | Check interval: {self.check_interval}s | "
            f"Smart Filtering: ENABLED",
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

                    # Update dashboard even when no new messages (every 10 cycles)
                    if run_counter % 10 == 0:
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

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup IMAP connection."""
        if self.mail:
            try:
                self.mail.close()
                self.mail.logout()
            except Exception:
                pass


def main():
    """Standalone entry point for testing."""
    logger.write_to_timeline(
        "Gmail Watcher IMAP (standalone mode)",
        actor="gmail_watcher_imap",
        message_level="INFO",
    )

    # Get credentials from settings
    email_address = settings.gmail_imap_address
    app_password = settings.gmail_imap_app_password

    if not email_address or not app_password:
        logger.log_error(
            "Gmail IMAP credentials not found in settings. "
            "Set GMAIL_IMAP_ADDRESS and GMAIL_IMAP_APP_PASSWORD in .env",
            actor="gmail_watcher_imap",
        )
        return

    watcher = GmailWatcherIMAP(
        email_address=email_address,
        app_password=app_password,
        check_interval=settings.gmail_watcher_check_interval,
        gmail_query="UNSEEN",  # Use UNSEEN instead of custom query
    )

    if watcher.mail:
        logger.write_to_timeline(
            "Running in standalone mode (Ctrl+C to stop)",
            actor="gmail_watcher_imap",
            message_level="INFO",
        )
        watcher.run()
    else:
        logger.log_error(
            "Gmail Watcher IMAP not connected. Check credentials.",
            actor="gmail_watcher_imap",
        )


if __name__ == "__main__":
    main()
