import unittest
from unittest.mock import patch
import frappe
from spotledger_hr.utilities.salary_formula_helpers import absence_only_employee


class TestAbsenceOnlyPeriodScope(unittest.TestCase):
    def test_only_explicit_inclusive_july_scope(self):
        config = {'absence_only_employee_periods': {'10': {'from_date': '2026-07-01', 'through_date': '2026-07-31'}}, 'absence_only_employees': ['10']}
        with patch.dict(frappe.conf, config):
            for start, end, expected in [('2026-07-01', '2026-07-31', True), ('2026-07-01', '2026-07-01', True), ('2026-07-31', '2026-07-31', True), ('2026-06-30', '2026-07-01', False), ('2026-07-31', '2026-08-01', False), ('2026-08-01', '2026-08-31', False), ('2026-07-31', '2026-07-01', False)]:
                with self.subTest(start=start, end=end):
                    self.assertEqual(absence_only_employee('10', start, end), expected)
            self.assertFalse(absence_only_employee('other', '2026-07-01', '2026-07-31'))
            self.assertFalse(absence_only_employee('10'))

    def test_legacy_employee_list_cannot_enable_unbounded_policy(self):
        with patch.dict(frappe.conf, {'absence_only_employees': ['10'], 'absence_only_employee_periods': {}}):
            self.assertFalse(absence_only_employee('10'))
