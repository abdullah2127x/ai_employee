# 🚀 Quick Start: Enable Gmail Watcher

## ⚡ 3-Step Setup

### 1️⃣ Get Credentials (5 minutes)

1. Go to: https://console.cloud.google.com/
2. **Create Project** → Name: "AI Employee"
3. **Enable Gmail API** → APIs & Services → Library → Search "Gmail" → Enable
4. **Create Credentials** → APIs & Services → Credentials → Create OAuth Client ID
   - Application type: **Desktop app**
   - Name: "AI Employee Gmail"
5. **Download JSON** → Save as `credentials.json`

---

### 2️⃣ Place Credentials File (30 seconds)

**Copy file to:**
```
vault/credentials.json
```

**Full path:**
```
D:\AbdullahQureshi\workspace\Hackathon-2025\GeneralAgentWithCursor\vault\credentials.json
```

---

### 3️⃣ Enable in .env (1 minute)

**Edit `.env` file** (already done!):

```env
# Change this from false to true:
ENABLE_GMAIL_WATCHER=true

# Optional: Customize settings
GMAIL_WATCHER_CHECK_INTERVAL=120
GMAIL_WATCHER_QUERY=is:unread is:important
```

---

### 4️⃣ First Run - Authorize (1 minute)

**Run orchestrator:**
```bash
python orchestrator.py
```

**What happens:**
1. Browser opens automatically
2. Sign in with Gmail
3. Grant permissions
4. Browser shows "Success!"
5. Token saved to `~/.gmail_token.json`
6. Gmail watcher starts running!

---

## ✅ Verify It's Working

**Check timeline logs:**
```
vault/Logs/timeline/YYYY-MM-DD.md
```

**Look for:**
```
[orchestrator] → Gmail Watcher enabled | Query: is:unread is:important | Interval: 120s
[orchestrator] → Gmail Watcher started (background thread)
[gmail_watcher] → Found 3 messages, 2 new
[gmail_watcher] → Created task file: EMAIL_20260323_*.md
```

---

## 📋 Current Configuration

| Setting | Value | Location |
|---------|-------|----------|
| **Enabled** | `false` (change to `true`) | `.env` line 9 |
| **Check Interval** | `120 seconds` | `.env` line 12 |
| **Gmail Query** | `is:unread is:important` | `.env` line 13 |
| **Credentials Path** | `vault/credentials.json` | Default |

---

## 🔧 Quick Commands

```bash
# Run full system (with Gmail watcher if enabled)
python orchestrator.py

# Test Gmail watcher only (no processing)
python watchers/main.py

# Check if Gmail libraries installed
pip list | findstr google
```

---

## ⚠️ Troubleshooting

### "Gmail credentials not found"
→ Check `vault/credentials.json` exists

### "Gmail API libraries not installed"
```bash
pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client
```

### Browser doesn't open
→ Check console for URL, copy/paste into browser manually

### No emails being processed
→ Check Gmail query isn't too restrictive
→ Try: `GMAIL_WATCHER_QUERY=is:unread`

---

## 📖 Full Documentation

- **Setup Guide:** `GMAIL_WATCHER_SETUP.md`
- **Architecture:** `WATCHER_ARCHITECTURE_GUIDE.md`
- **Skill File:** `vault/.claude/skills/process-email/SKILL.md`

---

**Last Updated:** 2026-03-23  
**Version:** 2.0
