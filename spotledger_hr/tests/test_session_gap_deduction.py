"""Unpaid intra-day session gap deduction (Factory Timing).

Real engine and controller arithmetic; only document, holiday and checkin
retrieval are replaced (same harness as test_overnight_tail_credit).
"""
import unittest
from unittest.mock import patch

import frappe
from frappe.utils import get_datetime

from spotledger_hr.attendance_rule_engine import AttendanceRuleEngine
from spotledger_hr.controllers.attendance_controller import AttendanceController


class TestSessionGapDeduction(unittest.TestCase):
    DATE = '2026-08-29'  # Saturday
    FRIDAY = '2026-08-28'

    def setUp(self):
        self.rule = frappe._dict(name='Rule', hours_calculation_mode='Factory Timing',
            factory_start_time='08:00:00', factory_end_time='17:00:00',
            required_factory_hours=8.5, break_duration_minutes=30,
            regular_break_start='12:30:00', regular_break_end='13:00:00',
            friday_start_time='07:30:00', friday_end_time='13:00:00',
            friday_break_start='13:00:00', friday_break_end='14:00:00',
            enable_friday_logic=1, checkin_grace_minutes=14, checkin_max_grace_minutes=30,
            checkout_grace_minutes=15, checkout_max_grace_minutes=30,
            enable_overtime_rounding=1, overtime_rounding_interval_minutes=30,
            overtime_rounding_threshold_minutes=15, allow_negative_hours=0,
            final_duration_rounding=0, final_duration_rounding_from_date=None,
            overnight_tail_credit=0, overnight_tail_credit_from_date=None)
        self.checkins = []
        self.prev_out = None
        self.holiday_list = None
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
        if filters.get('log_type') == 'OUT':  # previous day's last OUT (tail gate)
            return [frappe._dict(time=get_datetime(self.prev_out))] if self.prev_out else []
        return [frappe._dict(time=get_datetime(f'{self.day} {t}'), log_type=k) for k, t in self.checkins]

    def run_day(self, punches, date=None, gazetted=False, **rule):
        """Mirror AttendanceController.calculate_attendance_metrics for the punches."""
        self.rule.update(rule)
        self.checkins = punches
        date = self.day = date or self.DATE
        doc = AttendanceController.__new__(AttendanceController)
        doc.__dict__.update(employee='E', attendance_date=date, custom_manual_attendance=0, name=None, status='Present')
        doc.is_new = lambda: True
        engine = AttendanceRuleEngine('E', date)
        engine.is_gazetted = gazetted
        tail, primary_in = doc.get_overnight_tail(engine)
        ins = [t for k, t in punches if k == 'IN']
        outs = [t for k, t in punches if k == 'OUT']
        cin = (primary_in or get_datetime(f'{date} {ins[0]}')).strftime('%H:%M:%S')
        cout = get_datetime(f'{date} {outs[-1]}').strftime('%H:%M:%S')
        gaps = doc.get_session_gaps(engine, primary_in)
        kwargs = {'session_gaps': gaps} if gaps else {}
        if tail:
            return engine.calculate_attendance_summary(cin, cout, tail, **kwargs)
        return engine.calculate_attendance_summary(cin, cout, **kwargs)

    LIVE = [('IN', '07:56:00'), ('IN', '07:56:08'), ('OUT', '08:52:24'), ('OUT', '10:00:00'),
            ('IN', '13:14:00'), ('OUT', '13:14:33'), ('OUT', '17:00:00'), ('OUT', '17:09:00')]
    STRAIGHT = [('IN', '07:56:00'), ('OUT', '17:09:00')]

    def assertMetrics(self, s, total, brk, regular, ot, deficiency):
        self.assertAlmostEqual(s['total_hours'], total, places=3)
        self.assertEqual(s['break_duration_minutes'], brk)
        self.assertAlmostEqual(s['regular_hours'], regular, places=3)
        self.assertAlmostEqual(s['overtime_hours'], ot, places=3)
        self.assertAlmostEqual(s['deficiency_hours'], deficiency, places=3)

    # ---- live case -------------------------------------------------------
    def test_live_case_deducts_gap(self):
        s = self.run_day(self.LIVE)
        self.assertMetrics(s, 5.7667, 0, 5.7667, 0, 2.7333)
        self.assertEqual(s['adjusted_check_in'].strftime('%H:%M'), '08:00')
        self.assertEqual(s['adjusted_check_out'].strftime('%H:%M'), '17:00')

    def test_session_collapse_ignores_biometric_duplicates(self):
        # 08:52:24 OUT then 10:00 OUT is one OUT run -> gap is 10:00-13:14, not 08:52-13:14.
        doc = self._doc(self.LIVE)
        gaps = doc.get_session_gaps(AttendanceRuleEngine('E', self.DATE), None)
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0][0].strftime('%H:%M:%S'), '10:00:00')
        self.assertEqual(gaps[0][1].strftime('%H:%M:%S'), '13:14:00')

    def _doc(self, punches, date=None):
        self.checkins = punches
        self.day = date or self.DATE
        doc = AttendanceController.__new__(AttendanceController)
        doc.__dict__.update(employee='E', attendance_date=self.day, custom_manual_attendance=0, name=None)
        doc.is_new = lambda: True
        return doc

    # ---- non-gap days are bit-identical ---------------------------------
    def test_straight_day_unchanged(self):
        self.assertMetrics(self.run_day(self.STRAIGHT), 9.0, 30, 8.5, 0, 0)

    def test_stray_trailing_in_unchanged(self):
        punches = [('IN', '07:55:00'), ('OUT', '17:11:00'), ('IN', '17:11:00')]
        self.assertEqual(self._doc(punches).get_session_gaps(AttendanceRuleEngine('E', self.DATE), None), [])
        self.assertMetrics(self.run_day(punches), 9.0, 30, 8.5, 0, 0)

    def test_two_minute_gap_unchanged(self):
        punches = [('IN', '07:52:00'), ('OUT', '17:06:00'), ('IN', '17:08:00'), ('OUT', '20:02:00')]
        base = self.run_day([('IN', '07:52:00'), ('OUT', '20:02:00')])
        s = self.run_day(punches)
        for k in ('total_hours', 'regular_hours', 'overtime_hours', 'deficiency_hours', 'break_duration_minutes'):
            self.assertEqual(s[k], base[k], k)

    def test_same_second_duplicate_in_single_session(self):
        punches = [('IN', '07:56:00'), ('IN', '07:56:00'), ('OUT', '17:09:00')]
        self.assertEqual(self._doc(punches).get_session_gaps(AttendanceRuleEngine('E', self.DATE), None), [])

    # ---- threshold boundary ---------------------------------------------
    def gap_day(self, out, back):
        return [('IN', '08:00:00'), ('OUT', out), ('IN', back), ('OUT', '17:00:00')]

    def test_threshold_boundary(self):
        # gaps well away from the 12:30-13:00 break so only the threshold matters
        s29 = self.run_day(self.gap_day('09:00:00', '09:29:00'))
        s30 = self.run_day(self.gap_day('09:00:00', '09:30:00'))
        s31 = self.run_day(self.gap_day('09:00:00', '09:31:00'))
        self.assertMetrics(s29, 9.0, 30, 8.5, 0, 0)            # 29 min: ordinary short break
        self.assertMetrics(s30, 8.5, 30, 8.0, 0, 0.5)          # 30 min: deducted
        self.assertAlmostEqual(s31['deficiency_hours'], 8.5 - (9 - 31 / 60 - .5), places=3)

    # ---- break interplay -------------------------------------------------
    def test_gap_fully_covering_break_deducts_once(self):
        s = self.run_day(self.gap_day('12:00:00', '13:30:00'))
        self.assertMetrics(s, 7.5, 0, 7.5, 0, 1.0)

    def test_gap_partially_overlapping_break(self):
        # Gap 12:00-12:45 covers 15 of the 30 break minutes -> 15 remain.
        s = self.run_day(self.gap_day('12:00:00', '12:45:00'))
        self.assertMetrics(s, 8.25, 15, 8.0, 0, 0.5)

    def test_gap_exactly_the_break_window(self):
        s = self.run_day(self.gap_day('12:30:00', '13:00:00'))
        self.assertMetrics(s, 8.5, 0, 8.5, 0, 0)

    def test_gap_ending_at_break_start_and_starting_at_break_end(self):
        before = self.run_day(self.gap_day('12:00:00', '12:30:00'))   # ends where break starts
        self.assertMetrics(before, 8.5, 30, 8.0, 0, 0.5)
        after = self.run_day(self.gap_day('13:00:00', '13:30:00'))    # starts where break ends
        self.assertMetrics(after, 8.5, 30, 8.0, 0, 0.5)

    # ---- OT offset (owner decision) --------------------------------------
    def test_ot_offset_makes_up_shortfall_first(self):
        s = self.run_day([('IN', '08:00:00'), ('OUT', '10:00:00'), ('IN', '13:14:00'), ('OUT', '20:00:00')])
        self.assertAlmostEqual(s['overtime_hours'], 0.2667, places=3)
        self.assertEqual(s['deficiency_hours'], 0)

    def test_shortfall_not_made_up_gives_no_ot(self):
        s = self.run_day([('IN', '08:00:00'), ('OUT', '10:00:00'), ('IN', '13:14:00'), ('OUT', '18:00:00')])
        self.assertEqual(s['overtime_hours'], 0)
        self.assertAlmostEqual(s['deficiency_hours'], 1.7333, places=3)

    def test_makeup_exactly_consumes_premium(self):
        # Checkout clock rounding (19:44 -> 19:30) is pre-existing; off here so the
        # arithmetic is exact: 11.7333 span - 3.2333 gap = 8.5 net.
        s = self.run_day([('IN', '08:00:00'), ('OUT', '10:00:00'), ('IN', '13:14:00'), ('OUT', '19:44:00')],
                         enable_overtime_rounding=0)
        self.assertAlmostEqual(s['overtime_hours'], 0, places=3)
        self.assertAlmostEqual(s['deficiency_hours'], 0, places=3)

    def test_checkout_rounding_identical_on_gap_and_plain_days(self):
        # The client's checkout rounding is untouched: a gap day closes on the same
        # adjusted checkout as a plain day with that checkout, then loses only the gap.
        for out in ('19:44:00', '19:45:00', '20:58:00', '17:09:00'):
            with self.subTest(out=out):
                plain = self.run_day([('IN', '08:00:00'), ('OUT', out)])
                gap = self.run_day([('IN', '08:00:00'), ('OUT', '10:00:00'), ('IN', '13:14:00'), ('OUT', out)])
                self.assertEqual(gap['adjusted_check_out'], plain['adjusted_check_out'])
                self.assertAlmostEqual(plain['total_hours'] - gap['total_hours'], 3 + 14 / 60, places=3)

    def test_straight_long_day_keeps_overtime(self):
        s = self.run_day([('IN', '08:00:00'), ('OUT', '20:00:00')])
        self.assertEqual((s['overtime_hours'], s['deficiency_hours']), (3.0, 0))

    def test_never_both_overtime_and_deficiency(self):
        for out2 in ('15:00:00', '17:00:00', '18:30:00', '19:44:00', '21:00:00', '23:00:00'):
            for gap in (('10:00:00', '13:14:00'), ('09:00:00', '09:40:00'), ('12:00:00', '12:45:00')):
                with self.subTest(out2=out2, gap=gap):
                    s = self.run_day([('IN', '08:00:00'), ('OUT', gap[0]), ('IN', gap[1]), ('OUT', out2)])
                    self.assertFalse(s['overtime_hours'] > 0 and s['deficiency_hours'] > 0)

    # ---- tail interaction (highest-risk regression) ----------------------
    TAIL = [('IN', '00:06:00'), ('OUT', '00:24:00'), ('IN', '07:59:00'), ('OUT', '20:58:00')]
    TAIL_RULE = dict(overnight_tail_credit=1, overnight_tail_credit_from_date='2026-08-01')

    def test_tail_day_overnight_break_not_deducted(self):
        self.prev_out = '2026-08-03 23:55:00'
        s = self.run_day(self.TAIL, date='2026-08-04', **self.TAIL_RULE)
        self.assertAlmostEqual(s['overtime_hours'], 4.3, places=3)
        self.assertAlmostEqual(s['total_hours'], 13.3, places=3)
        self.assertEqual(s['deficiency_hours'], 0)

    def test_tail_day_with_final_rounding(self):
        self.prev_out = '2026-08-03 23:55:00'
        s = self.run_day(self.TAIL, date='2026-08-04', final_duration_rounding=1,
                         final_duration_rounding_from_date='2026-08-01', **self.TAIL_RULE)
        self.assertEqual(s['overtime_hours'], 4.5)

    def test_tail_credit_off_overnight_gap_not_deducted(self):
        # Tail credit disabled: the 00:24-07:59 overnight gap lies before the adjusted
        # check-in and must not be deducted (4-Aug legacy result stays 4.0 OT / 13.0).
        s = self.run_day(self.TAIL, date='2026-08-04')
        self.assertEqual((s['overtime_hours'], s['total_hours']), (4.0, 13.0))

    def test_tail_day_with_real_midday_gap_both_apply(self):
        self.prev_out = '2026-08-03 23:55:00'
        punches = [('IN', '00:06:00'), ('OUT', '00:24:00'), ('IN', '07:59:00'), ('OUT', '10:00:00'),
                   ('IN', '13:14:00'), ('OUT', '20:58:00')]
        s = self.run_day(punches, date='2026-08-04', **self.TAIL_RULE)
        # primary 08:00-21:00 (20:58 rounds up) = 13.0 - gap 3.2333 = 9.7667 net; OT 1.2667 + tail 0.3
        self.assertAlmostEqual(s['overtime_hours'], (13.0 - 3.2333 - 8.5) + 0.3, places=3)
        self.assertEqual(s['deficiency_hours'], 0)

    # ---- modes and policy that must not move -----------------------------
    def test_hours_completed_unchanged(self):
        # Hours Completed never sees gaps: the span is counted exactly as before.
        s = self.run_day(self.LIVE, hours_calculation_mode='Hours Completed')
        self.assertAlmostEqual(s['total_hours'], 17.15 - 7.9333, places=2)  # 07:56 -> 17:09 span
        self.assertEqual(s['deficiency_hours'], 0)

    def test_gazetted_gap_reduces_overtime(self):
        # Documented: gazetted pays every worked hour as OT; unpaid gap is not worked.
        s = self.run_day(self.gap_day('09:00:00', '09:40:00'), gazetted=True)
        self.assertAlmostEqual(s['overtime_hours'], 9.0 - 40 / 60 - 0.5, places=3)
        self.assertEqual(s['deficiency_hours'], 0)

    def test_friday_midmorning_gap(self):
        punches = [('IN', '07:30:00'), ('OUT', '09:00:00'), ('IN', '09:45:00'), ('OUT', '13:00:00')]
        s = self.run_day(punches, date=self.FRIDAY)
        # Friday 07:30-13:00 = 5.5 required; 45 min gap -> 0.75 h deficiency
        self.assertAlmostEqual(s['deficiency_hours'], 0.75, places=3)
        self.assertEqual(s['overtime_hours'], 0)

    def test_allow_negative_hours_deficiency_zero(self):
        s = self.run_day(self.LIVE, allow_negative_hours=1)
        self.assertEqual(s['deficiency_hours'], 0)

    def test_manual_attendance_skipped(self):
        doc = self._doc(self.LIVE)
        doc.custom_manual_attendance = 1
        self.assertEqual(doc.get_session_gaps(AttendanceRuleEngine('E', self.DATE), None), [])

    def test_engine_without_gaps_is_legacy(self):
        engine = AttendanceRuleEngine('E', self.DATE)
        a = engine.calculate_attendance_summary('07:56:00', '17:09:00')
        b = engine.calculate_attendance_summary('07:56:00', '17:09:00', session_gaps=[])
        self.assertEqual(a, b)
