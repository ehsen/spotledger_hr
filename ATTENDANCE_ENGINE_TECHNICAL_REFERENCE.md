# spotledger_hr — Attendance Engine Technical Reference

Status: written 2026-07-24, reflects the codebase after the cleanup commit `7f2fd2f`
(removed duplicate Attendance hook, dead payroll overrides, debug logging, legacy/scratch
files) plus a follow-up fix to `attendance_rule_engine.py` for the two issues originally
flagged in §5.1/§5.2 (weekly-off misclassified as gazetted holiday; gazetted overtime
hours double-multiplied) — both are now fixed in code, not just documented as risks.

This is the authoritative reference for implementing/validating this app's attendance
and payroll customizations at the client's production site. Older `*.md`/`*.txt` files
at the app root predate the cleanup and may describe removed code — trust this
document and the code over those.

---

## 1. What this app actually overrides today

| ERPNext/HRMS doctype | Override | Status |
|---|---|---|
| `Attendance` | `override_doctype_class` → `AttendanceController` | **Active** |
| `Salary Slip` | `salary_slip_controller.CustomSalarySlip` | **Disabled** (commented out in `hooks.py`) — decision pending |
| `Payroll Entry` | none (file deleted, was broken) | **Not overridden** — stock HRMS behavior |

Everything except Attendance currently runs **unmodified HRMS/ERPNext behavior**. The
only business logic actually live in production is the attendance-rule calculation
described below. Custom fields (`custom_*` on Employee/Attendance/Employee Checkin) and
two cosmetic Property Setters are also active but don't change control flow — see §6.

---

## 2. Production data pipeline

```
Biometric device (factory gate) → SQLite export file
        │
        ▼
attendance_controller.sync_attendance()          (whitelisted, manual/scheduled trigger)
        │  matches employee by Employee.name, falling back to Employee.custom_old_code
        ▼
Employee Checkin records (IN/OUT rows, custom_attendance_date set explicitly
                           to survive overnight shifts crossing midnight)
        │
        ▼
Bulk Attendance doctype (HR admin UI)
        │  - load_data(): groups Employee Checkin by employee+date,
        │    only for Employee.custom_attendance_required = 1
        │  - admin reviews/edits per employee/day before committing
        │  - bulk_create_attendance(): creates Attendance docs
        ▼
Attendance.validate() → AttendanceController.validate()
        │  - if custom_manual_attendance is falsy, re-pulls check-in/out
        │    from Employee Checkin (belt-and-suspenders vs Bulk Attendance)
        │  - runs AttendanceRuleEngine, writes custom_regular_hours,
        │    custom_overtime_hours, custom_deficiency_hours, working_hours, status
        ▼
(Currently nothing downstream — Salary Slip is stock HRMS, does not
 consume these custom_* fields unless/until item 4 below is resolved)
```

Employees not flagged `custom_attendance_required = 1` (e.g. salaried/managerial staff)
never go through Bulk Attendance and are presumably marked present via standard HRMS
flows.

---

## 3. Doctypes and fields

### Attendance Rule (company-level shift/overtime policy)

One record per company (or per shift pattern — `company` is the only Link field, so in
practice one rule per company unless you key employees to different rule docs by name).

| Field | Type | Default | Meaning |
|---|---|---|---|
| `factory_start_time` / `factory_end_time` | Time | — | Regular shift boundaries |
| `required_factory_hours` | Float | 8.5 | **Net** hours required (after break), used as the regular/overtime/deficiency threshold |
| `friday_start_time` / `friday_end_time` | Time | — | Shift boundaries on Friday, only used if `enable_friday_logic` |
| `checkin_grace_minutes` / `checkin_max_grace_minutes` | Int | 10 / 30 | See grace-period algorithm below |
| `checkout_grace_minutes` / `checkout_max_grace_minutes` | Int | 5 / 20 | Same, for checkout |
| `break_duration_minutes` | Int | 30 | Minutes deducted when the shift spans the break window |
| `regular_break_start` / `regular_break_end` | Time | — | Break window, non-Friday |
| `friday_break_start` / `friday_break_end` | Time | — | Break/prayer window on Friday |
| `ignore_break_in_overtime` | Check | 0 | Declared but **not read anywhere in `attendance_rule_engine.py`** — dead field today |
| `gazetted_overtime_multiplier` | Float | 2.0 | Applied *inside* the Attendance calculation itself (unusual — see §5.2) |
| `overtime_multiplier` | Float | 1.5 | Only read by the dormant `salary_slip_controller.py`, never by the Attendance calculation |
| `force_hours_on_friday` | Check | 1 | Declared but **not read anywhere in `attendance_rule_engine.py`** — dead field today |
| `allow_negative_hours` | Check | 0 | If set, deficiency is always reported as 0 instead of the shortfall |
| `enable_friday_logic` | Check | 1 | Master switch for all Friday-specific behavior |
| `consider_check_out_next_day` | Check | 1 | Declared but the overnight-shift handling in the engine is unconditional (always adjusts if checkout < checkin) — this flag is **not actually read**, again dead today |
| `allow_absent_on_holiday` | Check | 0 | Declared, **not read** by the engine — dead field today |

**Action item:** four fields above (`ignore_break_in_overtime`, `force_hours_on_friday`,
`consider_check_out_next_day`, `allow_absent_on_holiday`) exist on the doctype and are
presumably shown to the client as configurable, but currently have zero effect on
calculation. Decide per-field whether to wire them up or remove them before production
sign-off — a client toggling one of these and seeing no behavior change will be a
support headache.

### Employee (custom fields)

- `custom_attendance_rule` — Link to Attendance Rule. **Required**: `AttendanceRuleEngine.__init__` calls `frappe.throw()` if unset.
- `custom_attendance_required` — gates whether Bulk Attendance processes this employee.
- `custom_generate_salary_based_on_attendance` — checked by the dormant `salary_slip_controller.py`; currently inert since that override isn't wired in.
- `custom_old_code` — legacy/biometric device employee code, used as a fallback lookup by `validate_employee_code()`.
- Others (`custom_qr_code`, `custom_father_name`, government-ID fields) are unrelated to attendance/payroll.

### Attendance (custom fields, all written by `AttendanceController`)

`custom_regular_hours`, `custom_overtime_hours`, `custom_deficiency_hours`,
`custom_total_hours`, `custom_break_duration_minutes`, `custom_is_friday`,
`custom_is_gazetted_holiday`, `custom_adjusted_check_in`, `custom_adjusted_check_out`,
`custom_manual_attendance` (flag: skip re-pulling from Employee Checkin),
`custom_check_in_time`, `custom_check_out_time`.

### Employee Checkin (custom field)

`custom_attendance_date` — set explicitly by the sync/bulk-attendance flow so overnight
shifts group correctly under one attendance date instead of splitting across midnight.

---

## 4. AttendanceRuleEngine algorithm

Entry point: `AttendanceRuleEngine(employee, attendance_date).calculate_attendance_summary(check_in_time, check_out_time)` in
[attendance_rule_engine.py](spotledger_hr/attendance_rule_engine.py), where `check_in_time`/`check_out_time` are `HH:MM:SS` strings.

Step order (this exact order matters — grace adjustment happens *before* hours are computed):

### 4.1 Overnight shift handling (`handle_overnight_shift`)
If `check_out < check_in` on the same date, checkout is assumed to be the next calendar
day. This is unconditional — always applied, regardless of any doctype flag.

### 4.2 Grace-period adjustment

**Check-in** (`get_time_after_grace_in`): compare actual check-in against the shift start
time (`factory_start_time`, or `friday_start_time` if Friday + `enable_friday_logic`):
- `check_in ≤ start + checkin_grace_minutes` → snapped to exactly `start` (late arrival forgiven)
- `start + checkin_grace_minutes < check_in ≤ start + checkin_max_grace_minutes` → snapped to `start + checkin_max_grace_minutes` (partially forgiven, capped)
- later than that → actual check-in time used as-is (no forgiveness — full lateness counts)

**Check-out** (`get_time_after_grace_out`): symmetric logic around shift end time, with
an extra branch for Friday prayer break — if `enable_friday_logic` and checkout falls
inside `[friday_break_start, friday_break_end]`, it's snapped to the factory end time
(i.e., leaving during Friday prayers is *not* penalized as early departure). Otherwise:
- checkout well before end time (beyond `checkout_max_grace_minutes` early) → kept as-is (early departure, will show as deficiency)
- checkout within grace window either side of end time → snapped to exact end time
- checkout up to `checkout_max_grace_minutes` late → snapped to that max-grace boundary
- checkout beyond max grace → kept as-is (full overtime counted for the actual extra time)

### 4.3 Break deduction (`get_break_duration`)
All-or-nothing, not pro-rated: if the (post-grace) shift spans past the break end time,
the *entire* `break_duration_minutes` is deducted once. If checkout is before break start,
or check-in is after break start, no deduction at all.

### 4.4 Core formulas (all operate on **grace-adjusted** times)

```
total_hours   = (adjusted_check_out − adjusted_check_in) in hours
net_hours     = total_hours − break_hours

regular_hours    = min(net_hours, required_hours)          # required_hours = Friday-specific
                                                              # duration if Friday logic active,
                                                              # else required_factory_hours

overtime_hours:
    if is_gazetted_holiday:
        return net_hours                                     # raw hours - no required-hours
                                                              # threshold on a holiday; multiplier
                                                              # applied downstream at pay time (§5.2)
    elif net_hours > required_hours:
        return net_hours − required_hours
    else:
        return 0

deficiency_hours:
    if is_gazetted_holiday:
        return 0
    elif net_hours < required_hours:
        return 0 if allow_negative_hours else (required_hours − net_hours)
    else:
        return 0
```

`is_gazetted_holiday` — see §5.1 for how this is determined (weekly-offs are now
excluded) and what's still worth double-checking against the client's actual Holiday
List before go-live.

### 4.5 Status side effect
`AttendanceController.update_attendance_fields()` sets `Attendance.status`:
`Present` if `regular_hours ≥ 8.0` (hardcoded, **not** `required_factory_hours`) or if
there's any deficiency > 0 (deficiency also maps to `Present`, not `Half Day` — there is
no half-day path despite the code comment saying "Mark as half day").

---

## 5. Known issues / must-verify-before-production

### 5.1 ✅ FIXED — Gazetted-holiday detection could fire on every Friday

`_is_gazetted_holiday()` called `employee_utils.is_holiday(employee, date, raise_exception=False)`
with `only_non_weekly` left at its default of `False`. `is_holiday()` just checks whether
the date exists as a row in the employee's resolved Holiday List — it does not
distinguish "gazetted/public holiday" rows from "weekly off" rows unless the caller
explicitly passes `only_non_weekly=True`. Since ERPNext Holiday Lists commonly
auto-populate weekly offs (e.g. every Friday) as rows in the same `Holiday` child table,
any Holiday List with Friday marked as a weekly off would have caused **every Friday to
also satisfy `is_gazetted_holiday`**, doubling overtime and zeroing deficiency on those
days instead of following the intended Friday shift/break rules.

**Fix applied**: `_is_gazetted_holiday()` now passes `only_non_weekly=True`, so recurring
weekly-off rows no longer count as gazetted holidays — only actual named holiday rows do.
Friday continues to be handled exclusively via `enable_friday_logic`.

**Still recommended before production**: pull the client's actual Holiday List for each
company and confirm there's no *non-weekly* row that also happens to fall on a Friday
(e.g. a public holiday that lands on a Friday) — in that case gazetted-overtime rules
would correctly take priority over Friday rules, which is worth confirming is the
intended precedence with the client.

### 5.2 ✅ FIXED — Gazetted overtime hours were pre-multiplied, would have double-counted pay if `salary_slip_controller.py` is ever enabled

`calculate_overtime()` used to return `net_hours_worked * gazetted_overtime_multiplier`
on gazetted days — i.e. `custom_overtime_hours` on the Attendance record was already
scaled by the multiplier, not raw hours worked. Downstream (dormant),
`salary_slip_controller.calculate_attendance_based_salary()` computes:

```python
gzt_overtime_amount = gzt_overtime_hours * hourly_rate * gzt_overtime_multiplier
```

Since `gzt_overtime_hours` already contained one factor of `gazetted_overtime_multiplier`,
this would have multiplied by it again — gazetted overtime pay would have come out
multiplier² instead of multiplier× (e.g. 4x instead of 2x actual worked hours' pay).

**Fix applied**: on gazetted holidays, `calculate_overtime()` now returns raw
`net_hours_worked` (no required-hours threshold applies on a holiday — every hour worked
counts as overtime, but as a plain hour count). The multiplier is applied exactly once,
at pay time, by the salary controller — consistent with how the regular 1.5x
`overtime_multiplier` was already handled (§5.3). This also means `custom_overtime_hours`
on a gazetted-holiday Attendance record is now directly comparable to hours written on a
manual attendance card, instead of a pre-scaled number.

### 5.3 Regular `overtime_multiplier` (1.5x) has no effect on the Attendance record itself
Only `gazetted_overtime_multiplier` is applied inside `attendance_rule_engine.py`. The
1.5x regular-overtime multiplier exists on the doctype and is read by the dormant salary
controller, but `custom_overtime_hours` on a normal (non-gazetted) day is **raw hours**,
unscaled. This is actually the more defensible design (Attendance should record facts;
pay-scaling belongs in payroll) — flagged here only so nobody assumes multiplier-adjusted
numbers are already in the Attendance doctype when reviewing data against manual cards.

### 5.4 Four Attendance Rule fields are configurable but currently inert
See the "Action item" note under §3 — `ignore_break_in_overtime`, `force_hours_on_friday`,
`consider_check_out_next_day`, `allow_absent_on_holiday` are not read by the engine at all.

### 5.5 Historical bug, already fixed
Prior to commit `7f2fd2f`, Attendance was double-wired (`override_doctype_class` *and* a
`doc_events["Attendance"]["validate"]` hook both independently ran the rule engine on
every save). Fixed — only the class override remains. Mentioned here so nobody
re-introduces the second hook while wiring up future doc_events.

---

## 6. Salary Slip / Payroll Entry — current state (item 4, decision deferred)

- **`salary_slip_controller.py`** (dormant): correctly subclasses HRMS `SalarySlip`,
  only diverts to attendance-based calculation when
  `Employee.custom_generate_salary_based_on_attendance` is checked, otherwise defers
  entirely to standard salary-structure behavior via `super().validate()`. This is the
  sound implementation to build on if/when attendance-based payroll goes live — but see
  §5.2 for a real bug that needs fixing first.
- **Payroll Entry**: no override exists anymore (the previous one called a
  nonexistent parent method and was deleted). Payroll Entry runs 100% stock HRMS.
- Until item 4 is decided, **all Salary Slips use standard ERPNext salary structures**;
  the `custom_generate_salary_based_on_attendance` checkbox on Employee currently has no
  effect on anything.

---

## 7. Validating the engine against manual attendance cards

Since the client cross-checks computed hours against attendance cards where staff
hand-write their own overtime, use `spotledger_hr/tools/attendance_rule_tester.py`
(added alongside this doc) to get engine output for a batch of check-in/check-out pairs
**without creating any Attendance or Employee Checkin records** — pure, repeatable
calculation, safe to run against a live or staging site.

**Input CSV** (header required): `employee,date,check_in,check_out`
- `employee`: Employee ID or `custom_old_code` (resolved the same way the SQLite sync does)
- `date`: `YYYY-MM-DD` — determines which Attendance Rule variant (Friday/holiday) applies
- `check_in` / `check_out`: `HH:MM:SS`, 24-hour

**Run**:
```bash
bench --site <site> execute spotledger_hr.tools.attendance_rule_tester.run_from_csv \
  --kwargs "{'input_csv_path': '/path/to/in.csv', 'output_csv_path': '/path/to/out.csv'}"
```

**Output CSV** adds: `resolved_employee`, `total_hours`, `regular_hours`,
`overtime_hours`, `deficiency_hours`, `break_duration_minutes`, `is_friday`,
`is_gazetted_holiday`, `adjusted_check_in`, `adjusted_check_out`, `error` (populated
instead of aborting the batch when a row fails — bad employee code, no Attendance Rule
assigned, etc.).

Recommended validation pass before go-live: pull a few weeks of real biometric
check-in/out times for a representative sample of employees (mix of on-time, late,
early-leave, overtime, and at least one Friday and one holiday), run them through this
tool, and diff `overtime_hours`/`deficiency_hours` against what's written on the
matching manual cards. Any mismatch on Friday or holiday dates should be checked against
§5.1 first — that's the most likely source of discrepancy. Reconciling the actual
comparison logic (fuzzy-matching card handwriting/format to this CSV) is explicitly out
of scope for now per the client's direction — this tool only produces the computed side.
