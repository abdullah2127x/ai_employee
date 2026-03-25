# Gmail Filter Configuration Guide

**Quick reference for customizing email filtering in `gmail_watcher_imap.py`**

---

## 📍 Configuration Location

Edit `watchers/gmail_watcher_imap.py`, lines 44-124:

```python
FILTER_CONFIG = {
    # ... configuration here ...
}
```

---

## 🔧 Filter Categories

### 1. Skip Categories (Gmail Labels)
**Location:** `FILTER_CONFIG['skip_categories']`

Gmail automatically categorizes emails. Skip entire categories:

```python
"skip_categories": [
    "promotions",    # Marketing emails, deals, coupons
    "social",        # Social media notifications
    "updates",       # Newsletters, automated updates
    "forums",        # Forum notifications
],
```

**Add a category:**
```python
"skip_categories": ["promotions", "social", "updates", "forums", "spam"],
```

---

### 2. Skip Domains (Automated Senders)
**Location:** `FILTER_CONFIG['skip_domains']`

Common automated senders to always skip:

```python
"skip_domains": [
    "linkedin.com",
    "github.com",
    "facebook.com",
    "twitter.com",
    "instagram.com",
    "youtube.com",
    "medium.com",
    "substack.com",
    "reddit.com",
    "quora.com",
],
```

**Add a domain:**
```python
"skip_domains": ["linkedin.com", "github.com", "newsletter.company.com"],
```

---

### 3. Business Domains (Always Process)
**Location:** `FILTER_CONFIG['business_domains']`

Critical business domains to ALWAYS process:

```python
"business_domains": [
    "amazon.com",
    "aws.amazon.com",
    "google.com",
    "microsoft.com",
    "apple.com",
    "paypal.com",
    "stripe.com",
    "bank",  # Any bank domain
    "gov",  # Government domains
],
```

**Add a domain:**
```python
"business_domains": ["amazon.com", "your-company.com", "your-bank.com"],
```

⚠️ **Note:** `"bank"` and `"gov"` match any domain containing those strings (e.g., `chasebank.com`, `irs.gov`)

---

### 4. Skip Subject Keywords
**Location:** `FILTER_CONFIG['skip_subject_keywords']`

Subject line keywords that indicate emails to skip:

```python
"skip_subject_keywords": [
    "newsletter",
    "digest",
    "weekly roundup",
    "daily digest",
    "unsub",
    "unsubscribe",
    "marketing",
    "promo",
    "discount",
    "sale",
    "offer",
],
```

**Add a keyword:**
```python
"skip_subject_keywords": ["newsletter", "digest", "black friday", "cyber monday"],
```

⚠️ **Note:** Multi-word phrases work (e.g., `"weekly roundup"`)

---

### 5. Priority Subject Keywords
**Location:** `FILTER_CONFIG['priority_keywords']`

Subject line keywords that indicate IMPORTANT emails:

```python
"priority_keywords": [
    "urgent",
    "asap",
    "important",
    "action required",
    "payment",
    "invoice",
    "interview",
    "meeting",
    "job",
    "career",
],
```

**Add a keyword:**
```python
"priority_keywords": ["urgent", "asap", "deadline", "escalation"],
```

---

### 6. Priority Domains (Personal Emails)
**Location:** `FILTER_CONFIG['priority_domains']`

Personal email domains to always process:

```python
"priority_domains": [
    "gmail.com",
    "yahoo.com",
    "outlook.com",
    "hotmail.com",
    "icloud.com",
],
```

**Add a domain:**
```python
"priority_domains": ["gmail.com", "protonmail.com", "tutanota.com"],
```

---

## 🎯 How Filtering Works

### Filter Order (First Match Wins)

1. **Already Processed?** → Skip (don't process twice)
2. **Gmail Category Match?** → Skip (promotions, social, updates, forums)
3. **Business Domain?** → ✅ **PROCESS** (Amazon, Google, Microsoft, banks, gov)
4. **Skip Domain?** → Skip (LinkedIn, GitHub, etc.)
5. **Priority Keyword in Subject?** → ✅ **PROCESS** (urgent, invoice, meeting)
6. **Priority Domain?** → ✅ **PROCESS** (Gmail, Yahoo, Outlook - personal emails)
7. **Skip Keyword in Subject?** → Skip (newsletter, digest, promo)
8. **Individual Sender?** → ✅ **PROCESS** (no `<` or `.` in from address)
9. **Default** → Skip (if unclear)

### Filter Reason Examples

When an email is processed or skipped, a reason is logged:

**Process Reasons:**
- `"Business domain: amazon.com"`
- `"Priority: 'meeting' in subject"`
- `"Priority: gmail.com (personal email)"`
- `"Individual sender"`

**Skip Reasons:**
- `"Already processed"`
- `"Skipped: Promotions category"`
- `"Skipped: linkedin.com (automated sender)"`
- `"Skipped: 'newsletter' in subject"`
- `"Skipped: No priority indicators"`

---

## 🧪 Testing Your Configuration

### Test 1: Check Syntax
```bash
python -m py_compile watchers/gmail_watcher_imap.py
```

### Test 2: Run in Standalone Mode
```bash
python watchers/gmail_watcher_imap.py
```

Watch the console output for filter decisions:
```
[INFO] Found 15 unread, 3 to process, 12 skipped
[INFO] Created task file: email_20250325_143022_Meeting.md | Reason: Priority: 'meeting' in subject
```

### Test 3: Check Logs
After running, check:
- `vault/Logs/gmail_skipped.md` - See why emails were skipped
- `vault/Logs/gmail_processed.md` - See processed emails
- `vault/Logs/gmail_status_dashboard.md` - Overview

---

## 🎨 Customization Examples

### Example 1: Freelancer Configuration
Process client emails, skip everything else:

```python
FILTER_CONFIG = {
    "skip_categories": ["promotions", "social", "updates", "forums"],
    
    "skip_domains": [
        "linkedin.com", "github.com", "facebook.com",
        "twitter.com", "instagram.com", "youtube.com",
        "medium.com", "substack.com", "reddit.com", "quora.com",
        "upwork.com", "fiverr.com",  # Freelance platforms (notifications)
    ],
    
    "business_domains": [
        "client-company.com",  # Your client
        "paypal.com", "stripe.com",  # Payments
        "bank", "gov",
    ],
    
    "skip_subject_keywords": [
        "newsletter", "digest", "unsubscribe",
        "marketing", "promo", "discount", "sale", "offer",
    ],
    
    "priority_keywords": [
        "urgent", "asap", "important", "action required",
        "payment", "invoice", "project", "deadline",
        "meeting", "call", "interview",
    ],
    
    "priority_domains": ["gmail.com", "yahoo.com", "outlook.com"],
}
```

### Example 2: Job Seeker Configuration
Process recruiter emails, skip job board notifications:

```python
FILTER_CONFIG = {
    "skip_categories": ["promotions", "social", "updates", "forums"],
    
    "skip_domains": [
        "linkedin.com", "indeed.com", "glassdoor.com",
        "monster.com", "careerbuilder.com",
        "github.com", "facebook.com", "twitter.com",
    ],
    
    "business_domains": [
        "company.com",  # Target companies
        "recruiter.com",  # Recruiting agencies
        "paypal.com", "stripe.com",
        "bank", "gov",
    ],
    
    "skip_subject_keywords": [
        "newsletter", "digest", "unsubscribe",
        "job alert", "job match", "new jobs",
    ],
    
    "priority_keywords": [
        "urgent", "asap", "important",
        "interview", "offer", "position", "role",
        "meeting", "call", "phone screen",
    ],
    
    "priority_domains": ["gmail.com", "yahoo.com", "outlook.com"],
}
```

### Example 3: E-commerce Business Configuration
Process customer and vendor emails, skip marketing:

```python
FILTER_CONFIG = {
    "skip_categories": ["promotions", "social", "updates", "forums"],
    
    "skip_domains": [
        "linkedin.com", "github.com", "facebook.com",
        "twitter.com", "instagram.com", "youtube.com",
        "medium.com", "substack.com", "reddit.com", "quora.com",
    ],
    
    "business_domains": [
        "amazon.com", "aws.amazon.com",  # Amazon
        "shopify.com",  # E-commerce platform
        "paypal.com", "stripe.com",  # Payments
        "ups.com", "fedex.com", "usps.com",  # Shipping
        "bank", "gov",
    ],
    
    "skip_subject_keywords": [
        "newsletter", "digest", "unsubscribe",
        "marketing", "promo", "discount", "sale", "offer",
    ],
    
    "priority_keywords": [
        "urgent", "asap", "important", "action required",
        "payment", "invoice", "order", "refund", "return",
        "customer", "complaint", "issue", "problem",
    ],
    
    "priority_domains": ["gmail.com", "yahoo.com", "outlook.com"],
}
```

---

## ⚠️ Common Issues

### Issue 1: Too Many Emails Processed
**Problem:** Getting flooded with task files

**Solution:** Add more skip domains or categories
```python
"skip_domains": ["linkedin.com", "github.com", "MORE_DOMAINS"],
"skip_categories": ["promotions", "social", "updates", "forums"],
```

### Issue 2: Important Emails Skipped
**Problem:** Missing important emails

**Solution:** Add business domains or priority keywords
```python
"business_domains": ["important-sender.com"],
"priority_keywords": ["critical", "escalation"],
```

### Issue 3: Personal Emails Skipped
**Problem:** Gmail/Yahoo emails not processed

**Solution:** Ensure priority domains are configured
```python
"priority_domains": ["gmail.com", "yahoo.com", "outlook.com"]
```

### Issue 4: Newsletters Getting Through
**Problem:** Newsletters not being filtered

**Solution:** Add more skip keywords
```python
"skip_subject_keywords": [
    "newsletter", "digest", "weekly roundup",
    "daily digest", "substack", "mailchimp",
]
```

---

## 🔍 Debugging Filter Decisions

### Check Why Email Was Skipped
1. Open `vault/Logs/gmail_skipped.md`
2. Find the email in the table
3. Check the "Reason" column

### Check Why Email Was Processed
1. Open `vault/Logs/gmail_processed.md`
2. Find the email in the table
3. Check the "Filter Reason" column

### Enable Debug Logging
Add to `check_for_updates()` method:
```python
logger.write_to_timeline(
    f"Processing email {msg_id_str}: {msg.get('From', 'Unknown')} - {msg.get('Subject', 'No Subject')}",
    actor="gmail_watcher_imap",
    message_level="DEBUG",
)
```

---

## 📊 Filter Statistics

Check `vault/Logs/gmail_status_dashboard.md` for:
- Total processed this run
- Total skipped this run
- Pending AI processing count
- Recent processed emails

---

## 🎯 Best Practices

1. **Start Conservative:** Begin with strict filtering, relax as needed
2. **Monitor Logs:** Check skipped emails regularly for false positives
3. **Update Regularly:** Add new domains as they appear
4. **Test Changes:** Run standalone mode after config changes
5. **Backup Config:** Save your custom FILTER_CONFIG somewhere safe

---

## 📚 Related Files

- **Main Script:** `watchers/gmail_watcher_imap.py`
- **Reference:** `gmail_filter_processor.py`
- **Logs:** `vault/Logs/gmail_skipped.md`, `vault/Logs/gmail_processed.md`
- **Dashboard:** `vault/Logs/gmail_status_dashboard.md`
- **Task Files:** `vault/Needs_Action/email_*.md`

---

**Last Updated:** 2025-03-25  
**Version:** 2.0 (with smart filtering)
