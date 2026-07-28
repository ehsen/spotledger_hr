# Copyright (c) 2025, SpotLedger and contributors
# For license information, please see license.txt

"""
Standalone attendance-rule validation tool.

Purpose: feed a batch of (employee, date, check_in, check_out) rows through
AttendanceRuleEngine WITHOUT creating any Attendance/Employee Checkin records,
and get back the computed regular/overtime/deficiency hours as CSV. That
output is meant to be compared row-by-row against the client's manually
written attendance cards (which record check-in/out + overtime by hand) to
validate the engine's numbers before it is trusted for production payroll.

Usage (from bench console or `bench execute`):

    bench --site <site> execute spotledger_hr.tools.attendance_rule_tester.run_from_csv \
        --kwargs "{'input_csv_path': '/path/to/in.csv', 'output_csv_path': '/path/to/out.csv'}"

Input CSV columns (header required):
    employee,date,check_in,check_out

    - employee: Employee ID (e.g. HR-EMP-00128) or the value in the
      employee's custom_old_code field (legacy/biometric device code) -
      resolved the same way the SQLite sync resolves employees.
    - date: YYYY-MM-DD (this is the attendance date, used to pick
      Friday/holiday rules from the employee's Attendance Rule).
    - check_in / check_out: HH:MM:SS (24-hour). If check_out is earlier
      than check_in it is treated as an overnight shift automatically,
      same as the production engine does.

Output CSV adds one row per input row with:
    resolved_employee, total_hours, regular_hours, overtime_hours,
    deficiency_hours, break_duration_minutes, is_friday,
    is_gazetted_holiday, adjusted_check_in, adjusted_check_out, error

A row that fails (bad employee code, no Attendance Rule assigned, bad
time format, etc.) still appears in the output with the `error` column
filled in and every numeric column blank, rather than aborting the batch.
"""

import csv

import frappe

from spotledger_hr.attendance_rule_engine import AttendanceRuleEngine
from spotledger_hr.controllers.attendance_controller import validate_employee_code

OUTPUT_FIELDNAMES = [
	"employee",
	"date",
	"check_in",
	"check_out",
	"resolved_employee",
	"total_hours",
	"regular_hours",
	"overtime_hours",
	"deficiency_hours",
	"break_duration_minutes",
	"is_friday",
	"is_gazetted_holiday",
	"adjusted_check_in",
	"adjusted_check_out",
	"error",
]


def calculate_one(employee_code: str, date: str, check_in: str, check_out: str) -> dict:
	"""Run a single check-in/check-out pair through the attendance rule engine.

	Does not touch Attendance or Employee Checkin - pure calculation, safe to
	call repeatedly against production data for validation.
	"""
	row = {
		"employee": employee_code,
		"date": date,
		"check_in": check_in,
		"check_out": check_out,
		"resolved_employee": "",
		"total_hours": "",
		"regular_hours": "",
		"overtime_hours": "",
		"deficiency_hours": "",
		"break_duration_minutes": "",
		"is_friday": "",
		"is_gazetted_holiday": "",
		"adjusted_check_in": "",
		"adjusted_check_out": "",
		"error": "",
	}

	employee = validate_employee_code(employee_code)
	if not employee:
		row["error"] = f"Employee not found (tried name and custom_old_code): {employee_code}"
		return row
	row["resolved_employee"] = employee

	try:
		engine = AttendanceRuleEngine(employee, date)
		summary = engine.calculate_attendance_summary(check_in, check_out)
	except Exception as e:
		row["error"] = str(e)
		return row

	row["total_hours"] = round(summary.get("total_hours", 0), 2)
	row["regular_hours"] = round(summary.get("regular_hours", 0), 2)
	row["overtime_hours"] = round(summary.get("overtime_hours", 0), 2)
	row["deficiency_hours"] = round(summary.get("deficiency_hours", 0), 2)
	row["break_duration_minutes"] = summary.get("break_duration_minutes", 0)
	row["is_friday"] = summary.get("is_friday", False)
	row["is_gazetted_holiday"] = summary.get("is_gazetted_holiday", False)
	row["adjusted_check_in"] = summary.get("adjusted_check_in")
	row["adjusted_check_out"] = summary.get("adjusted_check_out")
	return row


def run_from_csv(input_csv_path: str, output_csv_path: str) -> dict:
	"""Batch-run calculate_one over every row of input_csv_path, write output_csv_path.

	Returns a small summary dict (total/succeeded/failed) so it prints
	something useful when called via `bench execute`.
	"""
	with open(input_csv_path, newline="") as f:
		reader = csv.DictReader(f)
		input_rows = list(reader)

	results = []
	failed = 0
	for r in input_rows:
		result = calculate_one(
			employee_code=r["employee"].strip(),
			date=r["date"].strip(),
			check_in=r["check_in"].strip(),
			check_out=r["check_out"].strip(),
		)
		if result["error"]:
			failed += 1
		results.append(result)
		# Each AttendanceRuleEngine call opens its own implicit read
		# transaction; roll back defensively so a long batch never
		# accumulates uncommitted state.
		frappe.db.rollback()

	with open(output_csv_path, "w", newline="") as f:
		writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDNAMES)
		writer.writeheader()
		writer.writerows(results)

	summary = {
		"total": len(results),
		"succeeded": len(results) - failed,
		"failed": failed,
		"output_csv_path": output_csv_path,
	}
	print(summary)
	return summary
