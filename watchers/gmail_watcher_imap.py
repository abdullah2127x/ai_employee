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
"""

import email
import imaplib
import base64
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
import re

from core.config import settings
from utils.logging_manager import LoggingManager
from utils.task_template import create_email_task

logger = LoggingManager()


class GmailWatcherIMAP:
    """
    Gmail Watcher using IMAP protocol with app password.
    
    Simple, development-friendly alternative to OAuth2-based watcher.
    """

    def __init__(
        self,
        email_address: str,
        app_password: str,
        check_interval: int = 120,
        gmail_query: str = "UNREAD IMPORTANT",
        imap_server: str = "imap.gmail.com",
        imap_port: int = 993,
    ):
        """
        Initialize IMAP Gmail watcher.

        Args:
            email_address: Gmail address (e.g., your.email@gmail.com)
            app_password: Gmail app password (16 characters, from Google security settings)
            check_interval: Seconds between checks (default: 120)
            gmail_query: IMAP search query (default: UNREAD IMPORTANT)
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
        self.vault_path = settings.vault_path
        self.needs_action = settings.needs_action_path

        # Track processed message IDs (with timestamps for cleanup)
        self.processed_ids: Dict[str, datetime] = {}
        self.processed_file = self.vault_path / '.gmail_imap_processed_ids.json'

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
            f"Query: {gmail_query} | Interval: {check_interval}s",
            actor="gmail_watcher_imap",
            message_level="INFO",
        )

    def _load_processed_ids(self):
        """Load processed message IDs from JSON file."""
        if self.processed_file.exists():
            try:
                import json
                data = json.loads(self.processed_file.read_text(encoding='utf-8'))
                # Convert to dict with datetime objects
                self.processed_ids = {
                    msg_id: datetime.fromisoformat(ts)
                    for msg_id, ts in data.items()
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
        import json
        # Convert datetime objects to ISO strings
        data = {msg_id: ts.isoformat() for msg_id, ts in self.processed_ids.items()}
        try:
            self.processed_file.write_text(json.dumps(data, indent=2), encoding='utf-8')
        except Exception as e:
            logger.log_error(
                f"Could not save processed IDs file: {e}",
                actor="gmail_watcher_imap",
            )

    def _cleanup_old_processed_ids(self, max_age_days: int = 7):
        """Remove processed IDs older than max_age_days."""
        cutoff = datetime.now() - timedelta(days=max_age_days)
        old_ids = [
            msg_id for msg_id, ts in self.processed_ids.items()
            if ts < cutoff
        ]
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
            
            # Login with app password
            self.mail.login(self.email_address, self.app_password)
            
            # Select inbox (read-only mode for safety)
            self.mail.select('INBOX', readonly=True)
            
            logger.write_to_timeline(
                f"Gmail IMAP connected | Server: {self.imap_server}:{self.imap_port}",
                actor="gmail_watcher_imap",
                message_level="INFO",
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

    def _decode_message_body(self, msg: email.message.Message) -> str:
        """
        Decode email body from IMAP message.
        
        Handles both plain text and HTML emails.
        Prefers plain text if both are available.
        """
        body = ""
        
        # Walk through message parts
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition") or "")
                
                # Skip attachments
                if "attachment" in content_disposition:
                    continue
                
                # Prefer plain text
                if content_type == "text/plain":
                    try:
                        charset = part.get_content_charset() or "utf-8"
                        payload = part.get_payload(decode=True)
                        if payload:
                            body = payload.decode(charset, errors="replace")
                            break  # Found plain text, use it
                    except Exception:
                        pass
                
                # Fallback to HTML
                if content_type == "text/html" and not body:
                    try:
                        charset = part.get_content_charset() or "utf-8"
                        payload = part.get_payload(decode=True)
                        if payload:
                            body = payload.decode(charset, errors="replace")
                    except Exception:
                        pass
        else:
            # Simple message (not multipart)
            try:
                charset = msg.get_content_charset() or "utf-8"
                payload = msg.get_payload(decode=True)
                if payload:
                    body = payload.decode(charset, errors="replace")
            except Exception:
                body = msg.get_payload() or "[Could not decode content]"
        
        return body if body else "[No content available]"

    def _parse_email_headers(self, raw_email: bytes) -> Dict[str, Any]:
        """Parse raw email bytes and extract headers and body."""
        msg = email.message_from_bytes(raw_email)
        
        # Extract headers
        headers = {
            'from': msg.get('From', 'Unknown'),
            'to': msg.get('To', 'Unknown'),
            'subject': msg.get('Subject', 'No Subject'),
            'date': msg.get('Date', ''),
            'message_id': msg.get('Message-ID', ''),
        }
        
        # Parse date
        try:
            from email.utils import parsedate_to_datetime
            received_date = parsedate_to_datetime(headers['date'])
        except Exception:
            received_date = datetime.now()
        
        # Decode body
        body = self._decode_message_body(msg)
        
        return {
            'headers': headers,
            'body': body,
            'received_date': received_date,
            'raw_msg': msg,
        }

    def check_for_updates(self) -> List[Dict[str, str]]:
        """
        Check for new unread important messages.
        
        Returns:
            List of message dicts with 'id', 'subject', 'from'
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
            
            # Search for unread important messages
            # IMAP search uses different syntax than Gmail
            status, messages = self.mail.search(None, self.gmail_query)
            
            if status != 'OK':
                logger.write_to_timeline(
                    f"IMAP search failed: {status}",
                    actor="gmail_watcher_imap",
                    message_level="WARNING",
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
            
            # Filter out already processed
            new_messages = []
            for msg_id in message_ids:
                msg_id_str = msg_id.decode('utf-8')
                if msg_id_str not in self.processed_ids:
                    new_messages.append({'id': msg_id_str})
            
            logger.write_to_timeline(
                f"Found {len(message_ids)} messages, {len(new_messages)} new",
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

    def create_action_file(self, message: Dict[str, str]) -> Optional[Path]:
        """
        Create a task file for a Gmail message.
        
        Uses v2 task_template API (create_email_task) for consistent format.

        Args:
            message: Message dict with 'id'

        Returns:
            Path to created file, or None on error
        """
        if self.mail is None:
            return None

        try:
            # Fetch message by ID
            status, msg_data = self.mail.fetch(message['id'], '(RFC822)')
            
            if status != 'OK':
                logger.log_warning(
                    f"Could not fetch message {message['id']}",
                    actor="gmail_watcher_imap",
                )
                return None
            
            # Parse email
            email_data = self._parse_email_headers(msg_data[0][1])
            headers = email_data['headers']
            body = email_data['body']
            received_date = email_data['received_date']
            
            # Determine priority based on subject/content
            priority = "normal"
            subject_lower = headers['subject'].lower()
            
            if any(word in subject_lower for word in ['urgent', 'asap', 'emergency']):
                priority = "urgent"
            elif any(word in subject_lower for word in ['invoice', 'payment', 'billing']):
                priority = "high"
            elif 'important' in subject_lower:
                priority = "high"
            
            # Create task file using v2 API
            task_id, task_content = create_email_task(
                from_address=headers['from'],
                subject=headers['subject'],
                content=body,
                timestamp=received_date,
                priority=priority,
            )
            
            # Write task file
            filepath = self.needs_action / f"{task_id}.md"
            temp_path = filepath.with_suffix('.tmp')
            
            # Atomic write
            temp_path.write_text(task_content, encoding='utf-8')
            temp_path.rename(filepath)
            
            # Mark as processed
            self.processed_ids[message['id']] = datetime.now()
            self._save_processed_ids()
            
            logger.write_to_timeline(
                f"Created task file: {filepath.name} | From: {headers['from'][:50]}",
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

    def run(self):
        """
        Main loop - runs continuously checking for new messages.
        
        Blocks until interrupted (Ctrl+C).
        """
        logger.write_to_timeline(
            f"Starting Gmail Watcher IMAP | Check interval: {self.check_interval}s",
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

        try:
            while True:
                items = self.check_for_updates()
                
                if items:
                    logger.write_to_timeline(
                        f"Processing {len(items)} new message(s)",
                        actor="gmail_watcher_imap",
                        message_level="INFO",
                    )
                    for item in items:
                        self.create_action_file(item)
                else:
                    logger.write_to_timeline(
                        "No new messages",
                        actor="gmail_watcher_imap",
                        message_level="DEBUG",
                    )
                
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
        gmail_query=settings.gmail_watcher_query,
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
