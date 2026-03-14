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
        settings = Settings()

        # Access settings
        print(settings.vault_path)
        print(settings.database_url)

        # Check mode
        if settings.dev_mode:
            print("Development mode enabled")
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
    # Database Settings
    # ========================================================================

    database_url: str = Field(
        default="sqlite:///database/tasks.db",
        description="Database connection URL"
    )

    @field_validator("database_url", mode="after")
    @classmethod
    def validate_database_url(cls, v):
        """Validate database URL format."""
        if not v:
            raise ValueError("DATABASE_URL cannot be empty")

        # Check for supported databases
        supported = ["sqlite", "postgresql", "mysql"]
        if not any(v.startswith(db) for db in supported):
            raise ValueError(
                f"Unsupported database URL. Must start with: {', '.join(supported)}"
            )

        return v

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

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Logging level"
    )

    log_dir: Path = Field(
        default=Path("./logs"),
        description="Directory for log files"
    )

    @field_validator("log_dir", mode="before")
    @classmethod
    def validate_log_dir(cls, v):
        """Convert string to Path."""
        if isinstance(v, str):
            return Path(v)
        return v

    # ========================================================================
    # Helper Properties
    # ========================================================================

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return not self.dev_mode and not self.dry_run

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.dev_mode or self.dry_run

    @property
    def is_sqlite(self) -> bool:
        """Check if using SQLite database."""
        return self.database_url.startswith("sqlite")

    @property
    def is_postgresql(self) -> bool:
        """Check if using PostgreSQL database."""
        return self.database_url.startswith("postgresql")

    @property
    def is_mysql(self) -> bool:
        """Check if using MySQL database."""
        return self.database_url.startswith("mysql")

    # ========================================================================
    # Validation Methods
    # ========================================================================

    def validate_for_production(self) -> None:
        """
        Validate settings for production deployment.

        Raises:
            ValueError: If settings are not suitable for production
        """
        errors = []

        if self.dry_run:
            errors.append("DRY_RUN must be False in production")

        if self.dev_mode:
            errors.append("DEV_MODE must be False in production")

        if self.is_sqlite:
            errors.append("SQLite not recommended for production. Use PostgreSQL.")

        if errors:
            raise ValueError("Production validation failed:\n" + "\n".join(errors))

    # ========================================================================
    # Display Methods
    # ========================================================================

    def summary(self) -> str:
        """Get a summary of current settings (safe to log)."""
        return f"""
Settings Summary:
  Vault Path: {self.vault_path}
  Database: {'SQLite' if self.is_sqlite else 'PostgreSQL' if self.is_postgresql else 'MySQL'}
  Mode: {'Development' if self.is_development else 'Production'}
  Dry Run: {self.dry_run}
  Claude Model: {self.claude_model}
  Log Level: {self.log_level}
  Gmail: {'Configured' if self.gmail_address else 'Not configured'}
""".strip()


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
