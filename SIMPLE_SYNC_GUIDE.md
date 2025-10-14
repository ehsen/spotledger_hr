# Simple Attendance Sync Guide 📤

## Super Simple! Just 3 Steps:

### Step 1: Open Bulk Attendance
Go to: **Bulk Attendance** in ERPNext

### Step 2: Click "Sync Attendance"
Look for the **"Sync Attendance"** button and click it

### Step 3: Upload & Sync
1. **Upload Database File**: Click "Choose File" and select your attendance database file (.db or .sqlite)
2. (Optional) Adjust batch size if needed (default: 50)
3. (Optional) Set re-sync date if you want to re-process old records
4. Click **"Start Sync"**

That's it! ✨

---

## What Happens Next?

You'll see a live progress dialog showing:
- ✅ Progress bar with percentage
- ✅ Real-time success/failed counts
- ✅ Current status
- ✅ Any errors (if they occur)

The screen **won't freeze** - you can see everything happening in real-time!

---

## Troubleshooting

### Issue: Dialog closes but nothing happens
**Solution**: 
1. Open browser console (F12)
2. Look for any error messages
3. Check the console logs to see what's happening

### Issue: "File not found" error
**Solution**: Make sure you've uploaded a valid SQLite database file (.db or .sqlite)

### Issue: "Employee not found" errors
**Solution**: Employee codes in the database must exactly match ERPNext Employee names

### Issue: Sync is slow
**Solution**: Increase the batch size (try 100 or 200 instead of 50)

---

## Advanced Options

### Batch Size
- **Small (20-30)**: Slower but safer, commits more frequently
- **Medium (50)**: Default, good balance
- **Large (100-200)**: Faster but commits less frequently

### Re-sync from Date
- Leave empty to sync only new records
- Set a date to re-process records from that date onwards
- Format: `YYYY-MM-DD HH:MM:SS`

---

## Database File Format

Your SQLite file should have this structure:

```sql
CREATE TABLE Attendance (
    id INTEGER PRIMARY KEY,
    employee_code TEXT,    -- Must match ERPNext Employee name
    date TEXT,             -- Format: DD-MM-YYYY
    check_in TEXT,         -- Format: HH:MM:SS
    check_out TEXT         -- Format: HH:MM:SS
);
```

---

## Example Workflow

```
User Action                     What Happens
────────────────────────────────────────────────────────
1. Click "Sync Attendance"  →  Dialog opens

2. Upload database file     →  File uploaded to server

3. Click "Start Sync"       →  Progress dialog appears
                                
                                ┌─────────────────────┐
                                │ Syncing Attendance  │
                                │                     │
                                │ [████████░░] 75%   │
                                │                     │
                                │ Processing...       │
                                │ Success: 73         │
                                │ Failed: 2           │
                                └─────────────────────┘

4. Sync completes          →  Shows final results
                               Form reloads with new data
```

---

## What Gets Created?

For each record in your database:
1. **Employee Checkin (IN)** - Check-in record
2. **Employee Checkin (OUT)** - Check-out record
3. **Attendance** - Auto-created by ERPNext from checkins
4. **Calculations** - Overtime, deficiency, etc. (automatic)

---

## Tips for Success

✅ **DO:**
- Use valid SQLite database files
- Ensure employee codes match ERPNext Employee names
- Check progress dialog for real-time status
- Review error messages if any appear
- Start with small files to test

❌ **DON'T:**
- Close the progress dialog while syncing
- Upload non-database files
- Use employee codes that don't exist in ERPNext
- Panic if some records fail (check Error Log for details)

---

## Success Indicators

### All Good ✅
- Progress bar turns **green**
- "Completed" status shown
- Success count matches total records
- Form reloads with new data

### Partial Success ⚠️
- Progress bar turns **orange/yellow**
- Some records failed
- Error details shown in dialog
- Check Error Log for full details

### Failed ❌
- Progress bar turns **red**
- Error message displayed
- Check console logs (F12)
- Verify file and database format

---

## Need More Help?

1. **Check Console Logs** (F12) for detailed debugging info
2. **Review Error Log** in ERPNext for failed records
3. **Verify Database Format** matches the required structure
4. **Check Employee Names** match between systems

---

**Remember:** The process is designed to be resilient. Even if some records fail, successfully synced records are saved!


