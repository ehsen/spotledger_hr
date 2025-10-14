# Attendance Sync - Quick Start Guide

## Overview

The attendance sync system reads attendance data from an external SQLite database and creates Employee Checkin records in ERPNext. These checkins automatically trigger attendance record creation with all calculations.

## Prerequisites

1. **SQLite Database**: Your external attendance database with the following structure:
   ```sql
   CREATE TABLE Attendance (
       id INTEGER PRIMARY KEY,
       employee_code TEXT,    -- Must match ERPNext Employee name
       date TEXT,             -- Format: DD-MM-YYYY
       check_in TEXT,         -- Format: HH:MM:SS
       check_out TEXT         -- Format: HH:MM:SS
   );
   ```

2. **Employee Names**: Employee codes in SQLite must exactly match ERPNext Employee names

## Setup (One-time)

### Step 1: Run Setup Script

```bash
bench --site [your-site-name] console
```

Then in the console:
```python
from spotledger_hr.setup.setup_attendance_sync import execute
execute()
```

This creates:
- Attendance Sync Settings DocType
- Unique database index to prevent duplicates

### Step 2: Configure Settings

1. Go to: **Attendance Sync Settings** in ERPNext
2. Set **Attendance Database Path**: `/private/files/attendance.db` (or your path, relative to site)
3. Optionally enable auto-sync and set frequency

## Usage

### Method 1: UI-Based Sync (Recommended) ⭐

The easiest way to sync with real-time progress indication:

1. Go to **Bulk Attendance** DocType
2. Click **"Sync from Database"** button
3. Configure sync parameters:
   - **Database Path**: `/private/files/attendance.db`
   - **Batch Size**: `50` (default)
   - **Force Sync Date**: Optional
4. Click **"Start Sync"**
5. Watch real-time progress with live statistics!

**Benefits**:
- ✅ No screen freeze
- ✅ Real-time progress bar
- ✅ Live success/failed counts
- ✅ Batch commits (safer)
- ✅ Error details shown inline
- ✅ User-friendly interface

### Method 2: Manual Sync from Console

```bash
bench --site [your-site-name] console
```

```python
# Import the function
from spotledger_hr.controllers.attendance_controller import sync_attendance

# Sync using path from settings
result = sync_attendance(attendance_db_path='/private/files/attendance.db')

# Or force sync from a specific date
result = sync_attendance(
    attendance_db_path='/private/files/attendance.db',
    force_from_date='2025-01-01 00:00:00'
)

# Check result
print(result)
```

### Method 2: From Browser Console (Frappe Desk)

Open browser console (F12) and run:

```javascript
frappe.call({
    method: 'spotledger_hr.controllers.attendance_controller.sync_attendance',
    args: {
        attendance_db_path: '/private/files/attendance.db'
    },
    callback: function(r) {
        console.log(r.message);
        if (r.message.success) {
            frappe.msgprint(`Synced ${r.message.successful} records successfully!`);
        }
    }
});
```

### Method 3: Create a Custom Button

Add to your DocType or Page:

```javascript
frappe.ui.form.on('Your DocType', {
    refresh: function(frm) {
        frm.add_custom_button(__('Sync Attendance'), function() {
            frappe.call({
                method: 'spotledger_hr.controllers.attendance_controller.sync_attendance',
                args: {
                    attendance_db_path: '/private/files/attendance.db'
                },
                freeze: true,
                freeze_message: __('Syncing attendance records...'),
                callback: function(r) {
                    if (r.message.success) {
                        frappe.msgprint(__('Successfully synced {0} records', [r.message.successful]));
                        frm.reload_doc();
                    }
                }
            });
        });
    }
});
```

## Check Sync Status

### From Console:
```python
from spotledger_hr.controllers.attendance_controller import get_sync_status

status = get_sync_status()
print(status)
```

### From Browser:
```javascript
frappe.call({
    method: 'spotledger_hr.controllers.attendance_controller.get_sync_status',
    callback: function(r) {
        console.log('Last Sync:', r.message.last_sync_time);
        console.log('Total Synced:', r.message.total_synced_records);
        console.log('Recent Checkins (7 days):', r.message.recent_checkins_7days);
    }
});
```

## Scheduled Auto-Sync

### Add to hooks.py

```python
# hooks.py

scheduler_events = {
    "cron": {
        "0 */2 * * *": [  # Every 2 hours
            "spotledger_hr.tasks.auto_sync_attendance"
        ]
    }
}
```

### Create tasks.py

```python
# spotledger_hr/tasks.py

import frappe
from spotledger_hr.controllers.attendance_controller import sync_attendance

def auto_sync_attendance():
    """Auto sync attendance from external database"""
    try:
        # Get database path from settings
        db_path = frappe.db.get_single_value('Attendance Sync Settings', 'attendance_db_path')
        auto_sync_enabled = frappe.db.get_single_value('Attendance Sync Settings', 'enable_auto_sync')
        
        if auto_sync_enabled and db_path:
            result = sync_attendance(attendance_db_path=db_path)
            frappe.logger().info(f"Auto sync completed: {result}")
        else:
            frappe.logger().info("Auto sync disabled or database path not set")
            
    except Exception as e:
        frappe.log_error(f"Auto sync failed: {str(e)}", "Auto Attendance Sync Error")
```

## Understanding the Flow

1. **Sync reads SQLite** → Fetches records after last sync time
2. **Creates Employee Checkin** → Two records per attendance (IN and OUT)
3. **ERPNext Auto-Attendance** → Converts checkins to Attendance records
4. **Attendance Rules Applied** → Calculates overtime, deficiency, etc.

## Important Notes

### Employee Code Mapping
- The `employee_code` in SQLite **must exactly match** the ERPNext Employee name
- No custom mapping or breeze_code field needed
- Example: If SQLite has `employee_code = "HR-EMP-00001"`, then ERPNext must have an Employee with name `"HR-EMP-00001"`

### Duplicate Prevention
- The system checks for existing checkins using: `employee + time + log_type`
- A unique database index prevents duplicates
- Safe to run sync multiple times - no duplicates will be created

### Overnight Shifts
- Automatically handled: If check-out time is before check-in time, the system adds 1 day to check-out
- Example: Check-in at 23:00, Check-out at 02:00 → Correctly calculated as 3 hours

### Date Format
- SQLite date format: `DD-MM-YYYY` (e.g., "13-10-2025")
- Time format: `HH:MM:SS` (e.g., "08:30:00")

## Response Format

Successful sync returns:
```json
{
    "success": true,
    "total_records": 100,
    "successful": 98,
    "failed": 2,
    "skipped": 0,
    "errors": [
        {
            "employee_code": "EMP001",
            "date": "2025-01-15",
            "error": "Employee not found: EMP001"
        }
    ],
    "last_sync_time": "2025-10-13 14:30:00"
}
```

## Troubleshooting

### Error: "Employee not found"
**Cause**: Employee code in SQLite doesn't match any ERPNext Employee name  
**Fix**: Ensure employee codes match exactly (case-sensitive)

### Error: "SQLite error: unable to open database file"
**Cause**: Database path is incorrect or file doesn't exist  
**Fix**: Verify path is relative to site directory: `frappe.get_site_path() + '/your/path'`

### Error: "Permission denied"
**Cause**: Database file not readable by frappe user  
**Fix**: 
```bash
sudo chown frappe:frappe /path/to/attendance.db
sudo chmod 644 /path/to/attendance.db
```

### No records synced
**Cause**: All records are before last_sync_time  
**Fix**: Use `force_from_date` parameter to sync from specific date

### Duplicate checkins (shouldn't happen)
**Cause**: Unique index not created  
**Fix**: 
```bash
bench --site [sitename] console
```
```python
from spotledger_hr.setup.setup_attendance_sync import add_unique_index_for_checkins
add_unique_index_for_checkins()
```

## Testing

### Test with sample data:

1. Create test SQLite database:
```python
import sqlite3
from datetime import datetime, timedelta

conn = sqlite3.connect('/tmp/test_attendance.db')
cursor = conn.cursor()

cursor.execute('''
    CREATE TABLE Attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_code TEXT,
        date TEXT,
        check_in TEXT,
        check_out TEXT
    )
''')

# Add test record (use actual employee name from your ERPNext)
cursor.execute('''
    INSERT INTO Attendance (employee_code, date, check_in, check_out)
    VALUES ('HR-EMP-00001', '13-10-2025', '08:30:00', '17:00:00')
''')

conn.commit()
conn.close()
```

2. Copy to site directory:
```bash
cp /tmp/test_attendance.db ~/frappe-bench/sites/[your-site]/private/files/
```

3. Run sync:
```python
from spotledger_hr.controllers.attendance_controller import sync_attendance
result = sync_attendance(attendance_db_path='/private/files/test_attendance.db')
print(result)
```

4. Verify Employee Checkin records created

## Production Deployment

1. ✅ Test with sample data
2. ✅ Verify employee name mapping
3. ✅ Run initial sync manually
4. ✅ Check created Employee Checkin records
5. ✅ Verify Attendance records auto-created
6. ✅ Configure Attendance Sync Settings
7. ✅ Enable auto-sync if needed
8. ✅ Monitor error logs initially

## Support

For issues or questions:
- Check Error Log DocType in ERPNext
- Review `frappe.log_error()` entries
- Verify SQLite database structure matches expected format
- Ensure Employee names match between systems

