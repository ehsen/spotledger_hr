"""Date-bound consumer regressions; mock only source/configuration access."""
import unittest
from unittest.mock import patch

import frappe
from frappe.utils import getdate

from spotledger_hr.controllers.attendance_controller import AttendanceController
from spotledger_hr.controllers.salary_slip_controller import CustomSalarySlip
from spotledger_hr.utilities.salary_formula_helpers import friday_absence_policy


class TestEmployeePolicyConsumers(unittest.TestCase):
    def setUp(self):
        # Load metadata before intercepting SQL aggregate reads.
        frappe.get_meta('Salary Slip')
        self.config = patch.dict(frappe.conf, {
            'absence_only_employee_periods': {'10': {
                'from_date': '2026-07-01', 'through_date': '2026-07-31'}},
            'payroll_employment_end_dates': {'HR-EMP-00074': '2026-07-18'},
        })
        self.config.start()
        self.addCleanup(self.config.stop)

    def slip(self, employee='10', start='2026-07-01', end='2026-07-31'):
        return CustomSalarySlip(dict(doctype='Salary Slip', employee=employee,
                                    start_date=start, end_date=end))

    def test_salary_consumers_only_suppress_inside_authorized_period(self):
        for employee, start, end, suppressed in (
            ('10', '2026-06-01', '2026-06-30', False),
            ('10', '2026-07-01', '2026-07-31', True),
            ('10', '2026-08-01', '2026-08-31', False),
            ('other', '2026-07-01', '2026-07-31', False),
            ('10', '2026-06-30', '2026-07-31', False),
            ('10', '2026-07-01', '2026-08-01', False),
        ):
            with self.subTest(employee=employee, start=start, end=end):
                slip = self.slip(employee, start, end)
                with patch.object(frappe.db, 'sql', return_value=[[3]]), patch(
                    'spotledger_hr.utilities.salary_formula_helpers.get_attendance_rule',
                    return_value=None,
                ):
                    self.assertEqual(slip._overtime_hours(), 0 if suppressed else 3)
                    self.assertEqual(slip._gzt_overtime_hours(), 0 if suppressed else 3)
                    self.assertEqual(slip._deficiency_hours(), 0 if suppressed else 3)

    def test_default_off_salary_consumers_preserve_hours(self):
        with patch.dict(frappe.conf, {'absence_only_employee_periods': {}}), patch.object(
            frappe.db, 'sql', return_value=[[3]],
        ), patch('spotledger_hr.utilities.salary_formula_helpers.get_attendance_rule', return_value=None):
            slip = self.slip()
            self.assertEqual((slip._overtime_hours(), slip._gzt_overtime_hours(),
                              slip._deficiency_hours()), (3, 3, 3))

    def test_cutoff_is_inclusive_in_every_aggregate(self):
        rule = frappe._dict(friday_absence_deficiency_hours=5.5,
                            friday_absence_policy_from_date='2026-07-01')
        with patch('spotledger_hr.utilities.salary_formula_helpers.get_attendance_rule', return_value=rule):
            for employee, start, end, expected_end, paid in (
                ('HR-EMP-00074', '2026-07-01', '2026-07-31', '2026-07-18', 18),
                ('HR-EMP-00074', '2026-06-01', '2026-06-30', '2026-06-30', 30),
                ('HR-EMP-00074', '2026-08-01', '2026-08-31', '2026-07-18', 0),
                ('other', '2026-07-01', '2026-07-31', '2026-07-31', 31),
            ):
                with self.subTest(employee=employee, start=start), patch.object(
                    frappe.db, 'sql', return_value=[[0]],
                ) as sql:
                    slip = self.slip(employee, start, end)
                    self.assertEqual(slip._paid_days(), paid)
                    self.assertEqual(slip._overtime_hours(), 0)
                    self.assertEqual(slip._gzt_overtime_hours(), 0)
                    self.assertEqual(slip._deficiency_hours(), 0)
                    friday_absence_policy(employee, start, end)
                    for call in sql.call_args_list:
                        self.assertEqual(getdate(call.args[1]['end']), getdate(expected_end))

    def assert_cutoff_paid_days(self, start, end, expected):
        with patch.object(frappe.db, 'sql', return_value=[[0]]), patch(
            'spotledger_hr.utilities.salary_formula_helpers.get_attendance_rule',
            return_value=None,
        ):
            self.assertEqual(self.slip('HR-EMP-00074', start, end)._paid_days(), expected)

    def test_paid_days_end_before_cutoff(self):
        self.assert_cutoff_paid_days('2026-07-01', '2026-07-17', 17)

    def test_paid_days_end_at_inclusive_cutoff(self):
        self.assert_cutoff_paid_days('2026-07-01', '2026-07-18', 18)

    def test_paid_days_end_after_cutoff(self):
        self.assert_cutoff_paid_days('2026-07-01', '2026-07-19', 18)

    def test_paid_days_start_after_cutoff(self):
        self.assert_cutoff_paid_days('2026-07-19', '2026-07-31', 0)

    def test_paid_days_cutoff_bounds_partial_and_cross_month_ranges(self):
        self.assert_cutoff_paid_days('2026-07-10', '2026-07-18', 9)
        self.assert_cutoff_paid_days('2026-06-30', '2026-07-18', 19)
        with patch.dict(frappe.conf, {'payroll_employment_end_dates': {}}):
            self.assert_cutoff_paid_days('2026-07-01', '2026-07-18', 31)
            self.assert_cutoff_paid_days('2026-06-30', '2026-07-18', 30)

    def test_attendance_consumer_only_promotes_within_scope(self):
        # Actual engine and controller; only Employee/Rule/holiday reads replaced.
        rule = frappe._dict(factory_start_time='08:00:00', factory_end_time='17:00:00',
            required_factory_hours=5, wage_rate_hours=8.5, break_duration_minutes=0,
            regular_break_start='13:00:00', regular_break_end='13:30:00',
            enable_friday_logic=0, checkin_grace_minutes=10,
            checkin_max_grace_minutes=30, checkout_grace_minutes=10,
            checkout_max_grace_minutes=30, allow_negative_hours=1,
            overtime_multiplier=0, gazetted_overtime_multiplier=2,
            hours_calculation_mode='Factory Timing')
        employee_doc = frappe._dict(custom_attendance_rule='_Policy Rule')
        def get_doc(doctype, name):
            return employee_doc if doctype == 'Employee' else rule
        with patch.object(frappe, 'get_doc', side_effect=get_doc), patch(
            'spotledger_hr.attendance_rule_engine.get_holiday_list_for_employee', return_value=None,
        ):
            for employee, date, enabled, expected in (
                ('10', '2026-06-30', True, 'Absent'),
                ('10', '2026-07-01', True, 'Present'),
                ('10', '2026-07-31', True, 'Present'),
                ('10', '2026-08-01', True, 'Absent'),
                ('other', '2026-07-01', True, 'Absent'),
                ('10', '2026-07-01', False, 'Absent'),
            ):
                with self.subTest(employee=employee, date=date, enabled=enabled):
                    doc = AttendanceController(dict(doctype='Attendance', employee=employee,
                        attendance_date=date, status='Absent', custom_manual_attendance=1,
                        custom_check_in_time=f'{date} 08:01:02',
                        custom_check_out_time=f'{date} 13:01:00'))
                    with patch.dict(frappe.conf, {'absence_only_employee_periods':
                        self.config.values['absence_only_employee_periods'] if enabled else {}}):
                        doc.calculate_attendance_metrics()
                    self.assertGreater(doc.working_hours, 0)
                    self.assertEqual(doc.status, expected)
