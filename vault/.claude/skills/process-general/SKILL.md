---
name: process-general
description: Fallback skill for task types without a dedicated skill file
---

# Skill: Process General Task

## What This Skill Handles

This is the fallback skill for any task that does not match a more specific
skill. The task type may be unknown, the file may be malformed, or a new
watcher may be producing tasks before its dedicated skill is written.

---

## Step 1 — Read the Full Task File

Read everything in the task file: frontmatter, content section, any metadata.
Try to understand what the human or watcher intended.

---

## Step 2 — Attempt Classification

Try to map the task to one of these categories:

- **Action request** — someone wants something done (reply, pay, send, book)
- **Information only** — someone shared data, no action needed
- **File or document** — a file arrived that needs review
- **Error or malformed** — the task file is missing required fields or makes no sense

---

## Step 3 — Apply Conservative Rules

Because this is a general/unknown task, apply conservative rules:

- If any financial amount is mentioned → `create_approval_request`
- If any external action is mentioned (send, post, pay, delete) → `create_approval_request`
- If it is purely informational → `complete_task`
- If you genuinely cannot determine intent → `needs_revision`

When in doubt, choose `needs_revision` over guessing.

---

## Step 4 — Write Your Response

Your `response` field should include:

- What you understood the task to be
- What classification you assigned and why
- What would make this task clearer (if needs_revision)
- Any concerns or flags

---

## Examples

**Example 1 — Simple informational note**

```json
{
  "decision": "complete_task",
  "category": "general",
  "summary": "Informational note logged — no action required",
  "action_taken": "Read and acknowledged the note",
  "response": "Note contains a reminder to review Project Alpha by end of week. No financial actions, no external communications required. Logged and filed.",
  "approval_reason": null
}
```

**Example 2 — Ambiguous request**

```json
{
  "decision": "needs_revision",
  "category": "general",
  "summary": "Task intent unclear — insufficient context to decide",
  "action_taken": "Flagged for human clarification",
  "response": "Task file contains the text 'handle this' with no further context. Cannot determine what action is required, what the subject is, or what the expected outcome should be. Please resubmit with a clear description of the desired action.",
  "approval_reason": null
}
```
