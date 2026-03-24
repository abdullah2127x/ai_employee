# 🚀 Gmail Watcher - IMAP Mode (Development)

**Quick setup for development using Gmail app password - NO OAuth2 complexity!**

---

## ⚡ 2-Minute Setup

### Step 1: Get Gmail App Password (2 minutes)

1. **Go to Google Account Security:**
   ```
   https://myaccount.google.com/security
   ```

2. **Enable 2-Factor Authentication** (if not already enabled):
   - Click "2-Step Verification"
   - Follow the setup process
   - Must be enabled to create app passwords

3. **Generate App Password:**
   - Go to: **App passwords** (under "2-Step Verification")
   - Or direct link: https://myaccount.google.com/apppasswords
   
4. **Create new app password:**
   - Select app: **Mail**
   - Select device: **Other (Custom name)**
   - Enter name: `AI Employee Dev`
   - Click **Generate**

5. **Copy the password:**
   - You'll get a 16-character password like: `abcd efgh ijkl mnop`
   - **Save this!** You'll need it in the next step
   - Remove spaces: `abcdefghijklmnop`

---

### Step 2: Configure .env (30 seconds)

**Edit `.env` file:**

```env
# Enable Gmail watcher
ENABLE_GMAIL_WATCHER=true

# Set mode to IMAP (development)
GMAIL_WATCHER_MODE=imap

# Your Gmail address
GMAIL_IMAP_ADDRESS=your.email@gmail.com

# Your app password (16 characters, no spaces)
GMAIL_IMAP_APP_PASSWORD=abcdefghijklmnop
```

**That's it!** No credentials.json, no OAuth flow, no browser authorization.

---

### Step 3: Run and Test

**Start orchestrator:**
```bash
python orchestrator.py
```

**Check logs:**
```
vault/Logs/timeline/YYYY-MM-DD.md
```

**Look for:**
```
[orchestrator] → Gmail Watcher enabled (IMAP mode) | Email: your.email@gmail.com
[gmail_watcher_imap] → Gmail IMAP connected | Server: imap.gmail.com:993
[gmail_watcher_imap] → Found 5 messages, 3 new
[gmail_watcher_imap] → Created task file: EMAIL_*.md
```

---

## 📋 Configuration Options

### Change Check Frequency

```env
# Check every 5 minutes (default: 2 minutes)
GMAIL_WATCHER_CHECK_INTERVAL=300
```

### Change Gmail Query

**Important:** IMAP uses different search syntax than Gmail!

```env
# All unread emails (recommended)
GMAIL_WATCHER_QUERY=UNREAD

# Unread from specific sender
GMAIL_WATCHER_QUERY=FROM:boss@company.com UNREAD

# Unread with subject containing "invoice"
GMAIL_WATCHER_QUERY=SUBJECT:invoice UNREAD

# Unread important (Gmail-specific, may not work with all accounts)
GMAIL_WATCHER_QUERY=UNREAD IMPORTANT
```

**Gmail vs IMAP Query Syntax:**

| Gmail (OAuth) | IMAP |
|---------------|------|
| `is:unread is:important` | `UNREAD IMPORTANT` |
| `from:boss@company.com` | `FROM:boss@company.com UNREAD` |
| `subject:invoice` | `SUBJECT:invoice UNREAD` |

---

## 🔧 Troubleshooting

### "LOGIN failed" error

**Problem:** Wrong app password or regular Gmail password

**Solution:**
1. Make sure you're using **app password**, not regular Gmail password
2. App password is 16 characters (no spaces)
3. Generate new one if needed: https://myaccount.google.com/apppasswords

---

### "IMAP not connected" warning

**Problem:** Connection issue or 2FA not enabled

**Solution:**
1. Verify 2FA is enabled on your Gmail account
2. Check firewall/antivirus isn't blocking IMAP
3. Test IMAP connection manually:
   ```bash
   # Windows (PowerShell)
   telnet imap.gmail.com 993
   
   # Should connect (screen goes blank)
   ```

---

### No emails being processed

**Problem:** Query too restrictive or all emails already processed

**Solution:**
1. Try broader query:
   ```env
   GMAIL_WATCHER_QUERY=UNREAD
   ```
2. Clear processed IDs cache:
   ```bash
   del vault\.gmail_imap_processed_ids.json
   ```

---

### "Too many login attempts" error

**Problem:** Gmail rate limiting

**Solution:**
1. Increase check interval:
   ```env
   GMAIL_WATCHER_CHECK_INTERVAL=300  # 5 minutes
   ```
2. Wait 1 hour for rate limit to reset

---

## 🆚 IMAP vs OAuth Mode

| Feature | IMAP Mode (Development) | OAuth Mode (Production) |
|---------|------------------------|------------------------|
| **Setup Time** | 2 minutes | 10 minutes |
| **Credentials** | Email + App Password | credentials.json |
| **2FA Required** | ✅ Yes | ✅ Yes |
| **Google Cloud Project** | ❌ No | ✅ Yes |
| **Browser Authorization** | ❌ No | ✅ Yes |
| **Security** | Good (app password) | Better (OAuth2 tokens) |
| **Best For** | Development, testing | Production deployment |

---

## 📝 How It Works

```
┌─────────────────────────────────────────────────────────────┐
│  Gmail Servers                                              │
│  - New email arrives                                        │
│  - Marked as unread                                         │
└─────────────────────────────────────────────────────────────┘
                          │
                          │ IMAP Protocol (every 2 min)
                          │ Port 993 (SSL)
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  GmailWatcherIMAP (gmail_watcher_imap.py)                   │
│  1. Connect via IMAP (login with app password)              │
│  2. Search: UNREAD IMPORTANT                                │
│  3. Fetch message headers + body                            │
│  4. Extract: From, Subject, Date, Content                   │
└─────────────────────────────────────────────────────────────┘
                          │
                          │ create_email_task()
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  Needs_Action/EMAIL_<task_id>.md                            │
│  - YAML frontmatter with metadata                           │
│  - Email body content                                       │
│  - Priority based on subject keywords                       │
└─────────────────────────────────────────────────────────────┘
                          │
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  Processing by Claude Code (via orchestrator)               │
│  - Reads CLAUDE.md + process-email/SKILL.md                 │
│  - Returns JSON decision                                    │
│  - Output to Done/ or Pending_Approval/                     │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔒 Security Notes

### App Password Security

- ✅ **Safe to use** in development environments
- ✅ More secure than regular password (can be revoked individually)
- ✅ Can be regenerated anytime without affecting other apps
- ❌ Don't commit to Git (already in .gitignore)
- ❌ Don't share publicly

### Revoke Access

To revoke app password access:
1. Go to: https://myaccount.google.com/security
2. **App passwords**
3. Find "AI Employee Dev"
4. Click **Remove** (trash icon)

---

## 📖 Additional Resources

- **Full Setup Guide:** `GMAIL_WATCHER_SETUP.md` (OAuth mode)
- **Architecture:** `WATCHER_ARCHITECTURE_GUIDE.md`
- **Email Skill:** `vault/.claude/skills/process-email/SKILL.md`

---

**Last Updated:** 2026-03-23  
**Version:** 2.0 (IMAP)
