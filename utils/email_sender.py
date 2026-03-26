"""
email_sender.py — Outbound email sender for AI Employee (v1.0)

Reads an approved RESULT_ file from Approved/, extracts the draft_reply
and thread metadata, and sends the reply via SMTP using Inaya's Gmail
App Password.

Always sends as a reply in the existing thread (In-Reply-To + References
headers), so the sent message appears in Gmail's conversation view.

Usage (called by orchestrator when a file lands in Approved/):
    python email_sender.py Approved/RESULT_email_20260325_014623_Re__test.md

OAuth2 migration note:
    The entire auth surface is isolated in _build_smtp_connection().
    When migrating to OAuth2 + Gmail REST API, replace only that function
    and _send_via_smtp() with a _send_via_gmail_api() equivalent.
    Everything else (parsing, logging, file movement) stays identical.
"""

import json
import re
import shutil
import smtplib
import ssl
import sys
from dataclasses import dataclass
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from enum import Enum
from pathlib import Path
from typing import Final

# ---------------------------------------------------------------------------
# Project imports
# ---------------------------------------------------------------------------

project_root = Path(__file__).parent.resolve()
sys.path.insert(0, str(project_root))

from core.config import settings
from utils.logging_manager import LoggingManager

logger = LoggingManager()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SMTP_HOST: Final[str] = "smtp.gmail.com"
SMTP_PORT: Final[int] = 465  # SSL — use 587 + STARTTLS if preferred

# Frontmatter fields we need from the RESULT_ file
FIELD_TASK_ID:       Final[str] = "task_id"
FIELD_TYPE:          Final[str] = "type"
FIELD_AI_DECISION:   Final[str] = "ai_decision"
FIELD_AI_CATEGORY:   Final[str] = "ai_category"

# Sections we parse from the markdown body
SECTION_DRAFT_REPLY: Final[str] = "## Draft Reply"

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


class SendOutcome(str, Enum):
    """Result of a send attempt. Used in status files and logs."""
    SENT          = "sent"
    SKIPPED       = "skipped"       # no draft_reply in result file
    PARSE_ERROR   = "parse_error"   # could not extract required data
    SMTP_ERROR    = "smtp_error"    # SMTP connection or send failed
    AUTH_ERROR    = "auth_error"    # credentials missing or rejected
    RUNNER_ERROR  = "runner_error"  # unexpected exception


@dataclass(frozen=True)
class EmailTask:
    """
    All data needed to send one outbound reply, parsed from a RESULT_ file.

    Attributes:
        task_id:          Unique task identifier (from YAML frontmatter)
        result_file:      Path to the RESULT_ markdown file
        to_address:       Recipient email address (the original sender)
        subject:          Email subject — prefixed with "Re: " if needed
        draft_reply:      Plain-text body to send
        gmail_message_id: Gmail message-id of the email being replied to,
                          used to set In-Reply-To and References headers
                          so Gmail threads the reply correctly.
                          May be None for new (non-reply) emails.
        original_subject: Raw subject from the source task file,
                          used to build the Re: subject line
    """
    task_id:          str
    result_file:      Path
    to_address:       str
    subject:          str
    draft_reply:      str
    gmail_message_id: str | None
    original_subject: str


@dataclass(frozen=True)
class SmtpCredentials:
    """
    SMTP authentication credentials.

    ── OAuth2 migration note ─────────────────────────────────────────────────
    Replace this dataclass with an OAuth2TokenCredentials dataclass that holds
    access_token, refresh_token, token_expiry, client_id, client_secret.
    Update _build_smtp_connection() to call the token refresh endpoint first,
    then authenticate with smtplib using the bearer token via XOAUTH2.
    ─────────────────────────────────────────────────────────────────────────
    """
    sender_email: str   # e.g. inayaqureshi3509@gmail.com
    app_password: str   # 16-char Gmail App Password (no spaces)


@dataclass
class SendResult:
    """
    Outcome of a single send attempt.

    Attributes:
        outcome:       SendOutcome enum value
        task_id:       Task this result belongs to
        timestamp:     When the attempt was made
        detail:        Human-readable description of what happened
        smtp_response: Raw SMTP server response string, if available
    """
    outcome:       SendOutcome
    task_id:       str
    timestamp:     datetime
    detail:        str
    smtp_response: str | None = None


# ---------------------------------------------------------------------------
# Credentials loader
# ── OAuth2 migration: replace this function with one that loads/refreshes
#    an OAuth2 token and returns OAuth2TokenCredentials instead.
# ---------------------------------------------------------------------------


def load_credentials() -> SmtpCredentials:
    """
    Load SMTP credentials from project settings.

    Expected settings attributes:
        settings.email_address   — sender Gmail address
        settings.email_password  — Gmail App Password

    Raises:
        ValueError: if credentials are missing or clearly invalid
    """
    email: str = getattr(settings, "email_address", "").strip()
    password: str = getattr(settings, "email_password", "").strip()

    if not email:
        raise ValueError(
            "settings.email_address is empty. "
            "Set EMAIL_ADDRESS in your .env file."
        )
    if not password:
        raise ValueError(
            "settings.email_password is empty. "
            "Set EMAIL_PASSWORD in your .env file."
        )
    if len(password.replace(" ", "")) != 16:
        raise ValueError(
            f"Gmail App Password must be 16 characters (got {len(password.replace(' ', ''))}). "
            "Generate one at myaccount.google.com → Security → App passwords."
        )

    return SmtpCredentials(
        sender_email=email,
        app_password=password.replace(" ", ""),  # strip spaces if copy-pasted
    )


# ---------------------------------------------------------------------------
# RESULT_ file parser
# ---------------------------------------------------------------------------


def _parse_yaml_frontmatter(content: str) -> dict[str, str]:
    """
    Extract key: value pairs from YAML frontmatter delimited by ---.

    Only handles simple string values (no nested YAML).
    Quoted values have their quotes stripped.

    Args:
        content: Full file content as a string

    Returns:
        Dict of frontmatter keys to string values (may be empty)
    """
    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return {}

    result: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, _, raw_value = line.partition(":")
        value = raw_value.strip().strip('"').strip("'")
        result[key.strip()] = value

    return result


def _extract_draft_reply(content: str) -> str | None:
    """
    Extract the draft reply body from the ## Draft Reply section.

    The section format (from build_output_file) is:
        ## Draft Reply

        > This reply is ready to send. **Auto-sent.**

        ```
        <reply body here>
        ```

    Args:
        content: Full RESULT_ file content

    Returns:
        Extracted reply body string, or None if the section is absent
        or the code fence is empty
    """
    # Find the section
    section_start = content.find(SECTION_DRAFT_REPLY)
    if section_start == -1:
        return None

    section = content[section_start:]

    # Extract text between the first ``` fence pair
    fence_match = re.search(r"```\s*\n(.*?)\n```", section, re.DOTALL)
    if not fence_match:
        return None

    body = fence_match.group(1).strip()
    return body if body else None


def _parse_original_task_frontmatter(task_id: str) -> dict[str, str]:
    """
    Read the original task file from Processing_Archive/ to get
    the sender address, subject, and Gmail message ID.

    Args:
        task_id: Task identifier matching the archived file stem

    Returns:
        Frontmatter dict from the original task file,
        or empty dict if the file cannot be found/read
    """
    archive_folder = settings.vault_path / "Processing_Archive"
    task_file = archive_folder / f"{task_id}.md"

    if not task_file.exists():
        logger.log_warning(
            f"Original task file not found: {task_file}",
            actor="email_sender",
        )
        return {}

    try:
        content = task_file.read_text(encoding="utf-8-sig")
        return _parse_yaml_frontmatter(content)
    except Exception as exc:
        logger.log_warning(
            f"Could not read original task file {task_file}: {exc}",
            actor="email_sender",
        )
        return {}


def parse_result_file(result_file: Path) -> EmailTask | None:
    """
    Parse a RESULT_ markdown file into an EmailTask.

    Returns None (with a logged warning) if any required field is missing.

    Args:
        result_file: Path to the RESULT_ file in Approved/

    Returns:
        EmailTask if all required data is present, None otherwise
    """
    try:
        content = result_file.read_text(encoding="utf-8-sig")
    except Exception as exc:
        logger.log_error(
            f"Cannot read result file {result_file}: {exc}",
            error=exc,
            actor="email_sender",
        )
        return None

    meta = _parse_yaml_frontmatter(content)
    task_id: str = meta.get(FIELD_TASK_ID, result_file.stem)
    task_type: str = meta.get(FIELD_TYPE, "")

    # Only email tasks have outbound replies
    if not task_type.startswith("email"):
        logger.write_to_timeline(
            f"Skipping non-email task: {task_id} (type={task_type})",
            actor="email_sender",
        )
        return None

    # Extract draft reply from the markdown body
    draft_reply = _extract_draft_reply(content)
    if not draft_reply:
        logger.write_to_timeline(
            f"No draft_reply in result file — skipping: {task_id}",
            actor="email_sender",
        )
        return None

    # Pull sender + thread info from the original task file
    original_meta = _parse_original_task_frontmatter(task_id)

    # The "from" in the original task is the person we reply TO
    raw_from: str = original_meta.get("from", "")
    to_address = _extract_email_address(raw_from)

    if not to_address:
        logger.log_error(
            f"Cannot determine reply-to address for {task_id}. "
            f"Original 'from' field: '{raw_from}'",
            actor="email_sender",
        )
        return None

    original_subject: str = original_meta.get("subject", "").strip().strip('"')
    gmail_message_id: str | None = original_meta.get("gmail_message_id") or None

    # Build subject: ensure "Re: " prefix, avoid "Re: Re: Re:"
    subject = _build_reply_subject(original_subject)

    return EmailTask(
        task_id=task_id,
        result_file=result_file,
        to_address=to_address,
        subject=subject,
        draft_reply=draft_reply,
        gmail_message_id=str(gmail_message_id) if gmail_message_id else None,
        original_subject=original_subject,
    )


def _extract_email_address(raw: str) -> str | None:
    """
    Extract a bare email address from a string like:
        'Abdullah Qureshi <abdullah2127x@gmail.com>'
        'abdullah2127x@gmail.com'

    Args:
        raw: Raw "From" header value

    Returns:
        Bare email address, or None if not found
    """
    # Try angle-bracket format first
    bracket_match = re.search(r"<([^>]+)>", raw)
    if bracket_match:
        return bracket_match.group(1).strip()

    # Fall back to bare email pattern
    bare_match = re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", raw)
    if bare_match:
        return bare_match.group(0).strip()

    return None


def _build_reply_subject(original_subject: str) -> str:
    """
    Build a reply subject line that has exactly one "Re: " prefix.

    Args:
        original_subject: Subject from the original email

    Returns:
        Subject string prefixed with "Re: " (deduplicated)
    """
    # Strip all existing Re:/RE:/re: prefixes
    cleaned = re.sub(r"^(Re|RE|re):\s*", "", original_subject).strip()
    return f"Re: {cleaned}" if cleaned else "Re: (no subject)"


# ---------------------------------------------------------------------------
# SMTP connection builder
# ── OAuth2 migration: replace this function.
#    New signature: _build_gmail_api_service(creds: OAuth2TokenCredentials)
#    Returns a googleapiclient Resource instead of smtplib.SMTP_SSL.
# ---------------------------------------------------------------------------


def _build_smtp_connection(credentials: SmtpCredentials) -> smtplib.SMTP_SSL:
    """
    Open and authenticate an SMTP_SSL connection to Gmail.

    Uses SSL on port 465. If you prefer STARTTLS on port 587, swap
    smtplib.SMTP_SSL for smtplib.SMTP and call .starttls() after connect.

    Args:
        credentials: SmtpCredentials with sender_email and app_password

    Returns:
        Authenticated smtplib.SMTP_SSL instance (caller must close it)

    Raises:
        smtplib.SMTPAuthenticationError: if credentials are rejected
        smtplib.SMTPConnectError: if Gmail cannot be reached
        ssl.SSLError: if the TLS handshake fails
    """
    ssl_context = ssl.create_default_context()
    server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=ssl_context)
    server.login(credentials.sender_email, credentials.app_password)
    return server


# ---------------------------------------------------------------------------
# Message builder
# ---------------------------------------------------------------------------


def _build_mime_message(
    task: EmailTask,
    credentials: SmtpCredentials,
) -> MIMEMultipart:
    """
    Build a MIME email message for the given task.

    Sets In-Reply-To and References headers when gmail_message_id is
    present, so Gmail correctly threads the reply with the original.

    The Gmail message ID from the task file is a numeric string (e.g.
    "1860577732689980861"). Gmail's SMTP threading needs the RFC 2822
    Message-ID format: <numeric_id@mail.gmail.com>.

    Args:
        task:        EmailTask with all send parameters
        credentials: SmtpCredentials providing the From address

    Returns:
        Fully constructed MIMEMultipart message ready to send
    """
    msg = MIMEMultipart("alternative")
    msg["From"]    = credentials.sender_email
    msg["To"]      = task.to_address
    msg["Subject"] = task.subject

    # Thread reply headers — Gmail uses these to stitch the reply into
    # the existing conversation. Without them, the reply appears as a
    # new thread even if the subject matches.
    if task.gmail_message_id:
        rfc_message_id = f"<{task.gmail_message_id}@mail.gmail.com>"
        msg["In-Reply-To"] = rfc_message_id
        msg["References"]  = rfc_message_id

    # Plain text part (primary — we keep it simple, no HTML)
    msg.attach(MIMEText(task.draft_reply, "plain", "utf-8"))

    return msg


# ---------------------------------------------------------------------------
# SMTP sender
# ── OAuth2 migration: replace _send_via_smtp() with _send_via_gmail_api().
#    The function signature and return type stay the same.
# ---------------------------------------------------------------------------


def _send_via_smtp(
    task: EmailTask,
    credentials: SmtpCredentials,
) -> SendResult:
    """
    Send the draft reply via SMTP and return a SendResult.

    Opens a fresh SSL connection per send — simple and safe for low
    volume. For high-volume use, pass a persistent connection instead.

    Args:
        task:        EmailTask with all send parameters
        credentials: SmtpCredentials for authentication

    Returns:
        SendResult with outcome SENT, SMTP_ERROR, or AUTH_ERROR
    """
    msg = _build_mime_message(task, credentials)

    try:
        with _build_smtp_connection(credentials) as server:
            refused = server.sendmail(
                from_addr=credentials.sender_email,
                to_addrs=[task.to_address],
                msg=msg.as_string(),
            )

        # sendmail() returns a dict of refused recipients — empty = all sent
        if refused:
            refused_str = str(refused)
            logger.log_warning(
                f"Some recipients refused: {refused_str}",
                actor="email_sender",
            )
            return SendResult(
                outcome=SendOutcome.SMTP_ERROR,
                task_id=task.task_id,
                timestamp=datetime.now(),
                detail=f"Recipients refused: {refused_str}",
                smtp_response=refused_str,
            )

        return SendResult(
            outcome=SendOutcome.SENT,
            task_id=task.task_id,
            timestamp=datetime.now(),
            detail=f"Sent to {task.to_address} | subject: {task.subject}",
            smtp_response="250 OK",
        )

    except smtplib.SMTPAuthenticationError as exc:
        return SendResult(
            outcome=SendOutcome.AUTH_ERROR,
            task_id=task.task_id,
            timestamp=datetime.now(),
            detail=(
                "SMTP authentication failed. Check EMAIL_PASSWORD in .env. "
                f"Server said: {exc.smtp_error!r}"
            ),
            smtp_response=str(exc.smtp_error),
        )

    except smtplib.SMTPRecipientsRefused as exc:
        return SendResult(
            outcome=SendOutcome.SMTP_ERROR,
            task_id=task.task_id,
            timestamp=datetime.now(),
            detail=f"All recipients refused: {exc.recipients}",
            smtp_response=str(exc.recipients),
        )

    except smtplib.SMTPException as exc:
        return SendResult(
            outcome=SendOutcome.SMTP_ERROR,
            task_id=task.task_id,
            timestamp=datetime.now(),
            detail=f"SMTP error: {exc}",
            smtp_response=str(exc),
        )

    except ssl.SSLError as exc:
        return SendResult(
            outcome=SendOutcome.SMTP_ERROR,
            task_id=task.task_id,
            timestamp=datetime.now(),
            detail=f"SSL/TLS error connecting to Gmail: {exc}",
            smtp_response=str(exc),
        )

    except OSError as exc:
        return SendResult(
            outcome=SendOutcome.SMTP_ERROR,
            task_id=task.task_id,
            timestamp=datetime.now(),
            detail=f"Network error: {exc}",
            smtp_response=str(exc),
        )


# ---------------------------------------------------------------------------
# Status file writer
# ---------------------------------------------------------------------------


def write_send_status(result: SendResult) -> None:
    """
    Write a send status JSON file to Runner_Status/ so the orchestrator
    knows the exact outcome without polling or guessing.

    File format mirrors the existing write_status() in claude_runner.py
    but adds smtp_response for debugging auth/network failures.

    Args:
        result: SendResult from _send_via_smtp()
    """
    status_folder = settings.vault_path / "Runner_Status"
    status_folder.mkdir(parents=True, exist_ok=True)

    payload: dict[str, str | None] = {
        "task_id":       result.task_id,
        "outcome":       f"email_{result.outcome.value}",
        "timestamp":     result.timestamp.isoformat(),
        "detail":        result.detail,
        "smtp_response": result.smtp_response,
    }

    status_path = status_folder / f"{result.task_id}_send.json"
    try:
        status_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except Exception as exc:
        logger.log_error(
            f"Failed to write send status file: {exc}",
            error=exc,
            actor="email_sender",
        )


# ---------------------------------------------------------------------------
# File movement helpers
# ---------------------------------------------------------------------------


def _move_result_file(
    result_file: Path,
    destination_folder: Path,
    reason: str,
) -> Path | None:
    """
    Move the RESULT_ file to a destination folder.

    Args:
        result_file:         Source file path
        destination_folder:  Target directory (created if absent)
        reason:              Short log message explaining the move

    Returns:
        New file path, or None if the move failed
    """
    if not result_file.exists():
        logger.log_warning(
            f"Cannot move — file missing: {result_file}",
            actor="email_sender",
        )
        return None

    destination_folder.mkdir(parents=True, exist_ok=True)
    destination = destination_folder / result_file.name

    try:
        shutil.move(str(result_file), str(destination))
        logger.write_to_timeline(
            f"Moved {result_file.name} → {destination_folder.name}/ ({reason})",
            actor="email_sender",
        )
        return destination
    except Exception as exc:
        logger.log_error(
            f"Failed to move {result_file.name}: {exc}",
            error=exc,
            actor="email_sender",
        )
        return None


# ---------------------------------------------------------------------------
# Main send orchestrator
# ---------------------------------------------------------------------------


def send_approved_reply(result_file: Path) -> bool:
    """
    Full pipeline for one approved RESULT_ file:
        1. Parse the file into an EmailTask
        2. Load SMTP credentials
        3. Send via SMTP
        4. Write send status
        5. Move file to Sent_Emails/ (success) or Send_Failed/ (failure)

    Args:
        result_file: Path to the RESULT_ file in Approved/

    Returns:
        True if the email was sent successfully, False otherwise
    """
    logger.write_to_timeline(
        f"Processing approved result: {result_file.name}",
        actor="email_sender",
    )

    # ── Step 1: Parse ────────────────────────────────────────────────────────
    task = parse_result_file(result_file)

    if task is None:
        # parse_result_file already logged the reason
        write_send_status(SendResult(
            outcome=SendOutcome.PARSE_ERROR,
            task_id=result_file.stem,
            timestamp=datetime.now(),
            detail="Could not parse result file into EmailTask",
        ))
        _move_result_file(
            result_file,
            settings.vault_path / "Send_Failed",
            "parse error",
        )
        return False

    logger.write_to_timeline(
        f"Sending to: {task.to_address} | subject: {task.subject} "
        f"| thread: {'yes' if task.gmail_message_id else 'no'}",
        actor="email_sender",
    )

    # ── Step 2: Load credentials ─────────────────────────────────────────────
    try:
        credentials = load_credentials()
    except ValueError as exc:
        logger.log_error(str(exc), actor="email_sender")
        write_send_status(SendResult(
            outcome=SendOutcome.AUTH_ERROR,
            task_id=task.task_id,
            timestamp=datetime.now(),
            detail=str(exc),
        ))
        _move_result_file(
            result_file,
            settings.vault_path / "Send_Failed",
            "credentials error",
        )
        return False

    # ── Step 3: Send ─────────────────────────────────────────────────────────
    result = _send_via_smtp(task, credentials)

    # ── Step 4: Write status ──────────────────────────────────────────────────
    write_send_status(result)

    # ── Step 5: Move file ─────────────────────────────────────────────────────
    if result.outcome == SendOutcome.SENT:
        logger.write_to_timeline(
            f"Email sent successfully → {task.to_address}",
            actor="email_sender",
        )
        _move_result_file(
            result_file,
            settings.vault_path / "Sent_Emails",
            "email sent",
        )
        return True
    else:
        logger.log_error(
            f"Send failed ({result.outcome.value}): {result.detail}",
            actor="email_sender",
        )
        _move_result_file(
            result_file,
            settings.vault_path / "Send_Failed",
            f"send failed: {result.outcome.value}",
        )
        return False


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """
    CLI entry point — called by the orchestrator when a file lands in Approved/.

    Usage:
        python email_sender.py Approved/RESULT_email_20260325_014623_Re__test.md
    """
    if len(sys.argv) < 2:
        print("Usage: python email_sender.py <result_file>")
        print("Example: python email_sender.py Approved/RESULT_email_20260325_014623_Re__test.md")
        sys.exit(1)

    result_file = Path(sys.argv[1])

    if not result_file.exists():
        logger.log_error(
            f"Result file not found: {result_file}",
            actor="email_sender",
        )
        sys.exit(1)

    success = send_approved_reply(result_file)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()