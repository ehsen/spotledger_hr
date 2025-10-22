# Quick Setup Guide: Attendance-Based Salary Calculation

## Installation Steps

### 1. Migrate and Install Fixtures

Run the following commands to install the new features:

```bash
cd /home/frappe/frappe-bench

# Run migrations to create/update database schema
bench --site [your-site-name] migrate

# If fixtures don't auto-install, manually import:
bench --site [your-site-name] import-doc apps/spotledger_hr/spotledger_hr/fixtures/salary_component.json
```

### 2. Restart Bench

After migration, restart the bench to load the new controller:

```bash
bench restart
```

### 3. Verify Salary Components

Go to: **HR > Payroll > Salary Component**

Verify these components exist:
- ✅ Gross Salary (Earning)
- ✅ Overtime (Earning)
- ✅ Overtime GZT (Earning)
- ✅ Advances (Deduction)

If missing, create them manually or re-import fixtures.

## Configure Employee for Attendance-Based Salary

### Step 1: Enable Employee Flags

For each employee who should use attendance-based salary:

1. Open: **HR > Employee > [Employee Name]**
2. Scroll to **Attendance and Leave Details** section
3. Check these boxes:
   - ✅ **Attendance Required** (`custom_attendance_required`)
   - ✅ **Generate Salary Based on Attendance** (`custom_generate_salary_based_on_attendance`)
4. Select an **Attendance Rule** in the `custom_attendance_rule` field
5. **Save** the employee

### Step 2: Verify Salary Structure Assignment

1. Go to: **HR > Payroll > Salary Structure Assignment**
2. Ensure the employee has an active assignment with:
   - Valid **From Date**
   - Selected **Salary Structure**
   - **Base** amount specified
   - Status: **Submitted** (docstatus = 1)

### Step 3: Verify Attendance Rule

1. Go to: **HR > Attendance Rule** (custom doctype)
2. Open the rule assigned to the employee
3. Verify:
   - **Required Working Hours** is set (e.g., 8 hours)
   - Other grace periods and break rules are configured

## Testing the Feature

### Option 1: Manual Test via Bench Console

```bash
cd /home/frappe/frappe-bench
bench --site [your-site-name] console
```

In the console, run:

```python
from spotledger_hr.tests.test_attendance_based_salary import run_manual_test
run_manual_test()
```

This will:
- Find an employee with attendance-based flags
- Check their attendance records
- Create a test salary slip
- Display the calculation breakdown
- Rollback (no data saved)

### Option 2: Create Salary Slip Manually

1. **Create Test Attendance Records** (if none exist):
   - Go to: **HR > Attendance > New**
   - Create several "Present" attendance records for your test employee
   - Add some overtime hours in `custom_overtime_hours` field
   - Submit the attendance records

2. **Create Salary Slip**:
   - Go to: **HR > Payroll > Salary Slip > New**
   - Select your test employee (with flags enabled)
   - Set Start Date: First day of month
   - Set End Date: Last day of month
   - Click **Save**

3. **Verify Calculation**:
   - Check **Earnings** tab:
     - Should show: Gross Salary, Overtime, Overtime GZT (if applicable)
   - Check **Deductions** tab:
     - Should show: Advances (if any exist)
   - **Payment Days** should equal attendance count

### Option 3: Test with Payroll Entry

1. Go to: **HR > Payroll > Payroll Entry > New**
2. Select:
   - Payroll frequency
   - Start Date and End Date
   - Department/Branch (optional filter)
3. Click **Get Employees**
4. Verify employees appear in the list
5. Click **Create Salary Slips**
6. Review generated slips - attendance-based employees should show custom calculation

## Verification Checklist

After creating a salary slip, verify:

### ✅ Component Verification
- [ ] Gross Salary appears in Earnings
- [ ] Overtime appears (if overtime hours exist)
- [ ] Overtime GZT appears separately (if worked on gazetted holiday)
- [ ] Advances appear in Deductions (if advances exist)
- [ ] Income Tax calculated by system (if applicable)

### ✅ Amount Verification

Run these queries to verify amounts:

```sql
-- Check employee settings
SELECT 
    name, 
    employee_name,
    custom_attendance_required,
    custom_generate_salary_based_on_attendance,
    custom_attendance_rule
FROM `tabEmployee`
WHERE name = 'EMP-00001';

-- Check attendance summary
SELECT 
    COUNT(*) as days_worked,
    SUM(CASE WHEN custom_is_gazetted_holiday = 0 THEN custom_overtime_hours ELSE 0 END) as regular_ot,
    SUM(CASE WHEN custom_is_gazetted_holiday = 1 THEN custom_overtime_hours ELSE 0 END) as gzt_ot
FROM `tabAttendance`
WHERE employee = 'EMP-00001'
AND attendance_date BETWEEN '2025-10-01' AND '2025-10-31'
AND status = 'Present'
AND docstatus = 1;

-- Check base salary
SELECT 
    salary_structure,
    base,
    from_date
FROM `tabSalary Structure Assignment`
WHERE employee = 'EMP-00001'
AND docstatus = 1
ORDER BY from_date DESC
LIMIT 1;

-- Check salary slip components
SELECT 
    salary_component,
    amount
FROM `tabSalary Detail`
WHERE parent = 'HR-SLP-2025-00001'
ORDER BY parentfield, idx;
```

### ✅ Calculation Verification

Manual calculation to verify:

```
Given:
- Base Salary: 50,000
- Days in Month: 31
- Days Worked: 26
- Regular Overtime: 10 hours
- Required Hours per Day: 8

Calculate:
1. Per Day Salary = 50,000 / 31 = 1,612.90
2. Gross Salary = 1,612.90 × 26 = 41,935.48
3. Hourly Rate = 50,000 / (31 × 8) = 201.61
4. Overtime Amount = 10 × 201.61 = 2,016.13
5. Total Earnings = 41,935.48 + 2,016.13 = 43,951.61
```

Compare with salary slip amounts.

## Common Issues and Solutions

### Issue: "No Attendance Rule set for Employee"

**Solution:**
1. Open Employee record
2. Set the `custom_attendance_rule` field
3. Save employee
4. Try creating salary slip again

### Issue: "No active Salary Structure found"

**Solution:**
1. Create a Salary Structure Assignment for the employee
2. Set base salary amount
3. Submit the assignment
4. Try creating salary slip again

### Issue: Salary components not appearing

**Solution:**
1. Check if Salary Components exist in master
2. Re-import fixtures: `bench --site [site] import-doc apps/spotledger_hr/spotledger_hr/fixtures/salary_component.json`
3. Verify component names match exactly: "Gross Salary", "Overtime", "Overtime GZT", "Advances"

### Issue: Standard employees affected

**Solution:**
- If employee does NOT have both flags enabled, standard HRMS calculation is used
- Verify employee flags: both must be enabled (= 1) for attendance-based calculation
- Standard employees should work normally without any changes

### Issue: Overtime hours not showing

**Solution:**
1. Check if Attendance records have `custom_overtime_hours` field populated
2. Verify attendance records are submitted (docstatus = 1)
3. Check date range matches salary slip period
4. Verify custom fields exist on Attendance doctype

## Advanced Configuration

### Custom Overtime Rates

Currently, overtime is calculated using the base hourly rate. To customize:

1. Modify `calculate_hourly_rate()` method in `salary_slip_controller.py`
2. Add overtime rate multiplier from Attendance Rule (if needed)
3. Apply different rates for different overtime types

### Additional Salary Components

To add more components (e.g., allowances, bonuses):

1. Create the Salary Component in master
2. Add calculation logic in `calculate_attendance_based_salary()` method
3. Append to earnings or deductions as needed

### Deficiency Deduction

To deduct for hours shortfall:

1. Query deficiency hours from Attendance (`custom_deficiency_hours`)
2. Calculate deficiency amount
3. Add as deduction component

## Support and Documentation

- **Full Documentation**: See `ATTENDANCE_BASED_SALARY.md`
- **Test Script**: `spotledger_hr/tests/test_attendance_based_salary.py`
- **Controller Code**: `spotledger_hr/controllers/salary_slip_controller.py`
- **Salary Components**: `spotledger_hr/fixtures/salary_component.json`

## Next Steps

After successful testing:

1. ✅ Enable flags for all attendance-based employees
2. ✅ Verify historical attendance data is complete
3. ✅ Run test payroll for one month
4. ✅ Compare with expected amounts
5. ✅ Train HR team on the process
6. ✅ Document any customizations
7. ✅ Set up regular payroll workflow

## Rollback (If Needed)

If you need to revert to standard HRMS:

1. Disable both flags on employees:
   - Uncheck `custom_attendance_required`
   - Uncheck `custom_generate_salary_based_on_attendance`

2. Salary slips will use standard calculation

3. To fully remove:
   - Remove override from hooks.py
   - Run: `bench restart`
   - Delete custom controller file (optional)

---

**Version**: 1.0  
**Last Updated**: October 2025  
**Module**: spotledger_hr

