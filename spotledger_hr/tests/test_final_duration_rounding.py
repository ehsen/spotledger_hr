"""Scoped final rounding: database-backed engine with rollback fixtures.

Not native Attendance lifecycle or payroll integration coverage.
"""
import unittest
import frappe
from spotledger_hr.attendance_rule_engine import AttendanceRuleEngine
from spotledger_hr.tests import test_friday_absence_policy as fixtures

KEY = 'spotledger_hr_final_duration_rounding'
MISSING = object()


class TestFinalDurationRounding(unittest.TestCase):
    change_rule = fixtures.TestFridayAbsencePolicy.change_rule

    def setUp(self):
        self.previous = frappe.conf.get(KEY, MISSING)
        self.addCleanup(self.restore_config)
        frappe.conf.pop(KEY, None)
        fixtures.TestFridayAbsencePolicy.setUp(self)
        self.change_rule(regular_break_start='12:30:00', regular_break_end='13:00:00',
                         checkin_grace_minutes=15, checkin_max_grace_minutes=30,
                         checkout_grace_minutes=15, checkout_max_grace_minutes=30,
                         enable_overtime_rounding=1, overtime_rounding_interval_minutes=30,
                         overtime_rounding_threshold_minutes=15)

    def restore_config(self):
        frappe.conf.pop(KEY, None)
        if self.previous is not MISSING:
            frappe.conf[KEY] = self.previous

    def tearDown(self):
        fixtures.TestFridayAbsencePolicy.tearDown(self)

    def activate(self):
        frappe.conf[KEY] = {self.rule.name: {'from_date': '2026-07-01', 'through_date': '2026-07-31'}}

    def engine(self, date='2026-07-11'):
        return AttendanceRuleEngine(self.employee, date)

    def test_opt_in_rounds_final_components_preserving_other_metrics(self):
        for start, end, component, expected in (
                ('08:47:00', '17:00:00', 'deficiency_hours', 1),
                ('08:47:00', '19:00:00', 'overtime_hours', 1)):
            frappe.conf.pop(KEY, None)
            before = self.engine().calculate_attendance_summary(start, end)
            self.activate()
            after = self.engine().calculate_attendance_summary(start, end)
            self.assertEqual(after[component], expected)
            for key in before.keys() - {'overtime_hours', 'deficiency_hours'}:
                self.assertEqual(after[key], before[key], key)
