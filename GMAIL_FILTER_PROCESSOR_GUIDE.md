# 📧 Gmail Filter Processor - Standalone Script

**Single script that does it all:**
1. ✅ Fetches unread emails from Gmail
2. ✅ Applies smart filtering (removes promotions, social, newsletters)
3. ✅ Creates task files only for important emails
4. ✅ Marks processed emails as read
5. ✅ Runs once and exits (no continuous watching)

---

## 🚀 Quick Start

### 1. Configure Settings in .env

Edit `.env` file in project root:

```env
# Gmail IMAP Settings
GMAIL_IMAP_ADDRESS=your.email@gmail.com
GMAIL_IMAP_APP_PASSWORD=abcdefghijklmnop  # Your 16-char app password (no spaces)
```

**Get App Password:**
1. Go to: https://myaccount.google.com/apppasswords
2. Create app password for "Mail"
3. Copy the 16-character password (remove spaces)
4. Paste in `.env` file

### 2. Run the Script

```bash
python gmail_filter_processor.py
```

That's it! The script will:
- Load credentials from `.env` via settings
- Connect to Gmail
- Fetch all unread emails
- Filter out promotions, social, newsletters
- Create task files for important emails only
- Mark all processed emails as read
- Exit

---

## 📋 What It Does

### Smart Filtering

**Automatically SKIPS:**
- ❌ Promotions (marketing, deals, coupons)
- ❌ Social media notifications (LinkedIn, Facebook, Twitter)
- ❌ Newsletters and digests
- ❌ Automated updates (GitHub, YouTube)
- ❌ Forum notifications

**Automatically PROCESSES:**
- ✅ Personal emails (gmail.com, yahoo.com, outlook.com)
- ✅ Urgent emails (subject contains "urgent", "ASAP", "important")
- ✅ Business emails (invoice, payment, meeting, interview)
- ✅ Unknown senders (not in skip list)

---

## 🎯 Example Output

```
======================================================================
  Gmail Filter Processor - Standalone Email Filter
======================================================================

📧 Account: inayaqureshi3509@gmail.com
📁 Output: vault/Needs_Action
🔍 Filtering 4 categories
   Skipping: promotions, social, updates, forums
   Priority: urgent, asap, important, action required, payment...

🔌 Connecting to Gmail IMAP...
✅ Connected to Gmail successfully
   Gmail extensions: Available ✓

📬 Fetching unread emails...
   Found 14 unread emails

🔄 Processing 14 unread emails...

[1/14] Processing message 88... ✅ Created: email_20260324_120000_Job_Interview_Tomorrow.md
[2/14] Processing message 89... ⊘ Skipped: linkedin.com (automated sender)
[3/14] Processing message 90... ⊘ Skipped: github.com (automated sender)
[4/14] Processing message 91... ✅ Created: email_20260324_120100_Invoice_Payment_Due.md
[5/14] Processing message 92... ⊘ Skipped: Skipped: promotions category
[6/14] Processing message 93... ⊘ Skipped: Skipped: social category
[7/14] Processing message 94... ✅ Created: email_20260324_120200_Meeting_Request.md
[8/14] Processing message 95... ⊘ Skipped: newsletter in subject
[9/14] Processing message 96... ⊘ Skipped: Already processed
[10/14] Processing message 97... ⊘ Skipped: Already processed
[11/14] Processing message 98... ⊘ Skipped: Already processed
[12/14] Processing message 99... ⊘ Skipped: Already processed
[13/14] Processing message 100... ⊘ Skipped: Already processed
[14/14] Processing message 101... ⊘ Skipped: Already processed

======================================================================
  Processing Summary
======================================================================
   Total unread emails: 14
   ✅ Processed: 3
   ⊘ Skipped: 11
   ❌ Errors: 0
======================================================================

👋 Disconnected from Gmail
```

---

## ⚙️ Customization

### Change Filtering Rules

Edit the `FILTER_CONFIG` dictionary (lines 36-85):

```python
FILTER_CONFIG = {
    # Categories to SKIP
    "skip_categories": [
        "promotions",    # Marketing emails
        "social",        # Social media
        "updates",       # Newsletters
        "forums",        # Forum notifications
    ],
    
    # Sender domains to SKIP
    "skip_domains": [
        "linkedin.com",
        "github.com",
        "facebook.com",
        # Add more...
    ],
    
    # Subject keywords to SKIP
    "skip_subject_keywords": [
        "newsletter",
        "digest",
        "unsubscribe",
        # Add more...
    ],
    
    # Subject keywords to PRIORITIZE
    "priority_keywords": [
        "urgent",
        "asap",
        "invoice",
        "interview",
        # Add more...
    ],
    
    # Priority sender domains (always process)
    "priority_domains": [
        "gmail.com",    # Personal emails
        "yahoo.com",
        "outlook.com",
        # Add more...
    ],
}
```

---

## 📁 Output

Task files are created in:
```
vault/Needs_Action/email_TIMESTAMP_SUBJECT.md
```

Each task file contains:
- YAML frontmatter with metadata
- Email headers (From, To, Subject, Date)
- Email body (truncated to 3000 chars)
- Filter reason (why this email was selected)
- Instructions for AI processing

---

## 🔄 How to Use in Workflow

### Option 1: Manual Run

Run whenever you want to process emails:
```bash
python gmail_filter_processor.py
```

### Option 2: Scheduled Task (Windows)

1. Open **Task Scheduler**
2. Create Basic Task
3. Trigger: Daily/Hourly
4. Action: Start a program
   - Program: `python.exe`
   - Arguments: `gmail_filter_processor.py`
   - Start in: `D:\AbdullahQureshi\workspace\Hackathon-2025\GeneralAgentWithCursor`

### Option 3: Cron Job (Linux/Mac)

```bash
# Edit crontab
crontab -e

# Run every hour
0 * * * * cd /path/to/project && python gmail_filter_processor.py
```

---

## 🛠️ Troubleshooting

### "LOGIN failed" error

**Solution:**
1. Make sure you're using **app password**, not regular password
2. Verify 2FA is enabled on your Gmail account
3. Generate new app password: https://myaccount.google.com/apppasswords

### "No unread emails" but I see emails in Gmail

**Possible causes:**
1. Emails are already marked as read in Gmail
2. Emails are in different folder (not INBOX)
3. Gmail categorization issue

**Solution:**
- Check Gmail web interface
- Verify emails are in INBOX and marked as unread

### Script creates too many task files

**Solution:**
- Add more domains to `skip_domains` list
- Add more keywords to `skip_subject_keywords`
- Remove categories from `skip_categories` if too aggressive

### Script misses important emails

**Solution:**
- Add keywords to `priority_keywords`
- Add sender domains to `priority_domains`
- Check if Gmail categorized them as promotions/social

---

## 📊 Comparison: Script vs Watcher

| Feature | Standalone Script | Continuous Watcher |
|---------|------------------|-------------------|
| **Runs** | Once on demand | Continuously in background |
| **Filtering** | Advanced smart filtering | Basic UNSEEN filter |
| **Control** | Full manual control | Automatic |
| **Resource Usage** | Minimal (runs briefly) | Continuous (uses memory) |
| **Best For** | Batch processing | Real-time processing |
| **Setup** | Simple (just run) | Requires configuration |

---

## 🎯 Best Practices

1. **Run regularly:** Daily or weekly for best results
2. **Review skipped emails:** Check Gmail occasionally to ensure nothing important is filtered
3. **Tune filters:** Adjust filtering rules based on your email patterns
4. **Backup:** Keep backups of important emails in Gmail
5. **Monitor:** Check task files in `Needs_Action/` folder regularly

---

## 📝 Example Use Cases

### Use Case 1: Daily Email Processing

```bash
# Every morning at 9 AM
python gmail_filter_processor.py
```

Creates task files for important emails received overnight.

### Use Case 2: Catch-up After Vacation

```bash
# Return from vacation - process all unread emails
python gmail_filter_processor.py
```

Filters out noise, creates tasks only for important emails.

### Use Case 3: Invoice Processing

Add to filtering:
```python
"priority_keywords": [
    "invoice",
    "payment",
    "billing",
    # ...existing...
]
```

Run daily to catch all payment-related emails.

---

## 🔒 Security

- ✅ App password stored locally (not committed to Git)
- ✅ IMAP read-only access (can't delete emails)
- ✅ No external API calls (direct IMAP connection)
- ✅ Processed IDs stored locally

**Never commit your app password to version control!**

---

## 📖 Additional Resources

- **Gmail App Password:** https://support.google.com/accounts/answer/185833
- **IMAP Protocol:** https://tools.ietf.org/html/rfc3501
- **Gmail IMAP Settings:** https://support.google.com/mail/answer/7126229

---

**Created:** 2026-03-24  
**Version:** 1.0
