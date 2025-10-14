# Attendance Rules Implementation Documentation

## Overview

This document provides comprehensive documentation for the enhanced Attendance Rule Engine implementation, which integrates all legacy attendance calculation logic into ERPNext 15 HRMS.

## Architecture

### Components

1. **Attendance Rule Engine** (`attendance_rule_engine.py`)
   - Core calculation engine with all legacy logic
   - Comprehensive attendance metrics calculation
   - Support for all attendance rules and edge cases

2. **Custom Attendance Controller** (`controllers/attendance_controller.py`)
   - ERPNext integration layer
   - Custom validation and calculation hooks
   - API endpoints for attendance operations

3. **Custom Fields** (`fixtures/custom_field_attendance.json`)
   - Extended Attendance DocType with calculated fields
   - Read-only fields for attendance metrics
   - Integration with ERPNext workflows

4. **Comprehensive Test Suite**
   - Unit tests for all calculation methods
   - Integration tests for ERPNext workflows
   - Edge case and error condition testing

## Attendance Rules Implementation

### 1. Basic Shift Rules

```python
# Factory timing configuration
factory_start_time: "07:30:00"
factory_end_time: "16:00:00"
required_factory_hours: 8.5
```

### 2. Grace Period Rules

#### Check-in Grace Logic
- **Within Grace Period** (≤ 10 minutes): Adjusted to factory start time
- **Between Grace and Max** (10-30 minutes): Adjusted to max grace time
- **Beyond Max Grace** (> 30 minutes): Actual check-in time

#### Check-out Grace Logic
- **Within Grace Period** (≤ 5 minutes): Adjusted to factory end time
- **Between Grace and Max** (5-20 minutes): Adjusted to max grace time
- **Beyond Max Grace** (> 20 minutes): Actual check-out time

### 3. Break Time Rules

#### Regular Day Break Logic
- **Break Duration**: 30 minutes (12:00-12:30)
- **No Break Deduction**: If checkout before break start OR checkin after break start
- **Full Break Deduction**: If checkout after break end

#### Friday Break Logic
- **Break Duration**: 90 minutes (12:30-14:00)
- **Special Prayer Break Handling**: Checkout during prayer break adjusted to factory end time
- **Different Break Times**: Separate break schedule for Fridays

### 4. Overtime Calculation Rules

#### Regular Day Overtime
```python
overtime = total_hours - required_factory_hours
```

#### Friday Overtime
```python
overtime = total_hours - required_factory_hours - (break_duration * ignore_break_factor)
```

#### Gazetted Holiday Overtime
```python
overtime = total_hours * gazetted_overtime_multiplier
```

### 5. Deficiency Calculation Rules

#### Regular Day Deficiency
```python
deficiency = required_factory_hours - total_hours
```

#### Friday Deficiency
- **Force Hours Enabled**: Same as regular day
- **Force Hours Disabled**: Same as regular day (current implementation)

#### Negative Hours Handling
- **Allowed**: Calculate actual deficiency
- **Not Allowed**: Return 0 for deficiency

### 6. Overnight Shift Rules

#### Next Day Checkout Detection
```python
if check_out < check_in:
    # Adjust checkout to next day
    adjusted_checkout = next_day + check_out_time
```

### 7. Holiday Rules

#### Gazetted Holiday Detection
- Integration with ERPNext Holiday List
- Special overtime calculation for holiday work
- No deficiency calculation on holidays

## API Reference

### Attendance Rule Engine

#### `AttendanceRuleEngine(employee, attendance_date)`
Initialize the attendance rule engine for a specific employee and date.

**Parameters:**
- `employee` (str): Employee ID
- `attendance_date` (str): Attendance date in YYYY-MM-DD format

**Methods:**

##### `calculate_attendance_summary(check_in_time, check_out_time)`
Calculate comprehensive attendance summary with all metrics.

**Parameters:**
- `check_in_time` (str): Check-in time in HH:MM:SS format
- `check_out_time` (str): Check-out time in HH:MM:SS format

**Returns:**
```python
{
    'total_hours': float,
    'regular_hours': float,
    'overtime_hours': float,
    'deficiency_hours': float,
    'is_friday': bool,
    'is_gazetted_holiday': bool,
    'adjusted_check_in': datetime,
    'adjusted_check_out': datetime,
    'break_duration_minutes': int
}
```

##### `get_time_after_grace_in(check_in_time)`
Calculate adjusted check-in time after applying grace period logic.

##### `get_time_after_grace_out(check_out_time)`
Calculate adjusted check-out time after applying grace period logic.

##### `get_break_duration(check_in_time, check_out_time)`
Calculate break duration based on check-in/out times.

##### `calculate_regular_hours(check_in_time, check_out_time)`
Calculate regular working hours after break deduction.

##### `calculate_overtime(check_in_time, check_out_time)`
Calculate overtime hours based on attendance rules.

##### `calculate_deficiency(check_in_time, check_out_time)`
Calculate deficiency hours (shortfall from required hours).

##### `handle_overnight_shift(check_in_time, check_out_time)`
Handle overnight shifts by adjusting checkout to next day if needed.

### Attendance Controller API

#### `calculate_attendance_preview(employee, attendance_date, check_in, check_out)`
Calculate attendance preview without saving.

**Parameters:**
- `employee` (str): Employee ID
- `attendance_date` (str): Attendance date
- `check_in` (str): Check-in datetime
- `check_out` (str): Check-out datetime

**Returns:**
```python
{
    'success': bool,
    'data': attendance_summary_dict
}
```

#### `bulk_calculate_attendance(attendance_records)`
Bulk calculate attendance for multiple records.

**Parameters:**
- `attendance_records` (list): List of attendance records

**Returns:**
```python
{
    'success': bool,
    'results': list,
    'errors': list,
    'total_processed': int,
    'successful': int,
    'failed': int
}
```

#### `get_attendance_rule_summary(employee)`
Get attendance rule summary for an employee.

#### `validate_attendance_rule_configuration(company)`
Validate attendance rule configuration for a company.

## Custom Fields

### Attendance DocType Extensions

| Field Name | Type | Description |
|------------|------|-------------|
| `custom_regular_hours` | Float | Calculated regular working hours after break deduction |
| `custom_overtime_hours` | Float | Calculated overtime hours based on attendance rules |
| `custom_deficiency_hours` | Float | Calculated deficiency hours (shortfall from required hours) |
| `custom_total_hours` | Float | Total hours worked between check-in and check-out |
| `custom_break_duration_minutes` | Int | Break duration deducted from working hours |
| `custom_is_friday` | Check | Indicates if attendance date is Friday |
| `custom_is_gazetted_holiday` | Check | Indicates if attendance date is a gazetted holiday |
| `custom_adjusted_check_in` | Datetime | Check-in time after applying grace period logic |
| `custom_adjusted_check_out` | Datetime | Check-out time after applying grace period logic |
| `custom_attendance_rule_applied` | Link | Attendance rule used for calculations |
| `custom_calculation_timestamp` | Datetime | Timestamp when attendance metrics were calculated |

## Testing

### Test Structure

```
tests/
├── fixtures/
│   └── attendance_test_data.py          # Test data and scenarios
├── test_attendance_rule_engine.py       # Engine unit tests
├── test_attendance_controller.py        # Controller integration tests
└── run_tests.py                         # Test runner script
```

### Test Categories

1. **Unit Tests**
   - Grace period logic
   - Break calculations
   - Overtime calculations
   - Deficiency calculations
   - Friday logic
   - Overnight shifts

2. **Integration Tests**
   - ERPNext Attendance DocType integration
   - Custom field population
   - Validation workflows
   - API endpoints

3. **Edge Case Tests**
   - Zero hours attendance
   - Very long shifts
   - Late checkin/early checkout
   - Invalid data handling

### Running Tests

```bash
# Run all tests
python run_tests.py

# Run specific test class
python run_tests.py TestAttendanceRuleEngine

# Run specific test method
python run_tests.py TestAttendanceRuleEngine test_engine_initialization
```

## Configuration

### Attendance Rule Setup

1. **Create Attendance Rule**
   ```json
   {
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
     "force_hours_on_friday": true,
     "allow_negative_hours": false,
     "enable_friday_logic": true,
     "consider_check_out_next_day": true,
     "allow_absent_on_holiday": false,
     "ignore_break_in_overtime": false
   }
   ```

2. **Assign to Employee**
   ```json
   {
     "doctype": "Employee",
     "employee": "EMP-001",
     "custom_attendance_rule": "Your Company"
   }
   ```

### Custom Fields Installation

```bash
# Install custom fields
bench --site your-site migrate
```

## Usage Examples

### Basic Attendance Calculation

```python
from spotledger_hr.attendance_rule_engine import AttendanceRuleEngine

# Initialize engine
engine = AttendanceRuleEngine("EMP-001", "2024-01-15")

# Calculate attendance summary
summary = engine.calculate_attendance_summary("07:30:00", "16:00:00")

print(f"Regular Hours: {summary['regular_hours']}")
print(f"Overtime Hours: {summary['overtime_hours']}")
print(f"Deficiency Hours: {summary['deficiency_hours']}")
```

### Attendance Preview API

```python
import frappe

# Calculate preview
result = frappe.call(
    "spotledger_hr.controllers.attendance_controller.calculate_attendance_preview",
    employee="EMP-001",
    attendance_date="2024-01-15",
    check_in="2024-01-15 07:30:00",
    check_out="2024-01-15 16:00:00"
)

if result['success']:
    print(f"Total Hours: {result['data']['total_hours']}")
```

### Bulk Attendance Processing

```python
import frappe

attendance_records = [
    {
        'employee': 'EMP-001',
        'attendance_date': '2024-01-15',
        'check_in': '2024-01-15 07:30:00',
        'check_out': '2024-01-15 16:00:00'
    },
    {
        'employee': 'EMP-002',
        'attendance_date': '2024-01-15',
        'check_in': '2024-01-15 07:30:00',
        'check_out': '2024-01-15 17:00:00'
    }
]

result = frappe.call(
    "spotledger_hr.controllers.attendance_controller.bulk_calculate_attendance",
    attendance_records=attendance_records
)

print(f"Processed: {result['total_processed']}")
print(f"Successful: {result['successful']}")
print(f"Failed: {result['failed']}")
```

## Error Handling

### Common Errors

1. **Missing Attendance Rule**
   ```
   Error: No Attendance Rule set for Employee: EMP-001
   ```
   **Solution**: Assign attendance rule to employee

2. **Invalid Configuration**
   ```
   Error: Check-in grace minutes cannot be greater than max grace minutes
   ```
   **Solution**: Fix attendance rule configuration

3. **Invalid Date/Time Format**
   ```
   Error: Invalid datetime format
   ```
   **Solution**: Use correct datetime format (YYYY-MM-DD HH:MM:SS)

### Error Handling Best Practices

1. **Always validate input data**
2. **Use try-catch blocks for API calls**
3. **Log errors for debugging**
4. **Provide meaningful error messages**
5. **Handle edge cases gracefully**

## Performance Considerations

### Optimization Tips

1. **Cache attendance rules** for frequently accessed employees
2. **Use bulk operations** for multiple attendance records
3. **Index database fields** for faster queries
4. **Implement pagination** for large datasets
5. **Use background jobs** for heavy calculations

### Monitoring

1. **Track calculation times** for performance monitoring
2. **Monitor error rates** for system health
3. **Log slow queries** for optimization
4. **Set up alerts** for system issues

## Troubleshooting

### Common Issues

1. **Calculations not updating**
   - Check if custom fields are installed
   - Verify attendance rule is assigned
   - Check for validation errors

2. **Incorrect overtime calculation**
   - Verify Friday logic is enabled
   - Check break duration settings
   - Validate holiday list configuration

3. **Grace period not working**
   - Check grace period settings
   - Verify timezone configuration
   - Validate datetime formats

### Debug Mode

```python
import frappe
from spotledger_hr.attendance_rule_engine import AttendanceRuleEngine

# Enable debug logging
frappe.conf.developer_mode = 1

# Initialize engine with debug
engine = AttendanceRuleEngine("EMP-001", "2024-01-15")
summary = engine.calculate_attendance_summary("07:30:00", "16:00:00")

# Check logs
frappe.logger().info(f"Attendance Summary: {summary}")
```

## Future Enhancements

### Planned Features

1. **Real-time attendance tracking**
2. **Mobile app integration**
3. **Advanced reporting**
4. **Automated notifications**
5. **Machine learning predictions**

### Extension Points

1. **Custom calculation methods**
2. **Additional validation rules**
3. **Integration with external systems**
4. **Custom reporting formats**
5. **Workflow automation**

## Support

For support and questions:

1. **Check documentation** first
2. **Review test cases** for examples
3. **Check error logs** for issues
4. **Contact development team** for complex issues

## License

This implementation is part of the SpotLedger HR module and follows the same license terms as the main application.
