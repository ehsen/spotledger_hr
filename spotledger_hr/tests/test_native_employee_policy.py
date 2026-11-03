"""Employee-specific payroll requirements expressed natively.

Employment end: Employee.relieving_date (inclusive), as in core HRMS.
Short-day entitlement: Attendance Rule fields (present_on_any_genuine_work,
allow_negative_hours, overtime multipliers), assigned through the Employee.

Synthetic fixtures only; execute on an isolated test site.
"""
import unittest

import frappe

from spotledger_hr.controllers.attendance_controller import AttendanceController
from spotledger_hr.tests import test_friday_absence_policy as fixtures
from spotledger_hr.tests.test_attendance_status_policy import TestAttendanceStatusPolicy


class TestRelievingDateCutoff(unittest.TestCase):
    setUp = fixtures.TestFridayAbsencePolicy.setUp
    tearDown = fixtures.TestFridayAbsencePolicy.tearDown
    attendance = fixtures.TestFridayAbsencePolicy.attendance

    def relieve(self, date):
        frappe.db.set_value('Employee', self.employee, 'relieving_date', date)
        frappe.clear_document_cache('Employee', self.employee)

    def seed(self):
        self.attendance('2026-07-14', 'Present', deficiency=7)
        self.attendance('2026-07-15')
        self.attendance('2026-07-16')
        self.attendance('2026-07-24')  # Friday after the last day
        self.attendance('2026-07-31')  # Friday after the last day
        self.attendance('2026-07-27', 'Present', deficiency=11, overtime=4)

    def test_nothing_after_the_inclusive_relieving_date_is_paid(self):
        self.seed()
        self.relieve('2026-07-18')
        self.assertEqual(self.slip._paid_days(), 16)
        self.assertEqual(self.slip._deficiency_hours(), 7)
        self.assertEqual(self.slip._overtime_hours(), 0)

    def test_last_day_attendance_is_included(self):
        self.attendance('2026-07-18')  # absent on the relieving date itself
        self.relieve('2026-07-18')
        self.assertEqual(self.slip._paid_days(), 17)

    def test_without_relieving_date_whole_period_applies(self):
        self.seed()
        self.assertEqual(self.slip._paid_days(), 31 - 4 + 2)
        self.assertEqual(self.slip._deficiency_hours(), 7 + 11 + 2 * 5.5)

    def test_other_periods_are_untouched(self):
        self.relieve('2026-07-18')
        self.slip.start_date, self.slip.end_date = '2026-06-01', '2026-06-30'
        self.assertEqual(self.slip._paid_days(), 30)

    def test_period_ending_on_relieving_date_counts_its_own_days(self):
        self.relieve('2026-07-18')
        self.slip.end_date = '2026-07-18'
        self.assertEqual(self.slip._paid_days(), 18)

    def test_relieving_on_period_end_is_a_full_period(self):
        self.relieve('2026-07-31')
        self.assertEqual(self.slip._paid_days(), 31)


class TestDeductOnlyForAbsences(unittest.TestCase):
    setUp = fixtures.TestFridayAbsencePolicy.setUp
    tearDown = fixtures.TestFridayAbsencePolicy.tearDown
    change_rule = fixtures.TestFridayAbsencePolicy.change_rule
    attendance = fixtures.TestFridayAbsencePolicy.attendance
    worked = TestAttendanceStatusPolicy.worked
    add_sources = TestAttendanceStatusPolicy.add_sources

    def flag(self, value=1):
        frappe.db.set_value('Employee', self.employee, 'custom_deduct_only_absences', value)
        frappe.clear_document_cache('Employee', self.employee)

    def short_day(self):
        return self.worked(date='2026-07-01', start='08:01:02', end='13:01:00', manual=False)

    def test_unflagged_employee_keeps_short_worked_day_absent(self):
        doc = self.short_day()
        self.add_sources(doc)
        doc.validate()
        self.assertEqual(doc.status, 'Absent')

    def test_flagged_employee_genuine_short_day_is_present_without_deficiency(self):
        self.flag()
        doc = self.short_day()
        self.add_sources(doc)
        doc.validate()
        self.assertEqual(doc.status, 'Present')
        self.assertEqual(doc.custom_deficiency_hours, 0)
        self.assertGreater(doc.working_hours, 0)

    def test_stale_pair_is_not_promoted(self):
        self.flag()
        doc = self.short_day()
        doc.validate()
        self.assertEqual(doc.status, 'Absent')

    def test_no_times_stays_absent(self):
        self.flag()
        doc = AttendanceController(dict(doctype='Attendance', employee=self.employee,
            attendance_date='2026-07-02', status='Absent', custom_manual_attendance=0))
        doc.validate()
        self.assertEqual(doc.status, 'Absent')

    def test_slip_pays_no_overtime_and_no_shortfall_but_true_absences_count(self):
        self.attendance('2026-07-02', 'Present', deficiency=3, overtime=4)
        self.attendance('2026-07-03')  # Friday absence, charged by the rule
        self.attendance('2026-07-06')  # weekday absence
        self.assertEqual(self.slip._overtime_hours(), 4)
        self.flag()
        self.assertEqual(self.slip._overtime_hours(), 0)
        self.assertEqual(self.slip._gzt_overtime_hours(), 0)
        self.assertEqual(self.slip._deficiency_hours(), 5.5)
        self.assertEqual(self.slip._paid_days(), 31 - 2 + 1)


class TestJoiningDateCutoff(unittest.TestCase):
    setUp = fixtures.TestFridayAbsencePolicy.setUp
    tearDown = fixtures.TestFridayAbsencePolicy.tearDown
    attendance = fixtures.TestFridayAbsencePolicy.attendance

    def setup_period(self, joining=None, relieving=None):
        self.slip.start_date, self.slip.end_date = '2026-09-01', '2026-09-30'
        if joining:
            frappe.db.set_value('Employee', self.employee, 'date_of_joining', joining)
        if relieving:
            frappe.db.set_value('Employee', self.employee, 'relieving_date', relieving)
        frappe.clear_document_cache('Employee', self.employee)

    def test_full_month_unchanged(self):
        self.setup_period()
        self.assertEqual(self.slip._paid_days(), 30)
        self.attendance('2026-09-08')
        self.assertEqual(self.slip._paid_days(), 29)

    def test_joined_mid_month_with_one_absence(self):
        self.setup_period(joining='2026-09-07')
        self.attendance('2026-09-19')
        self.attendance('2026-09-13')  # Sunday stays paid
        self.assertEqual(self.slip._paid_days(), 23)

    def test_joined_11th_no_absence(self):
        self.setup_period(joining='2026-09-11')
        self.assertEqual(self.slip._paid_days(), 20)

    def test_joined_on_first_and_last_day(self):
        self.setup_period(joining='2026-09-01')
        self.assertEqual(self.slip._paid_days(), 30)
        self.setup_period(joining='2026-09-30')
        self.assertEqual(self.slip._paid_days(), 1)

    def test_relieved_only_and_joined_and_relieved(self):
        self.setup_period(relieving='2026-09-20')
        self.assertEqual(self.slip._paid_days(), 20)
        self.setup_period(joining='2026-09-07')
        self.assertEqual(self.slip._paid_days(), 14)

    def test_joining_after_period_pays_nothing(self):
        self.setup_period(joining='2026-10-05')
        self.assertEqual(self.slip._paid_days(), 0)

    def test_pre_joining_sunday_not_counted_and_days_in_month_kept(self):
        self.setup_period(joining='2026-09-07')  # Sunday 6 Sep is before joining
        self.assertEqual(self.slip._paid_days(), 24)
        self.assertEqual(self.slip._days_in_month(), 30)
        self.assertEqual(self.slip._pre_joining_days(), 6)
