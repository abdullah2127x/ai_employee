"""
config.py - Centralized configuration management using Pydantic Settings

Provides type-safe environment variable management with validation.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
from pathlib import Path
from typing import Optional, Literal


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables and .env file.

    Usage:
        from core.config import settings

        # Access settings
        print(settings.vault_path)
        print(settings.logs_dir)

        # Check mode
        if settings.dev_mode:
            print("Development mode - console output enabled")
    """

    # ========================================================================
    # Core Settings
    # ========================================================================

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"  # Ignore extra env vars not defined here
    )

    # ========================================================================
    # Application Settings
    # ========================================================================

    # Vault Configuration
    vault_path: Path = Field(
        default=Path("./vault"),
        description="Path to Obsidian vault"
    )

    @field_validator("vault_path", mode="before")
    @classmethod
    def validate_vault_path(cls, v):
        """Convert string to Path."""
        if isinstance(v, str):
            return Path(v)
        return v

    # Watcher Configuration
    check_interval: int = Field(
        default=60,
        ge=10,
        le=3600,
        description="Interval in seconds between watcher checks"
    )

    # ========================================================================
    # Security Settings
    # ========================================================================

    dry_run: bool = Field(
        default=True,
        description="If True, prevent real actions (safe mode)"
    )

    dev_mode: bool = Field(
        default=True,
        description="If True, enable development features"
    )

    # ========================================================================
    # Claude Code Settings
    # ========================================================================

    claude_model: Literal[
        "claude-3-5-sonnet",
        "claude-3-opus",
        "claude-3-sonnet",
        "claude-3-haiku"
    ] = Field(
        default="claude-3-5-sonnet",
        description="Claude model to use"
    )

    claude_timeout: int = Field(
        default=300,
        ge=30,
        le=600,
        description="Timeout in seconds for Claude Code operations"
    )

    # ========================================================================
    # Email Settings (Optional)
    # ========================================================================

    gmail_address: Optional[str] = Field(
        default=None,
        description="Gmail address for Gmail watcher"
    )

    gmail_app_password: Optional[str] = Field(
        default=None,
        description="Gmail app password"
    )

    @field_validator("gmail_address", mode="after")
    @classmethod
    def validate_gmail_address(cls, v):
        """Validate Gmail address if provided."""
        if v and "@" not in v:
            raise ValueError("Invalid Gmail address")
        return v

    # ========================================================================
    # Logging Settings
    # ========================================================================

    logs_per_task_enabled: bool = Field(
        default=True,
        description="Enable detailed per-task log files"
    )

    min_log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Minimum log level to log (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    )

    # ========================================================================
    # Vault Paths (Computed Properties)
    # ========================================================================

    @property
    def needs_action_path(self) -> Path:
        """Path to Needs_Action folder"""
        return self.vault_path / "Needs_Action"

    @property
    def processing_path(self) -> Path:
        """Path to Processing folder"""
        return self.vault_path / "Processing"

    @property
    def done_path(self) -> Path:
        """Path to Done folder"""
        return self.vault_path / "Done"

    @property
    def inbox_path(self) -> Path:
        """Path to Inbox folder"""
        return self.vault_path / "Inbox"

    @property
    def drop_folder_path(self) -> Path:
        """Path to Drop folder (for file watcher)"""
        return self.inbox_path / "Drop"

    @property
    def drop_history_path(self) -> Path:
        """Path to Drop_History folder"""
        return self.inbox_path / "Drop_History"

    @property
    def hash_registry_path(self) -> Path:
        """Path to hash registry file"""
        return self.inbox_path / ".hash_registry.json"

    @property
    def plans_path(self) -> Path:
        """Path to Plans folder"""
        return self.vault_path / "Plans"

    @property
    def pending_approval_path(self) -> Path:
        """Path to Pending_Approval folder"""
        return self.vault_path / "Pending_Approval"

    @property
    def approved_path(self) -> Path:
        """Path to Approved folder"""
        return self.vault_path / "Approved"

    @property
    def in_progress_path(self) -> Path:
        """Path to In_Progress folder"""
        return self.vault_path / "In_Progress"

    @property
    def logs_dir(self) -> Path:
        """Path to Logs directory (derived from vault_path)"""
        return self.vault_path / "Logs"

    def ensure_vault_directories(self) -> None:
        """Create all vault directories if they don't exist"""
        directories = [
            self.needs_action_path,
            self.processing_path,
            self.done_path,
            self.inbox_path,
            self.drop_folder_path,
            self.drop_history_path,
            self.plans_path,
            self.pending_approval_path,
            self.approved_path,
            self.in_progress_path,
            self.logs_dir,
        ]
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)


# ============================================================================
# Global Settings Instance
# ============================================================================

# Create a singleton instance for easy import
settings = Settings()


def get_settings() -> Settings:
    """
    Get application settings.

    Returns:
        Settings instance

    Usage:
        from core import get_settings
        settings = get_settings()
    """
    return settings


def reload_settings() -> Settings:
    """
    Reload settings from environment.

    Useful for testing when you need to reset settings.

    Returns:
        New Settings instance
    """
    global settings
    settings = Settings()
    return settings


# ============================================================================
# CLI Helper
# ============================================================================

if __name__ == "__main__":
    # Print settings summary when run directly
    print(settings.summary())

    # Validate for production if requested
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--validate-prod":
        try:
            settings.validate_for_production()
            print("✅ Settings are valid for production")
        except ValueError as e:
            print(f"❌ Production validation failed:\n{e}")
            sys.exit(1)
