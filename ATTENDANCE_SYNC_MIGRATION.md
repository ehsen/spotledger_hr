# Attendance Sync Migration Guide

## Overview
The `sync_attendance` function has been migrated from the legacy system to the new attendance controller. The key difference is that instead of creating "Gate Entry" documents, the new system creates "Employee Checkin" records which integrate seamlessly with ERPNext HRMS.

## Key Changes

### 1. **From Gate Entry to Employee Checkin**
- **Legacy**: Created single "Gate Entry" documents with both check-in and check-out times
- **New**: Creates two separate "Employee Checkin" records:
  - One with `log_type = "IN"` for check-in
  - One with `log_type = "OUT"` for check-out

### 2. **Location of Code**
- **File**: `apps/spotledger_hr/spotledger_hr/controllers/attendance_controller.py`
- **Main Function**: `sync_attendance(attendance_db_path, sync_tracker_name=None)`

### 3. **Helper Functions Added**
- `fetch_attendance_data_from_sqlite()` - Reads from SQLite database
- `get_date_from_string()` - Converts date strings to date objects
- `convert_to_datetime()` - Combines date and time strings
- `validate_employee_code()` - Validates employee codes (supports breeze_code field)
- `validate_check_in_time()` - Validates and converts check-in times
- `validate_check_out_time()` - Validates check-out times (handles overnight shifts)
- `is_checkin_exists()` - Checks for duplicate records
- `create_employee_checkin_records()` - Creates Employee Checkin records
- `get_sync_status()` - Gets current sync status

## Required Setup

### 1. **No Custom Fields Required!**

The new implementation uses standard ERPNext fields:
- **Employee Checkin** uses the standard `time` field for check-in/out times
- **Employee codes** from SQLite directly match ERPNext Employee names (no mapping needed)

### 2. **Attendance Sync Settings (Single DocType)**

Create a new Single DocType called "Attendance Sync Settings" with:

```python
{
    'fieldname': 'last_sync_time',
    'label': 'Last Sync Time',
    'fieldtype': 'Datetime'
}
```

Alternatively, modify the sync function to use a different tracking mechanism based on your requirements.

## Usage

### Basic Sync Call

```python
# From Python
frappe.call({
    method: 'spotledger_hr.controllers.attendance_controller.sync_attendance',
    args: {
        attendance_db_path: '/path/to/attendance.sqlite',
        sync_tracker_name: 'Your Company Name'  # Optional
    }
})
```

### From JavaScript/Client

```javascript
frappe.call({
    method: 'spotledger_hr.controllers.attendance_controller.sync_attendance',
    args: {
        attendance_db_path: '/path/to/attendance.sqlite'
    },
    callback: function(r) {
        if (r.message.success) {
            frappe.msgprint('Sync completed successfully');
        }
    }
});
```

### Check Sync Status

```python
frappe.call({
    method: 'spotledger_hr.controllers.attendance_controller.get_sync_status',
    callback: function(r) {
        console.log('Last Sync:', r.message.last_sync_time);
        console.log('Recent Checkins (7 days):', r.message.recent_checkins_7days);
    }
});
```

## SQLite Database Format

The function expects SQLite database with the following structure:

```sql
CREATE TABLE Attendance (
    id INTEGER PRIMARY KEY,
    employee_code TEXT,
    date TEXT,  -- Format: DD-MM-YYYY
    check_in TEXT,  -- Format: HH:MM:SS
    check_out TEXT  -- Format: HH:MM:SS
);
```

## Features

### 1. **Duplicate Prevention**
- Checks for existing Employee Checkin records using `employee + time + log_type` combination
- Prevents duplicate sync of the same records
- Database unique index ensures data integrity

### 2. **Employee Validation**
- Employee codes from SQLite directly match ERPNext Employee names
- Simple validation: checks if Employee exists
- Logs errors for employees not found

### 3. **Overnight Shift Handling**
- Automatically detects when check-out is before check-in
- Adds one day to check-out time for overnight shifts

### 4. **Progress Tracking**
- Shows real-time progress during sync
- Displays percentage and current record number

### 5. **Error Handling**
- Comprehensive error logging
- Returns detailed error information
- Continues processing even if individual records fail

### 6. **Statistics and Reporting**
- Returns total records processed
- Counts successful and failed syncs
- Provides detailed error list

## Response Format

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

## Migration Steps

1. **Run Setup Script** to create Attendance Sync Settings DocType and database indexes:
   ```bash
   bench --site [sitename] execute spotledger_hr.setup.setup_attendance_sync.execute
   ```

2. **Configure Attendance Sync Settings**:
   - Go to Attendance Sync Settings in ERPNext
   - Set the `attendance_db_path` (relative to site path, e.g., `/private/files/attendance.db`)
   - Configure sync frequency if using automatic sync

3. **Ensure Employee Names Match**: 
   - Employee codes in SQLite database must exactly match ERPNext Employee names
   - No custom field mapping required

4. **Test Manual Sync** with sample data before production deployment

5. **Set up Scheduled Sync** (optional) using Frappe's scheduler

## Scheduled Job Example

```python
# In hooks.py
scheduler_events = {
    "cron": {
        "0 */2 * * *": [  # Every 2 hours
            "spotledger_hr.controllers.attendance_controller.sync_attendance"
        ]
    }
}
```

## Important Notes

1. **Database Path**: The path is relative to the Frappe site path
2. **Permissions**: The function uses `ignore_permissions=True` for system-level sync
3. **Transaction Management**: Uses `frappe.db.commit()` after updating sync time
4. **Progress Publishing**: Works in background jobs and shows real-time progress
5. **Error Logging**: All errors are logged to Error Log DocType

## Troubleshooting

### Issue: "No last sync time found"
**Solution**: This is normal on first sync. The system will sync all records from 2020-01-01. After the first sync, it will track the last sync time.

### Issue: "Employee not found"
**Solution**: 
- Ensure employee codes in SQLite database exactly match ERPNext Employee names
- Check Employee list in ERPNext to verify the employee exists
- The employee_code field in SQLite should be the exact Employee name in ERPNext

### Issue: "SQLite error"
**Solution**: 
- Check database path is correct and relative to site path
- Verify file permissions (readable by frappe user)
- Test database path: `frappe.get_site_path() + '/your/path/to/attendance.db'`

### Issue: Duplicate checkins appearing
**Solution**: 
- The unique index should prevent duplicates automatically
- If duplicates exist, run: `bench --site [sitename] execute spotledger_hr.setup.setup_attendance_sync.add_unique_index_for_checkins`
- Manually remove duplicate Employee Checkin records before running sync again

## Next Steps

After migration:
1. The Employee Checkin records will automatically create Attendance records (via ERPNext HRMS auto-attendance feature)
2. Attendance records will trigger the attendance calculation using the Attendance Rule Engine
3. All calculations (overtime, deficiency, etc.) will be automatically applied

