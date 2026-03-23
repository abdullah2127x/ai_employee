#!/usr/bin/env python3
"""
gmail_watcher.py - Gmail API watcher for AI Employee (v2)

Watches Gmail for new unread/important messages and creates task files
in Needs_Action/ folder for AI processing.

v2 Changes:
- Uses create_email_task() from task_template.py (v2 API)
- Integrated with LoggingManager (not Python logging)
- Supports content truncation for large emails
- Properly formatted task files for Claude Code processing

Usage:
    Enabled via settings.enable_gmail_watcher in .env

Requirements:
    pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client

Setup:
    1. Enable Gmail API in Google Cloud Console
    2. Download credentials.json (OAuth 2.0 Client ID)
    3. Place credentials in project root or specify path in settings
    4. First run opens browser for OAuth authorization
    5. Token saved to ~/.gmail_token.json
"""

import base64
import email
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional

# Gmail API imports
try:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    GMAIL_AVAILABLE = True
except ImportError:
    GMAIL_AVAILABLE = False

from core.config import settings
from utils.logging_manager import LoggingManager
from utils.task_template import create_email_task

logger = LoggingManager()

# Gmail API OAuth scopes
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']


class GmailWatcher:
    """
    Watches Gmail for new unread/important messages.
    
    Creates task files in Needs_Action/ folder for AI processing.
    Uses v2 task_template API for consistent task file format.
    """

    def __init__(
        self,
        credentials_path: Optional[Path] = None,
        token_path: Optional[Path] = None,
        check_interval: int = 120,
        gmail_query: str = "is:unread is:important",
    ):
        """
        Initialize Gmail watcher.

        Args:
            credentials_path: Path to Gmail API credentials JSON file
            token_path: Path to store/load OAuth token (default: ~/.gmail_token.json)
            check_interval: Seconds between checks (default: 120)
            gmail_query: Gmail search query for filtering (default: is:unread is:important)
        """
        if not GMAIL_AVAILABLE:
            raise ImportError(
                "Gmail API libraries not installed. "
                "Install with: pip install google-auth google-auth-oauthlib "
                "google-auth-httplib2 google-api-python-client"
            )

        # Use settings for vault path
        self.vault_path = settings.vault_path
        self.needs_action = settings.needs_action_path
        self.check_interval = check_interval
        self.gmail_query = gmail_query

        # Credentials paths
        self.credentials_path = credentials_path or (settings.vault_path / "credentials.json")
        self.token_path = token_path or (Path.home() / '.gmail_token.json')

        # Gmail API objects
        self.creds: Optional[Credentials] = None
        self.service: Optional[Any] = None

        # Track processed message IDs (with timestamps for cleanup)
        self.processed_ids: Dict[str, datetime] = {}
        self.processed_file = self.vault_path / '.gmail_processed_ids.json'

        # Ensure Needs_Action directory exists
        self.needs_action.mkdir(parents=True, exist_ok=True)

        # Load processed message IDs from file
        self._load_processed_ids()

        # Authenticate with Gmail API
        self._authenticate()

        logger.write_to_timeline(
            f"GmailWatcher initialized | Query: {gmail_query} | Interval: {check_interval}s",
            actor="gmail_watcher",
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
                    actor="gmail_watcher",
                    message_level="DEBUG",
                )
            except Exception as e:
                logger.log_warning(
                    f"Could not load processed IDs file: {e}",
                    actor="gmail_watcher",
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
                actor="gmail_watcher",
            )

    def _cleanup_old_processed_ids(self, max_age_days: int = 7):
        """
        Remove processed IDs older than max_age_days.
        
        Prevents unbounded growth of the processed IDs file.
        Gmail message IDs are unique forever, so old IDs can be safely removed.
        """
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
                actor="gmail_watcher",
                message_level="DEBUG",
            )

    def _authenticate(self):
        """Authenticate with Gmail API."""
        if not self.credentials_path.exists():
            logger.log_warning(
                f"Gmail credentials not found at {self.credentials_path}. "
                "Please place credentials.json in vault/ or specify path in settings.",
                actor="gmail_watcher",
            )
            return

        try:
            # Load existing token
            if self.token_path.exists():
                self.creds = Credentials.from_authorized_user_file(
                    str(self.token_path), SCOPES
                )
                logger.write_to_timeline(
                    "Loaded existing OAuth token",
                    actor="gmail_watcher",
                    message_level="DEBUG",
                )

            # Refresh or get new token
            if not self.creds or not self.creds.valid:
                if self.creds and self.creds.expired and self.creds.refresh_token:
                    logger.write_to_timeline(
                        "Refreshing expired OAuth token",
                        actor="gmail_watcher",
                        message_level="INFO",
                    )
                    self.creds.refresh(Request())
                else:
                    logger.write_to_timeline(
                        "Starting OAuth flow (first run or token invalid)",
                        actor="gmail_watcher",
                        message_level="INFO",
                    )
                    flow = InstalledAppFlow.from_client_secrets_file(
                        str(self.credentials_path), SCOPES
                    )
                    self.creds = flow.run_local_server(port=0)

                # Save token for next time
                self.token_path.write_text(self.creds.to_json())
                logger.write_to_timeline(
                    "OAuth token saved",
                    actor="gmail_watcher",
                    message_level="INFO",
                )

            # Build Gmail API service
            self.service = build('gmail', 'v1', credentials=self.creds)
            logger.write_to_timeline(
                "Gmail API authenticated successfully",
                actor="gmail_watcher",
                message_level="INFO",
            )

        except Exception as e:
            logger.log_error(
                f"Gmail authentication failed: {e}",
                actor="gmail_watcher",
            )
            self.service = None

    def _decode_message_body(self, msg: Dict[str, Any]) -> str:
        """
        Decode email body from Gmail API response.
        
        Handles both plain text and HTML emails.
        Prefers plain text if both are available.
        """
        try:
            # Try plain text first
            if 'parts' in msg['payload']:
                for part in msg['payload']['parts']:
                    if part['mimeType'] == 'text/plain':
                        body_data = part['body'].get('data', '')
                        if body_data:
                            return base64.urlsafe_b64decode(body_data).decode('utf-8')
            
            # Fallback to HTML
            if 'parts' in msg['payload']:
                for part in msg['payload']['parts']:
                    if part['mimeType'] == 'text/html':
                        body_data = part['body'].get('data', '')
                        if body_data:
                            return base64.urlsafe_b64decode(body_data).decode('utf-8')
            
            # Last resort: use snippet
            return msg.get('snippet', '[No content available]')
            
        except Exception as e:
            logger.log_warning(
                f"Could not decode message body: {e}",
                actor="gmail_watcher",
            )
            return msg.get('snippet', '[Error decoding content]')

    def check_for_updates(self) -> List[Dict[str, str]]:
        """
        Check for new unread important messages.
        
        Returns:
            List of message dicts with 'id' and 'threadId'
        """
        if not self.service:
            logger.write_to_timeline(
                "Gmail service not available (not authenticated)",
                actor="gmail_watcher",
                message_level="WARNING",
            )
            return []

        try:
            # Query Gmail
            results = self.service.users().messages().list(
                userId='me',
                q=self.gmail_query,
                maxResults=50  # Limit to 50 messages per check
            ).execute()

            messages = results.get('messages', [])
            
            if not messages:
                logger.write_to_timeline(
                    "No new messages found",
                    actor="gmail_watcher",
                    message_level="DEBUG",
                )
                return []

            # Filter out already processed
            new_messages = [
                m for m in messages
                if m['id'] not in self.processed_ids
            ]

            logger.write_to_timeline(
                f"Found {len(messages)} messages, {len(new_messages)} new",
                actor="gmail_watcher",
                message_level="INFO",
            )

            # Cleanup old processed IDs periodically
            if len(self.processed_ids) % 10 == 0:
                self._cleanup_old_processed_ids()

            return new_messages

        except HttpError as error:
            logger.log_error(
                f'Gmail API error: {error}',
                actor="gmail_watcher",
            )
            return []
        except Exception as e:
            logger.log_error(
                f'Error checking Gmail: {e}',
                actor="gmail_watcher",
            )
            return []

    def create_action_file(self, message: Dict[str, str]) -> Optional[Path]:
        """
        Create a task file for a Gmail message.
        
        Uses v2 task_template API (create_email_task) for consistent format.

        Args:
            message: Message dict with 'id' and 'threadId'

        Returns:
            Path to created file, or None on error
        """
        if not self.service:
            return None

        try:
            # Fetch full message
            msg = self.service.users().messages().get(
                userId='me',
                id=message['id'],
                format='full'
            ).execute()

            # Extract headers
            headers = {
                h['name']: h['value']
                for h in msg['payload'].get('headers', [])
            }

            # Get message body
            body = self._decode_message_body(msg)

            # Determine priority based on Gmail labels
            priority = "normal"
            labels = msg.get('labelIds', [])
            if 'IMPORTANT' in labels:
                priority = "high"
            if 'STARRED' in labels:
                priority = "urgent"

            # Parse date
            date_str = headers.get('Date', '')
            try:
                from email.utils import parsedate_to_datetime
                received_date = parsedate_to_datetime(date_str)
            except Exception:
                received_date = datetime.now()

            # Create task file using v2 API
            task_id, task_content = create_email_task(
                from_address=headers.get('From', 'Unknown'),
                subject=headers.get('Subject', 'No Subject'),
                content=body,
                timestamp=received_date,
                priority=priority,
            )

            # Write task file
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filepath = self.needs_action / f"{task_id}.md"
            temp_path = filepath.with_suffix('.tmp')

            # Atomic write
            temp_path.write_text(task_content, encoding='utf-8')
            temp_path.rename(filepath)

            # Mark as processed
            self.processed_ids[message['id']] = datetime.now()
            self._save_processed_ids()

            logger.write_to_timeline(
                f"Created task file: {filepath.name} | From: {headers.get('From', 'Unknown')[:50]}",
                actor="gmail_watcher",
                message_level="INFO",
            )

            return filepath

        except Exception as e:
            logger.log_error(
                f'Error creating action file for message {message["id"]}: {e}',
                actor="gmail_watcher",
            )
            return None

    def run(self):
        """
        Main loop - runs continuously checking for new messages.
        
        Blocks until interrupted (Ctrl+C).
        """
        logger.write_to_timeline(
            f"Starting Gmail Watcher | Check interval: {self.check_interval}s",
            actor="gmail_watcher",
            message_level="INFO",
        )

        if not self.service:
            logger.write_to_timeline(
                "Gmail Watcher cannot start - not authenticated",
                actor="gmail_watcher",
                message_level="WARNING",
            )
            return

        try:
            while True:
                items = self.check_for_updates()
                
                if items:
                    logger.write_to_timeline(
                        f"Processing {len(items)} new message(s)",
                        actor="gmail_watcher",
                        message_level="INFO",
                    )
                    for item in items:
                        self.create_action_file(item)
                else:
                    logger.write_to_timeline(
                        "No new messages",
                        actor="gmail_watcher",
                        message_level="DEBUG",
                    )

                # Wait for next check
                import time
                time.sleep(self.check_interval)

        except KeyboardInterrupt:
            logger.write_to_timeline(
                "Gmail Watcher stopped by user",
                actor="gmail_watcher",
                message_level="INFO",
            )

    def __enter__(self):
        """Context manager entry."""
        # Start in background thread if needed
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        # Cleanup if needed
        pass


def main():
    """Standalone entry point for testing."""
    logger.write_to_timeline(
        "Gmail Watcher (standalone mode)",
        actor="gmail_watcher",
        message_level="INFO",
    )

    watcher = GmailWatcher()
    
    if watcher.service:
        logger.write_to_timeline(
            "Running in standalone mode (Ctrl+C to stop)",
            actor="gmail_watcher",
            message_level="INFO",
        )
        watcher.run()
    else:
        logger.log_error(
            "Gmail Watcher not authenticated. Check credentials.",
            actor="gmail_watcher",
        )


if __name__ == "__main__":
    main()
