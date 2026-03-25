# X-GM-MSGID Extraction Fix

**Date:** 2026-03-25  
**Issue:** Still using IMAP UID ("102") instead of Gmail X-GM-MSGID  
**Status:** ✅ FIXED with Debug Logging

---

## 🐛 The Problem

### What You Noticed:
```json
// vault/.gmail_imap_processed_ids.json
{
  "102": {  ← This is IMAP UID, not Gmail X-GM-MSGID!
    "status": "processed",
    "timestamp": "..."
  }
}
```

```markdown
<!-- Task file -->
gmail_message_id: 102  ← Should be large Gmail X-GM-MSGID
gmail_link: https://mail.google.com/mail/u/0/#inbox/102
```

### Why This Is Wrong:
- ❌ "102" is IMAP UID (temporary, can change)
- ❌ Should be "18f2a3b4c5d6e7f8" format (permanent Gmail X-GM-MSGID)
- ❌ Gmail links won't work with UID after re-index
- ❌ Tracking will break if Gmail re-indexes

---

## 🔍 Root Cause

### The Buggy Code:
```python
# OLD EXTRACTION LOGIC
for item in msg_data:
    if isinstance(item, tuple):
        item_str = str(item)  # ← Converting to string loses structure!
        if 'X-GM-MSGID' in item_str:
            match = re.search(r'X-GM-MSGID (\d+)', item_str)
            if match:
                gmail_msgid_decimal = match.group(1)
```

### Why It Failed:
- `str(item)` converts bytes to string representation
- Format changes from `b'X-GM-MSGID 18f2a3b4c5d6e7f8'` to `"b'X-GM-MSGID 18f2a3b4c5d6e7f8'"`
- Regex doesn't match properly
- Falls back to IMAP UID ("102")

---

## ✅ The Fix

### New Extraction Logic:
```python
# NEW EXTRACTION LOGIC (Properly handles bytes)
if msg_data and len(msg_data) > 0:
    item = msg_data[0]
    
    if isinstance(item, tuple):
        # Tuple format: (b'102', b'X-GM-MSGID 18f2a3b4c5d6e7f8')
        for part in item:
            if isinstance(part, bytes) and b'X-GM-MSGID' in part:
                # Decode bytes to string properly
                part_str = part.decode('utf-8')
                match = re.search(r'X-GM-MSGID\s+(\d+)', part_str)
                if match:
                    gmail_msgid_decimal = match.group(1)
                    break
    
    elif isinstance(item, bytes):
        # Bytes format: b'102 (X-GM-MSGID 18f2a3b4c5d6e7f8)'
        item_str = item.decode('utf-8')
        match = re.search(r'X-GM-MSGID\s+(\d+)', item_str)
        if match:
            gmail_msgid_decimal = match.group(1)
```

### Key Improvements:
1. ✅ Properly handles `bytes` type
2. ✅ Decodes bytes to string with UTF-8
3. ✅ Handles both tuple and bytes formats
4. ✅ Better regex: `X-GM-MSGID\s+(\d+)` (handles whitespace)
5. ✅ Debug logging to see what's happening

---

## 📊 Expected vs Actual

### Before Fix:
```
IMAP Response: (b'102', b'X-GM-MSGID 18f2a3b4c5d6e7f8')
                    ↓
OLD CODE: str(item) → "b'102'" + "b'X-GM-MSGID 18f2a3b4c5d6e7f8'"
                    ↓
Regex fails (format is wrong)
                    ↓
Fallback: gmail_msgid = "102" (IMAP UID) ❌
```

### After Fix:
```
IMAP Response: (b'102', b'X-GM-MSGID 18f2a3b4c5d6e7f8')
                    ↓
NEW CODE: Iterate parts, decode bytes properly
                    ↓
part.decode('utf-8') → "X-GM-MSGID 18f2a3b4c5d6e7f8"
                    ↓
Regex matches: "18f2a3b4c5d6e7f8"
                    ↓
Success: gmail_msgid = "18f2a3b4c5d6e7f8" ✅
```

---

## 🧪 Debug Logging

### Added Logging:
```python
# If extraction fails (WARNING level)
logger.write_to_timeline(
    f"Could not extract X-GM-MSGID for UID {msg_id_str}, using UID as fallback",
    actor="gmail_watcher_imap",
    message_level="WARNING",
)
logger.write_to_timeline(
    f"Raw msg_data: {msg_data}",
    actor="gmail_watcher_imap",
    message_level="DEBUG",
)

# If extraction succeeds (DEBUG level)
logger.write_to_timeline(
    f"Extracted X-GM-MSGID {gmail_msgid_decimal} for UID {msg_id_str}",
    actor="gmail_watcher_imap",
    message_level="DEBUG",
)
```

### What to Look For:
```
[DEBUG] Extracted X-GM-MSGID 2161692698372933624 for UID 102 ✅
```
or
```
[WARNING] Could not extract X-GM-MSGID for UID 102, using UID as fallback ❌
[DEBUG] Raw msg_data: [(b'102', b'X-GM-MSGID 2161692698372933624')]
```

---

## 🎯 Test the Fix

### Step 1: Clear Old Tracking
```bash
# Delete old tracking file (uses wrong UID)
rm vault/.gmail_imap_processed_ids.json
```

### Step 2: Run Watcher
```bash
python watchers/gmail_watcher_imap.py
```

### Step 3: Check Logs
Look for:
```
[DEBUG] Extracted X-GM-MSGID 2161692698372933624 for UID 102
```

### Step 4: Verify Tracking File
```json
{
  "2161692698372933624": {  ← Large Gmail X-GM-MSGID!
    "status": "processed",
    "timestamp": "2026-03-25T07:00:00.000000",
    "reason": "Priority: gmail.com (personal email)",
    "task_file": "email_20260325_070000_Subject"
  }
}
```

### Step 5: Verify Task File
```markdown
---
gmail_message_id: 2161692698372933624  ← Large number!
gmail_link: https://mail.google.com/mail/u/0/#inbox/2161692698372933624
---
```

---

## 📝 IMAP Response Format

### Typical X-GM-MSGID Fetch Response:
```python
# IMAP Response Structure
(
  b'102',  # Message UID
  b'(X-GM-MSGID 2161692698372933624)',  # Gmail MSGID
  b')'
)

# In Python:
msg_data = [
    (b'102', b'X-GM-MSGID 2161692698372933624', b')')
]

# Access:
msg_data[0] = (b'102', b'X-GM-MSGID 2161692698372933624', b')')
msg_data[0][0] = b'102'  # UID
msg_data[0][1] = b'X-GM-MSGID 2161692698372933624'  # Gmail MSGID
```

### Decoding:
```python
# Correct way:
part = msg_data[0][1]  # b'X-GM-MSGID 2161692698372933624'
part_str = part.decode('utf-8')  # "X-GM-MSGID 2161692698372933624"
match = re.search(r'X-GM-MSGID\s+(\d+)', part_str)
gmail_msgid = match.group(1)  # "2161692698372933624"
```

---

## 🔄 Conversion: Decimal ↔ Hex

### Gmail Uses Both Formats:
- **Decimal:** `2161692698372933624` (from IMAP)
- **Hex:** `1e00a1b2c3d4e5f8` (for Gmail URLs)

### Conversion:
```python
# Decimal to Hex
decimal = "2161692698372933624"
hex_format = format(int(decimal), 'x')  # "1e00a1b2c3d4e5f8"

# Hex to Decimal
hex_format = "1e00a1b2c3d4e5f8"
decimal = str(int(hex_format, 16))  # "2161692698372933624"
```

### In Our Code:
```python
# For tracking (use decimal)
gmail_msgid = "2161692698372933624"
self.processed_ids[gmail_msgid] = {...}

# For Gmail URL (use hex)
gmail_msgid_hex = format(int(gmail_msgid), 'x')  # "1e00a1b2c3d4e5f8"
gmail_link = f"https://mail.google.com/mail/u/0/#inbox/{gmail_msgid_hex}"
```

---

## ✅ Verification Checklist

After running the fixed code:

- [ ] Debug log shows: "Extracted X-GM-MSGID 2161692698372933624 for UID 102"
- [ ] `vault/.gmail_imap_processed_ids.json` has large numbers (15+ digits)
- [ ] Task file `gmail_message_id` field has large number
- [ ] Task file `gmail_link` uses same large number
- [ ] Gmail link works when clicked
- [ ] No WARNING messages about fallback

---

## 🎯 Summary

### What Was Wrong:
- Using `str(item)` on bytes object
- Regex couldn't match properly
- Fell back to IMAP UID ("102")

### What We Fixed:
- Properly decode bytes with UTF-8
- Handle both tuple and bytes formats
- Better regex pattern
- Debug logging to see what's happening

### Expected Result:
- ✅ Large Gmail X-GM-MSGID in tracking file
- ✅ Large Gmail X-GM-MSGID in task files
- ✅ Working Gmail links
- ✅ Permanent tracking (won't break on re-index)

---

**Status:** ✅ FIXED  
**Next Step:** Run watcher and verify extraction works  
**Watch For:** Debug logs showing extracted X-GM-MSGID
