# 🤖 Personal AI Employee - Autonomous FTE System

**A standalone, production-ready AI employee system that autonomously manages personal and business affairs.**

**Tagline:** *Your life and business on autopilot. Local-first, agent-driven, human-in-the-loop.*

---

## 🎯 Project Overview

This is a **complete, standalone** Personal AI Employee system built with:

- **Claude Code** - AI reasoning engine
- **Obsidian** - Knowledge base and dashboard (local-first)
- **Python Watchers** - Event detection (Gmail, files, WhatsApp)
- **SQLModel** - Type-safe database tracking (SQLite/PostgreSQL/MySQL)
- **Pydantic Settings** - Modern configuration management
- **MCP Servers** - External action execution (email, payments, social)

---

## 🏆 Status: Bronze Tier Complete ✅

All Bronze Tier requirements met:

- [x] Obsidian vault with Dashboard.md and Company_Handbook.md
- [x] Working Watcher scripts (Filesystem + Gmail)
- [x] Claude Code integration with skills
- [x] Event-driven architecture with orchestrator
- [x] SQLite database with full audit trail
- [x] Human-in-the-loop approval workflow
- [x] Comprehensive documentation

---

## 🚀 Quick Start

### Prerequisites

```bash
# Python 3.13+
python --version

# UV package manager
pip install uv

# Claude Code
npm install -g @anthropic/claude-code
```

### Installation

```bash
# Clone this repository
git clone <your-repo-url>
cd GeneralAgentWithCursor

# Install dependencies
uv sync

# Configure environment
cp .env.example .env
# Edit .env with your settings
```

### Run the System

```bash
# Start the orchestrator
uv run python orchestrator.py

# In another terminal, drop a test file
echo "Test content" > vault/Inbox/Drop/test.txt

# Watch the AI process it!
```

---

## 📁 Project Structure

```
GeneralAgentWithCursor/          # ← STANDALONE PROJECT ROOT
├── core/                        # Core infrastructure
│   ├── __init__.py
│   └── config.py                # Pydantic Settings
│
├── database/                    # Database layer
│   ├── __init__.py
│   ├── models.py                # SQLModel models
│   └── db_engine.py             # Database engine
│
├── watchers/                    # Event detection
│   ├── __init__.py
│   ├── base_watcher.py          # Base class
│   ├── filesystem_watcher.py    # File monitoring
│   └── gmail_watcher.py         # Gmail API
│
├── skills/                      # Claude AI skills
│   ├── file-processor.md
│   └── email-triage.md
│
├── vault/                       # Obsidian vault
│   ├── Dashboard.md             # Real-time status
│   ├── Company_Handbook.md      # Business rules
│   ├── Business_Goals.md        # Objectives
│   └── ...                      # Workflow folders
│
├── orchestrator.py              # Main coordinator
├── config.py                    # Settings (deprecated)
├── pyproject.toml               # Python project
├── .env                         # Environment variables
└── README.md                    # This file
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    EXTERNAL WORLD                           │
│  Gmail │ WhatsApp │ File Drops │ Bank APIs │ Social Media  │
└────────┬──────────┬───────────┬────────────┬───────────────┘
         │          │           │            │
         ▼          ▼           ▼            ▼
┌─────────────────────────────────────────────────────────────┐
│                 WATCHERS (Perception Layer)                 │
│  Gmail Watcher │ File Watcher │ WhatsApp Watcher           │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│              OBSIDIAN VAULT (Event Queue)                   │
│         /Needs_Action/  /Processing/  /Done/                │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                  ORCHESTRATOR (Event Router)                │
│         Classifies → Routes → Triggers Claude               │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│               CLAUDE CODE + SKILLS (Reasoning)              │
│    email-triage │ file-processor │ invoice-generator        │
└────────────────────────────┬────────────────────────────────┘
                             │
              ┌──────────────┴───────────────┐
              │                              │
              ▼                              ▼
┌─────────────────────────┐    ┌──────────────────────────────┐
│  HUMAN-IN-THE-LOOP      │    │   ACTION LAYER (Execution)   │
│  /Pending_Approval/     │    │   MCP Servers                │
│  Human reviews & approves│   │   - Email                    │
│                         │    │   - Payments                 │
│                         │    │   - Social Media             │
└─────────────────────────┘    └──────────────────────────────┘
```

---

## 🔧 Configuration

### Environment Variables (.env)

```bash
# Vault
VAULT_PATH=./vault

# Database
DATABASE_URL=sqlite:///database/tasks.db

# Security
DRY_RUN=true
DEV_MODE=true

# Claude Code
CLAUDE_MODEL=claude-3-5-sonnet
CLAUDE_TIMEOUT=300

# Gmail (optional)
GMAIL_ADDRESS=your_email@gmail.com
GMAIL_APP_PASSWORD=your_app_password

# Logging
LOG_LEVEL=INFO
```

### Pydantic Settings (core/config.py)

Type-safe configuration with validation:

```python
from core import settings

# Access settings
db_url = settings.database_url
vault = settings.vault_path
log_level = settings.log_level

# Helper methods
if settings.is_development:
    print("Dev mode")

settings.validate_for_production()  # Check if ready for prod
```

---

## 📊 Database

### SQLModel ORM

```python
from database import Database, TaskCreate

# Initialize
db = Database(settings.database_url)
db.create_tables()

# Create task
task = db.create_task(TaskCreate(
    id="file_001",
    type="file_drop",
    source_file="vault/Inbox/Drop/test.txt"
))

# Query
stats = db.get_dashboard_stats()
```

### Database URLs

```bash
# SQLite (Development)
DATABASE_URL=sqlite:///database/tasks.db

# PostgreSQL (Production)
DATABASE_URL=postgresql://user:pass@localhost:5432/ai_employee

# MySQL
DATABASE_URL=mysql://user:pass@localhost:3306/ai_employee
```

**Switch databases by changing one environment variable!**

---

## 🎯 Features

### ✅ Implemented

| Feature | Status | Description |
|---------|--------|-------------|
| Filesystem Watcher | ✅ Complete | Monitors drop folder |
| Gmail Watcher | ✅ Complete | Gmail API integration |
| Event Router | ✅ Complete | Classifies and routes events |
| Claude Skills | ✅ Complete | file-processor, email-triage |
| Approval Workflow | ✅ Complete | Human-in-the-loop |
| SQLite Database | ✅ Complete | Full audit trail |
| Pydantic Settings | ✅ Complete | Type-safe config |
| Logging | ✅ Complete | File + console |

### 🚧 Coming Soon

| Feature | Priority | Description |
|---------|----------|-------------|
| WhatsApp Watcher | Medium | WhatsApp Web automation |
| Email MCP | High | Send emails via MCP |
| Invoice Generator | High | Auto-generate invoices |
| Dashboard Updater | Medium | Auto-update Dashboard.md |
| Odoo Integration | Low | ERP integration |

---

## 🧪 Testing

```bash
# Test configuration
uv run python test_config.py

# Test file drop flow
uv run python test_flow.py

# Test SQLModel database
uv run python test_sqlmodel.py
```

---

## 📚 Documentation

| Document | Purpose |
|----------|---------|
| **README.md** | This file - project overview |
| **QUICKSTART.md** | 5-minute setup guide |
| **CONFIG_GUIDE.md** | Configuration management |
| **ENV_MANAGEMENT.md** | Environment variables |
| **DATABASE_SUMMARY.md** | Database setup guide |
| **SQLMODEL_GUIDE.md** | SQLModel usage |
| **MIGRATION_GUIDE.md** | Configuration migration |

---

## 🔒 Security

### Best Practices

- ✅ **Environment variables** - Never commit secrets
- ✅ **.gitignore** - Comprehensive ignore rules
- ✅ **Dry run mode** - Safe testing
- ✅ **Approval workflow** - Human oversight
- ✅ **Audit logging** - All actions tracked

### Ignored Files

```bash
# Never committed to git:
.env                    # API keys, passwords
*.db                    # Database files
logs/                   # Log files
credentials.json        # OAuth credentials
token.json              # Auth tokens
```

---

## 🚀 Deployment

### Local Development

```bash
# SQLite database
DATABASE_URL=sqlite:///database/tasks.db
DRY_RUN=true
DEV_MODE=true
```

### Production (Cloud)

```bash
# PostgreSQL database
DATABASE_URL=postgresql://user:pass@db.host.com:5432/db
DRY_RUN=false
DEV_MODE=false

# Deploy to Railway, Render, Oracle Cloud, etc.
```

---

## 🎓 Learning Resources

- **Claude Code:** https://platform.claude.com/docs
- **SQLModel:** https://sqlmodel.tiangolo.com/
- **Pydantic:** https://docs.pydantic.dev/
- **Obsidian:** https://obsidian.md
- **Model Context Protocol:** https://modelcontextprotocol.io

---

## 📝 License

This project is part of the Personal AI Employee Hackathon 2026.

---

## 🎉 Acknowledgments

- **Panaversity** for organizing the hackathon
- **Anthropic** for Claude Code
- **Obsidian** for the knowledge base
- **SQLModel** for the ORM

---

## 📞 Support

- **Documentation:** See docs folder
- **Issues:** Open GitHub issue
- **Community:** Wednesday Research Meeting

---

**Built with ❤️ for the Personal AI Employee Hackathon 2026**

**Version:** 0.1.0 | **Status:** Bronze Complete ✅ | **Standalone Project**
