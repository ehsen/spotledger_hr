"""Opt-in employee policies; synthetic fixtures on isolated site only."""
import unittest
from unittest.mock import patch
import frappe
from spotledger_hr.tests.test_attendance_status_policy import TestAttendanceStatusPolicy
from spotledger_hr.tests.test_friday_absence_policy import TestFridayAbsencePolicy


class TestAbsenceOnly(TestAttendanceStatusPolicy):
    def setUp(self):
        super().setUp()
        self.config = patch.dict(frappe.conf, {'absence_only_employee_periods': {self.employee: {'from_date': '2026-07-01', 'through_date': '2026-07-31'}}})
        self.config.start()

    def tearDown(self):
        self.config.stop()
        super().tearDown()

    def test_positive_short_native_pair(self):
        doc = self.worked(date='2026-07-01', start='08:01:02', end='13:01:00', manual=False)
        self.change_rule(required_factory_hours=5, break_duration_minutes=0, allow_negative_hours=1)
        self.add_sources(doc)
        doc.validate()
        self.assertEqual(doc.status, 'Present')
        self.assertEqual(doc.custom_deficiency_hours, 0)
        self.assertGreater(doc.working_hours, 0)

    def test_blank_absence_remains_chargeable(self):
        doc = self.worked(date='2026-07-02', manual=False)
        doc.custom_check_in_time = None
        doc.custom_check_out_time = None
        doc.validate()
        self.assertEqual(doc.status, 'Absent')
        self.assertFalse(doc.custom_check_in_time)

    def test_stale_pair_does_not_promote(self):
        doc = self.worked(date='2026-07-01', start='08:01:02', end='13:01:00', manual=False)
        self.change_rule(required_factory_hours=5, break_duration_minutes=0, allow_negative_hours=1)
        doc.validate()
        self.assertEqual(doc.status, 'Absent')

    # Inherited legacy tests are exercised separately, not under this opt-in.


class TestEmploymentCutoff(TestFridayAbsencePolicy):
    def setUp(self):
        super().setUp()
        # Local business replica predates Friday custom fields; synthetic rule only.
        self.rule_access = patch('spotledger_hr.utilities.salary_formula_helpers.get_attendance_rule', return_value=self.rule)
        self.rule_access.start()

    def tearDown(self):
        self.rule_access.stop()
        super().tearDown()

    def test_post_departure_sundays_and_fridays(self):
        for day in range(19, 32):
            self.attendance(f'2026-07-{day:02}')
        with patch.dict(frappe.conf, {'payroll_employment_end_dates': {self.employee: '2026-07-18'}}):
            self.assertEqual(self.slip._paid_days(), 18)
            self.assertEqual(self.slip._deficiency_hours(), 0)

    def test_absence_only_no_short_charge_or_overtime(self):
        self.attendance('2026-07-02', 'Present', deficiency=3, overtime=4)
        self.attendance('2026-07-03')
        with patch.dict(frappe.conf, {'absence_only_employee_periods': {self.employee: {'from_date': '2026-07-01', 'through_date': '2026-07-31'}}}):
            self.assertEqual(self.slip._overtime_hours(), 0)
            self.assertEqual(self.slip._gzt_overtime_hours(), 0)
            self.assertEqual(self.slip._deficiency_hours(), 5.5)
