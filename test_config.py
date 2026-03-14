#!/usr/bin/env python3
"""
test_config.py - Test the Pydantic Settings configuration system

Run this to verify your .env configuration is working correctly.
"""
from core import settings


def main():
    """Test configuration loading."""
    print("=" * 70)
    print("⚙️  AI Employee Configuration Test")
    print("=" * 70)
    
    # Print settings summary
    print("\n" + settings.summary())
    
    # Test individual settings
    print("\n" + "=" * 70)
    print("📋 Detailed Settings")
    print("=" * 70)
    
    print(f"\n✅ Vault Path: {settings.vault_path}")
    print(f"   Exists: {settings.vault_path.exists()}")
    
    print(f"\n✅ Database URL: {settings.database_url}")
    print(f"   Type: {'SQLite' if settings.is_sqlite else 'PostgreSQL' if settings.is_postgresql else 'MySQL'}")
    print(f"   Mode: {'Development' if settings.is_development else 'Production'}")
    
    print(f"\n✅ Security:")
    print(f"   Dry Run: {settings.dry_run}")
    print(f"   Dev Mode: {settings.dev_mode}")
    
    print(f"\n✅ Claude Code:")
    print(f"   Model: {settings.claude_model}")
    print(f"   Timeout: {settings.claude_timeout}s")
    
    print(f"\n✅ Logging:")
    print(f"   Level: {settings.log_level}")
    print(f"   Directory: {settings.log_dir}")
    
    print(f"\n✅ Email:")
    if settings.gmail_address:
        print(f"   Address: {settings.gmail_address}")
        print(f"   Password: {'Configured' if settings.gmail_app_password else 'Not configured'}")
    else:
        print(f"   Not configured")
    
    # Validate for production
    print("\n" + "=" * 70)
    print("🔒 Production Validation")
    print("=" * 70)
    
    try:
        settings.validate_for_production()
        print("\n✅ Settings are valid for production!")
    except ValueError as e:
        print(f"\n⚠️  Not production-ready:")
        print(f"{e}")
        print("\n💡 To fix for production:")
        print("   1. Set DRY_RUN=false")
        print("   2. Set DEV_MODE=false")
        print("   3. Use PostgreSQL instead of SQLite")
        print("   4. Set DATABASE_URL in environment")
    
    # Test database connection (if SQLite)
    if settings.is_sqlite:
        print("\n" + "=" * 70)
        print("🗄️  Database Test (SQLite)")
        print("=" * 70)
        
        from database import Database
        
        try:
            db = Database(settings.database_url)
            db.create_tables()
            print("\n✅ Database connection successful!")
            print(f"   Location: {settings.database_url}")
        except Exception as e:
            print(f"\n❌ Database error: {e}")
    
    print("\n" + "=" * 70)
    print("✅ Configuration test complete!")
    print("=" * 70)
    
    # Next steps
    print("\n📝 Next Steps:")
    print("   1. Review settings above")
    print("   2. Edit .env file if changes needed")
    print("   3. Run: uv run python orchestrator.py")
    print()


if __name__ == "__main__":
    main()
