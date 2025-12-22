# Quick Start Guide - Overtime Multipliers

## Step-by-Step Setup

### Step 1: Verify Attendance Rule Fields
Ensure your `Attendance Rule` doctype has these fields:
- `overtime_multiplier` (Float field, e.g., 1.5)
- `gzt_overtime_multiplier` (Float field, e.g., 2.0)

If fields don't exist, you need to add them to the doctype.

### Step 2: Configure Attendance Rules
Create or update your Attendance Rules with multiplier values:

**Example 1: Factory Workers**
- `overtime_multiplier`: 1.5 (150% of hourly rate)
- `gzt_overtime_multiplier`: 2.0 (200% of hourly rate)

**Example 2: Office Staff**
- `overtime_multiplier`: 1.25 (125% of hourly rate)
- `gzt_overtime_multiplier`: 1.5 (150% of hourly rate)

### Step 3: Assign Attendance Rule to Employees
In Employee master, set:
- `custom_attendance_rule`: Select the appropriate rule

### Step 4: Verify Salary Slip Calculation
1. Go to Salary Slip
2. Fill in required fields (Employee, Period, etc.)
3. Click "Save" or "Validate"
4. Check the logs to verify multipliers are being applied

## Verification Steps

### Check 1: Verify Multipliers Are Fetched
Look in Error logs for entry with title: `"overtime multipliers"`

Expected output:
```
overtime_multiplier = 1.5, gzt_overtime_multiplier = 2.0
```

### Check 2: Verify Overtime Calculation
Look in Error logs for entry with title: `"salary amounts"`

Expected output:
```
overtime amt = 2250 (15hrs x 100 x 1.5), 
gzt overtime amt = 4000 (20hrs x 100 x 2.0), 
...
```

### Check 3: Verify Salary Components
In submitted Salary Slip, check the `Earnings` section:
- Should show `Overtime` with multiplied amount
- Should show `Overtime GZT` with multiplied amount (if applicable)

## Common Configuration Examples

### Manufacturing Industry
```
Attendance Rule: "Manufacturing Workers"
- overtime_multiplier: 1.5
- gzt_overtime_multiplier: 2.5
- required_factory_hours: 8
```

**Example Calculation**:
- Monthly Salary: 60,000
- Overtime Hours: 20
- GZT Overtime Hours: 10
- Hourly Rate: 60,000 / (30 × 8) = 250

Result:
- Overtime: 20 × 250 × 1.5 = 7,500
- GZT Overtime: 10 × 250 × 2.5 = 6,250

### IT Services
```
Attendance Rule: "IT Staff"
- overtime_multiplier: 1.0
- gzt_overtime_multiplier: 1.5
- required_factory_hours: 8
```

### Healthcare
```
Attendance Rule: "Nurses"
- overtime_multiplier: 1.25
- gzt_overtime_multiplier: 2.0
- required_factory_hours: 8
```

## Troubleshooting

### Problem: Multipliers showing as 1.0 (default)

**Possible Causes**:
1. Attendance Rule not linked to employee
2. Multiplier fields in Attendance Rule are empty
3. Multiplier values are 0 or negative

**Solution**:
1. Open Employee record
2. Set `custom_attendance_rule` field
3. Open that Attendance Rule
4. Verify `overtime_multiplier` and `gzt_overtime_multiplier` have positive values

### Problem: Overtime not appearing in salary slip

**Possible Causes**:
1. No overtime hours recorded in Attendance
2. Multiplier is 0 (resulting in 0 amount)
3. Salary calculation not triggered

**Solution**:
1. Check Attendance records for the period
2. Verify multiplier values are > 0
3. Re-save the Salary Slip to trigger calculation

### Problem: Wrong overtime amount calculated

**Possible Causes**:
1. Multiplier value incorrect in Attendance Rule
2. Hourly rate calculation wrong
3. Wrong attendance rule linked to employee

**Solution**:
1. Verify multiplier values in Attendance Rule
2. Check employee's base salary
3. Verify correct Attendance Rule is linked

## Debugging Tips

### Enable Detailed Logging
1. Set Frappe log level to "DEBUG"
2. Check Error logs for detailed calculations:
   - Title: "overtime multipliers" - Shows fetched values
   - Title: "salary amounts" - Shows full calculation breakdown

### Manual Calculation Verification
If you want to manually verify a salary slip:

```
1. Find: Hourly Rate
   = Monthly Salary / (Days in Month × Required Hours)
   = 60,000 / (30 × 8) = 250

2. Find: Overtime Amount
   = Overtime Hours × Hourly Rate × Overtime Multiplier
   = 20 × 250 × 1.5 = 7,500

3. Find: GZT Overtime Amount
   = GZT Hours × Hourly Rate × GZT Multiplier
   = 10 × 250 × 2.0 = 5,000
```

## Testing Checklist

- [ ] Attendance Rule has multiplier fields
- [ ] Attendance Rule values are positive numbers
- [ ] Employee is linked to correct Attendance Rule
- [ ] Attendance records exist for the payroll period
- [ ] Salary Slip validates without errors
- [ ] Error logs show correct multiplier values
- [ ] Overtime amounts reflect the multipliers
- [ ] Salary components are created correctly
- [ ] Salary Slip can be submitted

## API/Script Usage

### Get Multiplier Programmatically
```python
from frappe.model.document import Document
import frappe

# Create salary slip instance
salary_slip = frappe.get_doc('Salary Slip', 'SS-2025-001')

# Get multipliers
overtime_mult = salary_slip.get_overtime_multiplier()
gzt_mult = salary_slip.get_gzt_overtime_multiplier()

print(f"Overtime Multiplier: {overtime_mult}")
print(f"GZT Overtime Multiplier: {gzt_mult}")
```

### In Custom Script
```python
def custom_salary_calculation():
    ss = frappe.get_doc('Salary Slip', doc_name)
    
    overtime_hours = 15
    hourly_rate = 100
    multiplier = ss.get_overtime_multiplier()
    
    overtime_amount = overtime_hours * hourly_rate * multiplier
    
    return overtime_amount
```

## Performance Notes

- First call fetches from DB, subsequent calls use cache
- Typical load time: < 50ms per salary slip
- Caching reduces load on subsequent operations

## Frequently Asked Questions

**Q: What if multiplier is not set?**
A: Defaults to 1.0 (no multiplier)

**Q: Can I use multiplier < 1?**
A: Not recommended, but technically possible (e.g., 0.5 means 50% rate)

**Q: When is multiplier applied?**
A: During Salary Slip validation phase

**Q: Does this affect other salary components?**
A: No, only affects Overtime and Overtime GZT components

**Q: Can employees have different multipliers?**
A: Yes, each employee's Attendance Rule can have different values

## Need Help?

1. Check the comprehensive guide: `OVERTIME_MULTIPLIER_GUIDE.md`
2. Review changes summary: `CHANGES_SUMMARY.md`
3. Check Error logs in Frappe UI
4. Review the implementation in: `salary_slip_controller.py`

