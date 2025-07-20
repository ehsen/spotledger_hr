import frappe
from frappe.utils import get_datetime, get_time
from spotledger_hr.utilities.employee_utils import get_holiday_list_for_employee,is_holiday
from datetime import timedelta



def get_attendance_rule(employee):
    profile = frappe.get_doc("Employee", employee)
    if not profile.attendance_rule:
        frappe.throw(f"No Attendance Rule set for Employee: {employee}")
    return frappe.get_doc("Attendance Rule", profile.custom_attendance_rule)


def is_gazetted_date(date, employee):
    holiday_list = get_holiday_list_for_employee(employee)
    return is_holiday(holiday_list, date)


def get_time_after_grace(str_check_in, grace_minutes, max_grace_minutes, factory_time, attendance_date):
    dt_check_in = get_datetime(str_check_in)
    dt_factory_time = get_datetime(f"{attendance_date} {factory_time}")

    threshold_check_in = dt_factory_time + timedelta(minutes=grace_minutes)
    max_check_in_time = dt_factory_time + timedelta(minutes=max_grace_minutes)

    if dt_check_in <= threshold_check_in:
        return dt_factory_time
    elif dt_check_in <= max_check_in_time:
        return max_check_in_time
    else:
        return dt_check_in


def calculate_total_hours(check_out, check_in):
    return (get_datetime(check_out) - get_datetime(check_in)).total_seconds()


def calculate_overtime(check_out, check_in, employee, attendance_date):
    rule = get_attendance_rule(employee)

    total_worked_secs = calculate_total_hours(check_out, check_in)
    worked_hours = total_worked_secs / 3600

    if is_gazetted_date(attendance_date, employee):
        return worked_hours * rule.gazetted_overtime_multiplier

    regular_hours = rule.required_factory_hours
    ot = worked_hours - regular_hours

    if rule.ignore_break_in_overtime:
        ot += (rule.break_duration_minutes or 0) / 60

    return max(0, ot)


def calculate_deficiency(check_out, check_in, employee, attendance_date):
    rule = get_attendance_rule(employee)

    total_worked_secs = calculate_total_hours(check_out, check_in)
    worked_hours = total_worked_secs / 3600
    net_required = rule.required_factory_hours

    if rule.break_duration_minutes and not is_gazetted_date(attendance_date, employee):
        net_required -= rule.break_duration_minutes / 60

    if worked_hours < net_required:
        deficiency = net_required - worked_hours
        return deficiency if rule.allow_negative_hours else 0

    return 0
