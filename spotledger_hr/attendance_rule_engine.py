# Copyright (c) 2025, SpotLedger and contributors
# For license information, please see license.txt

"""
Enhanced Attendance Rule Engine
Comprehensive implementation of attendance calculation logic based on legacy controller
"""

import frappe
from frappe.utils import get_datetime, get_time, getdate, add_to_date, time_diff_in_seconds
from spotledger_hr.utilities.employee_utils import get_holiday_list_for_employee, is_holiday
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple, Union


class AttendanceRuleEngine:
    """Enhanced Attendance Rule Engine with comprehensive calculation logic"""
    
    def __init__(self, employee: str, attendance_date: str):
        self.employee = employee
        self.attendance_date = attendance_date
        self.rule = self._get_attendance_rule()
        self.is_friday = self._is_friday()
        self.is_gazetted = self._is_gazetted_holiday()
        self.is_hours_completed_mode = getattr(self.rule, "hours_calculation_mode", "Factory Timing") == "Hours Completed"
        
    def _get_attendance_rule(self):
        """Get attendance rule for employee"""
        employee_doc = frappe.get_doc("Employee", self.employee)
        if not employee_doc.custom_attendance_rule:
            frappe.throw(f"No Attendance Rule set for Employee: {self.employee}")
        return frappe.get_doc("Attendance Rule", employee_doc.custom_attendance_rule)
    
    def _is_friday(self) -> bool:
        """Check if attendance date is Friday"""
        return getdate(self.attendance_date).weekday() == 4  # 4 = Friday
    
    def _is_gazetted_holiday(self) -> bool:
        """Check if attendance date is a gazetted holiday

        Named (non-weekly-off) holidays always count as gazetted. Weekly-off
        days (e.g. Sunday) only count as gazetted if the rule opts in via
        treat_weekly_off_as_gazetted - without that flag, a Holiday List that
        auto-populates weekly offs would misclassify every Friday/Sunday as
        gazetted, doubling overtime and zeroing deficiency on those days.
        Friday already has its own dedicated handling via enable_friday_logic
        regardless of this setting.
        """
        try:
            holiday_list = get_holiday_list_for_employee(self.employee, raise_exception=False)
            if not holiday_list:
                return False
            if is_holiday(self.employee, self.attendance_date, raise_exception=False, only_non_weekly=True):
                return True
            if getattr(self.rule, "treat_weekly_off_as_gazetted", 0):
                return is_holiday(self.employee, self.attendance_date, raise_exception=False, only_non_weekly=False)
            return False
        except Exception:
            return False
    
    def get_current_datetime(self, date_str: str, time_str: str, add_day: bool = False) -> datetime:
        """Concatenate date & time strings and return datetime object"""
        if not add_day:
            return get_datetime(f"{date_str} {time_str}")
        else:
            dt = get_datetime(f"{date_str} {time_str}")
            return add_to_date(dt, days=1, as_datetime=True)
    
    def get_time_after_grace_in(self, check_in_time: str) -> datetime:
        """
        Calculate adjusted check-in time after applying grace period logic
        Based on legacy get_time_after_grace function
        """
        if " " not in check_in_time:
            dt_check_in = get_datetime(f"{self.attendance_date} {check_in_time}")
        else:
            dt_check_in = get_datetime(check_in_time)
        
        # Use Friday start time if it's Friday and Friday logic is enabled
        if self.is_friday and self.rule.enable_friday_logic and self.rule.friday_start_time:
            factory_start_time = self.rule.friday_start_time
        else:
            factory_start_time = self.rule.factory_start_time
            
        dt_factory_time = self.get_current_datetime(self.attendance_date, factory_start_time)
        
        max_check_in_time = add_to_date(
            dt_factory_time, 
            minutes=self.rule.checkin_max_grace_minutes, 
            as_datetime=True
        )
        threshold_check_in = add_to_date(
            dt_factory_time,
            minutes=self.rule.checkin_grace_minutes,
            as_datetime=True
        )

        if dt_check_in <= threshold_check_in:
            return dt_factory_time
        elif dt_check_in <= max_check_in_time:
            return max_check_in_time
        else:
            return dt_check_in
    
    def get_time_after_grace_out(self, check_out_time: str) -> datetime:
        """
        Calculate adjusted check-out time after applying grace period logic
        Based on legacy get_time_after_grace_out function with Friday prayer break handling
        """
        if " " not in check_out_time:
            dt_check_out = get_datetime(f"{self.attendance_date} {check_out_time}")
        else:
            dt_check_out = get_datetime(check_out_time)
        
        # Use Friday end time if it's Friday and Friday logic is enabled
        if self.is_friday and self.rule.enable_friday_logic and self.rule.friday_end_time:
            factory_end_time = self.rule.friday_end_time
        else:
            factory_end_time = self.rule.factory_end_time
            
        dt_factory_time = self.get_current_datetime(self.attendance_date, factory_end_time)
        
        # Calculate grace boundaries
        min_check_out_time = dt_factory_time - timedelta(minutes=self.rule.checkout_max_grace_minutes)  # Early cutoff
        threshold_check_out = dt_factory_time - timedelta(minutes=self.rule.checkout_grace_minutes)  # Early grace

        # Calculate late boundaries (times AFTER factory end time)
        max_allowed_checkout = dt_factory_time + timedelta(minutes=self.rule.checkout_max_grace_minutes)  # Max late allowed
        late_threshold = dt_factory_time + timedelta(minutes=self.rule.checkout_grace_minutes)  # Late grace
        # Friday prayer break handling
        if self.is_friday and self.rule.enable_friday_logic:
            friday_break_start = self.get_current_datetime(
                self.attendance_date, 
                self.rule.friday_break_start
            )
            friday_break_end = self.get_current_datetime(
                self.attendance_date, 
                self.rule.friday_break_end
            )
            
            if dt_check_out <= friday_break_start:
                return dt_check_out
            elif dt_check_out <= friday_break_end:
                return dt_factory_time
        
        # Regular grace period logic for checkouts
        if dt_check_out < threshold_check_out:
            # Early or within grace period before factory time - keep actual time
            return dt_check_out
        elif dt_check_out < late_threshold:
            # Within grace period (slightly early or late) - adjust to factory time
            return dt_factory_time
        elif dt_check_out <= max_allowed_checkout:
            # Late beyond grace period but within max grace - adjust to max allowed time
            return max_allowed_checkout
        else:
            # Very late beyond max grace - keep actual time
            return dt_check_out
    
    def get_required_factory_hours(self) -> float:
        """Get required factory hours for the day (Friday or regular)"""
        if self.is_friday and self.rule.enable_friday_logic and self.rule.friday_start_time and self.rule.friday_end_time:
            # Calculate Friday hours from Friday start and end times
            friday_start = get_datetime(f"{self.attendance_date} {self.rule.friday_start_time}")
            friday_end = get_datetime(f"{self.attendance_date} {self.rule.friday_end_time}")
            friday_hours = (friday_end - friday_start).total_seconds() / 3600
            return friday_hours
        else:
            # Use regular required factory hours
            return self.rule.required_factory_hours
    
    def get_break_times(self) -> Dict[str, datetime]:
        """Get break start and end times for the day"""
        break_times = {}
        
        if self.is_friday and self.rule.enable_friday_logic:
            break_times['start'] = self.get_current_datetime(
                self.attendance_date, 
                self.rule.friday_break_start
            )
            break_times['end'] = self.get_current_datetime(
                self.attendance_date, 
                self.rule.friday_break_end
            )
        else:
            break_times['start'] = self.get_current_datetime(
                self.attendance_date, 
                self.rule.regular_break_start
            )
            break_times['end'] = self.get_current_datetime(
                self.attendance_date, 
                self.rule.regular_break_end
            )
        
        return break_times
    
    def get_break_duration(self, check_in_time: str, check_out_time: str) -> int:
        """
        Calculate break duration based on check-in/out times
        Based on legacy get_break_duration function
        """
        if " " not in check_in_time:
            dt_check_in = get_datetime(f"{self.attendance_date} {check_in_time}")
        else:
            dt_check_in = get_datetime(check_in_time)

        if " " not in check_out_time:
            dt_check_out = get_datetime(f"{self.attendance_date} {check_out_time}")
        else:
            dt_check_out = get_datetime(check_out_time)

        break_times = self.get_break_times()
        
        # If checkout before break start OR checkin after break start, no break deduction
        if (dt_check_out <= break_times['start']) or (dt_check_in >= break_times['start']):
            return 0
        # Include a completed regular lunch at its end in Factory Timing only.
        # Keep Friday and Hours Completed boundary policy unchanged.
        elif dt_check_out > break_times['end'] or (
            dt_check_out == break_times['end']
            and not self.is_hours_completed_mode
            and not (self.is_friday and self.rule.enable_friday_logic)
        ):
            if self.is_friday and self.rule.enable_friday_logic:
                # Friday break is dynamic based on start/end times, not break_duration_minutes
                return int(time_diff_in_seconds(break_times['end'], break_times['start']))
            return self.rule.break_duration_minutes * 60  # Convert to seconds
        
        return 0
    
    def calculate_total_hours(self, check_in_time: str, check_out_time: str) -> float:
        """
        Calculate total hours worked between check-in and check-out
        Based on legacy calculate_total_hours function
        """
        if " " not in check_in_time:
            dt_check_in = get_datetime(f"{self.attendance_date} {check_in_time}")
        else:
            dt_check_in = get_datetime(check_in_time)

        if " " not in check_out_time:
            dt_check_out = get_datetime(f"{self.attendance_date} {check_out_time}")
        else:
            dt_check_out = get_datetime(check_out_time)
        
        
        total_seconds = time_diff_in_seconds(dt_check_out, dt_check_in)
        return total_seconds / 3600  # Convert to hours
    
    # Unpaid intra-day gaps (out then back in) of at least this long are not worked time.
    SESSION_GAP_THRESHOLD_MINUTES = 30

    def _session_gap_deduction_enabled(self) -> bool:
        """Factory Timing only; Hours Completed is never touched."""
        return getattr(self.rule, 'hours_calculation_mode', None) == 'Factory Timing'

    @staticmethod
    def _overlap_seconds(gaps, start: datetime, end: datetime) -> float:
        """Seconds of the (out, in) gaps that fall inside [start, end]."""
        total = 0.0
        for gap_out, gap_in in gaps:
            lo, hi = max(gap_out, start), min(gap_in, end)
            if hi > lo:
                total += (hi - lo).total_seconds()
        return total

    def get_net_worked_inputs(self, check_in_time: str, check_out_time: str,
                              session_gaps=None) -> Tuple[float, float]:
        """Single source of (total_hours, break_seconds) for every metric.

        total_hours is elapsed presence, less unpaid intra-day gaps of at
        least SESSION_GAP_THRESHOLD_MINUTES (clipped to the check-in/out window,
        so an overnight gap before the primary session never counts).
        break_seconds is the usual break, reduced by the part of the break
        window that a deducted gap already covers, so a gap and the break are
        never deducted on top of each other (a gap 12:00-12:45 against a
        12:30-13:00 break leaves 15 minutes of break).
        With no gaps the result is exactly the legacy calculation.
        """
        total_hours = self.calculate_total_hours(check_in_time, check_out_time)
        break_seconds = self.get_break_duration(check_in_time, check_out_time)
        if not session_gaps or not self._session_gap_deduction_enabled():
            return total_hours, break_seconds

        threshold = self.SESSION_GAP_THRESHOLD_MINUTES * 60
        gaps = [(o, i) for o, i in session_gaps if (i - o).total_seconds() >= threshold]
        if not gaps:
            return total_hours, break_seconds

        dt_in = get_datetime(check_in_time if " " in check_in_time else f"{self.attendance_date} {check_in_time}")
        dt_out = get_datetime(check_out_time if " " in check_out_time else f"{self.attendance_date} {check_out_time}")
        gap_seconds = self._overlap_seconds(gaps, dt_in, dt_out)
        if not gap_seconds:
            return total_hours, break_seconds

        break_times = self.get_break_times()
        covered = self._overlap_seconds(
            gaps, max(break_times['start'], dt_in), min(break_times['end'], dt_out))
        return total_hours - gap_seconds / 3600, max(0, break_seconds - covered)

    def calculate_regular_hours(self, check_in_time: str, check_out_time: str,
                                session_gaps=None) -> float:
        """
        Calculate regular working hours after break deduction
        Regular hours are capped at the required working hours
        """
        total_hours, break_duration_seconds = self.get_net_worked_inputs(
            check_in_time, check_out_time, session_gaps)
        break_hours = break_duration_seconds / 3600
        # Calculate net hours worked (after break deduction)
        net_hours_worked = total_hours - break_hours

        # Get required factory hours (this is NET working hours required)
        required_working_hours = self.get_required_factory_hours()

        # Regular hours are capped at required working hours
        # Any hours beyond this are considered overtime
        if net_hours_worked > required_working_hours:
            return required_working_hours
        else:
            return net_hours_worked
    
    def calculate_overtime(self, check_in_time: str, check_out_time: str,
                           extra_overtime_hours: float = 0, session_gaps=None) -> float:
        """
        Calculate overtime hours based on attendance rules
        Overtime = Net hours worked - Required working hours

        extra_overtime_hours is credited overtime that lies outside the
        primary session (cross-midnight tail). It joins the overtime before
        final rounding so the half-hour grid is applied once, to the sum.
        """
        total_hours, break_duration_seconds = self.get_net_worked_inputs(
            check_in_time, check_out_time, session_gaps)
        break_hours = break_duration_seconds / 3600
        net_hours_worked = total_hours - break_hours

        # Gazetted holiday: no required-hours threshold, every hour worked is
        # overtime. Return raw hours here (not pre-multiplied by
        # gazetted_overtime_multiplier) - the multiplier is a pay-rate concern
        # applied once downstream at payroll time. Baking it in here would
        # double-apply it wherever payroll also multiplies by the same rate,
        # and would make this field not comparable to raw hours on a manual
        # attendance card.
        if self.is_gazetted:
            return net_hours_worked + extra_overtime_hours

        # Get required factory hours (this is NET working hours required)
        required_working_hours = self.get_required_factory_hours()

        # Calculate overtime: net hours worked - required working hours
        # Note: required_factory_hours already represents NET working hours (no need to subtract break again)
        if net_hours_worked > required_working_hours:
            overtime = net_hours_worked - required_working_hours

            # Hours Completed mode: the 30-min/15-min rounding convention
            # applies to the overtime excess itself, not to the checkout
            # instant (there's no factory_end_time boundary for it to align
            # to, so rounding the checkout clock time would let the grid
            # accidentally decide the regular/deficiency split too - see
            # BFI/DriverProfile bug report).
            if self.is_hours_completed_mode:
                overtime = self.round_hours_to_grid(overtime)

            overtime += extra_overtime_hours
            if self._final_duration_rounding_enabled():
                overtime = self._round_final_duration(overtime)
            return max(0, overtime)

        if extra_overtime_hours > 0:
            # Primary session has no excess, but the tail is still overtime.
            if self._final_duration_rounding_enabled():
                return self._round_final_duration(extra_overtime_hours)
            return extra_overtime_hours

        return 0

    
    def calculate_deficiency(self, check_in_time: str, check_out_time: str,
                             session_gaps=None) -> float:
        """
        Calculate deficiency hours (shortfall from required hours)
        Deficiency = Required working hours - Net hours worked
        """
        if self.is_gazetted:
            return 0
        
        total_hours, break_duration_seconds = self.get_net_worked_inputs(
            check_in_time, check_out_time, session_gaps)
        break_hours = break_duration_seconds / 3600
        net_hours_worked = total_hours - break_hours
        
        # Get required factory hours (this is NET working hours required)
        required_working_hours = self.get_required_factory_hours()

        # Calculate deficiency: required working hours - net hours worked
        # Note: required_factory_hours already represents NET working hours (no need to subtract break again)
        if net_hours_worked < required_working_hours:
            deficiency = required_working_hours - net_hours_worked

            # Hours Completed mode: a shortfall within the dedicated grace
            # threshold isn't clock-boundary grace (checkin/checkout grace
            # fields don't apply - there's no clock window to be graced
            # against), so it needs its own field. The grace is subtracted
            # from the exact shortfall, not used as a cliff - this is the
            # only source of grace-like behavior left once the overtime
            # rounding no longer leaks into this side of the calculation
            # (see BFI/DriverProfile bug report), so it needs to behave
            # predictably at hours_deficiency_grace_minutes = 0.
            if self.is_hours_completed_mode:
                grace_hours = (getattr(self.rule, "hours_deficiency_grace_minutes", 0) or 0) / 60
                deficiency = max(0, deficiency - grace_hours)
                if deficiency == 0:
                    return 0

            if self.rule.allow_negative_hours:
                return 0
            if self._final_duration_rounding_enabled():
                deficiency = self._round_final_duration(deficiency)
            return deficiency

        return 0
    
    @staticmethod
    def _round_final_duration(hours: float) -> float:
        """Opt-in half-up 30-minute grid, stabilizing float subtraction to seconds.

        Punches have second precision; the legacy Hours Completed helper is unchanged.
        """
        seconds = round(max(0, hours) * 3600)
        return ((seconds + 900) // 1800) / 2

    def _final_duration_rounding_enabled(self) -> bool:
        """Rule-driven: the Attendance Rule opts in and says from which date.

        Only Factory Timing rules with the existing 30/15 minute overtime
        rounding enabled are eligible; anything else is unchanged.
        """
        rule = self.rule
        if (not getattr(rule, 'final_duration_rounding', 0)
                or not getattr(rule, 'final_duration_rounding_from_date', None)
                or getattr(rule, 'hours_calculation_mode', None) != 'Factory Timing'
                or not getattr(rule, 'enable_overtime_rounding', 0)
                or getattr(rule, 'overtime_rounding_interval_minutes', None) != 30
                or getattr(rule, 'overtime_rounding_threshold_minutes', None) != 15):
            return False
        return getdate(self.attendance_date) >= getdate(rule.final_duration_rounding_from_date)

    def _overnight_tail_credit_enabled(self) -> bool:
        """Rule-driven opt-in, same shape as _final_duration_rounding_enabled().

        Factory Timing only; attendance before the effective date is unchanged.
        """
        rule = self.rule
        if (not getattr(rule, 'overnight_tail_credit', 0)
                or not getattr(rule, 'overnight_tail_credit_from_date', None)
                or getattr(rule, 'hours_calculation_mode', None) != 'Factory Timing'):
            return False
        return getdate(self.attendance_date) >= getdate(rule.overnight_tail_credit_from_date)

    def handle_overnight_shift(self, check_in_time: str, check_out_time: str) -> Tuple[str, str]:
        """
        Handle overnight shifts by adjusting checkout to next day if needed
        Based on legacy add_day_in_checkout function
        """
        dt_check_in = get_datetime(f"{self.attendance_date} {check_in_time}")
        dt_check_out = get_datetime(f"{self.attendance_date} {check_out_time}")
        
        # Always return full datetime strings for consistency
        adjusted_check_in = f"{self.attendance_date} {check_in_time}"
        
        if dt_check_out < dt_check_in:
            # Checkout is before checkin, likely next day
            next_date = add_to_date(self.attendance_date, days=1, as_string=True)
            adjusted_check_out = f"{next_date} {check_out_time}"
            return adjusted_check_in, adjusted_check_out
        
        adjusted_check_out = f"{self.attendance_date} {check_out_time}"
        return adjusted_check_in, adjusted_check_out
    
    def round_checkout_time(self, checkout_time: datetime) -> datetime:
        """
        Round the checkout time to the nearest interval based on the overtime rounding configuration.
        """
        if not getattr(self.rule, 'enable_overtime_rounding', 0):
            return checkout_time
        
        interval = getattr(self.rule, 'overtime_rounding_interval_minutes', 30)
        threshold = getattr(self.rule, 'overtime_rounding_threshold_minutes', 15)
        
        # Avoid division by zero
        if not interval:
            return checkout_time
            
        minutes_into_interval = checkout_time.minute % interval
        floor_boundary = checkout_time - timedelta(minutes=minutes_into_interval, seconds=checkout_time.second)
        
        if minutes_into_interval >= threshold:
            return floor_boundary + timedelta(minutes=interval)
        return floor_boundary

    def round_hours_to_grid(self, hours: float) -> float:
        """
        Round a duration (in hours, not an absolute clock time) to the
        nearest interval based on the overtime rounding configuration.

        Used for Hours Completed mode's overtime excess, which has no
        factory_end_time boundary to align a clock-time rounding to -
        rounding the checkout instant instead (as round_checkout_time does)
        would let the grid decide whether a day is in deficiency at all,
        not just how many overtime minutes get reported.
        """
        if hours <= 0:
            return hours
        if not getattr(self.rule, 'enable_overtime_rounding', 0):
            return hours

        interval = getattr(self.rule, 'overtime_rounding_interval_minutes', 30)
        threshold = getattr(self.rule, 'overtime_rounding_threshold_minutes', 15)

        # Avoid division by zero
        if not interval:
            return hours

        total_minutes = hours * 60
        minutes_into_interval = total_minutes % interval
        floor_minutes = total_minutes - minutes_into_interval

        if minutes_into_interval >= threshold:
            floor_minutes += interval

        return floor_minutes / 60

    def calculate_attendance_summary(self, check_in_time: str, check_out_time: str,
                                     extra_overtime_hours: float = 0, session_gaps=None) -> Dict[str, Union[float, bool, str]]:
        """
        Calculate complete attendance summary with all metrics

        extra_overtime_hours: cross-midnight tail credit, ignored unless the
        rule opts in (so default-off output is identical to before).
        session_gaps: [(out_datetime, in_datetime)] unpaid intra-day gaps,
        Factory Timing only; None/empty gives the legacy result.
        """
        if not (extra_overtime_hours and extra_overtime_hours > 0 and self._overnight_tail_credit_enabled()):
            extra_overtime_hours = 0

        # Handle overnight shifts
        adjusted_check_in, adjusted_check_out = self.handle_overnight_shift(check_in_time, check_out_time)

        if self.is_hours_completed_mode:
            # Hours Completed mode: the factory clock window isn't the
            # employee's actual obligation, so don't clamp check-in/check-out
            # to factory_start_time/factory_end_time - use the actual
            # (overnight-adjusted) times as-is. Hours are counted from actual
            # time worked against required_factory_hours instead.
            adjusted_check_in_dt = get_datetime(adjusted_check_in)
            adjusted_check_out_dt = get_datetime(adjusted_check_out)
            # Deliberately no round_checkout_time() here: rounding the raw
            # checkout instant to the nearest half-hour before total_hours/
            # regular_hours/deficiency_hours are derived from it would let
            # the 30-min grid - meant only to smooth the reported overtime
            # once it's already established that overtime exists - decide
            # by accident whether the day is in deficiency or overtime at
            # all. The excess is rounded on its own further down, in
            # calculate_overtime, via round_hours_to_grid.
        else:
            # Apply grace period adjustments
            adjusted_check_in_dt = self.get_time_after_grace_in(adjusted_check_in)
            adjusted_check_out_dt = self.get_time_after_grace_out(adjusted_check_out)
            # Apply overtime rounding to checkout time
            adjusted_check_out_dt = self.round_checkout_time(adjusted_check_out_dt)

        # Keep as full datetime strings for calculations to preserve date rollovers
        final_check_in = adjusted_check_in_dt.strftime('%Y-%m-%d %H:%M:%S')
        final_check_out = adjusted_check_out_dt.strftime('%Y-%m-%d %H:%M:%S')
        
        # Calculate all metrics
        total_hours, break_duration_seconds = self.get_net_worked_inputs(
            final_check_in, final_check_out, session_gaps)
        regular_hours = self.calculate_regular_hours(final_check_in, final_check_out, session_gaps)
        overtime_hours = (self.calculate_overtime(final_check_in, final_check_out, extra_overtime_hours,
                                                  session_gaps)
                          if extra_overtime_hours else
                          self.calculate_overtime(final_check_in, final_check_out, session_gaps=session_gaps))
        deficiency_hours = self.calculate_deficiency(final_check_in, final_check_out, session_gaps)
        total_hours += extra_overtime_hours
        
        # Actual break duration (in seconds, convert to minutes)
        break_duration_minutes = int(break_duration_seconds / 60)
        return {
            'total_hours': total_hours,
            'regular_hours': regular_hours,
            'overtime_hours': overtime_hours,
            'deficiency_hours': deficiency_hours,
            'is_friday': self.is_friday,
            'is_gazetted_holiday': self.is_gazetted,
            'adjusted_check_in': adjusted_check_in_dt,
            'adjusted_check_out': adjusted_check_out_dt,
            'break_duration_minutes': break_duration_minutes
        }


# Legacy compatibility functions
def get_attendance_rule(employee: str):
    """Legacy compatibility function"""
    employee_doc = frappe.get_doc("Employee", employee)
    if not employee_doc.custom_attendance_rule:
        frappe.throw(f"No Attendance Rule set for Employee: {employee}")
    return frappe.get_doc("Attendance Rule", employee_doc.custom_attendance_rule)


def is_gazetted_date(date: str, employee: str) -> bool:
    """Legacy compatibility function"""
    holiday_list = get_holiday_list_for_employee(employee)
    return is_holiday(holiday_list, date)


def get_time_after_grace(str_check_in: str, grace_minutes: int, max_grace_minutes: int, 
                        factory_time: str, attendance_date: str) -> datetime:
    """Legacy compatibility function"""
    engine = AttendanceRuleEngine("", attendance_date)  # Employee not needed for this function
    return engine.get_time_after_grace_in(str_check_in)


def calculate_total_hours(check_out: str, check_in: str) -> float:
    """Legacy compatibility function"""
    # This is a simplified version - full implementation would need employee context
    dt_check_out = get_datetime(check_out)
    dt_check_in = get_datetime(check_in)
    return time_diff_in_seconds(dt_check_out, dt_check_in) / 3600


def calculate_overtime(check_out: str, check_in: str, employee: str, attendance_date: str) -> float:
    """Legacy compatibility function"""
    engine = AttendanceRuleEngine(employee, attendance_date)
    check_in_time = get_datetime(check_in).strftime('%H:%M:%S')
    check_out_time = get_datetime(check_out).strftime('%H:%M:%S')
    return engine.calculate_overtime(check_in_time, check_out_time)


def calculate_deficiency(check_out: str, check_in: str, employee: str, attendance_date: str) -> float:
    """Legacy compatibility function"""
    engine = AttendanceRuleEngine(employee, attendance_date)
    check_in_time = get_datetime(check_in).strftime('%H:%M:%S')
    check_out_time = get_datetime(check_out).strftime('%H:%M:%S')
    return engine.calculate_deficiency(check_in_time, check_out_time)