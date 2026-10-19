"""Cross-midnight overtime tail credit (Attendance Rule opt-in).

Real engine and controller arithmetic; only document, holiday and checkin
retrieval are replaced.
"""
import unittest
from unittest.mock import patch

import frappe
from frappe.utils import get_datetime

from spotledger_hr.attendance_rule_engine import AttendanceRuleEngine
from spotledger_hr.controllers.attendance_controller import AttendanceController


class TestOvernightTailCredit(unittest.TestCase):
    DATE = '2026-08-04'  # Tuesday

    def setUp(self):
        self.rule = frappe._dict(name='Rule', hours_calculation_mode='Factory Timing',
            factory_start_time='08:00:00', factory_end_time='17:00:00',
            required_factory_hours=8.5, break_duration_minutes=30,
            regular_break_start='12:30:00', regular_break_end='13:00:00',
            friday_start_time='07:30:00', friday_end_time='13:00:00',
            friday_break_start='13:00:00', friday_break_end='15:00:00',
            enable_friday_logic=1, checkin_grace_minutes=14, checkin_max_grace_minutes=30,
            checkout_grace_minutes=15, checkout_max_grace_minutes=30,
            enable_overtime_rounding=1, overtime_rounding_interval_minutes=30,
            overtime_rounding_threshold_minutes=15, allow_negative_hours=0,
            final_duration_rounding=0, final_duration_rounding_from_date=None,
            overnight_tail_credit=1, overnight_tail_credit_from_date='2026-08-01')
        self.checkins = []   # unlinked rows on the day
        self.prev_out = '2026-08-03 23:55:00'
        for target, kwargs in (
            ('frappe.get_doc', dict(side_effect=lambda doctype, name=None:
                frappe._dict(custom_attendance_rule=self.rule.name) if doctype == 'Employee' else self.rule)),
            ('spotledger_hr.attendance_rule_engine.get_holiday_list_for_employee', dict(return_value=None)),
            ('frappe.get_all', dict(side_effect=self.get_all)),
        ):
            patcher = patch(target, **kwargs)
            patcher.start()
            self.addCleanup(patcher.stop)

    def get_all(self, doctype, filters=None, **kw):
        if filters.get('log_type') == 'OUT':  # previous day's last OUT
            return [frappe._dict(time=get_datetime(self.prev_out))] if self.prev_out else []
        return [frappe._dict(time=get_datetime(f'{self.day} {t}'), log_type=k) for k, t in self.checkins]

    def run_day(self, punches, date=None, **rule):
        self.rule.update(rule)
        self.checkins = punches
        date = self.day = date or self.DATE
        doc = AttendanceController.__new__(AttendanceController)
        doc.__dict__.update(employee='E', attendance_date=date, custom_manual_attendance=0, name=None, status='Present')
        doc.is_new = lambda: True
        engine = AttendanceRuleEngine('E', date)
        tail, primary_in = doc.get_overnight_tail(engine)
        cin = (primary_in or get_datetime(f'{date} {punches[0][1]}')).strftime('%H:%M:%S')
        cout = get_datetime(f'{date} {[t for k, t in punches if k == "OUT"][-1]}').strftime('%H:%M:%S')
        return engine.calculate_attendance_summary(cin, cout, tail) if tail else engine.calculate_attendance_summary(cin, cout)

    LIVE = [('IN', '00:06:00'), ('OUT', '00:24:00'), ('IN', '07:59:00'), ('OUT', '20:58:00')]

    def test_live_case_credits_tail(self):
        s = self.run_day(self.LIVE)
        self.assertAlmostEqual(s['overtime_hours'], 4.3)
        self.assertEqual(s['regular_hours'], 8.5)
        self.assertAlmostEqual(s['total_hours'], 13.3)
        self.assertEqual(s['deficiency_hours'], 0)

    def test_opt_out_is_unchanged(self):
        for off in ({'overnight_tail_credit': 0}, {'overnight_tail_credit_from_date': None},
                    {'overnight_tail_credit_from_date': '2026-08-05'},
                    {'hours_calculation_mode': 'Hours Completed'}):
            with self.subTest(off=off):
                self.setUp()
                s = self.run_day(self.LIVE, **off)
                if off.get('hours_calculation_mode') != 'Hours Completed':
                    self.assertEqual((s['overtime_hours'], s['total_hours']), (4.0, 13.0))

    def test_tail_durations(self):
        for end, extra in (('00:35:00', 29 / 60), ('00:37:00', 31 / 60), ('00:36:00', .5)):
            with self.subTest(end=end):
                s = self.run_day([('IN', '00:06:00'), ('OUT', end)] + self.LIVE[2:])
                self.assertAlmostEqual(s['overtime_hours'], 4 + extra)

    def test_zero_length_and_one_sided_tail_ignored(self):
        for punches in ([('IN', '00:06:00'), ('OUT', '00:06:00')] + self.LIVE[2:],
                        [('IN', '00:06:00')] + self.LIVE[2:],
                        [('OUT', '00:24:00')] + self.LIVE[2:]):
            self.assertEqual(self.run_day(punches)['overtime_hours'], 4.0)

    def test_tail_must_end_before_primary_and_factory_start(self):
        # Pair ending after factory start is a normal double punch, not a tail.
        punches = [('IN', '00:06:00'), ('OUT', '08:05:00'), ('IN', '08:10:00'), ('OUT', '20:58:00')]
        self.assertEqual(self.run_day(punches)['overtime_hours'], 4.0)

    def test_morning_double_punch_not_credited(self):
        # The seven August candidates: pair at ~07:50 after a normal previous evening.
        self.prev_out = '2026-08-03 17:05:00'
        punches = [('IN', '07:49:00'), ('OUT', '07:56:00'), ('IN', '07:57:00'), ('OUT', '17:00:00')]
        self.assertEqual(self.run_day(punches)['overtime_hours'], 0)

    def test_previous_day_not_late_not_credited(self):
        self.prev_out = '2026-08-03 17:00:00'
        self.assertEqual(self.run_day(self.LIVE)['overtime_hours'], 4.0)
        self.prev_out = '2026-08-03 22:59:00'
        self.assertEqual(self.run_day(self.LIVE)['overtime_hours'], 4.0)
        self.prev_out = None
        self.assertEqual(self.run_day(self.LIVE)['overtime_hours'], 4.0)

    def test_tail_starting_after_one_am_not_credited(self):
        punches = [('IN', '01:30:00'), ('OUT', '01:50:00')] + self.LIVE[2:]
        self.assertEqual(self.run_day(punches)['overtime_hours'], 4.0)

    def test_biometric_duplicates_collapse(self):
        punches = [('IN', '00:06:00'), ('IN', '00:06:05'), ('OUT', '00:24:00'),
                   ('IN', '07:59:00'), ('IN', '07:59:14'), ('OUT', '20:58:00'), ('OUT', '20:58:51')]
        s = self.run_day(punches)
        self.assertAlmostEqual(s['overtime_hours'], 4.3)

    def test_primary_starts_at_own_in_not_tail_in(self):
        # Late main IN (08:20): grace clamp must see 08:20, not the tail's 00:06.
        punches = [('IN', '00:06:00'), ('OUT', '00:24:00'), ('IN', '08:20:00'), ('OUT', '17:00:00')]
        s = self.run_day(punches)
        self.assertGreater(s['deficiency_hours'], 0)
        self.assertAlmostEqual(s['overtime_hours'], .3)

    def test_rounding_applied_once_on_the_sum(self):
        s = self.run_day(self.LIVE, final_duration_rounding=1, final_duration_rounding_from_date='2026-08-01')
        self.assertEqual(s['overtime_hours'], 4.5)

    def test_friday_and_gazetted_credit_tail(self):
        # Documented: tail is real worked time, credited on any day type.
        self.prev_out = '2026-08-06 23:55:00'
        s = self.run_day([('IN', '00:06:00'), ('OUT', '00:24:00'), ('IN', '07:29:00'), ('OUT', '13:00:00')],
                         date='2026-08-07')
        self.assertAlmostEqual(s['overtime_hours'], .3)

    def test_manual_attendance_skipped(self):
        self.checkins = self.LIVE
        doc = AttendanceController.__new__(AttendanceController)
        doc.__dict__.update(employee='E', attendance_date=self.DATE, custom_manual_attendance=1, name=None)
        self.assertEqual(doc.get_overnight_tail(AttendanceRuleEngine('E', self.DATE)), (0, None))
