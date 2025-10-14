# Attendance Sync - Quick Reference

## 🚀 Quick Start

### 1. Setup (One-time)
```bash
bench --site [sitename] execute spotledger_hr.setup.setup_attendance_sync.execute
```

### 2. Configure
- Go to: **Attendance Sync Settings**
- Set: `attendance_db_path` = `/private/files/attendance.db`

### 3. Sync (UI Method - Recommended ⭐)
1. Go to **Bulk Attendance**
2. Click **"Sync from Database"**
3. Configure and click **"Start Sync"**
4. Watch real-time progress!

### 3. Sync (Console Method)
```python
from spotledger_hr.controllers.attendance_controller import sync_attendance
sync_attendance(attendance_db_path='/private/files/attendance.db')
```

---

## 📊 SQLite Database Format

```sql
CREATE TABLE Attendance (
    id INTEGER PRIMARY KEY,
    employee_code TEXT,    -- Exact ERPNext Employee name
    date TEXT,             -- DD-MM-YYYY
    check_in TEXT,         -- HH:MM:SS
    check_out TEXT         -- HH:MM:SS
);
```

**⚠️ Important**: `employee_code` must exactly match ERPNext Employee name!

---

## 💻 Usage Examples

### From Console
```python
from spotledger_hr.controllers.attendance_controller import sync_attendance

# Normal sync
sync_attendance(attendance_db_path='/private/files/attendance.db')

# Force sync from date
sync_attendance(
    attendance_db_path='/private/files/attendance.db',
    force_from_date='2025-01-01 00:00:00'
)
```

### From Browser (F12)
```javascript
frappe.call({
    method: 'spotledger_hr.controllers.attendance_controller.sync_attendance',
    args: { attendance_db_path: '/private/files/attendance.db' },
    callback: (r) => console.log(r.message)
});
```

### Check Status
```python
from spotledger_hr.controllers.attendance_controller import get_sync_status
print(get_sync_status())
```

---

## 🔧 Common Issues

| Issue | Solution |
|-------|----------|
| Employee not found | Verify employee_code matches ERPNext Employee name exactly |
| SQLite error | Check path: `frappe.get_site_path() + '/your/path'` |
| Permission denied | `sudo chown frappe:frappe /path/to/db` |
| No records | Use `force_from_date` parameter |

---

## ✅ Key Features

- ✅ **No custom fields needed** - Uses standard ERPNext fields
- ✅ **Duplicate prevention** - Automatic via unique index
- ✅ **Overnight shifts** - Handles automatically
- ✅ **Progress tracking** - Real-time during sync
- ✅ **Error logging** - Comprehensive error details
- ✅ **Auto-attendance** - Creates Attendance records automatically

---

## 📁 Files

- **Main**: `spotledger_hr/controllers/attendance_controller.py`
- **Setup**: `spotledger_hr/setup/setup_attendance_sync.py`
- **Docs**: 
  - `ATTENDANCE_SYNC_MIGRATION.md` (technical)
  - `ATTENDANCE_SYNC_USAGE.md` (user guide)
  - `ATTENDANCE_SYNC_SUMMARY.md` (overview)

---

## 🔄 Flow

```
SQLite DB → Employee Checkin (IN/OUT) → Attendance → Calculations
```

---

## 📝 Response Format

```json
{
    "success": true,
    "total_records": 100,
    "successful": 98,
    "failed": 2,
    "errors": [...],
    "last_sync_time": "2025-10-13 14:30:00"
}
```

---

## 🎯 Production Checklist

- [ ] Run setup script
- [ ] Configure Attendance Sync Settings  
- [ ] Test with sample data
- [ ] Verify Employee Checkin created
- [ ] Verify Attendance auto-created
- [ ] Check calculations (overtime, deficiency)
- [ ] Set up auto-sync (optional)
- [ ] Monitor error logs

---

## 🔗 Quick Links

| Task | Command |
|------|---------|
| Setup | `bench --site [site] execute spotledger_hr.setup.setup_attendance_sync.execute` |
| Sync | `frappe.call('spotledger_hr.controllers.attendance_controller.sync_attendance', ...)` |
| Status | `frappe.call('spotledger_hr.controllers.attendance_controller.get_sync_status')` |
| Console | `bench --site [site] console` |

---

**Need help?** Check `ATTENDANCE_SYNC_USAGE.md` for detailed examples.

