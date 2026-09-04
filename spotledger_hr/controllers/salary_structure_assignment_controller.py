# Copyright (c) 2026, SpotLedger and contributors
# For license information, please see license.txt

"""
Custom Salary Structure Assignment Controller — formula-helper injection,
mirroring controllers/salary_slip_controller.py.

HRMS's own component-evaluation architecture runs formulas through TWO
separate code paths, not one:

  1. SalaryStructureAssignment._evaluate_component_table() — a period-
     independent "full cycle, no absences" pre-pass (used both by
     SalaryStructureAssignment.calculate_ctc_and_gross() on save, and by
     SalarySlip._set_evaluated_components() on every slip creation, via
     get_evaluated_components()). This pass evaluates formulas with a bare
     COMPONENT_EVAL_GLOBALS dict as globals and its own synthetic `data`
     dict (built by _get_component_eval_context()) as locals.
  2. SalarySlip.eval_condition_and_formula() — the actual prorated pass
     that produces the amounts on the slip, using self.whitelisted_globals
     (see CustomSalarySlip).

Only (2) was covered by CustomSalarySlip's whitelisted_globals injection.
(1) runs first and unconditionally, on every slip creation, and calls
formulas like `days_in_month()` / `hourly_rate()` with only HRMS's bare
globals in scope -- raising NameError and aborting slip creation entirely
before (2) is ever reached.

Since _evaluate_component_table() reads its extra names from `data`
(passed as eval *locals*, not globals) rather than from `self`, the fix is
to inject the same helper callables into the dict returned by
_get_component_eval_context() -- Python resolves a bare name call like
`days_in_month()` against locals before globals, so this is picked up
without needing to touch the (hardcoded, not self.-scoped) globals dict in
_evaluate_component_table() itself.

This pass has no real attendance data (it deliberately simulates a full
cycle with zero absences/LWP for the CTC/annual-gross estimate), so
overtime_hours/gzt_overtime_hours/deficiency_hours are 0 here by design --
the real per-period values still come from CustomSalarySlip on the actual
slip.
"""

from frappe.utils import flt
from hrms.payroll.doctype.salary_structure_assignment.salary_structure_assignment import (
    SalaryStructureAssignment,
)

from spotledger_hr.utilities.salary_formula_helpers import (
    compute_hourly_rate,
    days_in_month_for,
    gzt_overtime_multiplier,
    overtime_multiplier,
    required_wage_hours,
)


class CustomSalaryStructureAssignment(SalaryStructureAssignment):
    def _get_component_eval_context(self):
        data = super()._get_component_eval_context()
        employee = self.employee
        base = flt(self.base)
        data.update(
            {
                "days_in_month": lambda: days_in_month_for(data.start_date),
                "paid_days": lambda: flt(data.payment_days),
                "required_hours": lambda: required_wage_hours(employee),
                "hourly_rate": lambda: compute_hourly_rate(employee, base, data.start_date),
                "overtime_hours": lambda: 0.0,
                "gzt_overtime_hours": lambda: 0.0,
                "deficiency_hours": lambda: 0.0,
                "overtime_multiplier": lambda: overtime_multiplier(employee),
                "gzt_overtime_multiplier": lambda: gzt_overtime_multiplier(employee),
                "pending_advance": lambda: 0.0,
            }
        )
        return data
