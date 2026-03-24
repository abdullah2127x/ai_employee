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
        
        # Ensure Needs_Action directory exists
        NEEDS_ACTION_PATH.mkdir(parents=True, exist_ok=True)
        
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
            safe_subject = headers['subject'][:30].replace(' ', '_').replace('/', '_').replace('\\', '_')
            # Remove special characters that cause Windows issues
            safe_subject = ''.join(c for c in safe_subject if c.isalnum() or c in ['_', '-'])
            task_id = f"email_{timestamp}_{safe_subject}"
            
            # Truncate body for task file (max 3000 chars)
            truncated_body = body[:3000] + "\n\n[Content truncated...]" if len(body) > 3000 else body
            
            # Build task file content
            task_content = f"""---
type: email
task_id: {task_id}
from: {headers['from']}
subject: {headers['subject']}
received: {received_date.isoformat()}
priority: {priority}
status: pending
filter_reason: {reason}
---

# Email: {headers['subject']}

## Email Information

| Property | Value |
|----------|-------|
| From | `{headers['from']}` |
| To | `{headers['to']}` |
| Received | {received_date.strftime('%Y-%m-%d %H:%M:%S')} |
| Priority | {priority.title()} |
| Filter Reason | {reason} |

---

## Email Content

{truncated_body}

---

## Instructions for AI

1. Identify the email type (request, invoice, informational, etc.)
2. Classify urgency and category
3. Apply business rules from Business_Goals.md and Company_Handbook.md
4. Return JSON decision as defined in CLAUDE.md

---

*Generated by AI Employee Gmail Filter Processor*
*Task ID: `{task_id}`*
*Message ID: `{msg_id}`*
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
                print(f"✅ Created: {filepath.name}")
            else:
                print("❌ Failed to create task file")
                self.error_count += 1
        
        # Save processed IDs
        self._save_processed_ids()
    
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
