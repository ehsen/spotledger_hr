"""Narrow Friday status regressions, using the isolated site's real rule engine."""
import unittest
import frappe
from spotledger_hr.controllers.attendance_controller import AttendanceController
from spotledger_hr.tests import test_friday_absence_policy as fixtures


class TestAttendanceStatusPolicy(unittest.TestCase):
    setUp = fixtures.TestFridayAbsencePolicy.setUp
    tearDown = fixtures.TestFridayAbsencePolicy.tearDown
    change_rule = fixtures.TestFridayAbsencePolicy.change_rule

    def worked(self, date='2026-07-03', start='07:37:00', end='13:02:00', status='Absent', manual=True):
        self.change_rule(factory_start_time='07:30:00', factory_end_time='17:00:00',
                         friday_start_time='07:30:00', friday_end_time='13:00:00',
                         friday_break_start='13:00:00', friday_break_end='14:00:00',
                         enable_friday_logic=1, regular_break_start='13:00:00',
                         regular_break_end='13:30:00', checkin_grace_minutes=10,
                         checkin_max_grace_minutes=30, checkout_grace_minutes=10,
                         checkout_max_grace_minutes=30)
        return AttendanceController(dict(doctype='Attendance', employee=self.employee,
            attendance_date=date, status=status, custom_manual_attendance=int(manual),
            custom_check_in_time=f'{date} {start}', custom_check_out_time=f'{date} {end}'))

    def add_sources(self, doc, kinds=('IN', 'OUT'), equal=False, other=False):
        for kind in kinds:
            frappe.get_doc(dict(doctype='Employee Checkin', employee=self.employee,
                time=doc.custom_check_in_time if kind == 'IN' or equal else doc.custom_check_out_time,
                log_type=kind, custom_attendance_date=doc.attendance_date,
                attendance='_Other Attendance' if other else None)).db_insert()

    def test_authentic_full_friday_insert_and_reload(self):
        doc = self.worked(manual=False)
        self.add_sources(doc)
        doc.insert()
        doc.reload()
        self.assertEqual(doc.working_hours, 5.5)
        self.assertEqual(doc.custom_deficiency_hours, 0)
        self.assertEqual(doc.status, 'Present')

    def test_own_linked_pair_on_existing_attendance(self):
        doc = self.worked(manual=False)
        self.add_sources(doc)
        doc.insert()
        frappe.db.set_value('Employee Checkin', {'employee': self.employee}, 'attendance', doc.name)
        doc.reload()
        doc.status = 'Absent'
        doc.save()
        doc.reload()
        self.assertEqual(doc.status, 'Present')
        self.assertEqual(doc.working_hours, 5.5)

    def test_native_leave_decisions_survive_validation(self):
        for half in (False, True):
            with self.subTest(half=half):
                frappe.db.savepoint('leave_matrix')
                self.rule.reload()
                doc = self.worked()
                leave = frappe.get_doc(dict(doctype='Leave Application', name=frappe.generate_hash(length=12),
                    employee=self.employee, from_date='2026-07-03', to_date='2026-07-03',
                    status='Approved', docstatus=1, half_day=int(half),
                    half_day_date='2026-07-03' if half else None))
                leave.db_insert()
                doc.validate()
                self.assertEqual(doc.status, 'Half Day' if half else 'On Leave')
                frappe.db.rollback(save_point='leave_matrix')

    def test_explicit_manual_full_friday(self):
        doc = self.worked()
        doc.insert()
        doc.reload()
        self.assertEqual(doc.status, 'Present')

    def test_stale_or_partial_or_other_sources_do_not_promote(self):
        for kinds, other in (((), False), (('IN',), False), (('OUT',), False), (('IN', 'OUT'), True)):
            with self.subTest(kinds=kinds, other=other):
                frappe.db.savepoint('sources')
                self.rule.reload()
                doc = self.worked(manual=False)
                self.add_sources(doc, kinds, other=other)
                doc.validate()
                self.assertEqual(doc.status, 'Absent')
                frappe.db.rollback(save_point='sources')

    def test_identical_raw_sources_with_stale_fields_do_not_promote(self):
        doc = self.worked(manual=False)
        self.add_sources(doc, equal=True)
        doc.validate()
        self.assertEqual(doc.status, 'Absent')

    def test_disabled_friday_short_friday_and_short_weekday_stay_absent(self):
        for date, end, enabled in (('2026-07-03', '13:02:00', 0),
                                   ('2026-07-03', '12:00:00', 1),
                                   ('2026-07-01', '12:00:00', 1)):
            doc = self.worked(date=date, end=end)
            self.change_rule(enable_friday_logic=enabled)
            doc.calculate_attendance_metrics()
            self.assertEqual(doc.status, 'Absent')

    def test_leave_half_day_and_wfh_stay_unchanged(self):
        for status in ('On Leave', 'Half Day', 'Work From Home'):
            doc = self.worked(status=status)
            doc.calculate_attendance_metrics()
            self.assertEqual(doc.status, status)

    def test_legacy_full_weekday_and_short_present_semantics(self):
        for date, end, status in (('2026-07-01', '17:00:00', 'Absent'),
                                  ('2026-07-01', '12:00:00', 'Present')):
            doc = self.worked(date=date, end=end, status=status)
            doc.calculate_attendance_metrics()
            self.assertEqual(doc.status, 'Present')

    def test_suppressed_deficiency_short_friday_stays_absent(self):
        doc = self.worked(end='12:00:00')
        self.change_rule(allow_negative_hours=1)
        doc.calculate_attendance_metrics()
        self.assertEqual(doc.custom_deficiency_hours, 0)
        self.assertEqual(doc.status, 'Absent')

    def test_gazetted_short_friday_stays_absent(self):
        from unittest.mock import patch
        from spotledger_hr.attendance_rule_engine import AttendanceRuleEngine
        doc = self.worked(end='12:00:00')
        with patch.object(AttendanceRuleEngine, '_is_gazetted_holiday', return_value=True):
            doc.calculate_attendance_metrics()
        self.assertEqual(doc.custom_deficiency_hours, 0)
        self.assertEqual(doc.status, 'Absent')

    def test_invalid_manual_duration_does_not_promote(self):
        for end in ('07:37:00', '07:00:00'):
            doc = self.worked(end=end)
            doc.calculate_attendance_metrics()
            self.assertEqual(doc.status, 'Absent')
