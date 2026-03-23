---
name: process-file-drop
description: Handles files dropped into the Drop folder by the filesystem watcher
---

# Skill: Process File Drop

## What This Skill Handles

A user dropped a file into the Drop folder. The watcher detected it, extracted
what content it could, and created a task file. Your job is to understand what
the file is, decide what to do with it, and return a JSON decision.

---

## Step 1 — Identify the File Type

Look at `file_extension` and `content_type` in the task frontmatter.

| Extension / Type    | How to treat it                                       |
| ------------------- | ----------------------------------------------------- |
| `.txt`, `.md`       | Read full content — treat as plain document           |
| `.py`, `.js`, `.ts` | Read full content — treat as code file                |
| `.pdf` (text)       | Read extracted text — treat as document               |
| `binary` / unknown  | No content available — base decision on filename only |

If `content_type` is `binary` or content is empty, base your decision on the
filename alone and note this limitation in your `response` field.

---

## Step 2 — Classify the Content

After reading the content, classify what this file actually is:

- **Invoice** — contains amount, vendor name, invoice number, due date
- **Contract / Legal** — contains terms, signatures, agreement language
- **Code** — source code file
- **Report / Document** — informational text, no action items
- **Data file** — CSV, JSON, structured data
- **Unknown** — cannot determine from content

---

## Step 3 — Check Business Rules

Read `Business_Goals.md` and `Company_Handbook.md` now.

Apply these rules based on classification:

**If Invoice:**

- Extract: invoice number, vendor name, amount, due date
- Check amount against `Company_Handbook.md` payment thresholds:
  - Under $50 AND vendor is in approved recurring list → `complete_task`
  - $50–$100 AND new vendor → `create_approval_request`
  - Over $100 → always `create_approval_request`
- Set `category` to `invoice`

**If Contract / Legal:**

- Always `create_approval_request` — never auto-complete legal documents
- Set `category` to `document`

**If Code:**

- `complete_task` — log what the file contains
- Set `category` to `general`

**If Report / Document:**

- `complete_task` — summarize content
- Set `category` to `document`

**If Data file:**

- `complete_task` — describe the structure and row count if visible
- Set `category` to `general`

**If Unknown:**

- `needs_revision` — cannot classify without more context
- Explain what information is missing in `response`

---

## Step 4 — Write Your Response

Your `response` field should include:

- What the file appears to be (your classification)
- Key data extracted (amounts, names, dates if present)
- What action you recommend or took
- Any flags or concerns (missing data, ambiguous content, policy conflicts)

Keep it factual. Do not fabricate values not present in the content.

---

## Examples

**Example 1 — Invoice over $100**

```json
{
  "decision": "create_approval_request",
  "category": "invoice",
  "summary": "Invoice #123 from Acme Corp for $500 — requires payment approval",
  "action_taken": "Extracted invoice details and flagged for approval per payment policy",
  "response": "Invoice #123 from Acme Corp. Amount: $500.00. Due: 2026-03-30. Exceeds $100 threshold per Company_Handbook.md. Vendor not in approved recurring list. Payment approval required before processing.",
  "approval_reason": "Payment of $500 exceeds $100 approval threshold defined in Company_Handbook.md"
}
```

**Example 2 — Text document**

```json
{
  "decision": "complete_task",
  "category": "document",
  "summary": "Meeting notes from 2026-03-20 team sync — filed and summarized",
  "action_taken": "Read and summarized document content, no action required",
  "response": "Meeting notes covering Q1 review and project status. Three action items identified: (1) Client A proposal due March 25, (2) Budget review scheduled for March 28, (3) New hire onboarding checklist to be completed. No financial actions or approvals needed.",
  "approval_reason": null
}
```

**Example 3 — Binary or unreadable file**

```json
{
  "decision": "needs_revision",
  "category": "general",
  "summary": "Binary file detected — cannot process without content extraction",
  "action_taken": "Flagged for revision as content could not be read",
  "response": "File 'report.xlsx' is a binary format. No text content was extracted. Cannot classify or process without content. Recommend adding Excel/PDF extraction support to the watcher, or manually converting to text before dropping.",
  "approval_reason": null
}
```
