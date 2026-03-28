#!/usr/bin/env python3
"""
gmail_watcher_imap.py - Clean Gmail Watcher using IMAP (Option B ready)
Inherits from BaseWatcher + uses centralized LoggingManager
"""

import email
import imaplib
import json
import re
from datetime import datetime
from email import message
from pathlib import Path
from typing import List, Dict, Any, Tuple

from base_watcher import BaseWatcher
from utils.task_template import create_email_task_enhanced
from core.config import settings
from utils.logging_manager import LoggingManager   # Not strictly needed since BaseWatcher provides it


class GmailWatcherIMAP(BaseWatcher):
    """Gmail IMAP watcher following BaseWatcher pattern for Option B."""

    def __init__(self, vault_path: str, email_address: str, app_password: str, check_interval: int = 180):
        super().__init__(vault_path, check_interval)

        self.email_address = email_address
        self.app_password = app_password

        # Processed tracking (to avoid re-processing same emails)
        self.processed_ids: Dict[str, Dict[str, Any]] = {}
        self.processed_file = self.vault_path / '.gmail_imap_processed_ids.json'

        self.skipped_emails: List[Dict] = []          # For skipped report
        self.processed_email_details: List[Dict] = [] # For processed report

        self.mail: imaplib.IMAP4_SSL | None = None

        self._load_processed_ids()
        self._connect()

    # ====================== FILTER CONFIG ======================
    FILTER_CONFIG = {
        "skip_categories": ["promotions", "social", "updates", "forums"],
        "skip_domains": [
            "linkedin.com", "github.com", "facebook.com", "twitter.com",
            "instagram.com", "youtube.com", "medium.com", "substack.com",
            "reddit.com", "quora.com"
        ],
        "business_domains": [
            "amazon.com", "aws.amazon.com", "google.com", "microsoft.com",
            "apple.com", "paypal.com", "stripe.com", "bank", "gov"
        ],
        "skip_subject_keywords": [
            "newsletter", "digest", "weekly roundup", "daily digest",
            "unsub", "unsubscribe", "marketing", "promo", "discount", "sale", "offer"
        ],
        "priority_keywords": [
            "urgent", "asap", "important", "action required",
            "payment", "invoice", "interview", "meeting", "job", "career"
        ],
        "priority_domains": ["gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "icloud.com"],
    }

    # ====================== ABSTRACT METHOD IMPLEMENTATIONS ======================

    def check_for_updates(self) -> List[Dict[str, Any]]:
        """Return list of new emails that should be processed."""
        if not self.mail:
            self._connect()
            if not self.mail:
                return []

        self._reconnect_if_needed()

        try:
            status, data = self.mail.uid('SEARCH', None, 'UNSEEN')
            if status != 'OK' or not data[0]:
                return []

            message_ids = data[0].split()
            new_messages = []

            for uid in message_ids:
                uid_str = uid.decode('utf-8')

                # Get permanent Gmail Message ID
                _, fetch_data = self.mail.uid('FETCH', uid, '(X-GM-MSGID)')
                gmail_msgid = None
                if fetch_data and fetch_data[0]:
                    match = re.search(rb'X-GM-MSGID\s+(\d+)', fetch_data[0])
                    if match:
                        gmail_msgid = match.group(1).decode()

                if not gmail_msgid:
                    gmail_msgid = uid_str

                if gmail_msgid in self.processed_ids:
                    continue

                # Fetch full email for filtering
                _, msg_data = self.mail.uid('FETCH', uid, '(RFC822 X-GM-LABELS)')
                if not msg_data or not msg_data[0]:
                    continue

                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)

                should_process, reason = self.should_process_email(msg, gmail_msgid)

                if should_process:
                    new_messages.append({
                        'uid': uid_str,
                        'gmail_msgid': gmail_msgid,
                        'reason': reason,
                    })
                else:
                    # Mark as seen and record as skipped
                    self.mail.uid('STORE', uid, '+FLAGS', '\\Seen')
                    self.skipped_emails.append({
                        'gmail_msgid': gmail_msgid,
                        'from': msg.get('From', 'Unknown'),
                        'subject': msg.get('Subject', 'No Subject'),
                        'reason': reason,
                    })

            return new_messages

        except Exception as e:
            self.logger.log_error("Error while checking for new emails", error=e, actor="gmail_watcher")
            return []

    def create_action_file(self, item: Dict[str, Any]) -> Path:
        """Create clean Needs_Action markdown file using the updated template."""
        try:
            _, msg_data = self.mail.uid('FETCH', item['uid'], '(RFC822)')
            if not msg_data or not msg_data[0]:
                raise ValueError("Could not fetch email content")

            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)

            headers = {
                'from': msg.get('From', 'Unknown'),
                'to': msg.get('To', 'Unknown'),
                'subject': msg.get('Subject', 'No Subject'),
            }

            body = self._decode_body(msg)

            # Parse received date
            received_date = datetime.now()
            try:
                from email.utils import parsedate_to_datetime
                received_date = parsedate_to_datetime(msg.get('Date', ''))
            except:
                pass

            is_reply = bool(msg.get('In-Reply-To') or msg.get('References'))

            gmail_msgid_hex = format(int(item['gmail_msgid']), 'x') if item['gmail_msgid'].isdigit() else item['gmail_msgid']
            gmail_link = f"https://mail.google.com/mail/u/0/#inbox/{gmail_msgid_hex}"

            # Basic priority (Claude will do deeper reasoning)
            subject_lower = headers['subject'].lower()
            priority = "urgent" if any(k in subject_lower for k in ['urgent', 'asap']) else \
                       "high" if any(k in subject_lower for k in ['invoice', 'payment', 'meeting']) else "normal"

            # Create task using clean template
            task_id, task_content = create_email_task_enhanced(
                from_address=headers['from'],
                to_address=headers['to'],
                subject=headers['subject'],
                content=body,
                timestamp=received_date,
                priority=priority,
                filter_reason=item['reason'],
                is_reply=is_reply,
                gmail_message_id=item['gmail_msgid'],
                gmail_link=gmail_link,
            )

            filepath = self.needs_action / f"{task_id}.md"
            temp_path = filepath.with_suffix('.tmp')

            temp_path.write_text(task_content, encoding='utf-8')
            temp_path.rename(filepath)

            # Mark email as read in Gmail
            self.mail.uid('STORE', item['uid'], '+FLAGS', '\\Seen')

            # Record as processed
            self.processed_ids[item['gmail_msgid']] = {
                "status": "processed",
                "timestamp": datetime.now().isoformat(),
                "reason": item['reason']
            }
            self._save_processed_ids()

            self.processed_email_details.append({
                'task_id': task_id,
                'from': headers['from'],
                'subject': headers['subject'],
                'priority': priority,
                'reason': item['reason']
            })

            return filepath

        except Exception as e:
            self.logger.log_error(f"Failed to create action file for email", error=e, actor="gmail_watcher")
            raise

    # ====================== HELPER METHODS ======================

    def _decode_body(self, msg: email.message.Message) -> str:
        """Extract plain text body with fallback."""
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    payload = part.get_payload(decode=True)
                    if payload:
                        body = payload.decode(part.get_content_charset() or 'utf-8', errors='replace')
                        break
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                body = payload.decode(msg.get_content_charset() or 'utf-8', errors='replace')

        return body.strip() or "[No content available]"

    def should_process_email(self, msg: email.message.Message, gmail_msgid: str) -> Tuple[bool, str]:
        """Smart filtering logic."""
        if gmail_msgid in self.processed_ids:
            return False, "Already processed"

        from_addr = msg.get('From', '')
        subject = msg.get('Subject', '')
        labels = msg.get('X-Gmail-Labels', '').lower()
        from_domain = from_addr.split('@')[-1].strip('>').lower() if '@' in from_addr else ''

        # Skip Gmail categories
        for cat in self.FILTER_CONFIG["skip_categories"]:
            if cat in labels:
                return False, f"Skipped: {cat} category"

        # Business domains = always process
        for domain in self.FILTER_CONFIG["business_domains"]:
            if domain in from_domain:
                return True, f"Business domain: {domain}"

        # Skip known automated senders
        for domain in self.FILTER_CONFIG["skip_domains"]:
            if domain in from_domain:
                return False, f"Skipped sender: {domain}"

        subject_lower = subject.lower()

        # Priority keywords
        for kw in self.FILTER_CONFIG["priority_keywords"]:
            if kw in subject_lower:
                return True, f"Priority keyword: {kw}"

        # Priority personal domains
        for domain in self.FILTER_CONFIG["priority_domains"]:
            if domain in from_domain:
                return True, f"Personal email: {domain}"

        # Skip subject keywords
        for kw in self.FILTER_CONFIG["skip_subject_keywords"]:
            if kw in subject_lower:
                return False, f"Skipped keyword: {kw}"

        return True, "Default: individual sender"

    def _load_processed_ids(self):
        if self.processed_file.exists():
            try:
                self.processed_ids = json.loads(self.processed_file.read_text(encoding='utf-8'))
            except Exception:
                self.processed_ids = {}

    def _save_processed_ids(self):
        try:
            self.processed_file.write_text(json.dumps(self.processed_ids, indent=2), encoding='utf-8')
        except Exception as e:
            self.logger.log_error("Failed to save processed IDs file", error=e, actor="gmail_watcher")

    def _reconnect_if_needed(self):
        if not self.mail:
            self._connect()
            return
        try:
            self.mail.noop()
        except Exception:
            self.logger.log_warning("IMAP connection lost, reconnecting...", actor="gmail_watcher")
            self._connect()

    def _connect(self):
        try:
            self.mail = imaplib.IMAP4_SSL(self.imap_server if hasattr(self, 'imap_server') else "imap.gmail.com", 
                                             self.imap_port if hasattr(self, 'imap_port') else 993)
            clean_pass = self.app_password.replace(' ', '')
            self.mail.login(self.email_address, clean_pass)
            self.mail.select('INBOX', readonly=False)
            self.logger.write_to_timeline("IMAP connection established", actor="gmail_watcher", message_level="INFO")
        except Exception as e:
            self.logger.log_error("Failed to connect to Gmail IMAP", error=e, actor="gmail_watcher")
            self.mail = None


def main():
    email_address = settings.gmail_imap_address
    app_password = settings.gmail_imap_app_password

    if not email_address or not app_password:
        print("ERROR: Gmail IMAP credentials missing in settings/.env")
        return

    watcher = GmailWatcherIMAP(
        vault_path=str(settings.vault_path),
        email_address=email_address,
        app_password=app_password,
        check_interval=180,
    )
    watcher.run()


if __name__ == "__main__":
    main()