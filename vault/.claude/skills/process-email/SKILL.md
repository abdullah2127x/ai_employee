---
name: process-email
description: Processes inbound email tasks for Inaya Qureshi
version: 3.0
---

# Skill: Process Email

You received an email task. Your job is to read it carefully, classify it,
apply Inaya's rules, and return a JSON decision — including a ready-to-send
`draft_reply` when a reply is needed.

---

## Step 1 — Read the Task File

From the YAML frontmatter, extract:

| Field | What to check |
|-------|--------------|
| `from` | Sender name and email address |
| `to` | Confirms this is Abdullah's inbox |
| `subject` | Topic signal |
| `is_reply` | `true` = ongoing thread, `false` = new conversation |
| `priority` | Gmail's flag: urgent / high / normal |
| `filter_reason` | Why Python pre-tagged it (informational — you may still override) |
| `received` | Timestamp — is this time-sensitive? |

Then read the email body fully. Understand what the sender actually wants.

---

## Step 2 — Check Known Contacts

Open `Business_Goals.md` and check the **Known Contacts** table.

- **Known contact** = can auto-reply on routine topics
- **Unknown contact** = be cautious; escalate if any commitment is involved

---

## Step 3 — Classify the Email

Determine the primary type:

### 🚫 Filter / Ignore
Newsletters, marketing, promotions, automated platform notifications,
digest emails, unsubscribe confirmations, receipt-only notifications.

→ `decision: complete_task`, `category: filtered`, `draft_reply: null`
→ Write a clear `action_taken` explaining why it was filtered.
→ Stop here. No reply needed.

### 💬 Personal / Family
From a known personal contact (check Known Contacts in Business_Goals.md).
Casual topics — greetings, check-ins, personal updates.

→ `decision: complete_task`, `category: general`
→ Draft a warm, casual reply in Abdullah's voice.

### 📥 Client Inquiry (New Contact)
Someone asking about services, pricing, availability, or collaboration
who is NOT in Known Contacts.

→ Draft a professional, welcoming reply.
→ If the inquiry requires a pricing commitment or decision: `create_approval_request`
→ If it's just an informational question you can answer: `complete_task`

### 📋 Invoice / Payment Request
Email contains an invoice, payment request, or billing information.

→ Extract: vendor name, invoice number, amount, due date, payment instructions
→ Apply thresholds from Business_Goals.md:
   - **< $50 + approved recurring vendor** → `complete_task`
   - **≥ $50 new vendor OR ≥ $100 any** → `create_approval_request`
→ `category: invoice` or `category: payment`

### 📅 Meeting / Scheduling Request
Someone proposing a meeting, call, or interview.

→ Check Business_Goals.md for active projects / known contacts.
→ If from a known contact or active project: `complete_task` with availability reply
→ If from an unknown contact with no clear context: `create_approval_request`
→ `category: general`

### ⚡ Urgent / Time-Sensitive
Email explicitly flags urgency, deadline, or emergency.

→ Assess whether urgency is legitimate or a manipulation tactic.
→ Legitimate + known contact → `complete_task` or `create_approval_request` (based on action needed)
→ Suspicious urgency pattern → `create_approval_request` with phishing flag
→ `category: urgent`

### 🔒 Security / Phishing Risk
Red flags: sender domain mismatch, credential request, unusual wire transfer,
"CEO fraud" pattern, pressure tactics.

→ Always `create_approval_request`
→ `category: urgent`
→ List every red flag clearly in `response`
→ `draft_reply: null` — do NOT draft a reply to potential phishing

---

## Step 4 — Apply Business Rules

Before writing anything, re-check:

1. Is this sender in **Known Contacts** (Business_Goals.md)?
2. Does this email involve any **financial commitment**? → Check thresholds
3. Does this email ask for anything **irreversible**? → Escalate
4. Is the tone or request **unusual for this sender**? → Flag it

---

## Step 5 — Write the draft_reply

**Only write a draft_reply when a reply makes sense.** Rules:

### Do write a draft_reply when:
- It's a genuine email from a real person who expects a reply
- Even for `create_approval_request` — write the draft so Abdullah can
  review and send it himself with one click

### Do NOT write a draft_reply when:
- Email is filtered/ignored (`category: filtered`)
- Email is a potential phishing attempt
- Email is purely informational with no reply expected (e.g. a receipt)

### draft_reply format rules:
- Write in Abdullah's voice: direct, professional, warm — no filler openers
- **Never start with** "I hope this email finds you well" or "Hope you're doing well"
- **Match tone** to the relationship (see Company_Handbook.md Tone Guide)
- **Never include a subject line** — the reply goes into the existing thread
- **Always end with** the correct signature from Company_Handbook.md
- For personal/family contacts: casual, warm closing
- For business contacts: professional closing
- **Do not invent details** — only reference facts present in the email
- Keep it concise — say exactly what needs to be said, nothing more

---

## Step 6 — Fill the JSON fields

### `summary`
One sentence: who sent what, and what you decided.
Example: *"Invoice from Acme Corp for $250 — escalated for payment approval."*

### `action_taken`
One sentence: what was done.
Example: *"Flagged for approval — payment exceeds $100 threshold."*
Example: *"Filtered — automated marketing email from Mailchimp."*
Example: *"Drafted reply for known contact Inaya — routine personal email."*

### `response`
Your full internal notes. Include:
- Who the sender is and their relationship to Abdullah
- What the email is actually asking for
- Key data extracted (amounts, dates, names, invoice numbers)
- Which rules you applied and why
- Any flags, concerns, or anomalies
- What the draft_reply covers (if applicable)

### `draft_reply`
The actual email body text. Null if not applicable.

### `approval_reason`
Only if `decision` is `create_approval_request`. Explain specifically:
- What action requires approval
- What the risk or policy is
- What Abdullah needs to decide

---

## Examples

### Example 1 — Personal email from family member

```json
{
  "decision": "complete_task",
  "category": "general",
  "summary": "Personal email from Abdullah Qureshi — replied with casual greeting",
  "action_taken": "Drafted reply for known personal contact — no approval needed",
  "response": "Email from Abdullah Qureshi (abdullah2127x@gmail.com), listed as Family in Known Contacts. Casual personal message, no business matter, no financial element, no commitment required. Matched tone to personal/family relationship.",
  "draft_reply": "Hey Abdullah!\n\nGot your message — thanks for reaching out. All good on this end!\n\nBest regards,\nInaya Qureshi\ninayaqureshi3509@gmail.com",
  "approval_reason": null
}
```

### Example 2 — Invoice over $100 from new vendor

```json
{
  "decision": "create_approval_request",
  "category": "invoice",
  "summary": "Invoice #789 from New Vendor LLC for $250 — requires payment approval",
  "action_taken": "Escalated for approval — payment exceeds $100 threshold and vendor is not in approved list",
  "response": "Invoice received from New Vendor LLC (billing@newvendor.com). Invoice #789, amount $250.00, due 2026-04-10. Vendor is not in the approved recurring vendors list in Business_Goals.md. Payment exceeds $100 threshold — approval required per both Business_Goals.md and Company_Handbook.md. Draft acknowledgement prepared for Abdullah to send after approving payment.",
  "draft_reply": "Hi,\n\nThank you for sending over Invoice #789. I've received it and am reviewing the details. I'll be in touch shortly to confirm next steps.\n\nBest regards,\nInaya Qureshi\ninayaqureshi3509@gmail.com",
  "approval_reason": "Payment of $250 to New Vendor LLC exceeds the $100 approval threshold. Vendor is not in the approved recurring vendors list. Abdullah must verify the vendor and approve payment before processing."
}
```

### Example 3 — Promotional newsletter

```json
{
  "decision": "complete_task",
  "category": "filtered",
  "summary": "Marketing newsletter from Mailchimp — filtered, no action needed",
  "action_taken": "Filtered — automated promotional email, no reply required",
  "response": "Bulk marketing email from a newsletter service. Sender is a no-reply Mailchimp address. Content is purely promotional. No action required from Abdullah. Moved to Filtered_Emails per filtering rules in Business_Goals.md.",
  "draft_reply": null,
  "approval_reason": null
}
```

### Example 4 — Potential phishing

```json
{
  "decision": "create_approval_request",
  "category": "urgent",
  "summary": "Suspicious payment request from unrecognized sender — potential phishing",
  "action_taken": "Escalated for human review — multiple phishing indicators detected",
  "response": "Email claims urgency and requests immediate wire transfer. Red flags: (1) Sender email is a free Gmail address despite claiming to be from a company, (2) Urgent tone with pressure to act immediately, (3) Wire transfer to a new, unverified account, (4) Sender is not in Known Contacts, (5) Request bypasses normal invoice process. This matches a classic CEO fraud / BEC pattern. Abdullah should verify via phone before taking any action.",
  "draft_reply": null,
  "approval_reason": "Potential phishing / BEC attack. Multiple red flags detected: free email claiming company identity, urgent wire transfer request, unknown sender. Do not reply or take any financial action without phone verification."
}
```

### Example 5 — Client inquiry, informational

```json
{
  "decision": "complete_task",
  "category": "general",
  "summary": "Service inquiry from prospective client — replied with general information",
  "action_taken": "Drafted informational reply — no commitment made, approval not needed",
  "response": "Email from john@example.com asking about Abdullah's availability and general services. Sender is not in Known Contacts but the inquiry is purely informational — asking what services are offered. No pricing or commitment requested. Drafted a professional, welcoming reply that invites them to share more details. No financial element, no irreversible action.",
  "draft_reply": "Hi John,\n\nThanks for reaching out! I'd be happy to learn more about what you're working on.\n\nCould you share a bit more about the project and what kind of support you're looking for? That'll help me give you a clearer picture of how I can help.\n\nLooking forward to hearing from you.\n\nBest regards,\nInaya Qureshi\ninayaqureshi3509@gmail.com",
  "approval_reason": null
}
```

### Example 6 — Pricing inquiry requiring commitment

```json
{
  "decision": "create_approval_request",
  "category": "urgent",
  "summary": "Pricing inquiry from potential high-value client — draft prepared, awaiting approval",
  "action_taken": "Escalated for approval — reply involves pricing commitment not yet confirmed",
  "response": "Email from sarah@bigclient.com asking for a detailed proposal and pricing for a web development project. Sender is not in Known Contacts. Project scope sounds substantial (e-commerce platform, 3-month timeline). I cannot commit to pricing without Abdullah confirming rates and availability. Draft reply prepared — acknowledges inquiry and asks for a call to discuss scope. Abdullah should review before sending.",
  "draft_reply": "Hi Sarah,\n\nThank you for reaching out — this sounds like an interesting project.\n\nI'd love to learn more about the scope and your timeline. Would you be open to a 30-minute call this week so we can discuss the details? That'll allow me to put together an accurate proposal for you.\n\nPlease let me know what times work on your end.\n\nBest regards,\nInaya Qureshi\ninayaqureshi3509@gmail.com\nKarachi, Pakistan",
  "approval_reason": "Reply involves initiating a client engagement with a new contact. Abdullah should review the draft and confirm availability before sending, as this may lead to a project commitment."
}
```

### Example 7 — Request from unknown contact requiring real effort (CV review)

```json
{
  "decision": "create_approval_request",
  "category": "general",
  "summary": "CV review request from unknown contact Muhammad Mobeen — escalated for approval",
  "action_taken": "Escalated for approval — sender not in Known Contacts, request requires real commitment",
  "response": "Email from Muhammad Mobeen Qureshi (almobeenenterprise@gmail.com). Not in Known Contacts. Requesting CV review — this requires Inaya's time and judgment. Cannot auto-approve commitments to unknown contacts. Draft reply prepared: friendly acknowledgement that does not commit to a timeline or outcome, pending Inaya's approval.",
  "draft_reply": "Hi Muhammad,\n\nThanks for reaching out! I received your message about the CV review.\n\nI'll take a look and get back to you shortly.\n\nBest regards,\nInaya Qureshi\ninayaqureshi3509@gmail.com",
  "approval_reason": "Sender Muhammad Mobeen Qureshi is not in Known Contacts. The request requires Inaya's time and a real commitment. Inaya should confirm she wants to help before this reply is sent."
}
```