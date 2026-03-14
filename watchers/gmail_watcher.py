"""
gmail_watcher.py - Watches Gmail for new important messages

Requires Gmail API credentials. See setup instructions in README.
"""
from pathlib import Path
from datetime import datetime
import logging
from .base_watcher import BaseWatcher

# Gmail API imports (install google-auth and google-api-python-client)
try:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    GMAIL_AVAILABLE = True
except ImportError:
    GMAIL_AVAILABLE = False
    logging.warning("Gmail API libraries not installed. Install with: pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client")


class GmailWatcher(BaseWatcher):
    """Watches Gmail for new important/unread messages."""
    
    SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
    
    def __init__(self, vault_path: str, credentials_path: str = None, token_path: str = None):
        """
        Initialize Gmail watcher.
        
        Args:
            vault_path: Path to Obsidian vault
            credentials_path: Path to Gmail API credentials JSON file
            token_path: Path to store/load OAuth token
        """
        super().__init__(vault_path, check_interval=120)  # Check every 2 minutes
        
        if not GMAIL_AVAILABLE:
            raise ImportError("Gmail API libraries not installed. See README for setup instructions.")
        
        self.credentials_path = Path(credentials_path) if credentials_path else None
        self.token_path = Path(token_path) if token_path else Path.home() / '.gmail_token.json'
        self.creds = None
        self.service = None
        self.processed_ids = set()
        
        # Load processed message IDs from file
        self.processed_file = self.vault_path / '.gmail_processed_ids.txt'
        if self.processed_file.exists():
            self.processed_ids = set(self.processed_file.read_text().splitlines())
        
        self._authenticate()
          
    def _authenticate(self):
        """Authenticate with Gmail API."""
        if not self.credentials_path or not self.credentials_path.exists():
            self.logger.warning("Gmail credentials not found. Please set up Gmail API access.")
            return
            
        # Load existing token
        if self.token_path.exists():
            self.creds = Credentials.from_authorized_user_file(str(self.token_path), self.SCOPES)
        
        # Refresh or get new token
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self.credentials_path), self.SCOPES)
                self.creds = flow.run_local_server(port=0)
            
            # Save token for next time
            self.token_path.write_text(self.creds.to_json())
        
        self.service = build('gmail', 'v1', credentials=self.creds)
        self.logger.info("Gmail API authenticated successfully")
    
    def check_for_updates(self) -> list:
        """Check for new unread important messages."""
        if not self.service:
            return []
            
        try:
            results = self.service.users().messages().list(
                userId='me',
                q='is:unread is:important'
            ).execute()
            
            messages = results.get('messages', [])
            new_messages = [m for m in messages if m['id'] not in self.processed_ids]
            
            return new_messages
            
        except HttpError as error:
            self.logger.error(f'Gmail API error: {error}')
            return []
        except Exception as e:
            self.logger.error(f'Error checking Gmail: {e}')
            return []
      
    def create_action_file(self, message) -> Path:
        """Create action file for a Gmail message."""
        try:
            msg = self.service.users().messages().get(
                userId='me',
                id=message['id']
            ).execute()
            
            # Extract headers
            headers = {h['name']: h['value'] for h in msg['payload'].get('headers', [])}
            
            # Get message body (simplified - handles text/plain)
            body = msg.get('snippet', '')
            
            content = f'''---
                type: email
                from: {headers.get('From', 'Unknown')}
                to: {headers.get('To', 'Unknown')}
                subject: {headers.get('Subject', 'No Subject')}
                date: {headers.get('Date', datetime.now().isoformat())}
                received: {datetime.now().isoformat()}
                message_id: {message['id']}
                priority: high
                status: pending
                ---

                # Email: {headers.get('Subject', 'No Subject')}

                ## From
                {headers.get('From', 'Unknown')}

                ## Date
                {headers.get('Date', 'Unknown')}

                ## Content
                {body}

                ## Suggested Actions
                - [ ] Reply to sender
                - [ ] Forward to relevant party
                - [ ] Archive after processing
                - [ ] Flag for follow-up
            '''
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filepath = self.needs_action / f'EMAIL_{timestamp}_{message["id"]}.md'
            filepath.write_text(content, encoding='utf-8')
            
            # Mark as processed
            self.processed_ids.add(message['id'])
            self.processed_file.write_text('\n'.join(self.processed_ids))
            
            return filepath
            
        except Exception as e:
            self.logger.error(f'Error creating action file for message {message["id"]}: {e}')
            raise
