"""Real engine arithmetic, with only document/holiday retrieval replaced.

No database connection or writes. Not a substitute for native DB integration.
"""
import unittest
from unittest.mock import patch
import frappe
from spotledger_hr.attendance_rule_engine import AttendanceRuleEngine

KEY = 'spotledger_hr_final_duration_rounding'
MISSING = object()


class TestFinalDurationRoundingDBFree(unittest.TestCase):
    def setUp(self):
        self.previous = frappe.conf.get(KEY, MISSING)
        self.addCleanup(self.restore_config)
        frappe.conf.pop(KEY, None)
        self.rule = frappe._dict(name='Exact Rule', hours_calculation_mode='Factory Timing',
            factory_start_time='08:00:00', factory_end_time='17:00:00',
            required_factory_hours=8.5, break_duration_minutes=30,
            regular_break_start='12:30:00', regular_break_end='13:00:00',
            friday_start_time='08:00:00', friday_end_time='17:00:00',
            friday_break_start='13:00:00', friday_break_end='15:00:00',
            enable_friday_logic=0, checkin_grace_minutes=15, checkin_max_grace_minutes=30,
            checkout_grace_minutes=15, checkout_max_grace_minutes=30,
            enable_overtime_rounding=1, overtime_rounding_interval_minutes=30,
            overtime_rounding_threshold_minutes=15, allow_negative_hours=0)
        self.docs = patch('frappe.get_doc', side_effect=lambda doctype, name:
            frappe._dict(custom_attendance_rule=self.rule.name) if doctype == 'Employee' else self.rule)
        self.holidays = patch('spotledger_hr.attendance_rule_engine.get_holiday_list_for_employee', return_value=None)
        self.docs.start()
        self.holidays.start()
        self.addCleanup(self.docs.stop)
        self.addCleanup(self.holidays.stop)

    def restore_config(self):
        frappe.conf.pop(KEY, None)
        if self.previous is not MISSING:
            frappe.conf[KEY] = self.previous

    def activate(self):
        frappe.conf[KEY] = {self.rule.name: {'from_date': '2026-07-01', 'through_date': '2026-07-31'}}

    def engine(self, date='2026-07-11'):
        return AttendanceRuleEngine('Synthetic', date)

    def test_scope_and_prerequisites_fail_closed(self):
        raw = self.engine().calculate_deficiency('08:47:00', '17:00:00')
        for config in [None, True, [], {}, {'Other Rule': {}},
                {self.rule.name: None}, {self.rule.name: {}},
                {self.rule.name: {'from_date': '2026-7-1', 'through_date': '2026-07-31'}},
                {self.rule.name: {'from_date': '2026-02-30', 'through_date': '2026-07-31'}},
                {self.rule.name: {'from_date': '2026-08-01', 'through_date': '2026-07-01'}},
                {self.rule.name: {'from_date': 20260701, 'through_date': '2026-07-31'}}]:
            with self.subTest(config=config):
                frappe.conf[KEY] = config
                self.assertEqual(self.engine().calculate_deficiency('08:47:00', '17:00:00'), raw)
        self.activate()
        for date in ['2026-06-30', '2026-08-01']:
            self.assertEqual(self.engine(date).calculate_deficiency('08:47:00', '17:00:00'), raw)
        for date in ['2026-07-01', '2026-07-31']:
            self.assertEqual(self.engine(date).calculate_deficiency('08:47:00', '17:00:00'), 1)
        for key, value in [('enable_overtime_rounding', 0),
                ('overtime_rounding_interval_minutes', 60),
                ('overtime_rounding_threshold_minutes', 10),
                ('hours_calculation_mode', 'Other')]:
            previous = self.rule[key]
            self.rule[key] = value
            self.assertEqual(self.engine().calculate_deficiency('08:47:00', '17:00:00'), raw)
            self.rule[key] = previous

    def test_summary_fractional_required_hours_exact_tie_and_adjacent_seconds(self):
        self.rule.required_factory_hours = 8.2
        self.activate()
        for start, expected in [('09:02:59', .5), ('09:03:00', 1), ('09:03:01', 1)]:
            with self.subTest(start=start):
                self.assertEqual(self.engine().calculate_attendance_summary(start, '17:00:00')['deficiency_hours'], expected)

    def test_checkbox_and_missing_mode_fail_closed(self):
        self.activate()
        for value in [None, 0, False, '0', 'false', -1, 2, '1', 1.0]:
            with self.subTest(value=value):
                self.rule.enable_overtime_rounding = value
                self.assertFalse(self.engine()._final_duration_rounding_enabled())
        for value in [1, True]:
            self.rule.enable_overtime_rounding = value
            self.assertTrue(self.engine()._final_duration_rounding_enabled())
        self.rule.pop('hours_calculation_mode')
        self.assertFalse(self.engine()._final_duration_rounding_enabled())

    def test_config_cleanup_preserves_absent_null_and_setup_failure(self):
        original = frappe.conf.get(KEY, MISSING)
        try:
            for previous in [MISSING, None, {'existing': {}}]:
                for setup_failure in [False, True]:
                    with self.subTest(previous=previous, setup_failure=setup_failure):
                        frappe.conf.pop(KEY, None)
                        if previous is not MISSING:
                            frappe.conf[KEY] = previous
                        case = TestFinalDurationRoundingDBFree()
                        try:
                            if setup_failure:
                                with patch('frappe._dict', side_effect=RuntimeError('setup failure')):
                                    with self.assertRaises(RuntimeError):
                                        case.setUp()
                            else:
                                case.setUp()
                                case.activate()
                        finally:
                            case.doCleanups()
                        self.assertIs(frappe.conf.get(KEY, MISSING), previous)
        finally:
            frappe.conf.pop(KEY, None)
            if original is not MISSING:
                frappe.conf[KEY] = original

    def test_duration_half_hour_thresholds_with_seconds(self):
        self.activate()
        engine = self.engine()
        for minutes, seconds, expected in [(14, 59, 0), (15, 0, .5), (15, 1, .5),
                (44, 59, .5), (45, 0, 1), (45, 1, 1), (60, 0, 1)]:
            with self.subTest(minutes=minutes, seconds=seconds):
                start = f'08:{minutes:02}:{seconds:02}' if minutes < 60 else '09:00:00'
                self.assertEqual(engine.calculate_deficiency(start, '17:00:00'), expected)
                end = f'17:{minutes:02}:{seconds:02}' if minutes < 60 else '18:00:00'
                self.assertEqual(engine.calculate_overtime('08:00:00', end), expected)
        self.assertEqual(engine.calculate_deficiency('08:00:00', '17:00:00'), 0)
        self.assertEqual(engine.calculate_overtime('08:00:00', '17:00:00'), 0)

    def test_exempt_modes_gazetted_and_suppression_are_unchanged(self):
        for mode, gazetted, suppressed in [('Hours Completed', False, 0),
                ('Factory Timing', True, 0), ('Factory Timing', False, 1)]:
            self.rule.hours_calculation_mode = mode
            self.rule.allow_negative_hours = suppressed
            self.rule.hours_deficiency_grace_minutes = 10
            for start, end in [('08:47:00', '17:00:00'), ('08:47:00', '19:00:00')]:
                frappe.conf.pop(KEY, None)
                engine = self.engine()
                engine.is_gazetted = gazetted
                before = engine.calculate_attendance_summary(start, end)
                self.activate()
                after = engine.calculate_attendance_summary(start, end)
                if suppressed and not gazetted:
                    self.assertEqual(after['deficiency_hours'], 0)
                    for key in before.keys() - {'overtime_hours'}:
                        self.assertEqual(after[key], before[key], key)
                else:
                    self.assertEqual(after, before)

    def test_friday_overnight_and_break_metrics_do_not_change(self):
        self.activate()
        for enabled in [0, 1]:
            self.rule.enable_friday_logic = enabled
            for date in ['2026-07-10', '2026-07-11']:
                for start, end in [('08:47:00', '12:30:00'), ('08:47:00', '13:00:00'),
                        ('08:47:00', '13:01:00'), ('08:47:00', '19:00:00'),
                        ('20:47:00', '06:00:00')]:
                    frappe.conf.pop(KEY, None)
                    before = self.engine(date).calculate_attendance_summary(start, end)
                    self.activate()
                    after = self.engine(date).calculate_attendance_summary(start, end)
                    for key in before.keys() - {'overtime_hours', 'deficiency_hours'}:
                        self.assertEqual(after[key], before[key], key)

    def test_real_controller_metric_mapping_preserves_status_and_other_fields(self):
        from spotledger_hr.controllers.attendance_controller import AttendanceController
        for status in ['Absent', 'Present']:
            for end in ['17:00:00', '19:00:00']:
                def calculate():
                    # Bypass Document metadata retrieval only; real controller methods run.
                    doc = object.__new__(AttendanceController)
                    doc.__dict__.update(employee='Synthetic', attendance_date='2026-07-11',
                        custom_check_in_time='2026-07-11 08:47:00',
                        custom_check_out_time='2026-07-11 ' + end, status=status)
                    doc.calculate_attendance_metrics()
                    return doc.__dict__.copy()
                frappe.conf.pop(KEY, None)
                before = calculate()
                self.activate()
                after = calculate()
                component = 'custom_deficiency_hours' if end == '17:00:00' else 'custom_overtime_hours'
                self.assertEqual(after[component], 1)
                for key in before.keys() - {'custom_deficiency_hours', 'custom_overtime_hours'}:
                    self.assertEqual(after[key], before[key], key)

    def test_opt_in_rounds_final_components_preserving_other_metrics(self):
        for start, end, component in [('08:47:00', '17:00:00', 'deficiency_hours'),
                                      ('08:47:00', '19:00:00', 'overtime_hours')]:
            frappe.conf.pop(KEY, None)
            before = self.engine().calculate_attendance_summary(start, end)
            self.activate()
            after = self.engine().calculate_attendance_summary(start, end)
            self.assertEqual(after[component], 1)
            self.assertNotEqual(before[component], after[component])
            for key in before.keys() - {'overtime_hours', 'deficiency_hours'}:
                self.assertEqual(after[key], before[key], key)
