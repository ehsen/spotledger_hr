# Overtime Multiplier Implementation Guide

## Overview
The Salary Slip calculation now incorporates overtime multipliers from the Attendance Rule. This allows for flexible overtime pay calculations based on rule-specific multiplier values.

## Changes Made

### 1. New Methods Added to CustomSalarySlip

#### `get_overtime_multiplier()`
**Purpose**: Fetches the regular overtime multiplier from the employee's Attendance Rule.

**Implementation**:
- Retrieves `custom_attendance_rule` from the Employee master
- Fetches `overtime_multiplier` from the Attendance Rule doctype
- Defaults to 1.0 (100%) if not found or if value is <= 0
- Uses `frappe.get_cached_doc()` for performance

**Usage Example**:
```python
multiplier = self.get_overtime_multiplier()
# Returns: 1.5 (150%), 1.25 (125%), etc.
```

#### `get_gzt_overtime_multiplier()`
**Purpose**: Fetches the gazetted holiday overtime multiplier from the employee's Attendance Rule.

**Implementation**:
- Retrieves `custom_attendance_rule` from the Employee master
- Fetches `gzt_overtime_multiplier` from the Attendance Rule doctype
- Defaults to 1.0 (100%) if not found or if value is <= 0
- Uses `frappe.get_cached_doc()` for performance

**Usage Example**:
```python
multiplier = self.get_gzt_overtime_multiplier()
# Returns: 2.0 (200%), 1.5 (150%), etc.
```

### 2. Modified Overtime Calculation Logic

**Previous Implementation**:
```python
overtime_amount = attendance_summary.get('overtime_hours', 0) * hourly_rate
gzt_overtime_amount = attendance_summary.get('gzt_overtime_hours', 0) * hourly_rate
```

**New Implementation**:
```python
overtime_hours = attendance_summary.get('overtime_hours', 0)
gzt_overtime_hours = attendance_summary.get('gzt_overtime_hours', 0)
overtime_amount = overtime_hours * hourly_rate * overtime_multiplier
gzt_overtime_amount = gzt_overtime_hours * hourly_rate * gzt_overtime_multiplier
```

**Formula**:
```
Overtime Amount = Overtime Hours × Hourly Rate × Overtime Multiplier
GZT Overtime Amount = GZT Overtime Hours × Hourly Rate × GZT Overtime Multiplier
```

### 3. Enhanced Logging

Detailed logging has been added to show:
- Overtime and GZT overtime multipliers being used
- Complete breakdown of overtime calculations including:
  - Hours worked
  - Hourly rate
  - Multiplier applied
  - Final calculated amount

Example log output:
```
overtime amt = 2250 (15hrs x 100 x 1.5), 
gzt overtime amt = 4000 (20hrs x 100 x 2.0), 
deficiency amt = 500, 
advances amt = 1000, 
base salary 50000
```

## Configuration Setup

### In Attendance Rule Doctype:

1. **overtime_multiplier** field
   - Example values: 1.25 (125%), 1.5 (150%), 2.0 (200%)
   - Default: 1.0 (no multiplier)
   - Used for regular overtime calculations

2. **gzt_overtime_multiplier** field
   - Example values: 1.5 (150%), 2.0 (200%), 2.5 (250%)
   - Default: 1.0 (no multiplier)
   - Used for gazetted holiday overtime calculations
   - Typically higher than regular overtime multiplier

### In Employee Master:

**custom_attendance_rule** field
- Link field pointing to the applicable Attendance Rule
- This determines which multipliers will be used for the employee

## Usage in Salary Calculation

### Flow:
1. Employee is assigned a `custom_attendance_rule`
2. When Salary Slip is validated:
   - `get_overtime_multiplier()` fetches overtime_multiplier from the rule
   - `get_gzt_overtime_multiplier()` fetches gzt_overtime_multiplier from the rule
   - Overtime amounts are calculated with these multipliers
   - Salary components are created with the multiplied amounts

### Example Scenario:

**Employee Details**:
- Monthly Salary: 50,000
- Attendance Rule: "Factory Workers"
- overtime_multiplier: 1.5
- gzt_overtime_multiplier: 2.0
- Required Factory Hours: 8

**Attendance Summary**:
- Regular Overtime Hours: 20
- GZT Overtime Hours: 10

**Calculations**:
1. Days in month: 30
2. Per day salary: 50,000 / 30 = 1,666.67
3. Hourly rate: 50,000 / (30 × 8) = 208.33
4. Overtime amount: 20 × 208.33 × 1.5 = 6,249.90
5. GZT Overtime amount: 10 × 208.33 × 2.0 = 4,166.60

**Salary Components Generated**:
- Gross Salary: 50,000
- Overtime: 6,249.90
- Overtime GZT: 4,166.60
- Deficiency: (calculated based on deficiency hours)
- Advances: (calculated from advance deductions)

## Error Handling & Defaults

### Scenarios Handled:

1. **No Attendance Rule Assigned**
   - Both multipliers default to 1.0
   - Overtime calculated without multiplier (standard rate)

2. **Multiplier Field Not Set**
   - If field is missing or empty: defaults to 1.0
   - If multiplier <= 0: defaults to 1.0

3. **Employee Not Found**
   - handled gracefully with try-except
   - Defaults ensure salary calculation continues

4. **Attendance Rule Not Found**
   - Uses defaults (1.0 for both multipliers)
   - Logging captures the scenario

## Performance Considerations

✅ **Optimization Features**:
- Uses `frappe.get_cached_doc()` instead of `frappe.get_doc()` for caching
- Only fetches data when needed
- Multiplier values are floats (no heavy calculations)

## Testing Checklist

- [ ] Verify multiplier values are fetched correctly from Attendance Rule
- [ ] Test overtime calculation with 1.5x multiplier
- [ ] Test GZT overtime calculation with 2.0x multiplier
- [ ] Verify default (1.0) when no rule is assigned
- [ ] Verify default (1.0) when multiplier field is empty
- [ ] Test with zero overtime hours (should result in 0 amount)
- [ ] Verify logging shows correct calculation breakdown
- [ ] Test with multiple attendance rules having different multipliers
- [ ] Verify salary slip submission creates correct components

## Integration Points

This implementation integrates with:
1. **Employee Master** - custom_attendance_rule field
2. **Attendance Rule** - overtime_multiplier and gzt_overtime_multiplier fields
3. **Attendance Records** - overtime_hours and gzt_overtime_hours fields
4. **Salary Slip** - earnings components (Overtime, Overtime GZT)

## Future Enhancements

Potential improvements:
1. Add UI components to visualize multiplier impact on salary
2. Multiplier history tracking for audit purposes
3. Exception handling for negative multipliers
4. Multiplier validation rules in Attendance Rule
5. Report showing multiplier usage across employees
6. Bulk salary slip generation with multiplier preview

## FAQ

**Q: What if the multiplier is less than 1?**
A: Values <= 0 are treated as 1.0 (default) for safety.

**Q: Can multipliers be fractional (e.g., 1.25)?**
A: Yes, any positive decimal value is supported.

**Q: What's the default multiplier if no Attendance Rule is set?**
A: 1.0 (100% - no multiplier applied)

**Q: When are multipliers applied?**
A: During the `validate()` method of Salary Slip, before standard Frappe HRMS validation.

**Q: Can different employees have different multipliers?**
A: Yes, each employee's custom_attendance_rule can point to different rules with different multipliers.

**Q: Are multipliers cached?**
A: Yes, using `frappe.get_cached_doc()` for performance.

