"""Final overtime/deficiency rounding is driven by Attendance Rule fields.

Real engine arithmetic; only document and holiday retrieval are replaced.
"""
import unittest
from unittest.mock import patch

import frappe

from spotledger_hr.attendance_rule_engine import AttendanceRuleEngine


class TestFinalDurationRounding(unittest.TestCase):
    def setUp(self):
        self.rule = frappe._dict(name='Rule', hours_calculation_mode='Factory Timing',
            factory_start_time='08:00:00', factory_end_time='17:00:00',
            required_factory_hours=8.5, break_duration_minutes=30,
            regular_break_start='12:30:00', regular_break_end='13:00:00',
            friday_start_time='08:00:00', friday_end_time='17:00:00',
            friday_break_start='13:00:00', friday_break_end='15:00:00',
            enable_friday_logic=0, checkin_grace_minutes=15, checkin_max_grace_minutes=30,
            checkout_grace_minutes=15, checkout_max_grace_minutes=30,
            enable_overtime_rounding=1, overtime_rounding_interval_minutes=30,
            overtime_rounding_threshold_minutes=15, allow_negative_hours=0,
            final_duration_rounding=0, final_duration_rounding_from_date=None)
        for target, kwargs in (
            ('frappe.get_doc', dict(side_effect=lambda doctype, name:
                frappe._dict(custom_attendance_rule=self.rule.name) if doctype == 'Employee' else self.rule)),
            ('spotledger_hr.attendance_rule_engine.get_holiday_list_for_employee', dict(return_value=None)),
        ):
            patcher = patch(target, **kwargs)
            patcher.start()
            self.addCleanup(patcher.stop)

    def enable(self, from_date='2026-07-01'):
        self.rule.final_duration_rounding = 1
        self.rule.final_duration_rounding_from_date = from_date

    def engine(self, date='2026-07-11'):
        return AttendanceRuleEngine('Synthetic', date)

    def test_opt_in_rounds_final_components(self):
        before = self.engine().calculate_attendance_summary('08:47:00', '17:00:00')
        self.enable()
        after = self.engine().calculate_attendance_summary('08:47:00', '17:00:00')
        self.assertNotEqual(before['deficiency_hours'], after['deficiency_hours'])
        self.assertEqual(after['deficiency_hours'], 1)

    def test_effective_from_date(self):
        raw = self.engine().calculate_deficiency('08:47:00', '17:00:00')
        self.enable('2026-07-11')
        self.assertEqual(self.engine('2026-07-10').calculate_deficiency('08:47:00', '17:00:00'), raw)
        self.assertEqual(self.engine('2026-07-11').calculate_deficiency('08:47:00', '17:00:00'), 1)
        self.assertEqual(self.engine('2026-08-20').calculate_deficiency('08:47:00', '17:00:00'), 1)

    def test_prerequisites_must_hold(self):
        raw = self.engine().calculate_deficiency('08:47:00', '17:00:00')
        self.enable()
        for key, value in (('final_duration_rounding_from_date', None), ('enable_overtime_rounding', 0),
                           ('overtime_rounding_interval_minutes', 60),
                           ('overtime_rounding_threshold_minutes', 10),
                           ('hours_calculation_mode', 'Hours Completed')):
            previous = self.rule[key]
            self.rule[key] = value
            self.assertEqual(self.engine().calculate_deficiency('08:47:00', '17:00:00'), raw, key)
            self.rule[key] = previous

    def test_half_hour_thresholds_with_seconds(self):
        self.enable()
        engine = self.engine()
        for minutes, seconds, expected in ((14, 59, 0), (15, 0, .5), (44, 59, .5), (45, 0, 1), (45, 1, 1)):
            with self.subTest(minutes=minutes, seconds=seconds):
                self.assertEqual(engine.calculate_deficiency(f'08:{minutes:02}:{seconds:02}', '17:00:00'), expected)
                self.assertEqual(engine.calculate_overtime('08:00:00', f'17:{minutes:02}:{seconds:02}'), expected)

    def test_gazetted_and_suppressed_deficiency_stay_unrounded_paths(self):
        self.enable()
        self.rule.allow_negative_hours = 1
        self.assertEqual(self.engine().calculate_deficiency('08:47:00', '17:00:00'), 0)
        self.rule.allow_negative_hours = 0
        engine = self.engine()
        engine.is_gazetted = True
        self.assertEqual(engine.calculate_deficiency('08:47:00', '17:00:00'), 0)

    def test_other_metrics_are_untouched(self):
        before = self.engine().calculate_attendance_summary('08:47:00', '19:00:00')
        self.enable()
        after = self.engine().calculate_attendance_summary('08:47:00', '19:00:00')
        for key in before.keys() - {'overtime_hours', 'deficiency_hours'}:
            self.assertEqual(after[key], before[key], key)
