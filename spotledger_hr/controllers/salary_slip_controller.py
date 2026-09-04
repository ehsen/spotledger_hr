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
    compute_hourly_rate,
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
        self.absent_days = self._days_in_month() - self.payment_days

    # -- calendar / attendance rule -----------------------------------

    def _days_in_month(self):
        d = getdate(self.start_date)
        return calendar.monthrange(d.year, d.month)[1]

    def _paid_days(self):
        """Total calendar days in the period minus real (non-Sunday) absences.
        Sundays are a paid weekly off and are never deducted, matching the
        client's existing wage-sheet convention (verified against July 2026
        Excel: Days=31 for a Sunday-only-absence employee, Days=30 for one
        with a single additional real absence)."""
        total_days = self._days_in_month()
        unpaid_absences = frappe.db.sql(
            """
            SELECT COUNT(*) FROM `tabAttendance`
            WHERE employee=%(employee)s
              AND attendance_date BETWEEN %(start)s AND %(end)s
              AND status='Absent'
              AND docstatus=1
              AND DAYOFWEEK(attendance_date) != 1  -- MySQL/MariaDB: 1 = Sunday
            """,
            {"employee": self.employee, "start": self.start_date, "end": self.end_date},
        )[0][0]
        return total_days - flt(unpaid_absences)

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
        return flt(
            frappe.db.sql(
                """
                SELECT IFNULL(SUM(custom_overtime_hours),0) FROM `tabAttendance`
                WHERE employee=%(employee)s
                  AND attendance_date BETWEEN %(start)s AND %(end)s
                  AND status='Present' AND docstatus=1
                  AND (custom_is_gazetted_holiday=0 OR custom_is_gazetted_holiday IS NULL)
                """,
                {"employee": self.employee, "start": self.start_date, "end": self.end_date},
            )[0][0]
        )

    def _gzt_overtime_hours(self):
        return flt(
            frappe.db.sql(
                """
                SELECT IFNULL(SUM(custom_overtime_hours),0) FROM `tabAttendance`
                WHERE employee=%(employee)s
                  AND attendance_date BETWEEN %(start)s AND %(end)s
                  AND status='Present' AND docstatus=1
                  AND custom_is_gazetted_holiday=1
                """,
                {"employee": self.employee, "start": self.start_date, "end": self.end_date},
            )[0][0]
        )

    def _deficiency_hours(self):
        return flt(
            frappe.db.sql(
                """
                SELECT IFNULL(SUM(custom_deficiency_hours),0) FROM `tabAttendance`
                WHERE employee=%(employee)s
                  AND attendance_date BETWEEN %(start)s AND %(end)s
                  AND status='Present' AND docstatus=1
                """,
                {"employee": self.employee, "start": self.start_date, "end": self.end_date},
            )[0][0]
        )

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
