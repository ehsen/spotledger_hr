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

        only_non_weekly=True excludes recurring weekly-off rows (e.g. Friday)
        from counting as a gazetted holiday - Friday already has its own
        dedicated handling via enable_friday_logic, and without this flag a
        Holiday List that auto-populates weekly offs would misclassify every
        Friday as gazetted, doubling overtime and zeroing deficiency on those days.
        """
        try:
            holiday_list = get_holiday_list_for_employee(self.employee, raise_exception=False)
            if not holiday_list:
                return False
            return is_holiday(self.employee, self.attendance_date, raise_exception=False, only_non_weekly=True)
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
        dt_check_in = get_datetime(f"{self.attendance_date} {check_in_time}")
        
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
        dt_check_out = get_datetime(f"{self.attendance_date} {check_out_time}")
        
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
        elif dt_check_out <= late_threshold:
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
        dt_check_in = get_datetime(f"{self.attendance_date} {check_in_time}")
        dt_check_out = get_datetime(f"{self.attendance_date} {check_out_time}")
        break_times = self.get_break_times()
        
        # If checkout before break start OR checkin after break start, no break deduction
        if (dt_check_out <= break_times['start']) or (dt_check_in >= break_times['start']):
            return 0
        # If checkout after break end, full break deduction
        elif dt_check_out > break_times['end']:
            return self.rule.break_duration_minutes * 60  # Convert to seconds
        
        return 0
    
    def calculate_total_hours(self, check_in_time: str, check_out_time: str) -> float:
        """
        Calculate total hours worked between check-in and check-out
        Based on legacy calculate_total_hours function
        """
        dt_check_in = get_datetime(f"{self.attendance_date} {check_in_time}")
        dt_check_out = get_datetime(f"{self.attendance_date} {check_out_time}")
        
        total_seconds = time_diff_in_seconds(dt_check_out, dt_check_in)
        return total_seconds / 3600  # Convert to hours
    
    def calculate_regular_hours(self, check_in_time: str, check_out_time: str) -> float:
        """
        Calculate regular working hours after break deduction
        Regular hours are capped at the required working hours
        """
        total_hours = self.calculate_total_hours(check_in_time, check_out_time)
        break_duration_seconds = self.get_break_duration(check_in_time, check_out_time)
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
    
    def calculate_overtime(self, check_in_time: str, check_out_time: str) -> float:
        """
        Calculate overtime hours based on attendance rules
        Overtime = Net hours worked - Required working hours
        """
        total_hours = self.calculate_total_hours(check_in_time, check_out_time)

        # Calculate net hours after break deduction
        break_duration_seconds = self.get_break_duration(check_in_time, check_out_time)
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
            return net_hours_worked

        # Get required factory hours (this is NET working hours required)
        required_working_hours = self.get_required_factory_hours()

        # Calculate overtime: net hours worked - required working hours
        # Note: required_factory_hours already represents NET working hours (no need to subtract break again)
        if net_hours_worked > required_working_hours:
            overtime = net_hours_worked - required_working_hours
            return max(0, overtime)

        return 0

    
    def calculate_deficiency(self, check_in_time: str, check_out_time: str) -> float:
        """
        Calculate deficiency hours (shortfall from required hours)
        Deficiency = Required working hours - Net hours worked
        """
        if self.is_gazetted:
            return 0
        
        total_hours = self.calculate_total_hours(check_in_time, check_out_time)
        
        # Calculate net hours after break deduction
        break_duration_seconds = self.get_break_duration(check_in_time, check_out_time)
        break_hours = break_duration_seconds / 3600
        net_hours_worked = total_hours - break_hours
        
        # Get required factory hours (this is NET working hours required)
        required_working_hours = self.get_required_factory_hours()

        # Calculate deficiency: required working hours - net hours worked
        # Note: required_factory_hours already represents NET working hours (no need to subtract break again)
        if net_hours_worked < required_working_hours:
            deficiency = required_working_hours - net_hours_worked
            return 0 if self.rule.allow_negative_hours else deficiency
        
        return 0
    
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
    
    def calculate_attendance_summary(self, check_in_time: str, check_out_time: str) -> Dict[str, Union[float, bool, str]]:
        """
        Calculate complete attendance summary with all metrics
        """
        # Handle overnight shifts
        adjusted_check_in, adjusted_check_out = self.handle_overnight_shift(check_in_time, check_out_time)

        # Apply grace period adjustments
        adjusted_check_in_dt = self.get_time_after_grace_in(adjusted_check_in.split(' ')[1])
        adjusted_check_out_dt = self.get_time_after_grace_out(adjusted_check_out.split(' ')[1])
        
        # Convert back to time strings for calculations
        final_check_in = adjusted_check_in_dt.strftime('%H:%M:%S')
        final_check_out = adjusted_check_out_dt.strftime('%H:%M:%S')
        
        # Calculate all metrics
        total_hours = self.calculate_total_hours(final_check_in, final_check_out)
        regular_hours = self.calculate_regular_hours(final_check_in, final_check_out)
        overtime_hours = self.calculate_overtime(final_check_in, final_check_out)
        deficiency_hours = self.calculate_deficiency(final_check_in, final_check_out)
        
        # Calculate actual break duration (in seconds, convert to minutes)
        break_duration_seconds = self.get_break_duration(final_check_in, final_check_out)
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