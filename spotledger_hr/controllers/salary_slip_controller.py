# Copyright (c) 2026, SpotLedger and contributors
# For license information, please see license.txt

"""
Custom Salary Slip Controller — formula-helper injection only.

Design intent (per Ehsen, Aug 2026): keep the actual payroll math native and
editable inside the Salary Structure UI as formulas, rather than hand-built
in Python. This controller does exactly one thing: it injects a handful of
read-only helper functions into SalarySlip.whitelisted_globals, the sandbox
dict that Salary Component 'formula' fields are eval'd against.

It does NOT override validate()/calculate_attendance_based_salary() and does
NOT bypass the Salary Structure's own earnings/deductions building logic —
that flow is left 100% to core HRMS. Formulas on "Breeze Salary" simply call
these functions instead of using bare literals.

Verified against July 2026 BFI Workers data (Muhammad Aslam / Syed Sadiq
Raza) — matches hand-calculated and Excel-reconciled figures exactly.
"""

import calendar

import frappe
from frappe.utils import flt, getdate
from hrms.payroll.doctype.salary_slip.salary_slip import SalarySlip

from spotledger_hr.utilities.salary_formula_helpers import (
    deduct_only_absences_employee,
    compute_hourly_rate,
    friday_absence_policy,
    get_attendance_rule,
    gzt_overtime_multiplier,
    overtime_multiplier,
    required_wage_hours,
)


class CustomSalarySlip(SalarySlip):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.whitelisted_globals.update(
            {
                "days_in_month": self._days_in_month,
                "paid_days": self._paid_days,
                "required_hours": self._required_hours,
                "hourly_rate": self._hourly_rate,
                "overtime_hours": self._overtime_hours,
                "gzt_overtime_hours": self._gzt_overtime_hours,
                "deficiency_hours": self._deficiency_hours,
                "overtime_multiplier": self._overtime_multiplier,
                "gzt_overtime_multiplier": self._gzt_overtime_multiplier,
                "pending_advance": self._pending_advance,
            }
        )

    def validate(self):
        super().validate()
        # Cosmetic only: the client's own wage-sheet convention treats
        # Sundays as a paid weekly off (not deducted), unlike ERPNext's
        # native payment_days, which excludes all Sundays/holidays from
        # the count. This has no effect on any earnings/deductions amount
        # — every component on Breeze Wages has depends_on_payment_days=0
        # — it only changes what's displayed/printed/reported.
        self.payment_days = self._paid_days()
        self.leave_without_pay = self._lwp_days()
        # Days before joining are neither paid nor absent.
        self.absent_days = max(
            self._days_in_month() - self._pre_joining_days() - self.payment_days, 0
        ) if self._joins_within_period() else self._days_in_month() - self.payment_days

    # -- calendar / attendance rule -----------------------------------

    def _days_in_month(self):
        d = getdate(self.start_date)
        return calendar.monthrange(d.year, d.month)[1]

    def _effective_end_date(self):
        """Last paid day of the slip: the native Employee.relieving_date
        (inclusive) when it falls inside the period, else the period end."""
        return getdate(self.actual_end_date)

    def _joins_within_period(self):
        joining = self.joining_date
        return bool(joining) and getdate(self.start_date) < joining <= getdate(self.end_date)

    def _effective_start_date(self):
        """First paid day of the slip: the native Employee.date_of_joining
        when it falls inside the period, else the period start."""
        return getdate(self.actual_start_date)

    def _pre_joining_days(self):
        if not self._joins_within_period():
            return 0
        return (self._effective_start_date() - getdate(self.start_date)).days

    def _lwp_window(self):
        """(start, end) of the days the slip pays for, or None when the
        employee joins after the period."""
        joining = self.joining_date
        if joining and joining > getdate(self.end_date):
            return None
        return self._effective_start_date(), self._effective_end_date()

    def _lwp_days(self):
        """Distinct dates inside the paid window covered by a submitted
        Attendance 'On Leave' of a Leave Type flagged is_lwp. Any weekday
        counts: Sundays, Fridays and named holidays included."""
        window = self._lwp_window()
        if not window:
            return 0
        return flt(
            frappe.db.sql(
                """
                SELECT COUNT(DISTINCT attendance_date) FROM `tabAttendance`
                WHERE employee=%(employee)s
                  AND attendance_date BETWEEN %(start)s AND %(end)s
                  AND status='On Leave'
                  AND docstatus=1
                  AND leave_type IN (SELECT name FROM `tabLeave Type` WHERE is_lwp=1)
                """,
                {"employee": self.employee, "start": window[0], "end": window[1]},
            )[0][0]
        )

    def _paid_days(self):
        """Total calendar days in the period minus real (non-Sunday) absences.
        Sundays are a paid weekly off and are never deducted, matching the
        client's existing wage-sheet convention (verified against July 2026
        Excel: Days=31 for a Sunday-only-absence employee, Days=30 for one
        with a single additional real absence).

        Dates covered by a submitted Leave Without Pay (Leave Type is_lwp)
        are unpaid whatever the weekday, Sundays and holidays included.
        Other leave types stay paid.

        A slip for an employee relieved inside the period stops at the
        relieving date, as in core HRMS: later Sundays and Friday credits
        are not paid. Likewise it starts at date_of_joining when that falls
        inside the period: earlier days (Sundays included) are not paid.
        The two clamps compose."""
        joining = self.joining_date
        if joining and joining > getdate(self.end_date):
            return 0
        start = self._effective_start_date()
        end = self._effective_end_date()
        total_days = self._days_in_month()
        relieving = self.relieving_date
        relieved = relieving and getdate(self.start_date) <= relieving <= getdate(self.end_date)
        if relieved or self._joins_within_period():
            total_days = (end - start).days + 1
        unpaid_absences = frappe.db.sql(
            """
            SELECT COUNT(DISTINCT attendance_date) FROM `tabAttendance`
            WHERE employee=%(employee)s
              AND attendance_date BETWEEN %(start)s AND %(end)s
              AND status='Absent'
              AND docstatus=1
              AND DAYOFWEEK(attendance_date) != 1  -- MySQL/MariaDB: 1 = Sunday
            """,
            {"employee": self.employee, "start": start, "end": end},
        )[0][0]
        eligible, _ = friday_absence_policy(self.employee, start, end)
        paid = total_days - flt(unpaid_absences) - self._lwp_days() + eligible
        return max(0, paid)

    def _get_attendance_rule(self):
        return get_attendance_rule(self.employee)

    def _required_hours(self):
        """Net hours per day used as the hourly-rate divisor. See
        spotledger_hr.utilities.salary_formula_helpers.required_wage_hours
        for why this is independent of required_factory_hours (the daily
        OT threshold)."""
        return required_wage_hours(self.employee)

    def _overtime_multiplier(self):
        return overtime_multiplier(self.employee)

    def _gzt_overtime_multiplier(self):
        return gzt_overtime_multiplier(self.employee)

    # -- rate --------------------------------------------------------

    def _hourly_rate(self):
        base = flt(getattr(self, "_salary_structure_assignment", None) and self._salary_structure_assignment.get("base"))
        if not base:
            base = flt(
                frappe.db.get_value(
                    "Salary Structure Assignment",
                    {"employee": self.employee, "salary_structure": self.salary_structure, "docstatus": 1},
                    "base",
                    order_by="from_date desc",
                )
            )
        return compute_hourly_rate(self.employee, base, self.start_date)

    # -- attendance sums -----------------------------------------------

    def _overtime_hours(self):
        if deduct_only_absences_employee(self.employee):
            return 0.0
        return flt(
            frappe.db.sql(
                """
                SELECT IFNULL(SUM(custom_overtime_hours),0) FROM `tabAttendance`
                WHERE employee=%(employee)s
                  AND attendance_date BETWEEN %(start)s AND %(end)s
                  AND status='Present' AND docstatus=1
                  AND (custom_is_gazetted_holiday=0 OR custom_is_gazetted_holiday IS NULL)
                """,
                {"employee": self.employee, "start": self.start_date, "end": self._effective_end_date()},
            )[0][0]
        )

    def _gzt_overtime_hours(self):
        if deduct_only_absences_employee(self.employee):
            return 0.0
        return flt(
            frappe.db.sql(
                """
                SELECT IFNULL(SUM(custom_overtime_hours),0) FROM `tabAttendance`
                WHERE employee=%(employee)s
                  AND attendance_date BETWEEN %(start)s AND %(end)s
                  AND status='Present' AND docstatus=1
                  AND custom_is_gazetted_holiday=1
                """,
                {"employee": self.employee, "start": self.start_date, "end": self._effective_end_date()},
            )[0][0]
        )

    def _deficiency_hours(self):
        eligible, hours = friday_absence_policy(self.employee, self.start_date, self._effective_end_date())
        if deduct_only_absences_employee(self.employee):
            return eligible * hours
        return flt(
            frappe.db.sql(
                """
                SELECT IFNULL(SUM(custom_deficiency_hours),0) FROM `tabAttendance`
                WHERE employee=%(employee)s
                  AND attendance_date BETWEEN %(start)s AND %(end)s
                  AND status='Present' AND docstatus=1
                """,
                {"employee": self.employee, "start": self.start_date, "end": self._effective_end_date()},
            )[0][0]
        ) + eligible * hours

    # -- advances --------------------------------------------------------

    def _pending_advance(self):
        """Sum of submitted, not-yet-applied Employee Advance Deduction rows
        for this employee within the payroll period. 'Not-yet-applied' means
        salary_slip is still blank, so an advance is never deducted twice."""
        return flt(
            frappe.db.sql(
                """
                SELECT IFNULL(SUM(deduction_amount),0) FROM `tabEmployee Advance Deduction`
                WHERE employee=%(employee)s
                  AND posting_date BETWEEN %(start)s AND %(end)s
                  AND docstatus=1
                  AND (salary_slip IS NULL OR salary_slip = '')
                """,
                {"employee": self.employee, "start": self.start_date, "end": self.end_date},
            )[0][0]
        )
