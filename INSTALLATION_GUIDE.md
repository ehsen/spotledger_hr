# Attendance Rules Implementation - Installation Guide

## 🚀 Quick Start

This guide will help you install and configure the enhanced Attendance Rule Engine for ERPNext 15 HRMS.

## 📋 Prerequisites

- ERPNext 15.x installed and running
- SpotLedger HR app installed
- Python 3.8+ with required dependencies
- Database access for custom field installation

## 🔧 Installation Steps

### Step 1: Install Custom Fields

```bash
# Navigate to your Frappe bench
cd /path/to/your/frappe-bench

# Install custom fields for Attendance DocType
bench --site your-site-name migrate
```

### Step 2: Verify Installation

```bash
# Check if custom fields are installed
bench --site your-site-name console

# In the console, run:
frappe.get_doc("DocType", "Attendance").fields
```

You should see the new custom fields:
- `custom_regular_hours`
- `custom_overtime_hours`
- `custom_deficiency_hours`
- `custom_total_hours`
- `custom_break_duration_minutes`
- `custom_is_friday`
- `custom_is_gazetted_holiday`
- `custom_adjusted_check_in`
- `custom_adjusted_check_out`
- `custom_attendance_rule_applied`
- `custom_calculation_timestamp`

### Step 3: Create Attendance Rule

```bash
# Create attendance rule via console or UI
bench --site your-site-name console
```

```python
# Create attendance rule
attendance_rule = frappe.get_doc({
    "doctype": "Attendance Rule",
    "company": "Your Company",
    "factory_start_time": "07:30:00",
    "factory_end_time": "16:00:00",
    "required_factory_hours": 8.5,
    "checkin_grace_minutes": 10,
    "checkin_max_grace_minutes": 30,
    "checkout_grace_minutes": 5,
    "checkout_max_grace_minutes": 20,
    "break_duration_minutes": 30,
    "regular_break_start": "12:00:00",
    "regular_break_end": "12:30:00",
    "friday_break_start": "12:30:00",
    "friday_break_end": "14:00:00",
    "gazetted_overtime_multiplier": 2.0,
    "force_hours_on_friday": True,
    "allow_negative_hours": False,
    "enable_friday_logic": True,
    "consider_check_out_next_day": True,
    "allow_absent_on_holiday": False,
    "ignore_break_in_overtime": False
})
attendance_rule.insert()
```

### Step 4: Assign Attendance Rule to Employees

```python
# Assign attendance rule to employees
employees = frappe.get_all("Employee", filters={"company": "Your Company"})

for emp in employees:
    employee_doc = frappe.get_doc("Employee", emp.name)
    employee_doc.custom_attendance_rule = "Your Company"
    employee_doc.save()
```

### Step 5: Test the Implementation

```bash
# Run tests to verify installation
cd apps/spotledger_hr
python spotledger_hr/tests/run_tests.py
```

## 🧪 Testing

### Run All Tests
```bash
python spotledger_hr/tests/run_tests.py
```

### Run Specific Test Categories
```bash
# Test attendance rule engine
python spotledger_hr/tests/run_tests.py TestAttendanceRuleEngine

# Test grace period logic
python spotledger_hr/tests/run_tests.py TestGracePeriodLogic

# Test break calculations
python spotledger_hr/tests/run_tests.py TestBreakCalculations

# Test overtime calculations
python spotledger_hr/tests/run_tests.py TestOvertimeCalculations

# Test deficiency calculations
python spotledger_hr/tests/run_tests.py TestDeficiencyCalculations

# Test Friday logic
python spotledger_hr/tests/run_tests.py TestFridayLogic

# Test overnight shifts
python spotledger_hr/tests/run_tests.py TestOvernightShifts

# Test complete attendance calculations
python spotledger_hr/tests/run_tests.py TestCompleteAttendanceCalculations

# Test edge cases
python spotledger_hr/tests/run_tests.py TestEdgeCases

# Test attendance controller
python spotledger_hr/tests/run_tests.py TestAttendanceController

# Test API functions
python spotledger_hr/tests/run_tests.py TestAttendanceControllerAPI

# Test integration
python spotledger_hr/tests/run_tests.py TestAttendanceControllerIntegration
```

### Run Specific Test Methods
```bash
# Test specific method
python spotledger_hr/tests/run_tests.py TestAttendanceRuleEngine test_engine_initialization
```

## 🔍 Verification

### 1. Check Attendance Rule Engine
```python
from spotledger_hr.attendance_rule_engine import AttendanceRuleEngine

# Test basic functionality
engine = AttendanceRuleEngine("EMP-001", "2024-01-15")
summary = engine.calculate_attendance_summary("07:30:00", "16:00:00")
print(summary)
```

### 2. Check API Functions
```python
import frappe

# Test attendance preview
result = frappe.call(
    "spotledger_hr.controllers.attendance_controller.calculate_attendance_preview",
    employee="EMP-001",
    attendance_date="2024-01-15",
    check_in="2024-01-15 07:30:00",
    check_out="2024-01-15 16:00:00"
)
print(result)
```

### 3. Check Custom Fields
```python
# Create test attendance record
attendance = frappe.get_doc({
    "doctype": "Attendance",
    "employee": "EMP-001",
    "attendance_date": "2024-01-15",
    "check_in": "2024-01-15 07:30:00",
    "check_out": "2024-01-15 16:00:00",
    "status": "Present"
})
attendance.insert()

# Check if custom fields are populated
print(f"Regular Hours: {attendance.custom_regular_hours}")
print(f"Overtime Hours: {attendance.custom_overtime_hours}")
print(f"Deficiency Hours: {attendance.custom_deficiency_hours}")
print(f"Total Hours: {attendance.custom_total_hours}")
print(f"Is Friday: {attendance.custom_is_friday}")
print(f"Is Gazetted Holiday: {attendance.custom_is_gazetted_holiday}")
```

## ⚙️ Configuration

### Attendance Rule Parameters

| Parameter | Description | Default | Example |
|-----------|-------------|---------|---------|
| `factory_start_time` | Factory start time | Required | "07:30:00" |
| `factory_end_time` | Factory end time | Required | "16:00:00" |
| `required_factory_hours` | Required working hours | 8.5 | 8.5 |
| `checkin_grace_minutes` | Check-in grace period | 10 | 10 |
| `checkin_max_grace_minutes` | Max check-in grace | 30 | 30 |
| `checkout_grace_minutes` | Check-out grace period | 5 | 5 |
| `checkout_max_grace_minutes` | Max check-out grace | 20 | 20 |
| `break_duration_minutes` | Break duration | 30 | 30 |
| `regular_break_start` | Regular break start | "12:00:00" | "12:00:00" |
| `regular_break_end` | Regular break end | "12:30:00" | "12:30:00" |
| `friday_break_start` | Friday break start | "12:30:00" | "12:30:00" |
| `friday_break_end` | Friday break end | "14:00:00" | "14:00:00" |
| `gazetted_overtime_multiplier` | Holiday overtime multiplier | 2.0 | 2.0 |
| `force_hours_on_friday` | Force full hours on Friday | True | True |
| `allow_negative_hours` | Allow negative hours | False | False |
| `enable_friday_logic` | Enable Friday special logic | True | True |
| `consider_check_out_next_day` | Allow overnight shifts | True | True |
| `allow_absent_on_holiday` | Mark absent on holiday | False | False |
| `ignore_break_in_overtime` | Ignore break in overtime | False | False |

## 🚨 Troubleshooting

### Common Issues

#### 1. Custom Fields Not Installed
**Error**: `AttributeError: 'Attendance' object has no attribute 'custom_regular_hours'`

**Solution**:
```bash
# Reinstall custom fields
bench --site your-site-name migrate
```

#### 2. Attendance Rule Not Found
**Error**: `No Attendance Rule set for Employee: EMP-001`

**Solution**:
```python
# Assign attendance rule to employee
employee = frappe.get_doc("Employee", "EMP-001")
employee.custom_attendance_rule = "Your Company"
employee.save()
```

#### 3. Invalid Configuration
**Error**: `Check-in grace minutes cannot be greater than max grace minutes`

**Solution**:
```python
# Fix attendance rule configuration
rule = frappe.get_doc("Attendance Rule", "Your Company")
rule.checkin_grace_minutes = 10
rule.checkin_max_grace_minutes = 30
rule.save()
```

#### 4. Tests Failing
**Error**: Test failures during installation verification

**Solution**:
```bash
# Check test data setup
python spotledger_hr/tests/run_tests.py TestAttendanceRuleEngine test_engine_initialization

# Check if test data is created properly
bench --site your-site-name console
```

### Debug Mode

Enable debug mode for detailed logging:

```python
import frappe
frappe.conf.developer_mode = 1

# Your code here
```

## 📊 Performance Optimization

### 1. Database Indexing
```sql
-- Add indexes for better performance
CREATE INDEX idx_attendance_employee_date ON `tabAttendance` (employee, attendance_date);
CREATE INDEX idx_attendance_rule_company ON `tabAttendance Rule` (company);
```

### 2. Caching
```python
# Enable caching for attendance rules
from frappe.cache_manager import cache

@cache.cache
def get_attendance_rule(employee):
    # Your code here
    pass
```

### 3. Bulk Operations
```python
# Use bulk operations for multiple records
attendance_records = [...]
result = frappe.call(
    "spotledger_hr.controllers.attendance_controller.bulk_calculate_attendance",
    attendance_records=attendance_records
)
```

## 🔄 Updates and Maintenance

### Updating the Implementation
```bash
# Pull latest changes
cd apps/spotledger_hr
git pull origin main

# Run migrations
bench --site your-site-name migrate

# Run tests
python spotledger_hr/tests/run_tests.py
```

### Regular Maintenance
```bash
# Check system health
bench --site your-site-name doctor

# Optimize database
bench --site your-site-name optimize

# Backup before updates
bench --site your-site-name backup
```

## 📞 Support

For support and questions:

1. **Check Documentation**: Review `ATTENDANCE_RULES_IMPLEMENTATION.md`
2. **Run Tests**: Verify installation with test suite
3. **Check Logs**: Review error logs for issues
4. **Contact Support**: Reach out to development team

## 🎉 Success!

If all tests pass and verification steps complete successfully, your Attendance Rule Engine is ready for production use!

### Next Steps

1. **Configure Attendance Rules** for your organization
2. **Assign Rules to Employees** 
3. **Test with Real Data** in a staging environment
4. **Train Users** on the new functionality
5. **Monitor Performance** and optimize as needed

---

**Congratulations!** You have successfully installed and configured the enhanced Attendance Rule Engine for ERPNext 15 HRMS. 🎊
