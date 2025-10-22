# Attendance-Based Salary Calculation

## Overview

This module implements attendance-based salary calculation for employees in Frappe HRMS. It allows calculating salaries based on actual attendance records rather than fixed monthly amounts, while maintaining full compatibility with standard Frappe HRMS for employees who don't need attendance-based calculations.

## Features

- **Conditional Calculation**: Only applies to employees with specific flags enabled
- **Backward Compatible**: Standard Frappe HRMS flow works for other employees
- **Comprehensive Tracking**: Supports regular overtime, gazetted holiday overtime, and advance deductions
- **Integration**: Uses existing Attendance records and Salary Structure data

## Setup

### 1. Enable Attendance-Based Salary for Employee

For each employee who should have attendance-based salary:

1. Open the Employee document
2. Check the following fields:
   - ✅ **Attendance Required** (`custom_attendance_required`)
   - ✅ **Generate Salary Based on Attendance** (`custom_generate_salary_based_on_attendance`)
3. Ensure the employee has an **Attendance Rule** assigned (`custom_attendance_rule`)
4. Ensure the employee has an active **Salary Structure Assignment**

### 2. Create Required Salary Components

The following Salary Components are required (automatically created via fixtures):

**Earnings:**
- **Gross Salary** - Base salary calculated from days worked
- **Overtime** - Regular overtime payment
- **Overtime GZT** - Gazetted holiday overtime payment

**Deductions:**
- **Advances** - Employee advance deductions

### 3. Install Fixtures

Run the following command to install the salary components:

```bash
bench --site [site-name] migrate
```

Or manually import fixtures:

```bash
bench --site [site-name] import-doc spotledger_hr/fixtures/salary_component.json
```

## How It Works

### Calculation Logic

When a Salary Slip is created for an attendance-based employee:

#### 1. **Gross Salary Calculation**
```
Gross Salary = (Base Monthly Salary / Days in Month) × Days Worked

Where:
- Base Monthly Salary = from employee's Salary Structure Assignment
- Days in Month = calendar days in the payroll month
- Days Worked = count of "Present" attendance records in payroll period
```

#### 2. **Overtime Calculation**
```
Hourly Rate = Base Monthly Salary / (Days in Month × Required Factory Hours)
Overtime Amount = Overtime Hours × Hourly Rate

Where:
- Required Factory Hours = from employee's Attendance Rule
- Overtime Hours = sum of custom_overtime_hours from Attendance records
  (excluding gazetted holidays)
```

#### 3. **Gazetted Overtime Calculation**
```
GZT Overtime Amount = GZT Overtime Hours × Hourly Rate

Where:
- GZT Overtime Hours = sum of custom_overtime_hours from Attendance records
  where custom_is_gazetted_holiday = 1
- Note: Multiplier is already applied in Attendance calculation
```

#### 4. **Advances Deduction**
```
Advances = sum of Employee Advance amounts in payroll period
```

### Data Sources

The system queries the following data:

1. **Days Worked**: Count of Attendance records with status = "Present"
2. **Overtime Hours**: Sum of `custom_overtime_hours` (non-gazetted)
3. **GZT Overtime**: Sum of `custom_overtime_hours` (gazetted holidays)
4. **Advances**: Sum of Employee Advance amounts

## Usage

### Creating Salary Slips

**Option 1: Individual Salary Slip**
1. Go to: HR > Payroll > Salary Slip > New
2. Select an Employee (with attendance-based flags enabled)
3. Set Start Date and End Date
4. Save the document
5. The system automatically:
   - Queries attendance records
   - Calculates salary components
   - Populates earnings and deductions

**Option 2: Bulk via Payroll Entry**
1. Go to: HR > Payroll > Payroll Entry > New
2. Select payroll period and filters
3. Click "Get Employees"
4. The system processes each employee:
   - Attendance-based employees: calculated from attendance
   - Standard employees: calculated from salary structure

### Verification

To verify the calculation:

1. **Check Days Worked**:
   ```sql
   SELECT COUNT(*) FROM `tabAttendance`
   WHERE employee = 'EMP-00001'
   AND attendance_date BETWEEN '2025-10-01' AND '2025-10-31'
   AND status = 'Present' AND docstatus = 1
   ```

2. **Check Overtime Hours**:
   ```sql
   SELECT SUM(custom_overtime_hours) FROM `tabAttendance`
   WHERE employee = 'EMP-00001'
   AND attendance_date BETWEEN '2025-10-01' AND '2025-10-31'
   AND status = 'Present' AND custom_is_gazetted_holiday = 0
   AND docstatus = 1
   ```

3. **Check Gazetted Overtime**:
   ```sql
   SELECT SUM(custom_overtime_hours) FROM `tabAttendance`
   WHERE employee = 'EMP-00001'
   AND attendance_date BETWEEN '2025-10-01' AND '2025-10-31'
   AND status = 'Present' AND custom_is_gazetted_holiday = 1
   AND docstatus = 1
   ```

## Example Calculation

### Scenario:
- Employee: EMP-00001
- Payroll Period: October 2025 (31 days)
- Base Monthly Salary: PKR 50,000
- Required Factory Hours: 8 hours/day
- Days Worked: 26 days
- Regular Overtime: 12 hours
- Gazetted Overtime: 8 hours
- Advances: PKR 5,000

### Calculation:

1. **Per Day Salary**:
   ```
   50,000 / 31 = PKR 1,612.90 per day
   ```

2. **Gross Salary**:
   ```
   1,612.90 × 26 = PKR 41,935.48
   ```

3. **Hourly Rate**:
   ```
   50,000 / (31 × 8) = PKR 201.61 per hour
   ```

4. **Overtime Amount**:
   ```
   12 × 201.61 = PKR 2,419.35
   ```

5. **GZT Overtime Amount**:
   ```
   8 × 201.61 = PKR 1,612.90
   ```

6. **Total Earnings**:
   ```
   41,935.48 + 2,419.35 + 1,612.90 = PKR 45,967.73
   ```

7. **Total Deductions**:
   ```
   Advances: PKR 5,000
   Income Tax: (calculated by system)
   ```

8. **Net Pay**:
   ```
   45,967.73 - 5,000 - Tax = Net Salary
   ```

## Technical Details

### File Structure

```
spotledger_hr/
├── controllers/
│   ├── attendance_controller.py
│   └── salary_slip_controller.py  # ← New
├── fixtures/
│   ├── custom_field.json
│   └── salary_component.json      # ← New
└── hooks.py                        # ← Updated
```

### Key Classes and Methods

**CustomSalarySlip** (extends SalarySlip):
- `validate()` - Entry point for salary calculation
- `should_calculate_from_attendance()` - Check if employee needs attendance-based calculation
- `calculate_attendance_based_salary()` - Main calculation method
- `get_attendance_hours_summary()` - Query attendance data
- `get_base_salary_from_structure()` - Get base salary
- `calculate_hourly_rate()` - Calculate overtime rate
- `get_employee_advances()` - Query advance deductions

### Database Queries

The controller performs optimized queries on:
- `tabAttendance` - For days worked and overtime hours
- `tabEmployee Advance` - For advance deductions
- `tabSalary Structure Assignment` - For base salary

## Troubleshooting

### Issue: Salary not calculating from attendance

**Check:**
1. Employee has both flags enabled:
   - `custom_attendance_required = 1`
   - `custom_generate_salary_based_on_attendance = 1`
2. Employee has valid Salary Structure Assignment
3. Attendance records exist for the payroll period
4. Attendance records are submitted (docstatus = 1)

### Issue: Overtime not showing

**Check:**
1. Attendance records have `custom_overtime_hours` populated
2. Attendance records are submitted
3. For regular overtime: `custom_is_gazetted_holiday = 0`
4. For GZT overtime: `custom_is_gazetted_holiday = 1`

### Issue: Wrong hourly rate

**Check:**
1. Employee has `custom_attendance_rule` assigned
2. Attendance Rule has `required_factory_hours` set (default: 8)
3. Base salary is correctly set in Salary Structure Assignment

### Issue: Advances not deducted

**Check:**
1. Employee Advance records exist for the payroll period
2. Employee Advance records are submitted (docstatus = 1)
3. `posting_date` falls within payroll start and end dates

## Migration from Legacy System

If migrating from the old breeze_payroll system:

1. **Ensure Attendance Data**: All attendance records have the custom fields populated
2. **Test Calculations**: Compare old vs new salary calculations
3. **Verify Components**: Ensure all salary components are created
4. **Employee Setup**: Enable flags for all attendance-based employees

### Legacy Compatibility

The module includes helper functions for legacy compatibility:
- `get_days_in_month(date)`
- `per_day_salary(monthly_salary, payroll_start_date)`
- `per_hour_salary(per_day_salary, required_hours)`
- `salary_as_per_days_worked(per_day_salary, days_worked)`

## Income Tax

Income tax is handled by Frappe HRMS's built-in tax calculation system:
- Configure tax slabs in: HR > Payroll > Income Tax Slab
- System automatically calculates tax based on gross earnings
- Medical allowance adjustments (if any) should be configured in tax slabs

## Future Enhancements

Potential future improvements:
- Support for deficiency deductions (hours shortfall)
- Multiple overtime rates/types
- Custom allowances based on attendance
- Attendance-based bonuses
- Integration with shift management

## Support

For issues or questions:
- Check the troubleshooting section above
- Review Attendance records for the employee
- Verify employee configuration flags
- Check system logs in Error Log doctype

