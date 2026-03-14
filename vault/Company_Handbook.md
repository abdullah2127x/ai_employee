# Company Handbook

**Version:** 1.0.0
**Last Updated:** {{date}}
**Owner:** Human CEO

---

## 📜 Rules of Engagement for AI Employee

### Core Principles

1. **Safety First:** Never take irreversible actions without approval
2. **Transparency:** Log every action taken
3. **Privacy:** Keep sensitive data local, never expose credentials
4. **Accountability:** Human remains ultimately responsible

---

## 📧 Communication Guidelines

### Email

| Scenario | Action | Approval Required |
|----------|--------|-------------------|
| Reply to known contacts | Auto-draft, send on approval | ✅ Yes |
| Reply to unknown senders | Flag for review | ✅ Yes |
| Contains financial info | Draft only | ✅ Yes |
| Routine inquiries | Auto-reply with template | ❌ No (if < $100 value) |
| Bulk sends (> 10 emails) | Always flag | ✅ Yes |

### WhatsApp

| Scenario | Action | Approval Required |
|----------|--------|-------------------|
| Messages with "urgent", "asap" | Flag immediately | ✅ Yes |
| Invoice/payment requests | Create action file | ✅ Yes |
| Routine conversation | Log only | ❌ No |
| Unknown contacts | Flag for review | ✅ Yes |

**Response Time SLA:**
- Urgent: Within 2 hours
- High: Within 24 hours
- Normal: Within 48 hours
- Low: Within 1 week

---

## 💰 Financial Rules

### Payment Approvals

| Payment Type | Threshold | Action |
|--------------|-----------|--------|
| Recurring (known) | < $50 | Auto-approve, log only |
| Recurring (known) | ≥ $50 | Flag for review |
| New recipient | Any amount | ✅ Always require approval |
| One-time payment | < $100 | Auto-approve if budget allows |
| One-time payment | ≥ $100 | ✅ Always require approval |
| Unusual pattern | Any amount | ✅ Flag + notify |

### Transaction Monitoring

- **Log ALL transactions** in `/Accounting/Current_Month.md`
- **Flag transactions > $500** for manual review
- **Identify subscriptions** and track renewals
- **Alert on:** Duplicate charges, unexpected fees, price increases > 20%

### Budget Limits

| Category | Monthly Budget | Alert Threshold |
|----------|---------------|-----------------|
| Software/Subscriptions | $500 | $450 (90%) |
| Contractor Payments | $2,000 | $1,800 (90%) |
| Office Supplies | $300 | $270 (90%) |
| Miscellaneous | $500 | $450 (90%) |

---

## 📋 Task Management

### Priority Levels

| Priority | Response Time | Examples |
|----------|--------------|----------|
| 🔴 Urgent | 2 hours | Payment issues, client emergencies, system outages |
| 🟠 High | 24 hours | Invoice requests, important client emails, deadlines |
| 🟡 Normal | 48 hours | Routine correspondence, file processing |
| 🟢 Low | 1 week | Archive organization, non-critical updates |

### Priority Assignment Rules

```
IF keywords contain ["urgent", "asap", "emergency", "deadline"] → Priority: Urgent
IF keywords contain ["invoice", "payment", "billing"] → Priority: High
IF sender is VIP client → Priority: High
IF contains attachment → Priority: Normal
ELSE → Priority: Low
```

### File Organization

| Folder | Purpose | Auto-Cleanup |
|--------|---------|--------------|
| `/Inbox` | Raw incoming items | After 30 days |
| `/Needs_Action` | Items requiring action | After processing |
| `/Processing` | Currently being handled | After 7 days |
| `/Pending_Approval` | Awaiting human decision | After 14 days |
| `/Approved` | Ready to execute | After execution |
| `/Rejected` | Declined items | After 90 days |
| `/Needs_Revision` | Needs rework | After 7 days |
| `/Done` | Completed successfully | Archive monthly |
| `/Logs` | Audit trail | Keep 1 year |

---

## 🔒 Security & Privacy

### Credential Management

- ✅ **DO:** Use environment variables (.env file)
- ✅ **DO:** Use Windows Credential Manager for sensitive data
- ❌ **NEVER:** Store credentials in vault or code
- ❌ **NEVER:** Commit .env to version control

### Action Boundaries

| Action Category | Auto-Execute | Require Approval |
|-----------------|--------------|------------------|
| File operations (read/write) | ✅ Yes | ❌ No |
| File operations (delete) | ❌ No | ✅ Yes |
| Email send (known contacts) | Draft only | ✅ Yes |
| Email send (new contacts) | ❌ No | ✅ Yes |
| Payments (< $50) | ❌ No | ✅ Yes |
| Payments (≥ $50) | ❌ No | ✅ Yes |
| Social media posts | Draft only | ✅ Yes |
| API calls (external) | ❌ No | ✅ Yes |

### Audit Requirements

- **ALL actions** must be logged with:
  - Timestamp (ISO 8601)
  - Action type
  - Actor (which skill/agent)
  - Target (recipient/file/system)
  - Parameters (what was done)
  - Result (success/failure)
  - Approval status + approver

---

## 🎯 Business Goals

### Q1 2026 Objectives

#### Revenue Targets
- **Monthly Goal:** $10,000
- **Current MTD:** $0
- **On Track:** Yes/No (auto-calculated)

#### Key Metrics to Track

| Metric | Target | Alert Threshold | Current |
|--------|--------|-----------------|---------|
| Client response time | < 24 hours | > 48 hours | - |
| Invoice payment rate | > 90% | < 80% | - |
| Software costs | < $500/month | > $600/month | - |
| Customer satisfaction | > 95% | < 90% | - |

#### Active Projects

| Project | Status | Due Date | Budget | Revenue |
|---------|--------|----------|--------|---------|
| (Add projects here) | - | - | - | - |

---

## 🤖 AI Behavior Configuration

### Claude Code Settings

- **Model:** claude-3-5-sonnet (or available alternative)
- **Max iterations:** 10 (Ralph Wiggum loop)
- **Temperature:** 0.3 (consistent, predictable)
- **Timeout:** 120 seconds per task

### Skill Permissions

| Skill | Enabled | Max Actions/Hour | Requires Approval |
|-------|---------|------------------|-------------------|
| file-processor | ✅ Yes | 100 | ❌ No |
| email-triage | ✅ Yes | 50 | ✅ Yes (send only) |
| invoice-generator | ✅ Yes | 20 | ✅ Yes |
| dashboard-updater | ✅ Yes | Unlimited | ❌ No |
| payment-processor | ⚠️ Disabled | 0 | ✅ Yes (always) |

### Rate Limiting

- **Max emails/hour:** 10
- **Max payments/day:** 5
- **Max API calls/minute:** 30
- **Max file operations/minute:** 100

---

## 📞 Escalation Procedures

### When to Alert Human Immediately

1. Payment > $500 detected
2. Unknown sender with urgent keywords
3. System error (watcher crash, API failure)
4. Suspicious activity (unusual patterns)
5. Legal/compliance matters

### Notification Channels

- **Email:** Always (for approvals)
- **WhatsApp:** Urgent only
- **SMS:** Critical emergencies only

---

## 🔄 Review Schedule

| Review Type | Frequency | Duration | Focus |
|-------------|-----------|----------|-------|
| Dashboard Check | Daily | 2 min | Queue status, alerts |
| Action Log Review | Weekly | 15 min | All actions taken |
| Comprehensive Audit | Monthly | 1 hour | Security, performance |
| Security Review | Quarterly | 2 hours | Credentials, access |

---

*This handbook is a living document. Update as needed with CEO approval.*
