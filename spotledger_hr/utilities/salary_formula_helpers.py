# Copyright (c) 2026, SpotLedger and contributors
# For license information, please see license.txt

"""
Shared, employee/period-parameterised logic behind the Breeze Wages formula
helpers (days_in_month, hourly_rate, required_hours, the OT multipliers).

Two separate HRMS code paths evaluate these formulas and each needs its own
copy of these functions injected into its own eval namespace:
  - SalarySlip.eval_condition_and_formula(), via self.whitelisted_globals
    (see controllers/salary_slip_controller.py)
  - SalaryStructureAssignment._evaluate_component_table(), via the data dict
    returned by _get_component_eval_context() (see
    controllers/salary_structure_assignment_controller.py)
Both call sites are HRMS core methods we don't own, so the shared math lives
here and each controller binds it into whatever namespace its call site
actually reads from.
"""

import calendar

import frappe
from frappe.utils import flt, getdate


def days_in_month_for(date_str) -> int:
    d = getdate(date_str)
    return calendar.monthrange(d.year, d.month)[1]


def get_attendance_rule(employee):
    rule_name = frappe.get_cached_value("Employee", employee, "custom_attendance_rule")
    if not rule_name:
        return None
    return frappe.get_cached_doc("Attendance Rule", rule_name)


def friday_absence_policy(employee, start_date, end_date):
    """Read-only opt-in: distinct submitted Friday absences, never missing work."""
    rule = get_attendance_rule(employee)
    hours = flt(rule.get("friday_absence_deficiency_hours")) if rule else 0
    effective = rule.get("friday_absence_policy_from_date") if rule else None
    if hours <= 0 or not effective:
        return 0, 0.0
    count = frappe.db.sql(
        """SELECT COUNT(DISTINCT attendance_date) FROM `tabAttendance`
        WHERE employee=%(employee)s AND docstatus=1 AND status='Absent'
          AND attendance_date BETWEEN %(start)s AND %(end)s
          AND attendance_date >= %(effective)s AND DAYOFWEEK(attendance_date)=6""",
        {"employee": employee, "start": start_date, "end": end_date, "effective": effective},
    )[0][0]
    return int(count), hours


def required_wage_hours(employee) -> float:
    """Net hours/day used as the hourly-rate divisor = wage_rate_hours minus
    break. Deliberately independent of required_factory_hours, which drives
    the daily regular/overtime split in the Attendance Rule Engine and may
    differ per rule (e.g. a driver's 9-hour shift)."""
    rule = get_attendance_rule(employee)
    if not rule:
        return 8.0
    net = flt(rule.wage_rate_hours) - flt(rule.break_duration_minutes or 0) / 60
    return net or 8.0


def compute_hourly_rate(employee, base, start_date) -> float:
    days = days_in_month_for(start_date)
    hours = required_wage_hours(employee)
    return flt(base) / (days * hours) if days and hours else 0


def overtime_multiplier(employee) -> float:
    """Per-employee multiplier from the assigned Attendance Rule. `0` is a
    valid, intentional value (e.g. a role ineligible for paid overtime), so
    it must not fall back to the 1.5 default — only the absence of a rule
    should."""
    rule = get_attendance_rule(employee)
    if not rule:
        return 1.5
    return flt(rule.overtime_multiplier)


def gzt_overtime_multiplier(employee) -> float:
    """See overtime_multiplier() — same rationale for not treating `0` as
    falsy."""
    rule = get_attendance_rule(employee)
    if not rule:
        return 2.0
    return flt(rule.gazetted_overtime_multiplier)
