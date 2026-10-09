"""Completed regular lunch boundary; isolated real-engine regression tests."""
import unittest

from spotledger_hr.attendance_rule_engine import AttendanceRuleEngine
from spotledger_hr.tests import test_friday_absence_policy as fixtures


class TestRegularBreakBoundary(unittest.TestCase):
    setUp = fixtures.TestFridayAbsencePolicy.setUp
    tearDown = fixtures.TestFridayAbsencePolicy.tearDown
    change_rule = fixtures.TestFridayAbsencePolicy.change_rule

    def summary(self, end, start='08:00:00', date='2026-07-11', **changes):
        self.change_rule(
            regular_break_start='12:30:00', regular_break_end='13:00:00',
            checkin_grace_minutes=10, checkin_max_grace_minutes=30,
            checkout_grace_minutes=10, checkout_max_grace_minutes=30,
            enable_overtime_rounding=1, overtime_rounding_interval_minutes=30,
            overtime_rounding_threshold_minutes=15, hours_deficiency_grace_minutes=0, **changes)
        return AttendanceRuleEngine(self.employee, date).calculate_attendance_summary(start, end)

    def assert_metrics(self, result, break_minutes, regular, deficiency, overtime=0):
        self.assertEqual(result['break_duration_minutes'], break_minutes)
        self.assertAlmostEqual(result['regular_hours'], regular)
        self.assertAlmostEqual(result['deficiency_hours'], deficiency)
        self.assertAlmostEqual(result['overtime_hours'], overtime)

    def test_completed_regular_lunch_at_adjusted_end(self):
        for end in ('12:59:00', '13:00:00', '13:01:00', '13:10:00'):
            with self.subTest(end=end):
                result = self.summary(end)
                self.assertEqual(result['adjusted_check_out'].strftime('%H:%M:%S'), '13:00:00')
                self.assert_metrics(result, 30, 4.5, 4)

    def test_before_break_and_partial_break_remain_undeducted(self):
        for end in ('12:00:00', '12:29:00', '12:30:00'):
            result = self.summary(end)
            regular = 4 if end == '12:00:00' else 4.5
            self.assert_metrics(result, 0, regular, 8.5 - regular)
        result = self.summary('12:45:00', enable_friday_logic=0)
        # Disable rounding on the engine to exercise an actual partial interval.
        engine = AttendanceRuleEngine(self.employee, '2026-07-11')
        engine.rule.enable_overtime_rounding = 0
        self.assert_metrics(engine.calculate_attendance_summary('08:00:00', '12:45:00'), 0, 4.75, 3.75)

    def test_full_normal_day_unchanged(self):
        self.assert_metrics(self.summary('17:00:00'), 30, 8.5, 0)

    def test_checkin_at_break_start_or_end_remains_undeducted(self):
        for start in ('12:30:00', '13:00:00'):
            result = self.summary('17:00:00', start=start)
            self.assertEqual(result['break_duration_minutes'], 0)

    def test_equal_break_start_and_end_keeps_existing_guard(self):
        self.summary('13:00:00')
        engine = AttendanceRuleEngine(self.employee, '2026-07-11')
        engine.rule.regular_break_start = '13:00:00'
        self.assertEqual(engine.get_break_duration('08:00:00', '13:00:00'), 0)

    def test_friday_helper_no_break_and_regular_break_unchanged(self):
        for break_start, break_end, minutes, regular, deficiency in (
                ('13:00:00', '14:00:00', 0, 5, 0),
                ('12:00:00', '12:30:00', 30, 4.5, 0.5)):
            result = self.summary('13:00:00', date='2026-07-10',
                enable_friday_logic=1, friday_start_time='08:00:00', friday_end_time='13:00:00',
                friday_break_start=break_start, friday_break_end=break_end)
            self.assert_metrics(result, minutes, regular, deficiency)
        engine = AttendanceRuleEngine(self.employee, '2026-07-10')
        self.assertEqual(engine.get_break_duration('08:00:00', '12:30:00'), 0)

    def test_hours_completed_boundary_keeps_existing_policy(self):
        self.assert_metrics(self.summary('13:00:00', hours_calculation_mode='Hours Completed'), 0, 5, 3.5)
        result = self.summary('12:59:00', hours_calculation_mode='Hours Completed')
        self.assertEqual(result['adjusted_check_out'].strftime('%H:%M:%S'), '12:59:00')
        self.assert_metrics(result, 0, 5 - 1 / 60, 3.5 + 1 / 60)

    def test_overnight_rollover_unchanged(self):
        result = self.summary('06:00:00', start='22:00:00')
        self.assertEqual(result['adjusted_check_out'].strftime('%Y-%m-%d %H:%M:%S'), '2026-07-12 06:00:00')
        self.assert_metrics(result, 0, 8, 0.5)
