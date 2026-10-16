import frappe
from frappe import _
from frappe.utils import today
"""
This file contains all the utilties for employee related ops
"""

def get_holiday_list_for_employee(employee, raise_exception=True):
	if employee:
		holiday_list, company = frappe.get_cached_value("Employee", employee, ["holiday_list", "company"])
	else:
		holiday_list = ""
		company = frappe.db.get_single_value("Global Defaults", "default_company")

	if not holiday_list:
		holiday_list = frappe.get_cached_value("Company", company, "default_holiday_list")

	if not holiday_list and raise_exception:
		frappe.throw(
			_("Please set a default Holiday List for Employee {0} or Company {1}").format(employee, company)
		)

	return holiday_list


def is_holiday(employee, date=None, raise_exception=True, only_non_weekly=False, with_description=False):
	"""
	Returns True if given Employee has an holiday on the given date
	        :param employee: Employee `name`
	        :param date: Date to check. Will check for today if None
	        :param raise_exception: Raise an exception if no holiday list found, default is True
	        :param only_non_weekly: Check only non-weekly holidays, default is False
	"""

	holiday_list = get_holiday_list_for_employee(employee, raise_exception)
	if not date:
		date = today()

	if not holiday_list:
		return False

	filters = {"parent": holiday_list, "holiday_date": date}
	if only_non_weekly:
		filters["weekly_off"] = False

	holidays = frappe.get_all("Holiday", fields=["description"], filters=filters, pluck="description")

	if with_description:
		return len(holidays) > 0, holidays

	return len(holidays) > 0

def absent_blocked_by_holiday(employee, date):
	"""
	Decide whether an Absent mark is invalid for `employee` on `date` because it falls on a
	named (non weekly-off) holiday of the employee's Holiday List (company default as fallback).
	Weekly offs are deliberately excluded: they are handled by the payroll rules.

	Returns (blocked, holidays, missing_list):
	  blocked      - True if Absent must not be recorded
	  holidays     - descriptions of the matching holidays
	  missing_list - True if neither the employee nor the company has a Holiday List
	"""
	if not get_holiday_list_for_employee(employee, raise_exception=False):
		return False, [], True

	is_off, holidays = is_holiday(
		employee, date, raise_exception=False, only_non_weekly=True, with_description=True
	)
	if not is_off:
		return False, [], False

	rule = frappe.get_cached_value("Employee", employee, "custom_attendance_rule")
	if rule and frappe.get_cached_value("Attendance Rule", rule, "allow_absent_on_holiday"):
		return False, holidays, False

	return True, holidays, False
