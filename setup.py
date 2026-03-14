"""
Setup script for initial project setup.
Run this to verify your environment and create necessary directories.
"""
import sys
import subprocess
from pathlib import Path


def check_python_version():
    """Check if Python version is 3.13+."""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 13):
        print(f"❌ Python 3.13+ required. Current version: {version.major}.{version.minor}")
        return False
    print(f"✅ Python {version.major}.{version.minor}.{version.micro}")
    return True


def check_uv():
    """Check if UV is installed."""
    try:
        result = subprocess.run(['uv', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ UV installed: {result.stdout.strip()}")
            return True
    except FileNotFoundError:
        pass
    print("❌ UV not found. Install with: pip install uv")
    return False


def check_claude_code():
    """Check if Claude Code is available."""
    try:
        result = subprocess.run(['claude', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ Claude Code: {result.stdout.strip()}")
            return True
    except FileNotFoundError:
        pass
    print("⚠️  Claude Code not found in PATH. Make sure it's installed.")
    return False


def setup_directories():
    """Create necessary directories."""
    dirs = [
        'vault/Inbox/Drop',
        'vault/Needs_Action',
        'vault/Done',
        'vault/Plans',
        'vault/Logs',
        'vault/Pending_Approval',
        'vault/Approved',
        'vault/Rejected',
        'vault/Accounting',
    ]
    
    for dir_path in dirs:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
        print(f"✅ Created: {dir_path}")


def main():
    """Run setup checks."""
    print("🔧 Setting up Personal AI Employee...\n")
    
    all_ok = True
    all_ok &= check_python_version()
    all_ok &= check_uv()
    check_claude_code()  # Warning only
    
    print("\n📁 Creating directory structure...")
    setup_directories()
    
    print("\n📦 Installing dependencies...")
    try:
        subprocess.run(['uv', 'sync'], check=True)
        print("✅ Dependencies installed")
    except subprocess.CalledProcessError:
        print("❌ Failed to install dependencies")
        all_ok = False
    
    if all_ok:
        print("\n✅ Setup complete! Next steps:")
        print("1. Copy config.example.json to config.json")
        print("2. Edit config.json with your settings")
        print("3. Run: python orchestrator.py --vault ./vault")
    else:
        print("\n⚠️  Setup incomplete. Please fix the issues above.")


if __name__ == '__main__':
    main()
