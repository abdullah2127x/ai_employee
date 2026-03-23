---
name: process-email
description: Handles email tasks from the Gmail watcher
---

# Skill: Process Email

## What This Skill Handles

An email was received and the Gmail watcher created a task file. Your job is to:
1. Read the email content and headers
2. Identify the email type and intent
3. Apply business rules from Business_Goals.md and Company_Handbook.md
4. Return a JSON decision

---

## Step 1 — Read Email Headers

Check the YAML frontmatter for:

| Field | What to Look For |
|-------|------------------|
| `from` | Sender address — known contact? Vendor? Spam? |
| `subject` | Topic — invoice, meeting, inquiry, newsletter? |
| `priority` | Gmail's priority flag (urgent, high, normal) |
| `received` | When it arrived — time-sensitive? |

---

## Step 2 — Classify the Email Type

After reading the content, classify what this email is:

**Invoice / Payment Request:**
- Contains amount, due date, payment instructions
- Vendor name, invoice number
- Action: Check Company_Handbook.md for payment thresholds

**Meeting Request:**
- Contains proposed dates/times
- Calendar invitation language
- Action: Check Business_Goals.md for priority

**Client Inquiry:**
- Question about services, pricing, availability
- Potential business opportunity
- Action: Respond or route to appropriate person

**Internal Communication:**
- From team member
- Project updates, requests, notifications
- Action: Acknowledge or act as needed

**Newsletter / Marketing:**
- Bulk email, promotional content
- Usually low priority
- Action: Archive or summarize

**Urgent / Time-Sensitive:**
- Deadline mentioned
- "ASAP", "urgent", "emergency" in subject or body
- Action: Prioritize response

---

## Step 3 — Check Business Rules

Read `Business_Goals.md` and `Company_Handbook.md` now.

Apply these rules based on classification:

**If Invoice / Payment Request:**

- Extract: invoice number, vendor name, amount, due date
- Check amount against `Company_Handbook.md` payment thresholds:
  - Under $50 AND vendor is in approved recurring list → `complete_task`
  - $50–$100 AND new vendor → `create_approval_request`
  - Over $100 → always `create_approval_request`
- Set `category` to `invoice` or `payment`

**If Meeting Request:**

- Check against `Business_Goals.md` active projects
- If related to active project → `complete_task` with response
- If unclear priority → `complete_task` with clarification request
- Set `category` to `general`

**If Client Inquiry:**

- If pricing question → check `Company_Handbook.md` for approved rates
  - Within approved rates → `complete_task` with response
  - Requires custom quote → `create_approval_request`
- If service question → `complete_task` with informational response
- Set `category` to `urgent` if high-value client

**If Internal Communication:**

- If action required → `complete_task` with action taken
- If informational → `complete_task` with acknowledgment
- Set `category` to `general`

**If Newsletter / Marketing:**

- `complete_task` — archive with summary
- Set `category` to `general`

**If Urgent / Time-Sensitive:**

- Assess urgency validity
- If legitimate urgent → `complete_task` with immediate action
- If suspicious urgency (potential scam) → `create_approval_request`
- Set `category` to `urgent`

---

## Step 4 — Write Your Response

Your `response` field should include:

- What the email is about (summary)
- Key data extracted (amounts, dates, names if present)
- What action you took or recommend
- Any flags or concerns (phishing, suspicious requests, policy conflicts)

Keep it factual. Do not fabricate values not present in the email.

---

## Security Rules (Always Apply)

1. **Phishing detection** — Flag if:
   - Sender address doesn't match claimed organization
   - Urgent payment request to new vendor
   - Suspicious links or attachments mentioned
   - Poor grammar/spelling from supposed professional source

2. **Sensitive data** — Never include in response:
   - Passwords or credentials
   - Credit card numbers
   - Personal identification numbers
   - API keys or secrets

3. **When uncertain** — Choose `create_approval_request` over guessing

---

## Examples

**Example 1 — Invoice from approved vendor under $50**

```json
{
  "decision": "complete_task",
  "category": "invoice",
  "summary": "Invoice #456 from Acme Corp for $35 — auto-approved per payment policy",
  "action_taken": "Logged invoice details, no payment action needed (under threshold)",
  "response": "Invoice #456 from Acme Corp (approved vendor #12). Amount: $35.00. Due: 2026-03-30. Under $50 threshold per Company_Handbook.md. Vendor is in approved recurring list. Invoice logged for records. No payment action required at this time.",
  "approval_reason": null
}
```

**Example 2 — Invoice over $100**

```json
{
  "decision": "create_approval_request",
  "category": "invoice",
  "summary": "Invoice #789 from New Vendor for $250 — requires payment approval",
  "action_taken": "Extracted invoice details, flagged for approval per payment policy",
  "response": "Invoice #789 from New Vendor LLC. Amount: $250.00. Due: 2026-03-25. Exceeds $100 threshold per Company_Handbook.md. Vendor not in approved recurring list. Payment approval required before processing. Invoice details: [summary of line items if available].",
  "approval_reason": "Payment of $250 exceeds $100 approval threshold. New vendor requires verification."
}
```

**Example 3 — Client pricing inquiry**

```json
{
  "decision": "complete_task",
  "category": "urgent",
  "summary": "Client inquiry about consulting rates — responded with approved pricing",
  "action_taken": "Sent response with standard consulting rates from Company_Handbook.md",
  "response": "Email from prospective client (john@example.com) inquiring about consulting rates. Responded with standard rates from Company_Handbook.md: $150/hour for strategy consulting, $100/hour for implementation. Included availability and next steps. Follow-up scheduled for March 28.",
  "approval_reason": null
}
```

**Example 4 — Suspicious payment request**

```json
{
  "decision": "create_approval_request",
  "category": "urgent",
  "summary": "Suspicious payment request — potential phishing attempt",
  "action_taken": "Flagged for human review due to phishing indicators",
  "response": "Email claims to be from 'CEO' requesting urgent wire transfer to new vendor. Red flags: (1) Sender address is gmail.com not company domain, (2) Urgent tone with pressure to act quickly, (3) New vendor not in approved list, (4) Wire transfer request (unusual). Recommend verifying via phone before any action.",
  "approval_reason": "Potential phishing attempt. Multiple red flags detected. Human verification required before any action."
}
```

**Example 5 — Meeting request for active project**

```json
{
  "decision": "complete_task",
  "category": "general",
  "summary": "Meeting request for Project Alpha — responded with availability",
  "action_taken": "Sent calendar response with available time slots",
  "response": "Meeting request from project stakeholder (sarah@client.com) for Project Alpha sprint review. Project is listed in Business_Goals.md as Q1 priority. Responded with available time slots: March 25 2-4pm, March 26 10am-12pm. Requested agenda and attendee list.",
  "approval_reason": null
}
```
